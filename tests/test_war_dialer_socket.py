"""Inherited DOOR32 sockets, telnet input and real carrier-loss boundaries."""
from contextlib import contextmanager
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

import pytest

from .door_python import DOOR_PYTHON

DOOR = Path(__file__).resolve().parents[1] / "war_dialer.py"
spec = importlib.util.spec_from_file_location("war_dialer_socket_test", DOOR)
wd = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wd
spec.loader.exec_module(wd)


@pytest.fixture
def wire(monkeypatch):
    local, peer = socket.socketpair()
    transport = wd._SocketTransport(local.detach())
    monkeypatch.setattr(wd, "_SOCKET_TRANSPORT", transport)
    monkeypatch.setattr(wd, "_PENDING_INPUT", [])
    try:
        yield transport, peer
    finally:
        transport.close()
        peer.close()


@pytest.mark.parametrize("command", [b"\xff\xfbM", b"\xff\xfcQ", b"\xff\xfdP", b"\xff\xfeY",
    b"\xff\xf1", b"\xff\xfa\x18MYP\xff\xffQ\xff\xf0"])
def test_telnet_commands_inside_arrow_keys_do_not_become_actions(wire, command):
    _, peer = wire
    peer.sendall(b"\x1b[" + command + b"A")
    assert wd.read_input_key() == ""
    peer.sendall(b"q")
    assert wd.read_input_key() == "q"


def test_partial_telnet_sequences_survive_timeouts(wire):
    transport, peer = wire
    for fragment in (b"\xff", b"\xfa", b"\x18M", b"\xff\xff", b"Q", b"\xff"):
        peer.sendall(fragment)
        assert transport(0.005) is None
    peer.sendall(b"\xf0Z\xff\xff")
    assert transport(0.1) == b"Z"
    assert transport(0.1) == b"\xff"


@pytest.mark.parametrize("ending", [b"\r\x00", b"\r\n", b"\r\xff\xfb\x01\x00"])
def test_cr_padding_is_one_enter_without_swallowing_the_next_key(wire, ending):
    transport, peer = wire
    peer.sendall(ending + b"Q")
    assert transport(0.1) == b"\r"
    assert transport(0.1) == b"Q"
    assert transport(0.01) is None


def test_socket_output_escapes_iac_after_cp437_encoding(wire, monkeypatch, capsys):
    _, peer = wire
    monkeypatch.setattr(wd, "_OUTPUT_ENCODING", "cp437")
    wd.out("ä\u00a0┌\r\n")
    assert peer.recv(20) == b"\x84\xff\xff\xda\r\n"
    assert capsys.readouterr().out == ""


def test_typed_ahead_socket_key_skips_splash_without_being_consumed(wire, monkeypatch):
    _, peer = wire
    monkeypatch.delenv("DOOR_SPLASH", raising=False)
    written = []
    monkeypatch.setattr(wd, "out", written.append)
    palette = wd.Palette(False)
    assert wd._splash_ready(palette)
    peer.sendall(b"q")
    assert not wd.play_splash(palette, {"handle": "Caller"}, 1, 80, 24)
    assert not written and wd.read_input_key() == "q"


def test_disconnected_socket_is_eof(wire):
    transport, peer = wire
    peer.close()
    with pytest.raises(EOFError):
        wd.read_key()
    with pytest.raises(wd._CarrierLost):
        transport.write(b"after disconnect")


@pytest.mark.skipif(os.name != "nt", reason="Windows pipe readiness")
def test_windows_pipe_splash_peek_preserves_typed_ahead_input(monkeypatch):
    read_fd, write_fd = os.pipe()
    stream = io.TextIOWrapper(io.FileIO(read_fd, closefd=False))
    monkeypatch.setattr(wd.sys, "stdin", stream)
    try:
        assert wd._splash_ready(wd.Palette(False))
        os.write(write_fd, b"q")
        assert not wd._splash_ready(wd.Palette(False))
        assert wd.read_key() == "q"
    finally:
        stream.close()
        os.close(read_fd)
        os.close(write_fd)


@contextmanager
def socket_visit(tmp_path):
    world = tmp_path / "world.db"
    conn = wd.connect(world)
    now = wd.now_utc()
    season = wd.current_world_season(conn, now)
    wd.ensure_exchanges_seeded(conn, season, now)
    wd.load_or_create_player(conn, 77, "Starfox", now, season)
    conn.execute("INSERT INTO meta(key,value) VALUES ('display:77',?)", (json.dumps({"fast": True}),))
    before = tuple(conn.execute("SELECT cash,crew,turns_used FROM players WHERE user_id=77").fetchone())
    conn.close()
    local, peer = socket.socketpair()
    drop = tmp_path / "DOOR32.SYS"
    drop.write_text(f"2\n{local.fileno()}\n38400\nTest BBS\n77\nTest Pilot\nStarfox\n100\n25\n1\n1\n")
    env = dict(os.environ, WAR_DIALER_DB_PATH=str(world), DOOR_SPLASH="0")
    env.pop("NETBBS_DOOR_INFO", None)
    if os.name == "nt":
        local.set_inheritable(True)
        inheritance = {"close_fds": False}
    else:
        inheritance = {"pass_fds": (local.fileno(),)}
    process = subprocess.Popen([DOOR_PYTHON, str(DOOR), str(drop)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, **inheritance)
    local.close()
    def wait_for(marker):
        pending = bytearray()
        deadline = time.monotonic() + 30
        while marker not in re.sub(rb"\x1b\[[0-9;]*[A-Za-z]", b"", pending):
            peer.settimeout(max(0.01, deadline - time.monotonic()))
            chunk = peer.recv(8192)
            assert chunk, (marker, bytes(pending))
            pending.extend(chunk)
        return bytes(pending)
    try:
        yield process, peer, world, before, wait_for
    finally:
        peer.close()
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=30)


def test_real_inherited_socket_routes_the_whole_visit(tmp_path):
    with socket_visit(tmp_path) as (process, peer, _, _, wait_for):
        wait_for(b"dial >")
        peer.sendall(b"q")
        assert process.wait(timeout=30) == 0
        assert process.stdout.read() == b""
        assert process.stderr.read() == b""


def test_carrier_drop_at_action_preview_spends_nothing(tmp_path):
    with socket_visit(tmp_path) as (process, peer, world, before, wait_for):
        wait_for(b"dial >")
        peer.sendall(b"t")
        wait_for(b"[A]")
        peer.close()
        assert process.wait(timeout=30) == 0
        assert process.stderr.read() == b""
        conn = wd.connect(world)
        assert tuple(conn.execute("SELECT cash,crew,turns_used FROM players WHERE user_id=77").fetchone()) == before
        conn.close()
