"""Classic host identity parsing and real standalone launches."""
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

import pytest

from tests.door_python import DOOR_PYTHON

DOOR = Path(__file__).resolve().parents[1] / "war_dialer.py"
FIXTURES = Path(__file__).parent / "fixtures/dropfiles"
spec = importlib.util.spec_from_file_location("war_dialer_dropfiles_test", DOOR)
wd = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wd
spec.loader.exec_module(wd)


@pytest.mark.parametrize("name,height", [("DOOR32.SYS", 24), ("DOOR.SYS", 30)])
def test_golden_classic_identity(name, height, monkeypatch):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    info = wd._load_door_info(str(FIXTURES / name))
    assert info["user_id"] == 77 and info["handle"] == "Starfox"
    assert info["terminal_width"] == 80 and info["terminal_height"] == height
    assert info["color_depth"] == "16" and info["minutes_left"] == 25
    if name == "DOOR32.SYS":
        assert info["comm_type"] == 2 and info["comm_handle"] == 1234
        assert info["node_name"] == "Test BBS"
    else:
        assert info["node_name"] == "Local"


def test_classic_cp437_alias_and_renamed_lf_file(tmp_path):
    lines = (FIXTURES / "DOOR32.SYS").read_text().splitlines()
    lines[6] = "Andr\u00e9"
    path = tmp_path / "caller.txt"
    path.write_bytes("\n".join(lines).encode("cp437"))
    assert wd._classic_door_info(path)["handle"] == "Andr\u00e9"


@pytest.mark.parametrize("name,contents", [
    ("DOOR32.SYS", "2\n1234\n"),
    ("DOOR.SYS", "COM1:\n"),
    ("unknown", "not a drop file"),
])
def test_malformed_classic_file_is_refused_without_creating_guest(tmp_path, monkeypatch, name, contents):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    path = tmp_path / name
    path.write_text(contents)
    with pytest.raises(wd.WorldStateError, match="no player was loaded"):
        wd._load_door_info(str(path))


def test_host_metadata_has_precedence_even_when_unreadable(tmp_path, monkeypatch):
    path = tmp_path / "host.json"
    monkeypatch.setenv("NETBBS_DOOR_INFO", str(path))
    with pytest.raises(wd.WorldStateError, match="launch metadata"):
        wd._load_door_info(str(FIXTURES / "DOOR.SYS"))
    host = {"user_id": 42, "handle": "Host caller", "war_dialer_owner": "a" * 32,
            "color_depth": "truecolor", "terminal_width": 64}
    path.write_text(json.dumps(host), encoding="utf-8")
    info = wd._load_door_info(str(tmp_path / "missing.sys"))
    assert all(info[key] == value for key, value in host.items())
    assert info["node_name"] == "NetBBS"


@pytest.mark.parametrize("line,value", [(0, "9"), (4, "0"), (4, "caller"), (9, "99")])
def test_invalid_classic_identity_is_rejected(tmp_path, line, value):
    lines = (FIXTURES / "DOOR32.SYS").read_text().splitlines()
    lines[line] = value
    path = tmp_path / "door32.sys"
    path.write_text("\n".join(lines))
    with pytest.raises(ValueError):
        wd._classic_door_info(path)


def test_neutral_defaults_and_basic_palette(monkeypatch):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    assert wd._load_door_info()["node_name"] == "Local"
    palette = wd.Palette(False, color_depth="16")
    for role in palette.ROLES:
        assert re.fullmatch(r"\x1b\[(?:3\d|9\d)m", palette.role(role))
    assert "38;5;" in wd.Palette(False).phosphor
    assert "38;2;" in wd.Palette(True).phosphor


def test_real_door_sys_launch_loads_the_classic_user(tmp_path):
    world = tmp_path / "world.db"
    env = dict(os.environ, WAR_DIALER_DB_PATH=str(world), DOOR_SPLASH="0")
    env.pop("NETBBS_DOOR_INFO", None)
    result = subprocess.run([DOOR_PYTHON, str(DOOR), str(FIXTURES / "DOOR.SYS")],
                            input=b"", capture_output=True, env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    assert b"38;5;" not in result.stdout and b"38;2;" not in result.stdout
    with sqlite3.connect(world) as conn:
        assert conn.execute("SELECT user_id,handle FROM players").fetchall() == [(77, "Starfox")]
