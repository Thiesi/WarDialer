"""
Carrier Detect (#24): War Dialer's presentation for wide, modern terminals.

Glass, keycaps, signal meters, the switch ring, the wide console, pixel art
and the result stamps are all presentation, so what these tests hold them to
is the contract the rest of the suite already enforces: every row fits its
terminal, nothing a caller reads changes words, and every capability a caller
lacks degrades to the frame they had before -- sixteen colors, CP437, ASCII
decorations, monochrome and Fast mode most of all.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from .test_war_dialer_presentation import _ANSI_RE, _painted_world, _screen_text, _screen_titles, wd
from .test_war_dialer_splash import INFO, _picture, _width


def _palette(depth: str = "truecolor"):
    return wd.Palette(truecolor=depth == "truecolor", color_depth=depth)


@pytest.fixture(autouse=True)
def _wide_state_restored(monkeypatch):
    """Display globals are module state; every test leaves them as it found them."""
    monkeypatch.setattr(wd, "_MARGIN", 0)
    monkeypatch.setattr(wd, "_ASCII_DECOR", False)
    monkeypatch.setattr(wd, "_OUTPUT_ENCODING", "utf-8")


# -- color -------------------------------------------------------------------------


def test_any_color_has_a_reading_at_every_depth():
    glass = wd.GLASS
    assert wd.xterm256(glass) in range(232, 256), "dark glass must recede as a grey, not glow as cube green"
    assert wd.xterm256((57, 255, 20)) == 82
    # Hue families: a dim phosphor stays green and an alarm stays red.
    assert wd.ansi16((20, 120, 40)) == 2 and wd.ansi16((57, 255, 20)) == 10
    assert wd.ansi16((255, 77, 77)) == 9
    sixteen = _palette("16")
    assert sixteen.tone((255, 176, 0)).startswith("\x1b[9")


@pytest.mark.parametrize("depth,expected", [("truecolor", True), ("256", True), ("16", False), ("none", False)])
def test_backgrounds_only_where_they_read_as_glass(depth, expected):
    p = _palette(depth)
    assert p.surfaces is expected
    assert bool(p.ground(wd.GLASS)) is expected


@pytest.mark.parametrize("preset", ["monochrome", "fast", "ascii_art"])
def test_presets_that_want_less_get_no_surfaces(preset):
    p = _palette()
    setattr(p, preset, True)
    assert not p.surfaces and p.ground(wd.GLASS) == ""


def test_glass_survives_every_reset_in_a_row():
    p = _palette()
    row = wd.sty(p.grey, "CASH") + " " + wd.sty(p.amber, "$12")
    glazed = wd.glaze(p, row)
    bg = p.ground(wd.GLASS)
    assert glazed.startswith(bg) and glazed.endswith(wd.RESET)
    # Every reset inside the row is followed by the glass again.
    assert glazed.count(wd.RESET + bg) == row.count(wd.RESET)
    assert _ANSI_RE.sub("", glazed) == "CASH $12"
    assert wd.glaze(_palette("16"), row) == row


def test_a_keycap_is_still_the_bracketed_key():
    for depth in ("truecolor", "256", "16", "none"):
        cap = wd.keycap(_palette(depth), "T")
        assert _ANSI_RE.sub("", cap) == "[T]"
    assert wd.keycap(_palette("16"), "T") == wd.sty(_palette("16").amber + wd.BOLD, "[T]")


# -- gauges ------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 0.4, 1, 33, 50, 79.9, 99.6, 100])
@pytest.mark.parametrize("climb", [False, True])
def test_a_signal_meter_is_exactly_its_width_and_never_lies_at_the_ends(value, climb):
    p = _palette()
    bar = wd.meter(p, value, 100, 18, climb=climb)
    plain = _ANSI_RE.sub("", bar)
    assert _width(plain) == 18
    lit = [ch for ch in plain if ch in wd.EIGHTHS[1:]]
    if value > 0:
        assert lit, "something is never drawn as nothing"
    else:
        assert not lit
    if value < 100:
        assert wd.gl("meter_off") in plain or plain[-1] in wd.EIGHTHS[1:8], "not-all is never all"
    else:
        assert plain == wd.EIGHTHS[8] * 18


def test_heat_warms_along_its_track():
    p = _palette()
    bar = wd.meter(p, 100, 100, 10, climb=True)
    colors = [escape for escape in _ANSI_RE.findall(bar) if "38;2;" in escape]
    assert colors[0] != colors[-1]
    first = tuple(int(n) for n in re.findall(r"\d+", colors[0])[2:5])
    last = tuple(int(n) for n in re.findall(r"\d+", colors[-1])[2:5])
    assert first[1] > first[0], "the cool end is green"
    assert last[0] > last[1], "the far end is the bust line's red"


def test_whole_cell_meters_where_there_is_no_glass():
    for depth in ("16", "none"):
        plain = _ANSI_RE.sub("", wd.meter(_palette(depth), 50, 100, 10))
        assert set(plain) <= {wd.gl("meter_on"), wd.gl("meter_off")}


def test_cp437_maps_every_new_block_to_one_column():
    for ch in "▏▎▍▌▋▊▉" + wd.QUADRANTS[1:] + "╭╮╰╯┬┴":
        mapped = ch.translate(wd._CP437_TRANSLATION)
        assert len(mapped) == 1
        mapped.encode("cp437")


# -- pixels ------------------------------------------------------------------------


def test_quadrants_keep_two_colors_and_the_surface():
    green, red = (0, 255, 0), (255, 0, 0)
    assert wd._quadrant(None, None, None, None) == (" ", None, None)
    glyph, fg, bg = wd._quadrant(green, None, None, green)
    assert glyph == "▚" and fg == green and bg is None
    glyph, fg, bg = wd._quadrant(green, green, red, red)
    assert glyph == "▀" and (fg, bg) == (green, red)


@pytest.mark.parametrize("pixels", ["quad", "half"])
@pytest.mark.parametrize("depth", ["truecolor", "256", "16"])
def test_the_wordmark_fits_and_draws_in_every_pixel_mode(pixels, depth):
    p = _palette(depth)
    p.pixels = pixels
    rows = wd.wordmark_rows(p)
    plain = [_ANSI_RE.sub("", row) for row in rows]
    assert len({_width(row) for row in plain}) == 1
    assert _width(plain[0]) <= 52, "the masthead's wordmark is promised to 52 columns"
    allowed = set(wd.QUADRANTS) if pixels == "quad" else set(" ▀▄█")
    assert set("".join(plain)) <= allowed
    if depth == "16":
        assert "48;" not in "".join(rows), "sixteen colors draw a silhouette, never a background"


def test_cp437_output_draws_pixels_in_half_blocks(monkeypatch):
    p = _palette()
    monkeypatch.setattr(wd, "_OUTPUT_ENCODING", "cp437")
    assert wd.pixel_across(p) == 1
    assert set(_ANSI_RE.sub("", "".join(wd.wordmark_rows(p)))) <= set(" ▀▄█")


def test_netbbs_can_say_a_font_has_no_quadrants(monkeypatch):
    monkeypatch.delenv("DOOR_PIXELS", raising=False)
    assert _palette().pixels == "quad"
    monkeypatch.setenv("DOOR_PIXELS", "half")
    assert _palette().pixels == "half"


def test_the_bloom_never_fills_a_counter():
    """An A, a D and an R keep their holes: bloom only grows outside the letters."""
    mask = wd.mast_mask("D")
    art = wd.phosphor_logo(mask)
    # The D's counter, two rows down and in from its stem, is still the surface.
    assert art[1 + 3][1 + 4] is None


# -- the ring ------------------------------------------------------------------------


@pytest.mark.parametrize("width", [50, 58, 72, 96])
def test_the_switch_ring_names_every_exchange_and_fits(tmp_path, width):
    conn, _ = _painted_world(tmp_path, f"ring{width}.db")
    p = _palette()
    exchanges = wd.list_exchanges(conn, 1)
    rows = wd.switch_ring(p, exchanges, 1, width)
    assert rows is not None and len(rows) == 5
    plain = [_ANSI_RE.sub("", row) for row in rows]
    assert all(_width(row) <= width for row in plain), plain
    for exchange in exchanges:
        assert f"{exchange.id:02d}" in plain[1] + plain[3]
    glyphs = {wd.gl(name) for name in ("mine", "rival", "npc", "free")}
    # Every node sits under the start of its name.
    for names, rail in ((plain[0], plain[1]), (plain[4], plain[3])):
        nodes = [index for index, ch in enumerate(rail) if ch in glyphs]
        assert len(nodes) == 5
        for column in nodes:
            assert names[column] != " ", (column, names, rail)
    conn.close()


def test_the_ring_reads_the_owner_colors_the_table_does(tmp_path):
    conn, _ = _painted_world(tmp_path, "ringcolor.db")
    p = _palette()
    exchanges = wd.list_exchanges(conn, 1)
    rail = wd.switch_ring(p, exchanges, 1, 72)[1]
    assert p.phosphor + wd.BOLD + wd.gl("mine") in rail
    assert p.magenta + wd.BOLD + wd.gl("rival") in rail
    conn.close()


def test_a_ring_too_narrow_to_name_leaves_it_to_the_compact_map(tmp_path):
    conn, _ = _painted_world(tmp_path, "narrow.db")
    assert wd.switch_ring(_palette(), wd.list_exchanges(conn, 1), 1, wd.RING_MIN_WIDTH - 1) is None
    conn.close()


# -- the wide console ------------------------------------------------------------------


@pytest.mark.parametrize("width,panel,margin", [(40, 40, 0), (80, 78, 0), (99, 78, 0),
                                                (100, 96, 2), (132, 104, 14), (200, 104, 48)])
def test_wide_terminals_get_a_centred_console(width, panel, margin):
    assert wd.apply_layout(width) == panel
    assert wd._MARGIN == margin


@pytest.mark.parametrize("width,height,most", [(132, 40, 1), (160, 50, 1), (100, 30, 2)])
def test_the_wide_switchboard_fits_on_one_page_given_the_rows(tmp_path, monkeypatch, width, height, most):
    conn, now = _painted_world(tmp_path, f"wide{width}.db")
    p = _palette()
    state = wd.dashboard_state(conn, 1, now)
    written: list[str] = []
    monkeypatch.setattr(wd, "out", written.append)
    monkeypatch.setattr(wd, "_OUTPUT_WIDTH", width)
    panel = wd.apply_layout(width)
    _, pages = wd.draw_dashboard(p, state, now, panel, height)
    assert pages <= most
    rows = _ANSI_RE.sub("", "".join(written)).split("\r\n")
    assert len(rows) <= height
    assert all(_width(row) <= width for row in rows)
    text = _screen_text(written)
    for fact in ("CASH $4,820", "HEAT", "CREW", "TURNS", "HOLD", "Uptown"):
        assert fact in text, fact
    if most == 1:
        titles = _screen_titles(written)
        for heading in ("CREW", "THE SCENE", "FEED", "ORDERS", "SEASON"):
            assert heading in titles, heading
    conn.close()


def test_a_split_card_joins_its_divider_to_the_rules_above_and_below():
    p = _palette()
    body = wd.split_rows(p, ["left one", "left two"], ["right"], 20)
    rows = [_ANSI_RE.sub("", row) for row in
            wd.frame_rows(p, 60, [("", ["head"]), (wd.Split("LEFT", "RIGHT", 20), body), ("FOOT", ["x"])])]
    divider = rows[3].index(wd.gl("v"), 1)
    assert rows[2][divider] == wd.gl("mt")
    assert rows[5][divider] == wd.gl("mb")
    assert "LEFT" in rows[2] and "RIGHT" in rows[2]
    assert len({_width(row) for row in rows}) == 1


# -- outcomes ---------------------------------------------------------------------------


@pytest.mark.parametrize("success,busted,word", [(True, False, "CONNECT"), (False, False, "NO CARRIER"),
                                                 (None, False, "OK"), (True, True, "BUSTED")])
def test_a_result_is_stamped_with_its_modem_code(success, busted, word):
    p = _palette()
    rows = wd.outcome_stamp(p, success, busted, 72)
    assert len(rows) == 3 and all(_width(_ANSI_RE.sub("", row)) <= 72 for row in rows)
    wd._ASCII_DECOR = True
    try:
        plain = _ANSI_RE.sub("", "".join(wd.outcome_stamp(p, success, busted, 72)))
    finally:
        wd._ASCII_DECOR = False
    assert word in plain, "ASCII decorations spell the code out"


def test_the_stamp_is_never_the_only_word_on_the_outcome(monkeypatch):
    p = _palette()
    written: list[str] = []
    monkeypatch.setattr(wd, "out", written.append)
    monkeypatch.setattr(wd, "_OUTPUT_WIDTH", 80)
    monkeypatch.setattr(wd, "read_input_key", lambda: " ")
    wd.show_action_result(p, ["The raid on mallory failed."], wd.ActionDelta(crew=-1), False, 78, 24,
                          success=False)
    assert "The raid on mallory failed." in _screen_text(written)
    # Twelve rows have none to spare for it.
    written.clear()
    wd.show_action_result(p, ["The raid on mallory failed."], wd.ActionDelta(crew=-1), False, 40, 12,
                          success=False)
    assert "▀" not in _ANSI_RE.sub("", "".join(written))


# -- the splash and the scenes ------------------------------------------------------------


@pytest.mark.parametrize("width,height", [(80, 24), (100, 30), (123, 33), (124, 34), (160, 50), (200, 60)])
@pytest.mark.parametrize("depth", ["truecolor", "256", "16"])
def test_the_attract_mode_stays_inside_every_large_terminal(width, height, depth):
    frames = wd.splash_frames(_palette(depth), INFO, 4, width, height, seed=2)
    for ops in frames:
        for row, col, segments in ops:
            text = "".join(t for _, t in segments)
            assert 1 <= row <= height and col >= 1 and col + _width(text) - 1 <= width
            assert not (row == height and col + _width(text) - 1 == width)
    plain = _picture(frames, width, height)
    for part in ("ATDT 555-0142", wd.SPLASH_CONNECT, "SEASON 4", "Harbor Lights", "alice"):
        assert part in plain


@pytest.mark.parametrize("width,height", [(80, 24), (132, 40)])
def test_the_scan_lands_on_the_number_it_dials(width, height):
    frames = wd.splash_frames(_palette(), INFO, 1, width, height, seed=9)
    connect = next(index for index, ops in enumerate(frames)
                   if any(wd.SPLASH_CONNECT in "".join(t for _, t in seg) for _, _, seg in ops))
    plain = _picture(frames[:connect + 1], width, height)
    assert "0142◆" in plain, "the number that answered is marked as a carrier"


def test_a_scene_is_centred_whether_composed_for_the_console_or_the_terminal(monkeypatch):
    """Action scenes are composed at the console's width and login scenes at the
    terminal's; on a wide terminal both land in the same place. The caller says
    which it is (#27): a console scene passes the margin, a terminal one none."""
    monkeypatch.setattr(wd, "_OUTPUT_WIDTH", 132)
    panel = wd.apply_layout(132)
    console = wd._Stage(_palette(), panel, 40, 1, margin=wd._MARGIN)
    terminal = wd._Stage(_palette(), 132, 40, 1)
    assert console.left == terminal.left == (132 - console.cols) // 2
    assert wd._Stage(_palette(), panel, 40, 1).left == (panel - console.cols) // 2


def test_console_scenes_land_in_the_console_on_a_wide_terminal(monkeypatch):
    # #27, by behaviour: a bust and a season change played on a 132-column
    # terminal are shifted into the console margin by their callers.
    monkeypatch.setattr(wd, "_OUTPUT_WIDTH", 132)
    panel = wd.apply_layout(132)
    assert wd._MARGIN
    placed: list[int] = []
    real = wd._Stage

    class Recording(real):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            placed.append(self.left)

    monkeypatch.setattr(wd, "_Stage", Recording)
    # Only what a bust scene reads of its player.
    player = SimpleNamespace(handle="Neo", season_number=1, turns_used=1, cash=100, crew=3)
    for compose in wd.outcome_scenes(_palette(), player, wd.ActionDelta(cash=-10, crew=-1), True,
                                     ["Busted."], panel, 40, None):
        compose()
    monkeypatch.setattr(wd, "play_scene", lambda p, width, height, compose: compose())
    monkeypatch.setattr(wd, "show_text_pages", lambda *args, **kwargs: None)
    wd.draw_season_change(_palette(), 2, panel, 40)
    centred = (132 - real(_palette(), 132, 40, 1).cols) // 2
    assert placed == [centred, centred]


def test_every_console_scene_is_placed_by_its_caller():
    # #27: _Stage no longer reads the layout globals, so its callers must say
    # where a scene sits. Read from the syntax tree rather than the text, so a
    # rewrapped call still counts and a new caller cannot slip past: every
    # scene composed outside `login_scenes` passes the console margin, and the
    # login scenes, composed at the terminal's own width, pass none.
    tree = ast.parse(Path(wd.__file__).read_text(encoding="utf-8"))
    stage = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_Stage")
    read = {node.id for node in ast.walk(stage) if isinstance(node, ast.Name)}
    assert not read & {"_MARGIN", "_OUTPUT_WIDTH"}

    def margins(node: ast.AST) -> dict[int, ast.expr | None]:
        return {id(call): next((kw.value for kw in call.keywords if kw.arg == "margin"), None)
                for call in ast.walk(node)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id.endswith("_scene_frames")}

    everywhere = margins(tree)  # functions, methods and lambdas alike
    login = margins(next(node for node in tree.body
                         if isinstance(node, ast.FunctionDef) and node.name == "login_scenes"))
    assert len(login) == 3
    assert all(margin is None for margin in login.values())
    console = [margin for call, margin in everywhere.items() if call not in login]
    assert console
    assert all(isinstance(margin, ast.Name) and margin.id == "_MARGIN" for margin in console)


def test_scenes_play_on_glass_only_where_there_is_glass():
    glassy = wd._Stage(_palette(), 80, 24, 1)
    assert glassy.backdrop is not None
    assert wd._Stage(_palette("16"), 80, 24, 1).backdrop is None
    assert wd._Stage(_palette(), 80, 24, 1, glass=False).backdrop is None
    glassy.snap()
    assert len(glassy.frames[0]) == 24, "the first frame lays the whole pane"


# -- the review's findings -------------------------------------------------------------


def test_a_link_lights_only_between_two_holdings_of_one_crew(tmp_path):
    conn, _ = _painted_world(tmp_path, "links.db")
    now = wd.now_utc()
    wd.load_or_create_player(conn, 3, "Nightline", now, 1)
    conn.execute("UPDATE exchanges SET controller_user_id=2, garrison=1 WHERE id=1")
    conn.execute("UPDATE exchanges SET controller_user_id=3, garrison=1 WHERE id=2")
    conn.commit()
    p = _palette()

    def link(rail: str) -> str:
        start = rail.index("01") + 2
        return rail[start:rail.index(p.magenta + wd.BOLD + wd.gl("rival"), start)]

    rail = wd.switch_ring(p, wd.list_exchanges(conn, 1), 1, 72)[1]
    assert wd.gl("h") in link(rail) and p.magenta not in link(rail), "two crews' holdings are not a run"
    conn.execute("UPDATE exchanges SET controller_user_id=2 WHERE id=2")
    conn.commit()
    rail = wd.switch_ring(p, wd.list_exchanges(conn, 1), 1, 72)[1]
    assert p.magenta in link(rail)
    conn.close()


def test_256_color_surfaces_stay_apart():
    p = _palette("256")
    grounds = [p.ground(rgb) for rgb in (wd.GLASS, wd.GLASS_SCAN, wd.TAB, wd.KEYCAP, wd.CHIP, wd.CAPTION_BAND)]
    assert len(set(grounds)) == len(grounds)
    assert "48;5;16m" not in "".join(grounds), "no surface is pure black"


@pytest.mark.parametrize("width", [101, 103, 105])
def test_the_console_keeps_the_owner_counts_when_the_ring_cannot_be_named(tmp_path, width):
    conn, now = _painted_world(tmp_path, f"counts{width}.db")
    p = _palette()
    panel = wd.panel_width(width)
    inner = wd._panel_width(p, panel - 1)
    cards = wd.dashboard_cards(p, wd.dashboard_state(conn, 1, now), now, inner)
    text = _ANSI_RE.sub("", " ".join(row for _, rows in cards for row in rows))
    assert "yours 1" in text and "rival 1" in text
    conn.close()


def test_a_split_card_carried_to_the_next_page_says_so():
    split = wd.Split("CREW", "THE SCENE", 20)
    pages = wd.paginate_cards([(split, [str(n) for n in range(10)])], 6)
    assert len(pages) > 1
    assert pages[1][0][0].left == "CREW (cont.)" and isinstance(pages[1][0][0], wd.Split)


def test_a_meter_track_is_one_run():
    bar = wd.meter(_palette(), 30, 100, 18, climb=True)
    track = _ANSI_RE.sub("", bar).count(wd.gl("meter_off"))
    assert track > 1 and wd.gl("meter_off") * track in bar


@pytest.mark.parametrize("word", [name.upper() for _threshold, name in wd.RANK_TIERS])
def test_an_unglowing_wordmark_still_casts_its_shadow(word):
    # Without the glow's padding the grid's corner is the glyph's own lit
    # top-left pixel; the outside flood used to start only there, find nothing,
    # and leave every tier-up wordmark without the shadow its grid reserved.
    mask = wd.mask_from_rows(wd._tier_word(word))
    art = wd.phosphor_logo(mask, glow=False)
    shade = wd.mix(wd.TINTS["phosphor"][2], (0, 0, 0), 0.72)
    shadow = {(y, x) for y, row in enumerate(art) for x, px in enumerate(row) if px == shade}
    assert shadow
    # Cast one pixel down and right of a lit pixel, never over a lit one.
    for y, x in shadow:
        assert mask[y - 1][x - 1] and not (y < len(mask) and x < len(mask[0]) and mask[y][x])
