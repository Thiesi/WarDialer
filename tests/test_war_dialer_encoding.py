"""CP437 wire bytes, authored screens and persistent caller preferences."""
import ast
import io
import json
import os
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from .test_war_dialer_presentation import wd, _WAR_DIALER_PATH, _painted_world, _walk_screens
from .test_war_dialer_dropfiles import FIXTURES, DOOR_PYTHON


@pytest.fixture(autouse=True)
def encoding_state(monkeypatch):
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    monkeypatch.setattr(wd, "_OUTPUT_ENCODING", "utf-8")
    monkeypatch.setattr(wd, "_DEFAULT_ENCODING", "utf-8")
    monkeypatch.setattr(wd, "_ASCII_DECOR", False)
    monkeypatch.setattr(wd, "_MONOCHROME", False)
    # Reconfiguration must not change pytest's own output stream.
    raw = io.BytesIO()
    terminal = io.TextIOWrapper(raw, encoding="utf-8", newline="")
    monkeypatch.setattr(wd, "sys", SimpleNamespace(**{**vars(sys), "stdout": terminal}))
    yield raw


def test_every_authored_glyph_has_an_explicit_cp437_form():
    tree = ast.parse(_WAR_DIALER_PATH.read_text(encoding="utf-8"))
    docs = {id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            node.value.translate(wd._CP437_TRANSLATION).encode("cp437", "strict")


@pytest.mark.parametrize("preset", ["default", "ascii_art", "monochrome", "fast"])
@pytest.mark.parametrize("width,height", [(40, 12), (64, 20), (80, 24)])
def test_every_screen_writes_strict_cp437(tmp_path, monkeypatch, encoding_state, preset, width, height):
    conn, _ = _painted_world(tmp_path)
    values = {"encoding": "cp437"}
    if preset != "default":
        values[preset] = True
    conn.execute("INSERT INTO meta(key,value) VALUES ('display:1',?)", (json.dumps(values),))
    palette = wd.Palette(False, color_depth="16")
    wd.apply_display(palette, values)
    output = wd.out
    screens = _walk_screens(conn, palette, width, height, monkeypatch)
    for screen in screens:
        expected = screen.translate(wd._CP437_TRANSLATION)
        expected.encode("cp437", "strict")  # no arbitrary-name fallback for authored art
        encoding_state.seek(0)
        encoding_state.truncate()
        output(screen)
        rendered = encoding_state.getvalue().decode("cp437", "strict")
        # Monochrome removes reset/bold SGR too, at the output boundary.
        assert wd._strip_ansi(rendered) == wd._strip_ansi(expected)
        for row in wd._strip_ansi(rendered).split("\r\n"):
            assert wd._visible_width(row) <= width
    conn.close()


@pytest.mark.parametrize("width,height", [(40, 12), (64, 20), (80, 24)])
def test_every_splash_frame_is_mapped(width, height):
    frames = wd.splash_frames(wd.Palette(False, color_depth="16"),
                              {"handle": "Jäger", "node_name": "Local"}, 1, width, height, seed=1)
    for frame in wd.splash_bytes(frames):
        frame.translate(wd._CP437_TRANSLATION).encode("cp437", "strict")


@pytest.mark.parametrize("host", [False, True])
def test_wire_encoding_preserves_controls_and_host_utf8(monkeypatch, encoding_state, host):
    if host:
        monkeypatch.setenv("NETBBS_DOOR_INFO", "host.json")
    wd.apply_display_encoding("cp437")
    wd.out("\x1b[2J\x1b[31mJäger ┌─┐ ▚\x1b[0m\r\n")
    raw = encoding_state.getvalue()
    assert raw.startswith(b"\x1b[2J\x1b[31m") and raw.endswith(b"\x1b[0m\r\n")
    assert ("Jäger".encode("utf-8") if host else "Jäger".encode("cp437")) in raw


def test_user_name_fallback_preserves_columns():
    text = "Jäger Łódź 界 🚀 e\u0301"
    converted = wd._cp437_text(text)
    converted.encode("cp437", "strict")
    assert "?" not in converted
    assert wd._visible_width(converted) == wd._visible_width(text)


def test_classic_launch_defaults_to_cp437_and_honors_saved_utf8(tmp_path):
    drop = tmp_path / "DOOR.SYS"
    lines = (FIXTURES / "DOOR.SYS").read_text().splitlines()
    lines[35] = "Jäger"
    drop.write_bytes("\n".join(lines).encode("cp437"))
    world = tmp_path / "classic.db"
    env = dict(os.environ, WAR_DIALER_DB_PATH=str(world), DOOR_SPLASH="0")
    env.pop("NETBBS_DOOR_INFO", None)
    def launch():
        result = subprocess.run([DOOR_PYTHON, str(_WAR_DIALER_PATH), str(drop)],
                                input=b"", capture_output=True, env=env, timeout=30)
        assert result.returncode == 0, result.stderr
        return result.stdout
    assert "Jäger".encode("cp437") in launch()
    with sqlite3.connect(world) as conn:
        conn.execute("INSERT INTO meta(key,value) VALUES ('display:77',?)",
                     (json.dumps({"encoding": "utf-8"}),))
    assert "Jäger".encode("utf-8") in launch()


@pytest.mark.parametrize("operation", ["close-season", "reset"])
def test_display_choice_survives_admin_operations(tmp_path, monkeypatch, operation):
    conn, _ = _painted_world(tmp_path)
    path = tmp_path / "paint.db"
    choices = iter(["4", "4", "B"])
    monkeypatch.setattr(wd, "pick_record_page", lambda *args, **kwargs: next(choices))
    wd.do_display(wd.Palette(False), conn, 1, 80, 24)
    assert wd.read_display(conn, 1)["encoding"] == "cp437"
    conn.close()
    wd.administer_world(path, "maintenance", maintenance=True)
    wd.administer_world(path, operation, confirm=path.name, reason="next competition")
    conn = wd.connect(path)
    assert wd.read_display(conn, 1)["encoding"] == "cp437"
    conn.close()
