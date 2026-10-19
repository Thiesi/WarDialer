"""NetBBS door API 5: game events and standings (issue #16).

A fake `door_info.json` and drop directory stand in for NetBBS, the way its own
`tests/fixtures/door_events_peer.py` does: these pin the files written, their
names and their JSON, and that nothing at all is written unless the host asked.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from .test_war_dialer_domain import FixedRandom, _save_fixture, _setup, db_path, wd  # noqa: F401


def _info(tmp_path, *, door_api=5, events=True, **limits):
    outbound = {"label": "WarDialer.door", "directory": "outbound", "results": str(tmp_path / "results")}
    if events:
        outbound["events"] = {"types": ["rank", "achievement", "medal", "capture", "perfect"],
                              "events_per_hour": 12, "title_max": 80, "standings_rows": 10, **limits}
    (tmp_path / "outbound").mkdir(exist_ok=True)
    info = {"user_id": 1, "handle": "alice", "door_api": door_api, "outbound": outbound}
    path = tmp_path / "door_info.json"
    path.write_text(json.dumps(info), encoding="utf-8")
    return info, str(path)


@pytest.fixture
def events(tmp_path):
    """Switch reporting on for caller 1; return a reader of what was dropped."""
    info, path = _info(tmp_path)
    wd._GAME_EVENTS.configure(info, path)

    def dropped():
        names = sorted(p.name for p in (tmp_path / "outbound").iterdir())
        assert all(name.endswith(".json") for name in names), names  # never a half-written file
        return [(name, json.loads((tmp_path / "outbound" / name).read_text(encoding="utf-8")))
                for name in names]
    yield dropped
    wd._GAME_EVENTS.configure({})


def _player(conn, user_id, handle, now, season, *, rank=0):
    player = wd.load_or_create_player(conn, user_id, handle, now, season)
    player.crew_recruited_total = rank // 10
    player.crew = 1000
    _save_fixture(conn, player)
    return wd.read_player(conn, user_id)


def _capture(conn, player, now, exchange=0):
    target = wd.list_exchanges(conn)[exchange]
    success, name, _busted = wd.resolve_root_exchange(conn, player, target.id, now, FixedRandom(0.99))
    assert success
    return name


@pytest.mark.parametrize("variant", ["no-events", "door-api-4", "no-outbound", "standalone"])
def test_nothing_is_written_unless_the_host_switched_events_on(tmp_path, db_path, variant):
    info, path = _info(tmp_path, events=variant != "no-events", door_api=4 if variant == "door-api-4" else 5)
    if variant == "no-outbound":
        del info["outbound"]
    wd._GAME_EVENTS.configure(info, None if variant == "standalone" else path)
    try:
        assert not wd._GAME_EVENTS.active
        now = wd.now_utc()
        conn, season = _setup(db_path, now)
        player = _player(conn, 1, "alice", now, season, rank=90)
        wd._GAME_EVENTS.arm(conn, player)
        _capture(conn, player, now)
        wd.settle_world(conn, now + wd.SEASON + timedelta(days=1))
        assert list((tmp_path / "outbound").iterdir()) == []
    finally:
        wd._GAME_EVENTS.configure({})


def test_a_live_capture_reports_one_event_and_the_table_it_changed(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    player = _player(conn, 1, "alice", now, season)
    wd._GAME_EVENTS.arm(conn, player)
    table = ("wardialer-000001-standings.json", {"standings": {"title": f"Season {season}", "rows": []}})
    assert events() == [table]  # the table as it stands; no event is news yet
    name = _capture(conn, player, now)
    rank = wd.rank_score(wd.read_player(conn, 1))
    assert events() == [
        table,
        ("wardialer-000002-event.json", {"event": {"type": "capture", "user_id": 1, "title": "the " + name}}),
        ("wardialer-000003-standings.json", {"standings": {"title": f"Season {season}", "rows": [
            {"user_id": 1, "value": f"{rank:,}", "label": wd.tier_name(rank)}]}}),
    ]


def test_a_tier_crossed_live_is_reported_once_and_one_held_at_login_is_not(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    player = _player(conn, 1, "alice", now, season, rank=90)
    wd._GAME_EVENTS.arm(conn, player)
    _capture(conn, player, now)  # +50: Newbie to Wannabe
    _capture(conn, player, now, exchange=1)  # still Wannabe
    ranks = [body["event"] for _, body in events() if body.get("event", {}).get("type") == "rank"]
    assert ranks == [{"type": "rank", "user_id": 1, "title": "Wannabe"}]


def test_an_offline_promotion_is_the_baseline_not_an_event(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    player = _player(conn, 1, "alice", now, season, rank=300)  # Script Kiddie before this session
    wd._GAME_EVENTS.arm(conn, player)
    _capture(conn, player, now)
    assert not any(body.get("event", {}).get("type") == "rank" for _, body in events())


def test_another_callers_promotion_is_theirs_to_report(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    wd._GAME_EVENTS.arm(conn, _player(conn, 1, "alice", now, season))
    rival = _player(conn, 2, "bob", now, season, rank=90)
    _capture(conn, rival, now)
    assert not any(body.get("event", {}).get("type") == "rank" for _, body in events())


def test_the_session_that_closes_a_season_reports_its_medals_then_an_empty_table(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    for user_id, rank in ((1, 100), (2, 300), (3, 0), (4, 200), (5, 50)):
        _player(conn, user_id, f"caller{user_id}", now, season, rank=rank)
    later = now + wd.SEASON + timedelta(days=1)
    wd.settle_world(conn, later)
    wd.settle_world(conn, later)  # archived once, reported once
    assert events() == [
        ("wardialer-000001-event.json", {"event": {"type": "medal", "user_ids": [2, 4, 1], "title": f"Season {season}"}}),
        ("wardialer-000002-standings.json", {"standings": {"title": f"Season {season + 1}", "rows": []}}),
    ]


def test_a_season_with_fewer_scorers_names_only_the_medallists(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    _player(conn, 1, "alice", now, season, rank=40)
    _player(conn, 2, "bob", now, season)
    wd.settle_world(conn, now + wd.SEASON + timedelta(days=1))
    medals = [body["event"] for _, body in events() if "event" in body]
    assert medals == [{"type": "medal", "user_ids": [1], "title": f"Season {season}"}]


def test_a_rolled_back_transaction_reports_nothing(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    player = _player(conn, 1, "alice", now, season)
    wd._GAME_EVENTS.arm(conn, player)
    with pytest.raises(RuntimeError):
        with wd._write_transaction(conn):
            wd._GAME_EVENTS.event("capture", "the 212-555 Uptown Exchange", user_id=1)
            conn.execute("UPDATE players SET crew_recruited_total=50 WHERE user_id=1")
            raise RuntimeError("the action failed")
    with wd._write_transaction(conn):
        pass
    assert [body for _, body in events()] == [{"standings": {"title": f"Season {season}", "rows": []}}]


def test_a_session_sends_the_table_as_it_stands_once_even_if_nothing_moves_it(db_path, events):
    # Issue #19: a baseline NetBBS never received left `!top` empty until some
    # session happened to reorder the top ten.
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    _player(conn, 2, "bob", now, season, rank=700)
    player = _player(conn, 1, "alice", now, season, rank=100)
    wd._GAME_EVENTS.arm(conn, player)
    wd.read_player_page(conn, 1, now, standings=True)
    wd.list_raid_targets(conn, player, now)
    assert events() == [("wardialer-000001-standings.json", {"standings": {"title": f"Season {season}", "rows": [
        {"user_id": 2, "value": "700", "label": "Hacker"},
        {"user_id": 1, "value": "100", "label": "Wannabe"}]}})]


def test_the_next_session_sends_its_own_table_once(db_path, tmp_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    player = _player(conn, 1, "alice", now, season, rank=100)
    wd._GAME_EVENTS.arm(conn, player)
    for name in [p.name for p in (tmp_path / "outbound").iterdir()]:
        (tmp_path / "outbound" / name).unlink()  # NetBBS took it
    info, path = _info(tmp_path)
    wd._GAME_EVENTS.configure(info, path)  # a new launch
    wd._GAME_EVENTS.arm(conn, player)
    wd._GAME_EVENTS.arm(conn, player)
    assert [body["standings"]["rows"][0]["user_id"] for _, body in events()] == [1]


def test_a_season_closed_at_login_sends_its_empty_table_once(db_path, events):
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    _player(conn, 1, "alice", now, season, rank=100)
    later = now + wd.SEASON + timedelta(days=1)
    player = wd.load_or_create_player(conn, 1, "alice", later, season + 1)  # login settles the close
    wd._GAME_EVENTS.arm(conn, player)
    assert [body for _, body in events()] == [
        {"event": {"type": "medal", "user_ids": [1], "title": f"Season {season}"}},
        {"standings": {"title": f"Season {season + 1}", "rows": []}},
    ]


def test_request_names_sort_in_the_order_they_were_written(tmp_path, events):
    for n in range(12):
        wd._GAME_EVENTS.event("capture", f"exchange {n}", user_id=1)
    wd._GAME_EVENTS.committed()
    assert [body["event"]["title"] for _, body in events()] == [f"exchange {n}" for n in range(12)]


def test_titles_types_and_rows_follow_the_hosts_limits(tmp_path, db_path):
    info, path = _info(tmp_path, title_max=12, standings_rows=2, types=["rank", "medal"])
    wd._GAME_EVENTS.configure(info, path)
    try:
        now = wd.now_utc()
        conn, season = _setup(db_path, now)
        for user_id in (2, 3, 4):
            _player(conn, user_id, f"caller{user_id}", now, season, rank=100 * user_id)
        player = _player(conn, 1, "alice", now, season, rank=290)
        wd._GAME_EVENTS.arm(conn, player)
        _capture(conn, player, now)  # 340: past caller 3, and a capture is not among this host's types
        wd._GAME_EVENTS.event("medal", "Season\n4 of the long\x1b[1m war", user_ids=[4, 3, 2, 1])
        wd._GAME_EVENTS.committed()
        bodies = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((tmp_path / "outbound").iterdir())]
        assert [b["event"]["type"] for b in bodies if "event" in b] == ["rank", "medal"]
        medal = next(b["event"] for b in bodies if b.get("event", {}).get("type") == "medal")
        assert medal == {"type": "medal", "user_ids": [4, 3, 2], "title": "Season 4 of"}
        standings = [b["standings"]["rows"] for b in bodies if "standings" in b]
        assert standings and all(len(rows) == 2 for rows in standings)
        assert [row["user_id"] for row in standings[-1]] == [4, 1]
        for body in bodies:
            assert len(json.dumps(body).encode()) <= (8192 if "standings" in body else 2048)
    finally:
        wd._GAME_EVENTS.configure({})


def test_a_drop_directory_that_cannot_be_written_never_breaks_play(tmp_path, db_path, events):
    (tmp_path / "outbound").rmdir()
    now = wd.now_utc()
    conn, season = _setup(db_path, now)
    player = _player(conn, 1, "alice", now, season, rank=90)
    wd._GAME_EVENTS.arm(conn, player)
    _capture(conn, player, now)
    assert wd.read_player(conn, 1).exchanges_taken_total == 1


def test_the_door_reads_its_switch_from_the_launch_metadata(tmp_path, monkeypatch):
    info, path = _info(tmp_path)
    monkeypatch.setenv("NETBBS_DOOR_INFO", path)
    try:
        wd._GAME_EVENTS.configure(info)
        assert wd._GAME_EVENTS.active and wd._GAME_EVENTS.directory == tmp_path / "outbound"
    finally:
        wd._GAME_EVENTS.configure({})
