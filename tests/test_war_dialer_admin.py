"""The standalone administration boundary uses real worlds and SQLite snapshots."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

DOOR = Path(__file__).resolve().parents[1] / "war_dialer.py"
spec = importlib.util.spec_from_file_location("war_dialer_admin_test", DOOR)
wd = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wd
spec.loader.exec_module(wd)


@pytest.fixture
def world(tmp_path):
    path = tmp_path / "world.db"
    conn = wd.connect(path)
    now = wd.now_utc()
    wd.bind_world_owner(conn, "a" * 32)
    season = wd.current_world_season(conn, now)
    wd.ensure_exchanges_seeded(conn, season, now)
    wd.load_or_create_player(conn, 1, "Caller", now, season)
    wd.record_event(conn, 1, "Rival", "Keep this receipt", now)
    conn.close()
    return path


def test_status_is_read_only_and_missing_world_is_not_created(world, tmp_path):
    before = world.read_bytes()
    assert wd.administer_world(world, "status")["players"] == 1
    assert world.read_bytes() == before
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.Error):
        wd.administer_world(missing, "status")
    assert not missing.exists()


@pytest.mark.parametrize("command", ["close-season", "reset"])
def test_snapshot_contains_wal_and_precedes_change(world, command):
    wd.administer_world(world, "maintenance", maintenance=True)
    # Keep this connection open so the committed receipt is still in the WAL.
    conn = wd.connect(world)
    try:
        wd.record_event(conn, 1, "Rival", "Only in WAL", wd.now_utc())
        original = conn.execute("SELECT handle,created_at FROM players WHERE user_id=1").fetchone()
        result = wd.administer_world(world, command, confirm=world.name, reason="new contest")
        entry = result["recent_operations"][-1]
        saved = wd.inspect_world(Path(entry["snapshot"]))
        assert saved["events"] == 2
        assert saved["stored_season"] == "1"
        assert result["stored_season"] == "2"
        assert result["maintenance"] == "on"
        assert result["owner"] == "a" * 32
        assert result["events"] == 0 if command == "reset" else result["events"] >= 2
        assert tuple(conn.execute("SELECT handle,created_at FROM players WHERE user_id=1").fetchone()) == tuple(original)
    finally:
        conn.close()


def test_destructive_refusals_do_not_change_world(world, tmp_path):
    before = wd.inspect_world(world)
    with pytest.raises(wd.WorldStateError, match="maintenance"):
        wd.administer_world(world, "reset", confirm=world.name, reason="test")
    assert wd.inspect_world(world) == before
    wd.administer_world(world, "maintenance", maintenance=True)
    before = wd.inspect_world(world)
    with pytest.raises(wd.WorldStateError, match="Confirm"):
        wd.administer_world(world, "reset", confirm="wrong", reason="test")
    with pytest.raises(FileExistsError):
        wd.administer_world(world, "reset", confirm=world.name, reason="test", snapshot=world)
    with pytest.raises(OSError):
        wd.administer_world(world, "reset", confirm=world.name, reason="test", snapshot=tmp_path / "absent" / "save.db")
    assert wd.inspect_world(world) == before


def test_active_session_refuses_maintenance_and_reset(world):
    with wd.world_session(world):
        with pytest.raises(wd.WorldStateError, match="busy"):
            wd.administer_world(world, "maintenance", maintenance=True)
    wd.administer_world(world, "maintenance", maintenance=True)
    with wd.world_session(world):
        with pytest.raises(wd.WorldStateError, match="busy"):
            wd.administer_world(world, "reset", confirm=world.name, reason="test")
    assert not list(world.parent.glob("*.before-*.db"))


def test_reset_retains_latest_hundred_audit_entries(world):
    wd.administer_world(world, "maintenance", maintenance=True)
    conn = wd.connect(world)
    entries = [{"action": "old", "sequence": n} for n in range(110)]
    conn.execute("UPDATE meta SET value=? WHERE key='sysop_audit'", (json.dumps(entries),))
    conn.close()
    wd.administer_world(world, "reset", confirm=world.name, reason="test")
    with sqlite3.connect(world) as conn:
        saved = json.loads(conn.execute("SELECT value FROM meta WHERE key='sysop_audit'").fetchone()[0])
    assert len(saved) == 100 and saved[0]["sequence"] == 11
    assert saved[-1]["action"] == "reset competition"


def test_failed_snapshot_validation_leaves_world_unchanged(world, tmp_path, monkeypatch):
    wd.administer_world(world, "maintenance", maintenance=True)
    before = wd.inspect_world(world)
    snapshot = tmp_path / "snapshot.db"
    inspect = wd.inspect_world
    def reject_snapshot(path):
        if Path(path) == snapshot:
            raise wd.WorldStateError("snapshot validation failed")
        return inspect(path)
    monkeypatch.setattr(wd, "inspect_world", reject_snapshot)
    with pytest.raises(wd.WorldStateError, match="snapshot validation"):
        wd.administer_world(world, "reset", confirm=world.name, reason="test", snapshot=snapshot)
    assert inspect(world) == before
    assert not snapshot.exists()


def test_failed_audit_rolls_back_mutation_and_keeps_recovery_snapshot(world, tmp_path, monkeypatch):
    wd.administer_world(world, "maintenance", maintenance=True)
    before = wd.inspect_world(world)
    snapshot = tmp_path / "snapshot.db"
    def fail_audit(*args, **kwargs):
        raise sqlite3.OperationalError("audit write failed")
    monkeypatch.setattr(wd, "_admin_audit", fail_audit)
    with pytest.raises(sqlite3.Error, match="audit write failed"):
        wd.administer_world(world, "reset", confirm=world.name, reason="test", snapshot=snapshot)
    assert wd.inspect_world(world) == before
    assert wd.inspect_world(snapshot)["stored_season"] == "1"


def test_cli_runs_without_host_and_reports_json_errors(world, tmp_path):
    env = dict(os.environ, WAR_DIALER_DB_PATH=str(world), DOOR_SPLASH="0")
    env.pop("NETBBS_DOOR_INFO", None)
    def run(*args):
        return subprocess.run([sys.executable, "-I", str(DOOR), *args], env=env,
                              capture_output=True, text=True, timeout=15)
    status = run("--admin", "status", "--json")
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["players"] == 1
    maintenance = run("--admin", "maintenance", "on", "--json")
    assert maintenance.returncode == 0, maintenance.stderr
    assert json.loads(maintenance.stdout)["maintenance"] == "on"
    human = run("--admin=status")
    assert human.returncode == 0 and "stored_season: 1" in human.stdout
    error = run("--admin", "status", "--world", str(tmp_path / "absent.db"), "--json")
    assert error.returncode == 1 and json.loads(error.stdout)["error"]


# -- `--admin stats`: what callers have actually done -------------------------------

class _Rolls:
    """Every roll succeeds, every range pays its low end."""

    def random(self):
        return 0.0

    def randint(self, low, high):
        return low

    def choice(self, seq):
        return seq[0]


def _played_world(world):
    """Two callers with a few committed turns each, one of them busted."""
    conn = wd.connect(world)
    now = wd.now_utc()
    try:
        wd.ensure_schema(conn)
        first = wd.refresh_player(conn, 1, now)
        wd.resolve_trade_warez(conn, first, now, _Rolls())
        wd.resolve_dial(conn, first, now, _Rolls())
        lead = wd.read_leads(conn, 1, now)[0]
        wd.resolve_lead(conn, first, lead, now, _Rolls())
        wd.resolve_job(conn, first, now, _Rolls(), choice=wd.JobChoice(0, 0))
        second = wd.load_or_create_player(conn, 2, "Other", now, first.season_number)
        conn.execute("UPDATE players SET heat=100 WHERE user_id=2")
        second = wd.refresh_player(conn, 2, now)
        assert wd.resolve_trade_warez(conn, second, now, _Rolls())[1]      # busted
    finally:
        conn.close()


def test_stats_sum_every_sheet_and_name_nobody(world):
    _played_world(world)
    before = world.read_bytes()
    stats = wd.administer_world(world, "stats")
    assert world.read_bytes() == before                                    # read-only
    assert stats["players"] == 2 and stats["sheets"] == 2
    totals = stats["totals"]
    assert (totals["turns"], totals["trades"], totals["sweeps"]) == (5, 2, 1)
    assert (totals["carrier_tries"], totals["carriers"], totals["contract_tries"]) == (1, 1, 1)
    assert totals["busts"] == 1 and "best_rank" not in totals              # peaks are not sums
    assert stats["per_100_turns"]["trades"] == 40.0 and stats["per_100_turns"]["busts"] == 20.0
    assert stats["success"] == {"carriers": 1.0, "contracts": 1.0, "operations": None, "raids": None}
    assert stats["badge_holders"]["carrier"] == 1 and stats["badge_holders"]["busted"] == 1
    assert set(stats["badge_holders"]) == {key for key, *_ in wd.BADGES}
    rank = stats["season_rank"]
    assert rank["players"] == 2 and rank["ranked"] == 1 and rank["top"] > 0
    assert sum(rank["tiers"].values()) == 2
    # Aggregate only: no handle and no account ID anywhere in it.
    text = json.dumps(stats)
    assert "Caller" not in text and "Other" not in text and "user_id" not in text


def test_stats_cap_a_rate_when_a_sheet_predates_attempt_counting(world):
    _played_world(world)
    conn = wd.connect(world)
    conn.execute("UPDATE career SET data=? WHERE user_id=1",
                 (json.dumps({"stats": {"carriers": 9, "carrier_tries": 3}, "badges": {}}),))
    conn.commit()
    conn.close()
    assert wd.administer_world(world, "stats")["success"]["carriers"] == 1.0


def test_stats_on_a_fresh_world_and_through_the_command_line(world):
    stats = wd.administer_world(world, "stats")
    assert stats["sheets"] == 0 and stats["totals"] == {} and stats["per_100_turns"] == {}
    rank = stats["season_rank"]
    assert (rank["players"], rank["ranked"], rank["top"]) == (1, 0, 0)   # one caller, nothing earned
    result = subprocess.run([sys.executable, str(DOOR), "--world", str(world), "--admin", "stats", "--json"],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and json.loads(result.stdout)["sheets"] == 0
    plain = subprocess.run([sys.executable, str(DOOR), "--world", str(world), "--admin", "stats"],
                           capture_output=True, text=True, timeout=60)
    assert plain.returncode == 0 and "badge_holders:" in plain.stdout
