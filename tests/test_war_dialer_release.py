"""The NetBBS door profile each release ships beside the door (issue #23)."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / "profiles/netbbs.json").read_text(encoding="utf-8"))
DOOR = (ROOT / "war_dialer.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")


def test_profile_launches_the_door_natively_over_stdio():
    assert PROFILE["name"] == "War Dialer"
    assert PROFILE["args"] == ["{install_dir}/war_dialer.py"]
    profile = PROFILE["profile"]
    assert (profile["version"], profile["adapter"], profile["endpoint"]) == (1, "native", "stdio")
    assert profile["encoding"] == "utf-8"
    assert (profile["width"], profile["height"]) == (0, 0)


def test_profile_claims_only_what_the_door_does():
    profile = PROFILE["profile"]
    # NetBBS signals a resize with SIGUSR1; the door must be listening for it.
    assert profile["resize_signal"] is True and "signal.SIGUSR1, _note_resize" in DOOR
    # Several sessions share one WAL world, which NetBBS allows only when certified.
    assert 1 < profile["max_sessions"] <= 36 and profile["multinode_certified"] is True


def test_profile_keeps_the_world_in_the_node_backup():
    # NetBBS backs up `<node>.db.doors/war-dialer.db`, the bundled copy's world.
    assert list(PROFILE["profile"]["environment"]) == ["WAR_DIALER_DB_PATH"]
    assert PROFILE["profile"]["environment"]["WAR_DIALER_DB_PATH"].endswith(".db.doors/war-dialer.db")
    assert 'os.environ.get("WAR_DIALER_DB_PATH")' in DOOR


def test_release_ships_the_profile_under_the_checksums():
    assert "sha256sum war_dialer.py netbbs.json > SHA256SUMS" in WORKFLOW
    assert re.search(r"gh release create .* war_dialer\.py netbbs\.json SHA256SUMS", WORKFLOW)


def test_release_notes_read_the_schema_the_door_declares():
    # The workflow's pattern must still find the constant, or every note says
    # the format changed.
    assert re.search(r"^WORLD_SCHEMA_VERSION = [0-9]+$", DOOR, re.M)
    assert "^WORLD_SCHEMA_VERSION = " in WORKFLOW
