"""
Pressing your luck (world schema 13): the dig inside a hack.

Measured, the best play had been to spend Heat to the bust line and stop: a
calculation with nothing in it decided under uncertainty. A dig is the gamble.
A hack that lands leaves its line open; each dig adds Rank to what the caller
carries, and what they carry is theirs only once they hang up. A trace loses
it.

These tests hold the dig to the rules every other action keeps -- one
transaction a commit, nothing between a decision and its commit, a stale offer
refused without spending -- and to the promises it makes a caller: a dig costs
no turn, Rank that has been credited is never taken back, and the hack's own
Rank and payout are never at stake.
"""

from __future__ import annotations

import sqlite3

import pytest

from .test_war_dialer_dialing import (Rolls, _ANSI_RE, _lead, _module_state_restored, _painted_world,  # noqa: F401
                                      _palette, _play, _screen_text, _titles, wd, world)

WARM = 30       # what a warm carrier is worth, and so what its digs are sized on


def _hack(conn, player, now):
    """Crack a warm carrier, leaving its line open."""
    lead = _lead(conn, system=5, difficulty=1)
    success, _, busted = wd.resolve_lead(conn, player, lead, now, Rolls(0.0))
    assert success and not busted
    return player


# -- the rules ---------------------------------------------------------------------

def test_a_hack_that_lands_opens_a_line_and_one_that_fails_does_not(world):
    conn, now, player = world
    assert wd.dig_terms(player) is None
    wd.resolve_lead(conn, player, _lead(conn, system=5, difficulty=3), now, Rolls(0.99))
    assert wd.dig_terms(player) is None
    _hack(conn, player, now)
    assert (player.line_rank, player.line_depth, player.line_banked) == (WARM, 0, 0)
    assert wd.dig_terms(player) == (wd.DIGS[0][0], 15)
    stored = wd.read_player(conn, 1)
    assert (stored.line_rank, stored.line_depth, stored.line_banked) == (WARM, 0, 0)


def test_a_contract_and_an_operation_open_a_line_sized_on_their_own_rank(world):
    conn, now, player = world
    _, success, _, _ = wd.resolve_job(conn, player, now, Rolls(0.0), choice=wd.JobChoice(0, 1))
    assert success and player.line_rank == 15
    for step in ("case", "prepare", "execute"):
        result = wd.resolve_operation(conn, player, now, step, Rolls(0.0), choice=wd.JobChoice(0, 1))
    assert result[1] and player.line_rank == 30


def test_a_dig_costs_no_turn_or_cash_adds_heat_and_carries_rank_until_the_line_is_dug_out(world):
    conn, now, player = world
    _hack(conn, player, now)
    turns, cash, heat, rank = player.turns_used, player.cash, player.heat, wd.rank_score(player)
    carried = 0
    for depth, (_, share) in enumerate(wd.DIGS):
        delta = wd.ActionDelta()
        held, amount, busted = wd.resolve_dig(conn, player, now, Rolls(0.99), delta=delta)
        assert held and not busted and amount == WARM * share // 100
        carried += amount
        assert (delta.turns, delta.cash) == (0, 0) and delta.heat == pytest.approx(wd.DIG_HEAT)
        if depth < len(wd.DIGS) - 1:
            # Carried, not credited: Rank has not moved yet.
            assert delta.rank == 0 and player.line_banked == carried
            assert wd.rank_score(player) == rank
    # The third dig is the last, and hangs up with everything.
    assert delta.rank == carried == 90 and wd.rank_score(player) == rank + 90
    assert player.turns_used == turns and player.cash == cash
    assert player.heat == pytest.approx(heat + 3 * wd.DIG_HEAT)
    assert wd.dig_terms(player) is None
    with pytest.raises(wd.ActionRejected, match="line has dropped"):
        wd.resolve_dig(conn, player, now, Rolls(0.99))


def test_a_trace_loses_what_was_carried_and_nothing_that_was_earned(world):
    conn, now, player = world
    cash = player.cash
    _hack(conn, player, now)
    earned, paid = wd.rank_score(player), player.cash
    assert earned == WARM and paid > cash
    wd.resolve_dig(conn, player, now, Rolls(0.99))
    wd.resolve_dig(conn, player, now, Rolls(0.99))
    assert player.line_banked == 45 and wd.rank_score(player) == earned
    heat = player.heat
    delta = wd.ActionDelta()
    held, amount, busted = wd.resolve_dig(conn, player, now, Rolls(0.0), delta=delta)
    assert not held and amount == 45 and not busted
    # Rank is monotonic: what was carried was never credited, so nothing is taken back.
    assert wd.rank_score(player) == earned and delta.rank == 0
    assert player.cash == paid and delta.cash == 0 and delta.turns == 0
    assert player.heat == pytest.approx(heat + wd.DIG_TRACE_HEAT)
    assert wd.dig_terms(player) is None


def test_hanging_up_keeps_what_was_carried_and_costs_nothing(world):
    conn, now, player = world
    _hack(conn, player, now)
    wd.resolve_dig(conn, player, now, Rolls(0.99))
    turns, heat, cash = player.turns_used, player.heat, player.cash
    delta = wd.ActionDelta()
    assert wd.resolve_hang_up(conn, player, now, delta=delta) == 15
    assert delta.rank == 15 and wd.rank_score(player) == WARM + 15
    assert (player.turns_used, player.heat, player.cash) == (turns, heat, cash)
    assert wd.dig_terms(player) is None and wd.read_player(conn, 1).line_rank == 0
    assert wd.resolve_hang_up(conn, player, now) == 0          # nothing left to hang up on
    assert wd.rank_score(player) == WARM + 15


def test_a_dig_is_allowed_with_no_turns_left_and_starts_no_turn_window(world):
    conn, now, player = world
    conn.execute("UPDATE players SET turns_used=?, turn_day_start=? WHERE user_id=1",
                 (wd.TURNS_PER_DAY - 1, wd.to_iso(now)))
    player = wd.refresh_player(conn, 1, now)
    _hack(conn, player, now)
    assert player.turns_used == wd.TURNS_PER_DAY
    held, _, _ = wd.resolve_dig(conn, player, now, Rolls(0.99))
    assert held and player.turns_used == wd.TURNS_PER_DAY


def test_any_other_action_hangs_up_and_keeps_what_was_carried(world):
    """A caller who dropped carrier on the offer walked away with it."""
    conn, now, player = world
    _hack(conn, player, now)
    wd.resolve_dig(conn, player, now, Rolls(0.99))
    delta = wd.ActionDelta()
    wd.resolve_trade_warez(conn, player, now, Rolls(0.99), delta=delta)
    assert wd.dig_terms(player) is None and wd.read_player(conn, 1).line_rank == 0
    assert wd.rank_score(player) == WARM + 15
    assert delta.rank == 0                                    # the Trade earned none of it
    with pytest.raises(wd.ActionRejected, match="line has dropped"):
        wd.resolve_dig(conn, player, now, Rolls(0.99))


def test_a_second_session_cannot_dig_the_same_dig_twice(world):
    conn, now, player = world
    _hack(conn, player, now)
    other = wd.read_player(conn, 1)                           # a second session's snapshot
    wd.resolve_dig(conn, player, now, Rolls(0.99))
    with pytest.raises(wd.ActionRejected, match="line has dropped"):
        wd.resolve_dig(conn, other, now, Rolls(0.99))         # it was offered dig one
    assert wd.read_player(conn, 1).line_banked == 15


def test_a_bust_on_a_dig_loses_what_was_carried(world):
    conn, now, player = world
    _hack(conn, player, now)
    wd.resolve_dig(conn, player, now, Rolls(0.99))
    conn.execute("UPDATE players SET heat=90 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    # First roll: the line holds. Second roll: the bust lands.
    held, amount, busted = wd.resolve_dig(conn, player, now, Rolls(0.99, 0.0))
    assert held and busted and player.heat == 0 and wd.dig_terms(player) is None
    assert wd.rank_score(player) == WARM                      # busted with the goods
    assert wd.read_career(conn, 1)["stats"]["busts"] == 1


def test_a_bust_on_the_hack_itself_leaves_no_line(world):
    conn, now, player = world
    conn.execute("UPDATE players SET heat=100 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    success, _, busted = wd.resolve_lead(conn, player, _lead(conn, system=5, difficulty=1), now, Rolls(0.0))
    assert success and busted and wd.dig_terms(player) is None


def test_the_sheet_counts_digs_traces_and_a_line_dug_out(world):
    conn, now, player = world
    _hack(conn, player, now)
    delta = wd.ActionDelta()
    for _ in wd.DIGS:
        wd.resolve_dig(conn, player, now, Rolls(0.99), delta=delta)
    assert delta.badges == ["deep"]
    _hack(conn, player, now)
    wd.resolve_dig(conn, player, now, Rolls(0.0))
    stats = wd.read_career(conn, 1)["stats"]
    assert (stats["digs"], stats["traces"], stats["deep_dives"]) == (4, 1, 1)
    assert stats["turns"] == 2                                # the two hacks; a dig is no turn
    assert stats["best_rank"] == wd.rank_score(player)


def test_a_season_closing_on_an_open_line_counts_what_it_carried(world):
    conn, now, player = world
    _hack(conn, player, now)
    wd.resolve_dig(conn, player, now, Rolls(0.99))
    wd.settle_world(conn, now + wd.SEASON)
    assert conn.execute("SELECT rank FROM season_results WHERE user_id=1").fetchone()[0] == WARM + 15
    fresh = wd.read_player(conn, 1)
    assert (fresh.line_rank, fresh.line_depth, fresh.line_banked, fresh.operation_lead) == (0, 0, 0, 0)
    assert wd.rank_score(fresh) == 0


def test_the_dig_table_keeps_its_shape():
    """Two digs worth taking, then a long shot: the third is the gamble."""
    assert len(wd.DIGS) == 3
    carried, values = 0, []
    for trace, share in wd.DIGS:
        values.append((1 - trace) * share - trace * carried)   # expected Rank, in percent of the hack's
        carried += share
    assert values[0] > 0 and values[1] > 0 and values[2] < 0
    assert [trace for trace, _ in wd.DIGS] == sorted(trace for trace, _ in wd.DIGS)


# -- schema 13 ---------------------------------------------------------------------

def test_the_open_line_upgrade_is_atomic_idempotent_and_hangs_up_nobody_new(world):
    conn, now, player = world
    wd.resolve_trade_warez(conn, player, now, Rolls(0.99))
    for column in ("operation_lead", "line_banked", "line_depth", "line_rank"):
        conn.execute(f"ALTER TABLE players DROP COLUMN {column}")
    conn.execute("PRAGMA user_version=12")
    before = list(conn.iterdump())

    def deny_version(action, name, value, *args):
        return (sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_PRAGMA and name == "user_version"
                and value == "13" else sqlite3.SQLITE_OK)

    conn.set_authorizer(deny_version)
    with pytest.raises(sqlite3.DatabaseError):
        wd.ensure_schema(conn)
    conn.set_authorizer(None)
    assert list(conn.iterdump()) == before
    wd.ensure_schema(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 13
    upgraded = wd.read_player(conn, 1)
    assert (upgraded.line_rank, upgraded.operation_lead, upgraded.cash) == (0, 0, player.cash)
    before = list(conn.iterdump())
    wd.ensure_schema(conn)
    assert list(conn.iterdump()) == before


# -- the screens -------------------------------------------------------------------

def _dial_world(tmp_path, name="luck.db"):
    conn, now = _painted_world(tmp_path, name)
    conn.execute("UPDATE players SET heat=10 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    _lead(conn, system=5, difficulty=1)
    return conn, now, player


def test_a_result_with_an_open_line_offers_the_dig_and_states_its_terms(tmp_path, monkeypatch):
    conn, now, player = _dial_world(tmp_path)
    written = _play(monkeypatch, ["1", "A", "B"])              # hack it, then leave the dialer
    wd.do_dial(_palette(), conn, player, Rolls(0.0), 79, 24)
    text, titles = _screen_text(written), _titles(written)
    assert "LINE OPEN" in titles
    assert "dig 1/3 +15 Rank" in text and "holds" in text and "75%" in text
    assert "carrying 0 Rank" in text
    assert "Nothing carried yet: a trace costs no Rank, but adds 12 Heat and drops the line." in text
    assert "[D] Dig deeper" in _ANSI_RE.sub("", "".join(written))
    conn.close()


def test_digging_then_hanging_up_shows_each_dig_and_what_they_came_to(tmp_path, monkeypatch):
    conn, now, player = _dial_world(tmp_path)
    rank, turns = wd.rank_score(player), player.turns_used
    keys = iter(["D", "D", " "])                              # dig, dig, hang up
    written = _play(monkeypatch, ["1", "A", "B"])
    monkeypatch.setattr(wd, "read_input_key", lambda: next(keys, " "))
    # The hack lands (0.0), then both digs hold (0.99).
    wd.do_dial(_palette(), conn, player, Rolls(0.0, 0.99), 79, 24)
    text = _screen_text(written)
    assert "Deeper. 15 more Rank in hand; hang up to keep it." in text
    assert "Deeper. 30 more Rank in hand; hang up to keep all 45." in text
    assert "dig 3/3 +45 Rank" in text and "A trace loses all 45 of it" in text
    assert "You hang up clean. The digs come to +45 Rank." in text
    after = wd.read_player(conn, 1)
    assert wd.rank_score(after) == rank + WARM + 45 and after.turns_used == turns + 1
    assert (after.line_rank, after.line_banked) == (0, 0)
    conn.close()


def test_a_trace_from_the_result_says_what_it_lost_and_offers_nothing_more(tmp_path, monkeypatch):
    conn, now, player = _dial_world(tmp_path)
    rank = wd.rank_score(player)
    keys = iter(["D", "D", " "])
    written = _play(monkeypatch, ["1", "A", "B"])
    monkeypatch.setattr(wd, "read_input_key", lambda: next(keys, " "))
    # The hack lands, the first dig holds, the second is traced.
    wd.do_dial(_palette(), conn, player, Rolls(0.0, 0.99, 0.0), 79, 24)
    text = _screen_text(written)
    assert "Traced! The line drops and the 15 Rank you carried goes with it." in text
    assert wd.RESULT_FLAVOUR["traced"][1] in text
    last = _ANSI_RE.sub("", "".join(written)).rsplit("ACTION RESULT", 1)[-1]
    assert "LINE OPEN" not in last and "[D] Dig" not in last and "hang up clean" not in last
    after = wd.read_player(conn, 1)
    assert after.line_rank == 0 and wd.rank_score(after) == rank + WARM
    conn.close()


def test_a_line_dug_out_from_the_result_credits_everything_at_once(tmp_path, monkeypatch):
    conn, now, player = _dial_world(tmp_path)
    rank = wd.rank_score(player)
    keys = iter(["D", "D", "D", " "])
    written = _play(monkeypatch, ["1", "A", "B"])
    monkeypatch.setattr(wd, "read_input_key", lambda: next(keys, " "))
    wd.do_dial(_palette(), conn, player, Rolls(0.0, 0.99), 79, 24)
    text = _screen_text(written)
    assert "Dug out. Everything you carried is yours: +90 Rank." in text
    assert "hang up clean" not in text                        # already hung up, by the third dig
    assert wd.rank_score(wd.read_player(conn, 1)) == rank + WARM + 90
    conn.close()


@pytest.mark.parametrize("width,height", [(80, 24), (40, 12), (132, 40)])
def test_the_offer_fits_its_terminal(tmp_path, monkeypatch, width, height):
    conn, now = _painted_world(tmp_path, f"offer{width}.db")
    player = wd.refresh_player(conn, 1, now)
    wd.open_line(player, 75)
    player.line_depth, player.line_banked = 2, 112
    written = _play(monkeypatch, [], width)
    wd.show_action_result(_palette(), ["Deeper. 75 more Rank in hand; hang up to keep all 112."],
                          wd.ActionDelta(), False, wd.apply_layout(width), height, player=player,
                          success=True, again=True)
    rows = _ANSI_RE.sub("", "".join(written)).split("\r\n")
    assert all(wd._dlen(row) <= width for row in rows)
    assert "[D] Dig" in " ".join(rows) and "[A] Again" in " ".join(rows)
    conn.close()


def test_a_preview_says_the_dig_is_coming(tmp_path):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    lead = _lead(conn, system=5, difficulty=3)
    assert wd.DIG_TERMS in wd.action_preview_lines("carrier", player, lead)
    assert wd.DIG_TERMS in wd.action_preview_lines("job", player, wd.JobChoice(0, 1))
    assert wd.DIG_TERMS not in wd.action_preview_lines("trade", player)
    conn.close()


# -- operations on carriers --------------------------------------------------------
#
# Three turns on a standing contract earned less Rank a turn than running it
# cold, and carriers widened the gap. An operation can now case a carrier out
# of the black book instead: the number is pinned, and a failed execution
# keeps it where a cold hack burns it.

from datetime import timedelta

ICE = 15        # LEAD_SYSTEMS index of an ice-tier system, worth 70 Rank


def _cased(conn, player, now, **lead):
    """Case a carrier and return the caller, the lead and its id."""
    target = _lead(conn, **lead)
    assert wd.resolve_operation(conn, player, now, "case", Rolls(0.0), lead=target) is None
    return target


def test_casing_a_carrier_pins_it_against_going_cold_and_against_a_full_book(world):
    conn, now, player = world
    target = _cased(conn, player, now, system=ICE, difficulty=16)
    assert wd.operation_state(player) == (-1, 1, 1, target.id)
    assert wd.cased_lead(conn, player) == target
    # Long past its seventy-two hours, it is still in the book.
    later = now + timedelta(hours=200)
    assert wd.read_leads(conn, 1, later) == [target]
    # And a sweep into a full book drops other numbers, never this one.
    for _ in range(wd.BOOK_LIMIT):
        _lead(conn, found=later, expires=later + wd.LEAD_LIFETIME)
    wd.resolve_dial(conn, wd.refresh_player(conn, 1, later), later, Rolls(0.0))
    book = wd.read_leads(conn, 1, later)
    assert target in book and len(book) == wd.BOOK_LIMIT + 1
    assert wd.dashboard_state(conn, 1, later).book == wd.BOOK_LIMIT + 1


def test_a_cased_number_cannot_be_hacked_cold(world):
    conn, now, player = world
    target = _cased(conn, player, now, system=5, difficulty=3)
    turns = player.turns_used
    with pytest.raises(wd.ActionRejected, match="cased for an operation"):
        wd.resolve_lead(conn, player, target, now, Rolls(0.0))
    assert wd.read_player(conn, 1).turns_used == turns and wd.cased_lead(conn, player) == target


def test_executing_a_cased_carrier_has_the_operations_edge(world):
    conn, now, player = world
    target = _cased(conn, player, now, system=ICE, difficulty=16, low=500, high=775)
    assert wd.lead_odds(player, target) == pytest.approx(wd.success_chance(3, 16))
    assert wd.lead_odds(player, target, operation=True) == pytest.approx(wd.success_chance(3, 16) + 0.15)
    easy = wd.Lead(0, 0, "x", 1, 1, 1, "", "", "")
    player.crew = 40
    assert wd.lead_odds(player, easy, operation=True) == 0.9          # the cap holds
    player = wd.refresh_player(conn, 1, now)
    cash = player.cash
    wd.resolve_operation(conn, player, now, "prepare", Rolls(0.0))
    assert player.cash == cash - 50 and player.operation_stage == 2
    delta = wd.ActionDelta()
    name, success, payout, busted = wd.resolve_operation(conn, player, now, "execute", Rolls(0.0), delta=delta)
    assert success and not busted and name == "Defense contractor timeshare, 415-555-0142"
    assert payout == 1000                                             # double the low end
    assert delta.rank == 70 + wd.OPERATION_RANK
    assert wd.operation_state(player) == (-1, 1, 0, 0) and wd.read_leads(conn, 1, now) == []
    assert player.line_rank == 70 + wd.OPERATION_RANK                 # and the line is open
    stats = wd.read_career(conn, 1)["stats"]
    assert (stats["operations"], stats["carriers"], stats["ice"], stats["operation_tries"]) == (1, 1, 1, 1)
    assert "carrier_tries" not in stats


def test_a_failed_execution_keeps_the_number_and_its_casing(world):
    conn, now, player = world
    target = _cased(conn, player, now, system=ICE, difficulty=16)
    wd.resolve_operation(conn, player, now, "prepare", Rolls(0.0))
    crew = player.crew
    name, success, payout, busted = wd.resolve_operation(conn, player, now, "execute", Rolls(0.99))
    assert not success and payout == 0
    assert player.crew == crew - 1                                    # the tier's own loss
    assert wd.operation_state(player) == (-1, 1, 1, target.id)        # back to cased
    assert wd.read_leads(conn, 1, now) == [target]
    assert wd.dig_terms(player) is None
    # Prepare again, and it can be run again.
    wd.resolve_operation(conn, player, now, "prepare", Rolls(0.0))
    assert wd.resolve_operation(conn, player, now, "execute", Rolls(0.0))[1]


def test_abandoning_unpins_the_number(world):
    conn, now, player = world
    target = _cased(conn, player, now, system=5, difficulty=3)
    wd.abandon_operation(conn, player, now)
    assert wd.operation_state(player) == (-1, 1, 0, 0)
    assert wd.read_leads(conn, 1, now) == [target]                    # still fresh: still there
    assert wd.read_leads(conn, 1, now + timedelta(hours=200)) == []   # and cold like any other


def test_a_stale_cold_or_foreign_number_cannot_be_cased(world):
    conn, now, player = world
    expired = _lead(conn, expires=now - timedelta(minutes=1))
    foreign = _lead(conn, user_id=2)
    changed = _lead(conn)
    conn.execute("UPDATE leads SET difficulty=9 WHERE id=?", (changed.id,))
    for target in (expired, foreign, changed):
        with pytest.raises(wd.ActionRejected):
            wd.resolve_operation(conn, player, now, "case", Rolls(0.0), lead=target)
    stored = wd.read_player(conn, 1)
    assert stored.turns_used == 0 and wd.operation_state(stored) == (-1, 1, 0, 0)


def test_a_cased_number_that_is_gone_can_only_be_abandoned(world):
    conn, now, player = world
    target = _cased(conn, player, now, system=5, difficulty=3)
    wd.resolve_operation(conn, player, now, "prepare", Rolls(0.0))
    conn.execute("DELETE FROM leads WHERE id=?", (target.id,))
    assert wd.cased_lead(conn, player) is None
    turns = player.turns_used
    with pytest.raises(wd.ActionRejected, match="cased number is gone"):
        wd.resolve_operation(conn, player, now, "execute", Rolls(0.0))
    assert wd.read_player(conn, 1).turns_used == turns
    assert wd.operation_target(player) == "a carrier that is gone"
    wd.abandon_operation(conn, player, now)
    assert wd.operation_state(player) == (-1, 1, 0, 0)


def test_a_season_takes_the_cased_carrier_with_the_operation(world):
    conn, now, player = world
    _cased(conn, player, now, system=5, difficulty=3)
    wd.settle_world(conn, now + wd.SEASON)
    fresh = wd.read_player(conn, 1)
    assert wd.operation_state(fresh) == (-1, 1, 0, 0)
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_a_contract_operation_is_untouched(world):
    conn, now, player = world
    for step in ("case", "prepare"):
        wd.resolve_operation(conn, player, now, step, Rolls(0.0), choice=wd.JobChoice(2, 1))
    assert wd.operation_state(player) == (2, 1, 2, 0) and wd.cased_lead(conn, player) is None
    assert wd.operation_target(player) == wd.JOBS[2][0]
    name, success, payout, _ = wd.resolve_operation(conn, player, now, "execute", Rolls(0.0))
    assert success and name == wd.JOBS[2][0] and payout == wd.JOBS[2][2][0] * 2


def test_the_ops_picker_offers_the_books_carriers_after_the_contracts(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    _lead(conn, system=0, difficulty=1)
    hard = _lead(conn, system=ICE, difficulty=16)
    written = _play(monkeypatch, ["6", "A"])                   # the first carrier, then Act on Case
    # Tall enough for the five contracts and both carriers on one page.
    assert wd.do_operation(_palette(), conn, player, Rolls(0.0), 79, 60) is True
    text, titles = _screen_text(written), _titles(written)
    assert "CASE AN OPERATION" in titles and "CONTRACTS AND CARRIERS" in titles
    # Hardest first: the ice carrier is offered ahead of the soft one.
    assert text.index("Defense contractor timeshare") < text.index("Voicemail box at an ad agency")
    assert "operation payout" in text and "+100 Rank" in text
    assert "CASE PREVIEW" in titles and "a cased number does not go cold" in text
    assert "Casing saved." in text
    assert wd.read_player(conn, 1).operation_lead == hard.id
    conn.close()


def test_a_cased_carrier_shows_on_the_switchboard_the_hub_and_the_black_book(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    target = _cased(conn, player, now, system=ICE, difficulty=16)
    other = _lead(conn, system=0, difficulty=1)
    state = wd.dashboard_state(conn, 1, now)
    assert state.cased == target
    written = _play(monkeypatch, [])
    wd.draw_dashboard(_palette(), state, now, 79, 24)
    assert "OPS Defense contractor ti" in _screen_text(written)
    chain = _ANSI_RE.sub("", " ".join(wd.operation_chain(_palette(), state.player, 75, target)))
    assert "carrier Defense contractor timeshare, 415-555-0142" in chain and "ICE" in chain
    # In the book it is marked, says where it is run from, and offers no digit.
    written = _play(monkeypatch, ["B"])
    wd.do_dial(_palette(), conn, state.player, Rolls(0.0), 79, 24)
    plain = _ANSI_RE.sub("", "".join(written))
    assert "CASED" in plain and "[O] Ops on the switchboard runs it" in _screen_text(written)
    assert "[-]" in plain and "pick [2]" in plain and "pick [1]" not in plain
    conn.close()


def test_an_execute_preview_for_a_carrier_states_the_operations_terms(tmp_path):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    target = _cased(conn, player, now, system=ICE, difficulty=16, low=500, high=775)
    wd.resolve_operation(conn, player, now, "prepare", Rolls(0.0))
    lines = wd.operation_preview_lines(player, "execute", target)
    text = " ".join(lines)
    assert "Operation: Defense contractor timeshare at 415-555-0142." in text
    assert f"Success: {wd.lead_odds(player, target, operation=True):.1%}" in text
    assert "Success pays $1,000-$1,550 and +100 Rank" in text
    assert "Operation failure keeps the number and its casing" in text
    assert "One attempt: win or lose" not in text
    cards = wd.operation_step_cards(_palette(), player, "execute", target, 75)
    assert [title for title, _ in cards][-2:] == ["STAKES", "TERMS"]
    conn.close()


# -- raids: an honest range, and a strike back --------------------------------------
#
# A raid was a blind roll at "10%-90%", and after one the 24-hour shield left
# the crew that was hit with nothing to do about it. A rival's crew is now
# public as a rough size, which the preview turns into a range, and a raided
# crew may strike back once.

@pytest.fixture
def rivals(tmp_path):
    """Two crews past their newcomer shields, in the same tier."""
    conn = wd.connect(tmp_path / "raid.db")
    wd.ensure_schema(conn)
    now = wd.now_utc()
    wd.get_or_create_season_anchor(conn, now)
    wd.ensure_exchanges_seeded(conn, 1, now)
    for user_id, handle in ((1, "Alpha"), (2, "Beta")):
        wd.load_or_create_player(conn, user_id, handle, now, 1)
    conn.execute("UPDATE players SET cash=1000, crew=6, created_at=?", (wd.to_iso(now - wd.GRACE * 2),))
    yield conn, now, wd.refresh_player(conn, 1, now), wd.refresh_player(conn, 2, now)
    conn.close()


def test_a_crew_reads_as_a_size_and_never_as_a_number():
    assert wd.crew_read(1) == ("a handful", 1, 3) and wd.crew_read(3)[0] == "a handful"
    assert wd.crew_read(4) == ("a small crew", 4, 8)
    assert wd.crew_read(20) == ("a full crew", 9, 20)
    assert wd.crew_read(21) == ("a big crew", 21, 50)
    assert wd.crew_read(51) == ("an army", 51, None) and wd.crew_read(9000)[0] == "an army"
    # Every size's range starts where the last one stopped.
    reads = [wd.crew_read(crew) for crew in range(1, 60)]
    assert all(low <= crew and (most is None or crew <= most)
               for crew, (_, low, most) in zip(range(1, 60), reads))


def test_a_raids_odds_are_a_range_that_holds_the_real_figure(rivals):
    conn, now, alpha, beta = rivals
    for crew in (1, 3, 4, 8, 9, 20, 21, 50, 51, 400):
        beta.crew = crew
        worst, best = wd.raid_odds_band(alpha, beta, now)
        assert worst <= wd.success_chance(alpha.crew, crew) <= best
        assert 0.10 <= worst <= best <= 0.90
    beta.crew = 6
    text = " ".join(wd.action_preview_lines("raid", alpha, beta))
    assert "Their crew reads as a small crew (4-8): your odds are 43%-60%." in text
    assert "They may strike back for 48 hours" in text
    cards = wd.stakes_cards(_palette(), "raid", alpha, beta, 75)
    stakes = _ANSI_RE.sub("", " ".join(dict(cards)["STAKES"]))
    assert "43%-60%" in stakes and "their crew a small crew" in stakes and "private" not in stakes


def test_a_raid_hands_its_target_one_strike_back_through_shields_and_tier(rivals):
    conn, now, alpha, beta = rivals
    assert wd.raid_block(beta, alpha, now)[0] == "eligible" and not wd.holds_grudge(beta, alpha, now)
    wd.resolve_raid(conn, alpha, 2, now, Rolls(0.99))                 # Alpha raids Beta, and fails
    beta = wd.refresh_player(conn, 2, now)
    assert beta.last_raided_by == 1 and wd.holds_grudge(beta, alpha, now)
    assert wd.grudge_until(beta) == wd.from_iso(beta.raid_shield_until) - wd.RAID_SHIELD + wd.GRUDGE
    receipt = wd.history_events(conn, 2)[0].summary_text
    assert "tried to raid you and got bounced" in receipt and "You may strike back for 48 hours." in receipt
    # Shields and tier would each block an ordinary raid on Alpha; the strike goes through all three.
    conn.execute("UPDATE players SET raid_shield_until=?, created_at=?, bonus_rank=5000 WHERE user_id=1",
                 (wd.to_iso(now + wd.DAY), wd.to_iso(now)))
    alpha = wd.refresh_player(conn, 1, now)
    assert wd.is_in_grace(alpha, now) and wd.tier_index(wd.rank_score(alpha)) > 1
    verdict, reason = wd.raid_block(beta, alpha, now)
    assert verdict == "grudge" and reason.startswith("Strike back until ")
    assert wd.is_eligible_raid_target(beta, alpha, now)
    assert wd.raid_block(alpha, beta, now)[0] == "recovering"         # the raider gets no such pass
    cash = beta.cash
    success, amount, _ = wd.resolve_raid(conn, beta, 1, now, Rolls(0.0))
    assert success and amount == int(alpha.cash * wd.RAID_STEAL_FRACTION) and beta.cash == cash + amount
    # Spent: one strike a raid suffered, and it handed Alpha none in return.
    assert beta.last_raided_by is None and not wd.holds_grudge(beta, alpha, now)
    alpha = wd.refresh_player(conn, 1, now)
    assert alpha.last_raided_by is None and not wd.holds_grudge(alpha, beta, now)
    assert "strike back" not in wd.history_events(conn, 1)[0].summary_text
    with pytest.raises(wd.ActionRejected, match="no longer eligible"):
        wd.resolve_raid(conn, beta, 1, now, Rolls(0.0))


def test_a_strike_back_has_better_odds_and_runs_out(rivals):
    conn, now, alpha, beta = rivals
    wd.resolve_raid(conn, alpha, 2, now, Rolls(0.99))
    beta = wd.refresh_player(conn, 2, now)
    alpha = wd.refresh_player(conn, 1, now)
    plain = wd.success_chance(beta.crew, alpha.crew)
    # A roll that only the strike's bonus turns into a win.
    roll = plain + wd.GRUDGE_ODDS / 2
    snapshot = wd.refresh_player(conn, 2, now)
    assert wd.action_raid(snapshot, wd.refresh_player(conn, 1, now), Rolls(roll), now=now)[0] is True
    worst, best = wd.raid_odds_band(beta, alpha, now)
    assert best == pytest.approx(min(0.9, wd.success_chance(beta.crew, wd.crew_read(alpha.crew)[1]) + wd.GRUDGE_ODDS))
    text = " ".join(wd.action_preview_lines("raid", beta, alpha))
    assert "Striking back: +10% to your odds" in text and "hands them none" in text
    # Forty-eight hours on, the grudge has run out and the ordinary rules are back.
    later = now + wd.GRUDGE + timedelta(minutes=1)
    assert not wd.holds_grudge(beta, alpha, later)
    assert wd.raid_block(beta, alpha, later)[0] == "eligible"


def test_the_rival_screens_show_a_crews_size_and_a_strike_back(rivals):
    conn, now, alpha, beta = rivals
    wd.resolve_raid(conn, alpha, 2, now, Rolls(0.99))
    beta = wd.refresh_player(conn, 2, now)
    alpha = wd.refresh_player(conn, 1, now)
    rows = _ANSI_RE.sub("", " ".join(wd.rival_entry_rows(_palette(), beta, alpha, now, 70)))
    assert "raid strike back" in rows and "crew a small crew" in rows and "Strike back until" in rows
    assert f"crew {alpha.crew}" not in rows                           # the size, never the number
    page = wd.read_player_page(conn, 2, now)
    cards = dict(wd.rivals_cards(_palette(), page, 2, 75, now))
    table = _ANSI_RE.sub("", " ".join(cards["RIVAL CREWS"]))
    assert "grudge" in table and "PROTECTION" not in cards
