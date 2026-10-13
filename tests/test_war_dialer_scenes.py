"""
War Dialer's mid-game scenes: the root, the raid, the hack, the bust, the
promotion, the crackdown, the receipts waiting at login and a medal's cracktro.

Every composer is pure, so each one is held to the terminal's bounds at every
size the door accepts, to CP437, to a wire budget and to a caption that says
the outcome. Just as important is when a scene is *not* played: under the
presets and the switch that drop it, when input is waiting, and anywhere it
would come before the commit it shows.
"""

from __future__ import annotations

import io
from datetime import timedelta

import pytest

from .test_war_dialer_splash import _picture, _width, wd


@pytest.fixture(autouse=True)
def _scenes_switched_on(monkeypatch):
    """The suite turns scenes off (conftest); these tests are about them."""
    monkeypatch.delenv("DOOR_SCENES", raising=False)


def _palette(depth: str = "truecolor"):
    return wd.Palette(truecolor=depth == "truecolor", color_depth=depth)


KINDS = ["mine", "rival", "npc", None, "rival", "npc", None, "mine", "rival", None]
WIDE = "Ｗｉｄｅ" * 6

SCENES = {
    "root-won": lambda p, w, h, **kw: wd.root_scene_frames(
        p, w, h, handle="alice", exchange_name="415-555 Bay Exchange", role="carrier",
        defender="rival", kinds=KINDS, index=4, success=True,
        caption="You root 415-555 Bay Exchange. It's yours now.", sub="+50 Rank, $12/hour", **kw),
    "root-held": lambda p, w, h, **kw: wd.root_scene_frames(
        p, w, h, handle="alice", exchange_name="415-555 Bay Exchange", role="pbx",
        defender="npc", kinds=KINDS, index=2, success=False,
        caption="The exchange's defenses hold.", sub="-1 crew, -$25 cash", **kw),
    "root-free": lambda p, w, h, **kw: wd.root_scene_frames(
        p, w, h, handle=WIDE, exchange_name="212-555 Hub Exchange", role="hub",
        defender=None, kinds=KINDS, index=3, success=True,
        caption="You root 212-555 Hub Exchange. It's yours now.", **kw),
    "bust": lambda p, w, h, **kw: wd.bust_scene_frames(
        p, w, h, cash_before=1200, cash_after=900, crew_before=10, crew_after=8,
        caption="*** BUSTED *** Heat reset to 0", sub="Job failed. Recovery payout $0.", **kw),
    "raid-won": lambda p, w, h, **kw: wd.raid_scene_frames(
        p, w, h, handle="alice", target="mallory", success=True, amount=340, crew=6,
        caption="You hit mallory; gross take $340.", sub="+25 Rank", **kw),
    "raid-lost": lambda p, w, h, **kw: wd.raid_scene_frames(
        p, w, h, handle="alice", target=WIDE, success=False, crew=5, crew_lost=1,
        caption="The raid failed.", sub="-1 crew, -$40 cash", **kw),
    "crackdown": lambda p, w, h, **kw: wd.crackdown_scene_frames(
        p, w, h, season_number=12, caption="Fed crackdown: season 12 has started.",
        sub="Crews and exchanges have reset.", **kw),
    "tier": lambda p, w, h, **kw: wd.tier_scene_frames(
        p, w, h, handle="alice", old_tier="Wannabe", new_tier="Script Kiddie", rank=312,
        caption="Promoted: Script Kiddie", sub="Rank 312, up from Wannabe", **kw),
    "tier-top": lambda p, w, h, **kw: wd.tier_scene_frames(
        p, w, h, handle=WIDE, old_tier="Elite", new_tier="Legend", rank=2800,
        caption="Promoted: Legend", **kw),
    "messages": lambda p, w, h, **kw: wd.messages_scene_frames(
        p, w, h, actors=["mallory", WIDE, "eve"], count=3,
        caption="3 hostile receipts while you were away.", sub="Your log follows.", **kw),
    "cracktro": lambda p, w, h, **kw: wd.cracktro_scene_frames(
        p, w, h, season_number=4, podium=[("Gold", "alice", 3100), ("Silver", WIDE, 2200),
                                          ("Bronze", "eve", 900)],
        handle="alice", placement=1, caption="Season 4: you placed #1, Gold.", **kw),
}
SCENES.update({
    f"job-{contract}-{'won' if success else 'lost'}": (
        lambda p, w, h, contract=contract, success=success, **kw: wd.hack_scene_frames(
            p, w, h, handle="alice", contract=contract, approach=contract % 3, success=success,
            payout=420, crew_lost=0 if success else 1,
            caption="Success! Gross payout $420." if success else "Job failed. Recovery payout $0.", **kw))
    for contract in range(len(wd.JOBS)) for success in (True, False)
})
SCENES["operation"] = lambda p, w, h, **kw: wd.hack_scene_frames(
    p, w, h, handle="alice", contract=3, approach=2, success=True, payout=800, operation=True,
    caption="Operation succeeded! Gross payout $800; slot clear.", **kw)
SIZES = [(40, 12), (64, 20), (72, 24), (80, 24), (132, 50)]


@pytest.mark.parametrize("name", sorted(SCENES))
@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("depth", ["truecolor", "256", "16"])
def test_every_write_stays_inside_the_terminal(name, width, height, depth):
    frames = SCENES[name](_palette(depth), width, height, seed=1)
    assert frames
    for ops in frames:
        for row, col, segments in ops:
            text = "".join(t for _, t in segments)
            assert "\r" not in text and "\n" not in text and "\x1b" not in text
            # Every visible character carries its color; a space never takes it away.
            assert all(style or not part.strip() for style, part in segments), (name, segments)
            assert 1 <= row <= height, (name, row, text)
            assert col >= 1 and col + _width(text) - 1 <= width, (name, row, col, text)
            assert not (row == height and col + _width(text) - 1 == width)


@pytest.mark.parametrize("name", sorted(SCENES))
def test_it_is_brief_never_quiet_and_small_on_the_wire(name):
    frames = SCENES[name](_palette(), 80, 24, seed=3)
    seconds = len(frames) * wd.SCENE_FRAME_SECONDS
    assert 1.2 <= seconds <= 4.0, (name, seconds)
    assert all(frames[1:]), "a frame without a write reads as a screen waiting on a key"
    wire = wd.splash_bytes(frames)
    assert sum(len(text.encode()) for text in wire) < 60_000


@pytest.mark.parametrize("name", sorted(SCENES))
@pytest.mark.parametrize("width,height", [(40, 12), (80, 24)])
def test_it_ends_on_its_caption_and_composes_the_same_way_every_time(name, width, height):
    frames = SCENES[name](_palette(), width, height, seed=5)
    assert frames == SCENES[name](_palette(), width, height, seed=5)
    plain = " ".join(_picture(frames, width, height).split())
    caption = {"bust": "BUSTED", "crackdown": "season 12", "tier": "Script Kiddie",
               "tier-top": "Legend", "messages": "3 hostile receipts", "cracktro": "placed #1",
               "root-won": "It's yours", "root-free": "It's yours", "root-held": "defenses hold",
               "raid-won": "gross take", "raid-lost": "raid failed", "operation": "Operation succeeded"}
    expected = caption.get(name, "Success!" if name.endswith("won") else "Job failed")
    assert expected in plain, (name, plain)


@pytest.mark.parametrize("name", sorted(SCENES))
@pytest.mark.parametrize("width,height", [(40, 12), (80, 24)])
def test_every_frame_is_mapped_to_cp437(name, width, height):
    for frame in wd.splash_bytes(SCENES[name](_palette("16"), width, height, seed=1)):
        wd._cp437_text(frame).encode("cp437", "strict")
        frame.translate(wd._CP437_TRANSLATION)


def test_the_tier_font_spells_every_tier():
    for _, name in wd.RANK_TIERS:
        rows = wd._tier_word(name)
        assert len({len(row) for row in rows}) == 1
        assert len(rows[0]) <= 80 - 26
        for ch in name.upper().replace(" ", ""):
            assert ch in wd._TIER_FONT


# -- when a scene plays --------------------------------------------------------------

def _idle(monkeypatch):
    written = []
    monkeypatch.setattr(wd, "out", written.append)
    monkeypatch.setattr(wd.select, "select", lambda r, w, x, t: ([], [], []))
    monkeypatch.setattr(wd.sys, "stdin", io.StringIO(""))
    return written


def _compose():
    return SCENES["bust"](_palette(), 80, 24)


def test_left_to_run_it_plays_every_frame_and_never_waits_for_a_key(monkeypatch):
    written = _idle(monkeypatch)
    beats = []
    monkeypatch.setattr(wd, "_beat", lambda s, *, hand_back=True: beats.append(hand_back) and False)
    monkeypatch.setattr(wd, "read_input_key", lambda: pytest.fail("a scene waited for a key"))
    assert wd.play_scene(_palette(), 80, 24, _compose) == wd.SCENE_SHOWN
    assert len(written) == len(_compose()) + 2
    assert beats and not any(beats)  # a skip key is never handed to the screen behind
    assert written[0].startswith("\x1b[?25l\x1b[2J") and written[-1].endswith("\x1b[?25h")


def test_any_key_ends_it_and_the_rest_of_the_chain(monkeypatch):
    written = _idle(monkeypatch)
    calls = []
    monkeypatch.setattr(wd, "_beat", lambda s, *, hand_back=True: calls.append(1) or len(calls) == 2)
    composed = []
    assert wd.play_scenes(_palette(), 80, 24, [lambda: composed.append("a") or _compose(),
                                               lambda: composed.append("b") or _compose()]) is True
    assert composed == ["a"] and len(written) == 1 + 2 + 1


def test_switched_off_waiting_input_and_motionless_presets_play_nothing(monkeypatch):
    written = _idle(monkeypatch)
    composed = []

    def compose():
        composed.append(1)
        return _compose()

    monkeypatch.setenv("DOOR_SCENES", "off")
    assert wd.play_scene(_palette(), 80, 24, compose) == wd.SCENE_ABSENT
    monkeypatch.delenv("DOOR_SCENES")
    for preset in ("fast", "monochrome", "ascii_art"):
        p = _palette()
        setattr(p, preset, True)
        assert wd.play_scene(p, 80, 24, compose) == wd.SCENE_ABSENT
    assert wd.play_scene(_palette(), 39, 24, compose) == wd.SCENE_ABSENT
    monkeypatch.setattr(wd.select, "select", lambda r, w, x, t: (r, [], []))
    assert wd.play_scene(_palette(), 80, 24, compose) == wd.SCENE_ABSENT
    assert written == [] and composed == []


def test_the_splash_switch_does_not_turn_scenes_off(monkeypatch):
    _idle(monkeypatch)
    monkeypatch.setenv("DOOR_SPLASH", "0")
    monkeypatch.setattr(wd, "_beat", lambda s, *, hand_back=True: True)
    assert wd.play_scene(_palette(), 80, 24, _compose) == wd.SCENE_SKIPPED


def _player(**fields):
    base = dict(user_id=1, handle="alice", cash=900, crew=8, crew_recruited_total=0,
                exchanges_taken_total=0, successful_raids=0, successful_jobs=0, heat=0.0,
                heat_updated_at="", turns_used=3, turn_day_start="", last_raided_by=None,
                season_number=2, created_at="")
    return wd.Player(**{**base, **fields})


def test_a_bust_replaces_the_actions_own_scene_and_a_promotion_follows():
    player = _player(successful_raids=4)  # 100 Rank: Wannabe
    delta = wd.ActionDelta(cash=-300, crew=-2, rank=25)
    own = lambda: []
    scenes = wd.outcome_scenes(_palette(), player, delta, True, ["The raid failed."], 80, 24, own)
    assert len(scenes) == 2 and own not in scenes
    picture = _picture(scenes[0](), 80, 24)
    assert "BUSTED" in picture and "The raid failed." in picture
    assert "Wannabe" in _picture(scenes[1](), 80, 24)
    assert wd.outcome_scenes(_palette(), player, wd.ActionDelta(rank=0), False, [], 80, 24, own) == [own]


def test_the_result_screen_opens_with_the_scene_instead_of_the_sweep(monkeypatch):
    shown, swept = [], []
    monkeypatch.setattr(wd, "play_scenes", lambda p, w, h, composers: shown.append(composers) or True)
    monkeypatch.setattr(wd, "resolve_sweep", lambda *a, **k: swept.append(1))
    monkeypatch.setattr(wd, "show_text_pages", lambda *a, **k: None)
    scene = lambda: []
    wd.show_action_result(_palette(), ["ok"], wd.ActionDelta(), False, 78, 24, scene=scene)
    assert shown == [[scene]] and swept == []
    monkeypatch.setattr(wd, "play_scenes", lambda p, w, h, composers: False)
    wd.show_action_result(_palette(), ["ok"], wd.ActionDelta(), False, 78, 24, scene=scene)
    assert swept == [1]


def test_login_scenes_follow_unseen_receipts(tmp_path):
    conn = wd.connect(tmp_path / "w.db")
    wd.ensure_schema(conn)
    now = wd.now_utc()
    season = wd.current_world_season(conn, now)
    wd.ensure_exchanges_seeded(conn, season, now)
    player = wd.load_or_create_player(conn, 1, "alice", now, season)
    assert wd.login_scenes(_palette(), conn, player, 80, 24) == []
    wd.record_event(conn, 1, "mallory", "mallory raided you and got away with $40!", now)
    wd.record_event(conn, 1, None, f"{wd.CRACKDOWN_RECEIPT} 3. Final Rank 9.", now)
    scenes = wd.login_scenes(_palette(), conn, player, 80, 24)
    pictures = [_picture(compose(), 80, 24) for compose in scenes]
    assert len(pictures) == 2
    assert "Fed crackdown" in pictures[0] and "mallory" in pictures[1]
    wd.mark_events_seen(conn, 1, [e.id for e in wd.unseen_events(conn, 1)], now + timedelta(seconds=1))
    assert wd.login_scenes(_palette(), conn, player, 80, 24) == []
    conn.close()
