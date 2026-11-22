"""
War dialing, rigs, line conditions and the rap sheet (world schema 12).

The door is named after a sweep it never let a caller run. These tests hold
the loop that fixes that to the rules the rest of the game already keeps: one
turn and one transaction an action, a preview that is refused once it is
stale, nothing spent by a rejection, and a season that takes everything
competitive with it while the rap sheet stays.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest

from .test_war_dialer_presentation import _ANSI_RE, _painted_world, _screen_text, _screen_titles, wd


class Rolls:
    """A stand-in for `random.Random` that returns the rolls it is given.

    `random()` hands out `values` in order and then repeats the last one;
    `randint` returns the low end and `choice` the first entry unless told
    otherwise, so a test names the one roll it is about.
    """

    def __init__(self, *values: float, pick: int = 0, high: bool = False):
        self.values = list(values) or [0.0]
        self.pick, self.high = pick, high

    def random(self) -> float:
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]

    def randint(self, low: int, high: int) -> int:
        return high if self.high else low

    def choice(self, seq):
        return seq[min(self.pick, len(seq) - 1)]

    def sample(self, population, count):
        return list(population)[:count]


@pytest.fixture(autouse=True)
def _module_state_restored(monkeypatch):
    """Layout and the wire are module state; every test leaves them as it found them."""
    monkeypatch.setattr(wd, "_MARGIN", 0)
    monkeypatch.setattr(wd, "_LINE_INDEX", 0)
    monkeypatch.setattr(wd, "_LINE_DAY", 0)


@pytest.fixture
def world(tmp_path):
    """A fresh world with one caller past the newcomer shield and cash to spend."""
    conn = wd.connect(tmp_path / "dial.db")
    wd.ensure_schema(conn)
    now = wd.now_utc()
    wd.get_or_create_season_anchor(conn, now)
    wd.ensure_exchanges_seeded(conn, 1, now)
    wd.load_or_create_player(conn, 1, "Zero", now, 1)
    conn.execute("UPDATE players SET cash=1000 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    yield conn, now, player
    conn.close()


def _lead(conn, user_id=1, *, system=0, difficulty=1, low=100, high=155, perk="", season=1,
          found=None, expires=None):
    found = found or wd.now_utc()
    expires = expires or found + wd.LEAD_LIFETIME
    lead_id = conn.execute(
        "INSERT INTO leads(user_id,season,system,number,difficulty,pay_low,pay_high,perk,found_at,"
        "expires_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user_id, season, system, "415-555-0142", difficulty, low, high, perk,
         wd.to_iso(found), wd.to_iso(expires))).lastrowid
    return wd._row_to_lead(conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())


# -- the sweep ---------------------------------------------------------------------

def test_a_sweep_spends_a_turn_adds_dial_heat_and_fills_the_black_book(world):
    conn, now, player = world
    delta = wd.ActionDelta()
    # 0.9: no second find, no rig find; the tier roll lands in the last weight.
    found, busted = wd.resolve_dial(conn, player, now, Rolls(0.9), delta=delta)
    assert not busted and len(found) == 1
    assert (delta.turns, delta.cash, delta.crew, delta.rank) == (1, 0, 0, 0)
    assert delta.heat == pytest.approx(wd.DIAL_HEAT)
    book = wd.read_leads(conn, 1, now)
    assert book == found
    lead = book[0]
    assert lead.number.startswith("212-555-01") and len(lead.number) == 12
    assert wd.from_iso(lead.expires_at) - wd.from_iso(lead.found_at) == wd.LEAD_LIFETIME


def test_a_sweep_always_finds_one_carrier_and_often_two(world):
    conn, now, player = world
    assert wd.sweep_count(player, Rolls(0.99)) == 1
    assert wd.sweep_count(player, Rolls(0.0)) == 2          # stock rig: no third
    player.rig = 3
    assert wd.sweep_count(player, Rolls(0.0)) == 3


def test_a_full_book_drops_its_oldest_number(world):
    conn, now, player = world
    old = [_lead(conn) for _ in range(wd.BOOK_LIMIT)]
    found, _ = wd.resolve_dial(conn, player, now, Rolls(0.0))
    book = wd.read_leads(conn, 1, now)
    assert len(found) == 2 and len(book) == wd.BOOK_LIMIT
    assert [lead.id for lead in book] == [lead.id for lead in old[2:]] + [lead.id for lead in found]


def test_carriers_go_cold_and_a_season_takes_the_book(world):
    conn, now, player = world
    fresh = _lead(conn)
    _lead(conn, expires=now + timedelta(hours=1))
    assert len(wd.read_leads(conn, 1, now)) == 2
    assert wd.read_leads(conn, 1, now + timedelta(hours=2)) == [fresh]
    wd.settle_world(conn, now + wd.SEASON)
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_difficulty_is_sized_on_living_crew_with_a_floor_per_tier(world):
    conn, now, player = world
    player.crew, player.posted = 2, 8      # ten living; posting them buys no soft numbers
    for tier, (_, share, floor, pay, _, _, _) in enumerate(wd.LEAD_TIERS):
        roll = (sum(wd.sweep_weights(0)[:tier]) + 0.5) / 100
        system, number, difficulty, low, high, perk = wd.roll_lead(player, Rolls(roll, 0.99), "415-555")
        assert wd.LEAD_SYSTEMS[system][1] == tier
        assert difficulty == max(floor, round(10 * share))
        assert low == int((45 + 11 * difficulty) * pay) and high == int(low * wd.LEAD_PAY_SPREAD)
        assert perk == ""
    player.crew, player.posted = 3, 0
    assert wd.roll_lead(player, Rolls(0.999, 0.99), "415-555")[2] == wd.LEAD_TIERS[3][2]


def test_a_better_rig_moves_the_sweep_toward_harder_carriers():
    for rig in range(len(wd.RIGS)):
        weights = wd.sweep_weights(rig)
        assert sum(weights) == 100 and min(weights) > 0
    assert wd.sweep_weights(5)[3] > wd.sweep_weights(0)[3]
    assert wd.sweep_weights(5)[0] < wd.sweep_weights(0)[0]


# -- hacking a carrier -------------------------------------------------------------

def test_a_cracked_carrier_pays_ranks_and_is_burned(world):
    conn, now, player = world
    lead = _lead(conn, system=5, difficulty=3)          # a warm system
    delta = wd.ActionDelta()
    success, payout, busted = wd.resolve_lead(conn, player, lead, now, Rolls(0.0), delta=delta)
    assert success and not busted and payout == 100
    assert (delta.cash, delta.rank, delta.turns, delta.crew) == (100, 30, 1, 0)
    assert delta.heat == pytest.approx(10)
    assert player.bonus_rank == 30 and wd.rank_score(player) == 30
    assert wd.read_leads(conn, 1, now) == []


def test_a_failed_carrier_costs_crew_by_tier_and_is_burned_too(world):
    conn, now, player = world
    soft, warm = _lead(conn, system=0), _lead(conn, system=5, difficulty=3)
    assert wd.resolve_lead(conn, player, soft, now, Rolls(0.99))[:2] == (False, 0)
    assert player.crew == wd.STARTING_CREW                  # a soft system costs nobody
    assert wd.resolve_lead(conn, player, warm, now, Rolls(0.99))[:2] == (False, 0)
    assert player.crew == wd.STARTING_CREW - 1 and player.bonus_rank == 0
    assert wd.read_leads(conn, 1, now) == []


@pytest.mark.parametrize("perk", ["crew", "cool", "kit", "jackpot"])
def test_each_perk_pays_out_only_on_success(world, perk):
    conn, now, player = world
    conn.execute("UPDATE players SET heat=30 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    lead = _lead(conn, system=5, difficulty=3, perk=perk)
    delta = wd.ActionDelta()
    success, payout, _ = wd.resolve_lead(conn, player, lead, now, Rolls(0.0), delta=delta)
    assert success
    if perk == "crew":
        assert delta.crew == 1 and delta.rank == 30 + 10
    elif perk == "cool":
        assert delta.heat == pytest.approx(-wd.LEAD_COOL_HEAT)
    elif perk == "kit":
        assert player.support == "burner" and payout == 100
    else:
        assert payout == 200 and delta.cash == 200


def test_a_codes_perk_pays_cash_when_the_slot_is_full_and_never_burns_itself(world):
    conn, now, player = world
    conn.execute("UPDATE players SET support='stash' WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    lead = _lead(conn, system=5, difficulty=3, perk="kit")
    success, payout, _ = wd.resolve_lead(conn, player, lead, now, Rolls(0.0))
    assert success and payout == 100 + wd.LEAD_KIT_CASH and player.support == "stash"


def test_a_cold_trail_does_not_spend_a_burner_kit(world):
    conn, now, player = world
    conn.execute("UPDATE players SET support='burner', heat=30 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    lead = _lead(conn, system=5, difficulty=3, perk="cool")
    wd.resolve_lead(conn, player, lead, now, Rolls(0.0))
    assert player.support == "burner" and player.heat == pytest.approx(20)


def test_a_cold_stale_or_foreign_number_is_refused_without_spending(world):
    conn, now, player = world
    expired = _lead(conn, expires=now - timedelta(minutes=1))
    foreign = _lead(conn, user_id=2)
    changed = _lead(conn)
    conn.execute("UPDATE leads SET difficulty=9 WHERE id=?", (changed.id,))
    before = wd.read_player(conn, 1)
    for lead in (expired, foreign, changed):
        with pytest.raises(wd.ActionRejected):
            wd.resolve_lead(conn, player, lead, now, Rolls(0.0))
    after = wd.read_player(conn, 1)
    assert (after.cash, after.turns_used, after.heat) == (before.cash, before.turns_used, before.heat)


def test_carrier_rank_counts_in_the_standings_sql(world):
    conn, now, player = world
    wd.resolve_lead(conn, player, _lead(conn, system=15, difficulty=1), now, Rolls(0.0))
    assert wd.rank_score(player) == 70
    stored = conn.execute(f"SELECT {wd._RANK_SQL} FROM players WHERE user_id=1").fetchone()[0]
    assert stored == 70
    page = wd.read_player_page(conn, 1, now, standings=True)
    assert page.position == 1 and wd.rank_score(page.entries[0]) == 70


# -- the rig -----------------------------------------------------------------------

def test_a_rig_costs_cash_and_a_turn_and_is_worth_rank(world):
    conn, now, player = world
    delta = wd.ActionDelta()
    wd.resolve_crew_purchase(conn, player, now, wd.CrewChoice("rig"), delta=delta)
    name, price, rank = wd.RIGS[1]
    assert player.rig == 1 and wd.rig_name(player) == name
    assert (delta.cash, delta.rank, delta.turns) == (-price, rank, 1)
    assert wd.crew_item(wd.CrewChoice("rig"), player)[1].startswith(wd.RIGS[2][0])


def test_the_top_rig_and_an_unaffordable_one_are_refused(world):
    conn, now, player = world
    conn.execute("UPDATE players SET rig=?, cash=100 WHERE user_id=1", (len(wd.RIGS) - 1,))
    player = wd.refresh_player(conn, 1, now)
    assert "top rig" in wd.crew_block_reason(player, wd.CrewChoice("rig"))
    conn.execute("UPDATE players SET rig=0 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    assert "Need $150 more" in wd.crew_block_reason(player, wd.CrewChoice("rig"))
    with pytest.raises(wd.ActionRejected):
        wd.resolve_crew_purchase(conn, player, now, wd.CrewChoice("rig"))
    assert wd.read_player(conn, 1).turns_used == 0


def test_a_season_takes_the_rig_and_its_rank(world):
    conn, now, player = world
    wd.resolve_crew_purchase(conn, player, now, wd.CrewChoice("rig"))
    later = now + wd.SEASON
    wd.settle_world(conn, later)
    fresh = wd.read_player(conn, 1)
    assert (fresh.rig, fresh.bonus_rank, wd.rank_score(fresh)) == (0, 0, 0)
    assert conn.execute("SELECT rank FROM season_results WHERE user_id=1").fetchone()[0] == wd.RIGS[1][2]


# -- recruiting --------------------------------------------------------------------

def test_recruits_cost_more_for_each_living_member_past_the_flat_crew(world):
    conn, now, player = world
    assert wd.recruit_cost(player) == wd.RECRUIT_COST
    player.crew = wd.RECRUIT_FLAT_CREW
    assert wd.recruit_cost(player) == wd.RECRUIT_COST
    player.crew, player.posted = 4, 6
    assert wd.recruit_cost(player) == wd.RECRUIT_COST + wd.RECRUIT_STEP * 5
    carrier = next(e for e in wd.list_exchanges(conn) if e.role == "carrier")
    assert wd.service_cost(carrier, player) == wd.recruit_cost(player) - 10


def test_posted_crew_is_read_with_the_row_and_never_stored(world):
    conn, now, player = world
    conn.execute("UPDATE exchanges SET controller_user_id=1, garrison=7 WHERE id=1")
    assert wd.read_player(conn, 1).posted == 7
    assert "posted" not in {row["name"] for row in conn.execute("PRAGMA table_info(players)")}
    with pytest.raises(wd.ActionRejected, match=r"need \$125"):
        conn.execute("UPDATE players SET cash=100 WHERE user_id=1")
        wd.resolve_recruit(conn, wd.refresh_player(conn, 1, now), now)


# -- line conditions ---------------------------------------------------------------

@pytest.fixture
def lines(monkeypatch):
    monkeypatch.delenv("DOOR_LINES", raising=False)
    yield
    wd._LINE_INDEX = wd._LINE_DAY = 0


def test_the_wire_is_clear_on_day_one_and_never_repeats_a_day(lines):
    world = "0123456789abcdef0123456789abcdef"
    assert wd._line_pick(world, 1, 0) == 0
    picks = [wd._line_pick(world, 1, day) for day in range(1, 28)]
    assert all(1 <= pick < len(wd.LINE_CONDITIONS) for pick in picks)
    assert all(a != b for a, b in zip(picks, picks[1:]))
    assert len(set(picks)) >= 5
    assert picks == [wd._line_pick(world, 1, day) for day in range(1, 28)]
    # Another season, and another board, each get their own calendar.
    assert picks != [wd._line_pick(world, 2, day) for day in range(1, 28)]
    assert picks != [wd._line_pick("f" * 32, 1, day) for day in range(1, 28)]


def test_every_condition_is_a_bonus_or_a_trade_and_fits_the_switchboard():
    keys = [key for key, _, _, _ in wd.LINE_CONDITIONS]
    assert len(set(keys)) == len(keys) and wd.LINE_CONDITIONS[0][3] == {}
    known = {"trade", "pay", "heat", "capture", "recruit", "finds", "rank"}
    for key, name, blurb, effects in wd.LINE_CONDITIONS:
        assert set(effects) <= known
        # A badge, a gap and the sentence on one row of an eighty-column frame.
        assert len(name) + 2 + 3 + len(blurb) <= 75, key
        if effects.get("heat", 0) > 0:
            assert effects.get("pay", 0) > 0     # more Heat is always paid for


def _set_line(key):
    wd._LINE_INDEX = next(i for i, entry in enumerate(wd.LINE_CONDITIONS) if entry[0] == key)


def test_conditions_change_exactly_the_rules_they_name(world, lines):
    conn, now, player = world
    hub = next(e for e in wd.list_exchanges(conn) if e.role == "hub")
    plain = (wd.trade_payout_range(player), wd.job_terms(wd.JobChoice(0, 1))[2],
             wd.adjusted_heat(player, "job", 15), wd.capture_cost(hub), wd.recruit_cost(player),
             wd.sweep_count(player, Rolls(0.99)))
    _set_line("rush")
    assert wd.trade_payout_range(player) == (plain[0][0] + 15, plain[0][1] + 15)
    _set_line("board")
    assert wd.job_terms(wd.JobChoice(0, 1))[2] == (plain[1][0] * 125 // 100, plain[1][1] * 125 // 100)
    _set_line("noise")
    assert wd.adjusted_heat(player, "job", 15) == 13 and wd.adjusted_heat(player, "trade", 1) == 0
    assert wd.adjusted_heat(player, "service", -15) == -15       # only gains are touched
    _set_line("sweep")
    assert wd.adjusted_heat(player, "job", 15) == 18
    assert wd.job_terms(wd.JobChoice(0, 1))[2][1] == plain[1][1] * 150 // 100
    _set_line("trunks")
    assert wd.capture_cost(hub) == plain[3] - 15
    _set_line("blood")
    assert wd.recruit_cost(player) == plain[4] - 20
    _set_line("busy")
    assert wd.sweep_count(player, Rolls(0.99)) == plain[5] + 1
    _set_line("meet")
    lead = _lead(conn, system=5, difficulty=3)
    assert wd.lead_terms(lead)[4] == 35
    wd.action_job(player, Rolls(0.0), wd.JobChoice(0, 0))
    assert player.bonus_rank == 5


def test_the_switch_pins_a_clear_wire(world, monkeypatch):
    conn, now, player = world
    monkeypatch.delenv("DOOR_LINES", raising=False)
    wd.settle_world(conn, now + 5 * wd.DAY)
    assert wd._LINE_INDEX != 0 and wd._LINE_DAY == 105
    monkeypatch.setenv("DOOR_LINES", "0")
    wd.settle_world(conn, now + 5 * wd.DAY)
    assert (wd._LINE_INDEX, wd._LINE_DAY) == (0, 0)


def test_a_preview_from_yesterdays_wire_is_stale(world, lines):
    conn, now, player = world
    day = now + 3 * wd.DAY + timedelta(hours=1)
    snapshot = wd.refresh_player(conn, 1, day)
    assert snapshot.line_day == 103
    with pytest.raises(wd.ActionRejected, match="changed during the preview"):
        wd.resolve_trade_warez(conn, snapshot, day + wd.DAY, Rolls(0.0), require_preview=True)
    assert wd.read_player(conn, 1).turns_used == 0
    snapshot = wd.refresh_player(conn, 1, day + wd.DAY)
    wd.resolve_trade_warez(conn, snapshot, day + wd.DAY, Rolls(0.0), require_preview=True)


# -- the rap sheet -----------------------------------------------------------------

def test_the_rap_sheet_counts_deeds_and_awards_each_badge_once(world):
    conn, now, player = world
    delta = wd.ActionDelta()
    wd.resolve_dial(conn, player, now, Rolls(0.9), delta=delta)
    assert delta.badges == []
    lead = _lead(conn, system=15, difficulty=1, perk="jackpot")       # ice, jackpot
    wd.resolve_lead(conn, player, lead, now, Rolls(0.0), delta=delta)
    assert set(delta.badges) == {"carrier", "ice", "till"}
    wd.resolve_lead(conn, player, _lead(conn), now, Rolls(0.0), delta=delta)
    assert delta.badges == []
    career = wd.read_career(conn, 1)
    assert career["stats"]["sweeps"] == 1 and career["stats"]["carriers"] == 2
    assert career["stats"]["best_rank"] == wd.rank_score(player)
    assert set(career["badges"]) == {"carrier", "ice", "till"}
    # Announced on the result that earned them; the feed keeps the turn's own line.
    assert not any(event.summary_text.startswith("Badge earned") for event in wd.history_events(conn, 1))


def test_a_medal_earned_while_away_leaves_a_read_receipt(world):
    conn, now, player = world
    wd.resolve_lead(conn, player, _lead(conn), now, Rolls(0.0))
    wd.settle_world(conn, now + wd.SEASON)
    receipts = [event for event in wd.history_events(conn, 1) if event.summary_text.startswith("Badge earned")]
    assert [event.summary_text for event in receipts] == ["Badge earned: PODIUM. [I] Scene shows your rap sheet."]
    assert receipts[0].seen_at is not None and receipts[0].actor_handle is None


def test_the_generic_counters_feed_the_sheet_and_a_bust_is_counted(world):
    conn, now, player = world
    wd.resolve_recruit(conn, player, now)
    wd.resolve_job(conn, player, now, Rolls(0.0), choice=wd.JobChoice(0, 0))
    wd.resolve_root_exchange(conn, player, 1, now, Rolls(0.0))
    conn.execute("UPDATE players SET heat=100 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    _, busted = wd.resolve_trade_warez(conn, player, now, Rolls(0.0))
    assert busted
    stats = wd.read_career(conn, 1)["stats"]
    assert (stats["recruits"], stats["contracts"], stats["captures"], stats["busts"]) == (1, 1, 1, 1)
    assert stats["most_held"] == 1 and stats["most_crew"] >= 3
    assert {"root", "busted"} <= set(wd.read_career(conn, 1)["badges"])
    # The rules' own tally is read once and never rides on the snapshot.
    assert "deeds" not in player.__dict__
    assert (stats["turns"], stats["trades"], stats["contract_tries"], stats["root_tries"]) == (4, 1, 1, 1)


def test_a_rejected_action_leaves_no_trace_on_the_sheet(world):
    conn, now, player = world
    conn.execute("UPDATE players SET turns_used=? , turn_day_start=? WHERE user_id=1",
                 (wd.TURNS_PER_DAY, wd.to_iso(now)))
    player = wd.refresh_player(conn, 1, now)
    with pytest.raises(wd.ActionRejected):
        wd.resolve_dial(conn, player, now, Rolls(0.0))
    assert wd.read_career(conn, 1) == {"stats": {}, "badges": {}}
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_the_sheet_survives_a_season_and_records_its_finish(world):
    conn, now, player = world
    wd.resolve_lead(conn, player, _lead(conn), now, Rolls(0.0))
    wd.settle_world(conn, now + wd.SEASON)
    career = wd.read_career(conn, 1)
    assert career["stats"]["seasons"] == 1 and career["stats"]["medals"] == 1
    assert career["stats"]["carriers"] == 1 and career["stats"]["best_rank"] == 20
    assert {"carrier", "podium"} <= set(career["badges"])


def test_unreadable_sheet_data_reads_as_an_empty_sheet(world):
    conn, now, player = world
    conn.execute("INSERT INTO career(user_id,data) VALUES (1,'not json')")
    assert wd.read_career(conn, 1) == {"stats": {}, "badges": {}}
    conn.execute("UPDATE career SET data='{\"stats\": {\"busts\": -4, \"raids\": \"x\"}, \"badges\": {}}'")
    assert wd.read_career(conn, 1)["stats"] == {}
    wd.resolve_dial(conn, player, now, Rolls(0.9))
    assert wd.read_career(conn, 1)["stats"]["sweeps"] == 1


def test_every_badge_reads_a_stat_the_sheet_keeps():
    counted = ({key for key, _ in wd.CAREER_COUNTS} | wd.CAREER_PEAKS | set(wd.CAREER_TRIES)
               | {"ice", "jackpots", "deep_dives"})
    keys = [key for key, *_ in wd.BADGES]
    assert len(set(keys)) == len(keys)
    for key, name, how, stat, need in wd.BADGES:
        assert stat in counted and need >= 1, key
        assert name == name.upper() and how.endswith(".")


# -- schema 12 ---------------------------------------------------------------------

def _drop_to_schema_11(conn):
    """Undo schemas 13 and 12, leaving the world as v1.5.1 wrote it."""
    for column in ("operation_lead", "line_banked", "line_depth", "line_rank"):
        conn.execute(f"ALTER TABLE players DROP COLUMN {column}")
    conn.execute("DROP TABLE career")
    conn.execute("DROP TABLE leads")
    conn.execute("ALTER TABLE players DROP COLUMN bonus_rank")
    conn.execute("ALTER TABLE players DROP COLUMN rig")
    conn.execute("PRAGMA user_version=11")


def test_the_carrier_schema_upgrade_is_atomic_idempotent_and_starts_empty(world):
    conn, now, player = world
    wd.resolve_trade_warez(conn, player, now, Rolls(0.0))
    _drop_to_schema_11(conn)
    before = list(conn.iterdump())

    def deny_version(action, name, value, *args):
        return (sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_PRAGMA and name == "user_version"
                and value == "12" else sqlite3.SQLITE_OK)

    conn.set_authorizer(deny_version)
    with pytest.raises(sqlite3.DatabaseError):
        wd.ensure_schema(conn)
    conn.set_authorizer(None)
    assert list(conn.iterdump()) == before
    wd.ensure_schema(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == wd.WORLD_SCHEMA_VERSION
    upgraded = wd.read_player(conn, 1)
    assert (upgraded.rig, upgraded.bonus_rank, upgraded.cash) == (0, 0, player.cash)
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM career").fetchone()[0] == 0
    before = list(conn.iterdump())
    wd.ensure_schema(conn)
    assert list(conn.iterdump()) == before


def test_an_older_world_settles_and_archives_without_the_new_columns(world):
    """The SysOp's commands settle a world they do not upgrade."""
    conn, now, player = world
    conn.execute("UPDATE players SET crew_recruited_total=3 WHERE user_id=1")
    _drop_to_schema_11(conn)
    wd.settle_world(conn, now + wd.SEASON)
    assert conn.execute("SELECT rank FROM season_results WHERE user_id=1").fetchone()[0] == 30
    assert wd.read_leads(conn, 1, now + wd.SEASON) == []
    assert wd.read_career(conn, 1) == {"stats": {}, "badges": {}}


# -- the screens -------------------------------------------------------------------

def _palette(depth="truecolor"):
    return wd.Palette(truecolor=depth == "truecolor", color_depth=depth)


def _titles(written) -> str:
    """Every screen's titles: a screen opens on its own clear, not on a new row,
    so the rows are read one screen at a time."""
    return " | ".join(_screen_titles(screen) for screen in "".join(written).split("[2J[H"))


def _play(monkeypatch, keys, width=80):
    """Run a screen against scripted keys; return everything it wrote."""
    written: list[str] = []
    wanted = list(keys)
    monkeypatch.setattr(wd, "out", written.append)
    monkeypatch.setattr(wd, "_OUTPUT_WIDTH", width)
    monkeypatch.setattr(wd, "read_input_key", lambda: " ")
    monkeypatch.setattr(wd, "read_menu_choice",
                        lambda valid, **_: wanted.pop(0) if wanted else "B")
    return written


@pytest.mark.parametrize("width,height", [(80, 24), (64, 20), (40, 12), (132, 40)])
def test_the_dial_screen_fits_and_offers_the_sweep_and_each_number(tmp_path, monkeypatch, width, height):
    conn, now = _painted_world(tmp_path, f"book{width}.db")
    player = wd.refresh_player(conn, 1, now)
    _lead(conn, system=5, difficulty=3, perk="crew")
    _lead(conn, system=15, difficulty=16, perk="jackpot")
    written = _play(monkeypatch, ["B"], width)
    wd.do_dial(_palette(), conn, player, Rolls(0.0), wd.apply_layout(width), height)
    rows = _ANSI_RE.sub("", "".join(written)).split("\r\n")
    assert all(wd._dlen(row) <= width for row in rows)
    text, titles = _screen_text(written), _screen_titles(written)
    assert "WAR DIALER" in titles
    assert "415-555-0142" in text and "[S]" in text
    if width >= 64:
        assert "BLACK BOOK" in titles and "RECRUIT" in text
    conn.close()


def test_an_empty_book_says_how_to_fill_it(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    written = _play(monkeypatch, ["B"])
    wd.do_dial(_palette(), conn, player, Rolls(0.0), 79, 24)
    text = _screen_text(written)
    assert "No numbers yet" in text and "[S] Sweep" in text
    conn.close()


def test_a_sweep_from_the_dial_screen_previews_commits_and_lists_its_finds(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    written = _play(monkeypatch, ["S", "A", "B"])
    wd.do_dial(_palette(), conn, player, Rolls(0.0), 79, 24)
    text, titles = _screen_text(written), _titles(written)
    assert "SWEEP PREVIEW" in titles and "ACTION RESULT" in titles and "CARRIERS" in titles
    assert "2 carriers answered" in text
    assert len(wd.read_leads(conn, 1, now)) == 2 and wd.read_player(conn, 1).turns_used == 8
    conn.close()


def test_backing_out_of_a_carrier_preview_spends_nothing(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    _lead(conn, system=5, difficulty=3)
    written = _play(monkeypatch, ["1", "B", "B"])
    wd.do_dial(_palette(), conn, player, Rolls(0.0), 79, 24)
    assert "CARRIER PREVIEW" in _titles(written)
    assert "One attempt: win or lose, the number is burned." in _screen_text(written)
    assert len(wd.read_leads(conn, 1, now)) == 1 and wd.read_player(conn, 1).turns_used == 7
    conn.close()


def test_a_hack_from_the_dial_screen_announces_a_badge(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    _lead(conn, system=5, difficulty=1)
    written = _play(monkeypatch, ["1", "A", "B"])
    wd.do_dial(_palette(), conn, player, Rolls(0.0), 79, 24)
    text, titles = _screen_text(written), _titles(written)
    assert "You're in. Gross payout $100." in text
    assert "BADGE EARNED" in titles and "CARRIER DETECT" in text
    assert wd.read_leads(conn, 1, now) == []
    conn.close()


def test_the_switchboard_leads_with_today_and_one_next_move(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    monkeypatch.delenv("DOOR_LINES", raising=False)
    state = wd.dashboard_state(conn, 1, now)
    written = _play(monkeypatch, [])
    _, pages = wd.draw_dashboard(_palette(), state, now, 79, 24)
    text, titles = _screen_text(written), _screen_titles(written)
    assert "TODAY" in titles and "wire changes in" in titles
    assert "CLEAR LINES" in text and "RIG 300 baud" in text and "BOOK 0/6" in text
    assert "[D] Dial" in text
    # The standing rules are Help's to state, not every visit's.
    assert "Gold / Silver / Bronze" not in text
    wd._LINE_INDEX = wd._LINE_DAY = 0
    conn.close()


def test_the_next_move_names_what_the_caller_is_out_of_first(tmp_path):
    conn, now = _painted_world(tmp_path)
    state = wd.dashboard_state(conn, 1, now)
    assert "Close to the bust line" in wd.next_move(state, now)      # the painted world sits at 72
    state.player.heat = 10
    assert "black book is empty" in wd.next_move(state, now)
    state.book = 2
    assert "2 carriers in your black book" in wd.next_move(state, now)
    state.player.crew = 1
    assert "One crew member left" in wd.next_move(state, now)
    state.player.heat = 84
    assert "The line is hot" in wd.next_move(state, now)
    state.player.turns_used = wd.TURNS_PER_DAY
    assert "Out of turns" in wd.next_move(state, now)
    conn.close()


def test_the_kit_board_sells_the_next_rig(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    written = _play(monkeypatch, ["6", "A"])
    assert wd.do_crew(_palette(), conn, player, 79, 24) is True
    text = _screen_text(written)
    assert "1200 baud modem" in text and "1200 baud modem installed." in text
    assert wd.read_player(conn, 1).rig == 1
    conn.close()


@pytest.mark.parametrize("width,height", [(80, 24), (40, 12), (132, 40)])
def test_the_sweep_scene_stays_inside_its_terminal(width, height):
    finds = [("415-555-0142", "University VAX in the physics lab", 1),
             ("415-555-0177", "Central office switch console", 3)]
    frames = wd.dial_scene_frames(_palette(), width, height, seed=7, prefix="415-555",
                                  rig="2400 baud", finds=finds,
                                  caption="2 carriers answered. In your black book now.")
    assert len(frames) > wd.SCENE_HOLD_FRAMES
    for frame in frames:
        for row, column, segments in frame:
            assert 1 <= row <= height
            assert column + sum(wd._dlen(text) for _, text in segments) - 1 <= width
    drawn = "".join(text for frame in frames for _, _, segments in frame for _, text in segments)
    assert "CARRIER" in drawn and "415-555-0142" in drawn


# -- the rest of the overhaul's screens ---------------------------------------------

def test_a_result_offers_again_only_on_its_last_page(monkeypatch):
    keys = iter(["A", "A"])
    written: list[str] = []
    monkeypatch.setattr(wd, "out", written.append)
    monkeypatch.setattr(wd, "read_input_key", lambda: next(keys))
    cards = [("", [f"row {n}" for n in range(14)])]
    # Two pages at twelve rows: the first A only turns the page.
    assert wd.show_text_pages(_palette(), "ACTION RESULT", [], 79, 12, cards=cards,
                              onboarding=True, again=True) == "A"
    text = _ANSI_RE.sub("", "".join(written))
    assert text.count("[A] Again") == 1 and "Press any key to continue..." in text
    # Without `again`, A is any key: it continues and asks for nothing.
    monkeypatch.setattr(wd, "read_input_key", lambda: "A")
    assert wd.show_text_pages(_palette(), "ACTION RESULT", [], 79, 24, cards=cards[:1],
                              onboarding=True) == "B"


def test_again_reruns_a_contract_from_its_preview(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    previews = []

    def pages(p, title, paragraphs, width, height, **kwargs):
        if kwargs.get("again"):
            return "A" if len(previews) < 3 else "B"    # ask for two repeats
        previews.append(title)
        return "A"

    picks = iter(["1", "1"])
    monkeypatch.setattr(wd, "show_text_pages", pages)
    monkeypatch.setattr(wd, "pick_record_page", lambda *a, **k: next(picks))
    monkeypatch.setattr(wd, "out", lambda text: None)
    assert wd.do_job(_palette(), conn, player, now, Rolls(0.0), 79, 24) is True
    assert previews == ["JOB PREVIEW"] * 3            # picked once, previewed every time
    assert wd.read_player(conn, 1).turns_used == 7 + 3
    conn.close()


def test_a_carrier_preview_shows_the_line_it_picks_up(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    conn.execute("UPDATE players SET rig=4 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    lead = _lead(conn, system=6, difficulty=3)
    written = _play(monkeypatch, ["B"])
    assert wd.confirm_action(_palette(), conn, player, "carrier", 79, 24, lead) is False
    text, titles = _screen_text(written), _titles(written)
    assert "THE LINE" in titles and "STAKES" in titles and "TERMS" in titles
    assert "ATDT 415-555-0142" in text and "CONNECT 14400" in text and "Username:" in text
    # The head card and the gauges say the cost and the Heat; the terms do not repeat them.
    assert "Back spends nothing" not in text and "Heat decays while you wait" not in text
    fast = _palette()
    fast.fast = True
    written = _play(monkeypatch, ["B"])
    wd.confirm_action(fast, conn, player, "carrier", 79, 24, lead)
    assert "ATDT" not in _screen_text(written)
    conn.close()


@pytest.mark.parametrize("width,height,crowned", [(132, 40, True), (80, 24, False), (132, 26, False)])
def test_a_tall_console_wears_the_masthead_on_its_switchboard(tmp_path, monkeypatch, width, height, crowned):
    conn, now = _painted_world(tmp_path)
    state = wd.dashboard_state(conn, 1, now)
    written = _play(monkeypatch, [], width)
    _, pages = wd.draw_dashboard(_palette(), state, now, wd.apply_layout(width), height)
    rows = _ANSI_RE.sub("", "".join(written)).split("\r\n")
    assert len(rows) <= height and all(wd._dlen(row) <= width for row in rows)
    assert (wd.SPLASH_TAGLINE in _screen_text(written)) is crowned
    if crowned:
        assert pages == 1
    conn.close()


def test_the_sign_off_says_what_tonight_was_worth(tmp_path, monkeypatch):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    conn.execute("UPDATE players SET turn_day_start=? WHERE user_id=1", (wd.to_iso(now),))
    player = wd.refresh_player(conn, 1, now)
    written = _play(monkeypatch, [])
    wd.draw_goodbye(_palette(), player, 79, session=(wd.rank_score(player) - 45, player.cash + 120))
    text = _screen_text(written)
    assert "tonight Rank +45" in text and "-$120" in text and "turns left 8" in text
    assert "fresh turns in" in text
    written.clear()
    wd.draw_goodbye(_palette(), player, 79)
    assert "tonight" not in _screen_text(written)
    conn.close()


def test_the_rap_sheet_lists_every_badge_earned_or_not(tmp_path):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    career = {"stats": {"carriers": 3, "best_rank": 1500, "best_rig": 2}, "badges": {"carrier": "2026-11-22"}}
    cards = wd.rap_sheet_cards(_palette(), career, player, 75)
    assert [title for title, _ in cards] == ["", "RECORD", "HIGH-WATER MARKS", "BADGES"]
    text = _ANSI_RE.sub("", "\n".join(row for _, rows in cards for row in rows))
    assert f"badges 1/{len(wd.BADGES)}" in text and "carriers cracked 3" in text
    assert "best season rank 1,500" in text and "ELITE" in text and "2400 baud" in text
    for _, name, how, _, _ in wd.BADGES:
        assert name in text and how in text
    assert "2026-11-22" in text
    assert all(wd._dlen(row) <= 75 for _, rows in cards for row in rows)
    conn.close()


def test_the_modem_lamps_are_a_reading_not_a_decoration():
    plain = _ANSI_RE.sub("", wd.modem_leds(_palette(), {"MR", "TR", "CD"}))
    assert plain == "HS○ AA○ CD● OH○ RD○ SD○ TR● MR●"


def test_a_results_closing_line_belongs_to_its_turn(tmp_path):
    conn, now = _painted_world(tmp_path)
    player = wd.refresh_player(conn, 1, now)
    quiet, ranked = wd.ActionDelta(), wd.ActionDelta(rank=15)
    assert wd.result_flavour(None, quiet, True) == "Sirens cut through the carrier tone."
    assert wd.result_flavour(player, quiet, False) in wd.RESULT_FLAVOUR["quiet"]
    assert wd.result_flavour(player, ranked, False) in wd.RESULT_FLAVOUR["rank"]
    assert wd.result_flavour(player, quiet, False) == wd.result_flavour(player, quiet, False)
    conn.close()


# -- operators push back -----------------------------------------------------------

HARBOR = 6      # Night Relay Union's Carrier Switch: crew of 4, +2 security when held


def _hold_home(conn, now, garrison, *, exchange=HARBOR, clock=None):
    """Hand the caller an operator's home with `garrison` posted."""
    conn.execute("UPDATE exchanges SET controller_user_id=1, npc_key='', garrison=?, controlled_since=?, "
                 "income_collected_at=?, npc_return_at=? WHERE id=?",
                 (garrison, wd.to_iso(now), wd.to_iso(now),
                  wd.to_iso(clock) if clock else "", exchange))


def _expected_retake(exchange_id, deadline, crew, defence):
    roll = wd.random.Random(wd.zlib.crc32(f"{exchange_id}/{wd.to_iso(deadline)}".encode("ascii"))).random()
    return roll < wd.success_chance(crew, defence)


def _first_deadline(now, *, retake):
    """A deadline whose roll comes out the way a test needs it to."""
    return next(now + wd.NPC_PUSHBACK_GRACE + timedelta(hours=step) for step in range(200)
                if _expected_retake(HARBOR, now + wd.NPC_PUSHBACK_GRACE + timedelta(hours=step), 4, 3) is retake)


def test_capturing_an_operators_home_starts_its_clock(world):
    conn, now, player = world
    conn.execute("UPDATE players SET crew=40 WHERE user_id=1")
    player = wd.refresh_player(conn, 1, now)
    success, _, _ = wd.resolve_root_exchange(conn, player, HARBOR, now, Rolls(0.0))
    assert success
    home = next(e for e in wd.list_exchanges(conn) if e.id == HARBOR)
    assert wd.from_iso(home.npc_return_at) == wd.from_iso(home.controlled_since) + wd.NPC_PUSHBACK_GRACE
    assert wd.home_threat(home) == ("Night Relay Union", 4, 1)       # one defender + 2 security
    wd.resolve_root_exchange(conn, player, 1, now, Rolls(0.0))
    plain = next(e for e in wd.list_exchanges(conn) if e.id == 1)
    assert plain.npc_return_at == "" and wd.home_threat(plain) is None


def test_a_defence_that_matches_the_crew_is_never_tested(world):
    conn, now, player = world
    _hold_home(conn, now, 2, clock=now + wd.NPC_PUSHBACK_GRACE)      # 2 posted + 2 security = 4
    for day in range(3, 12):
        wd.settle_world(conn, now + day * wd.DAY)
    home = next(e for e in wd.list_exchanges(conn) if e.id == HARBOR)
    assert home.controller_user_id == 1 and home.garrison == 2
    assert wd.history_events(conn, 1) == []
    assert wd.from_iso(home.npc_return_at) > now + 11 * wd.DAY


def test_a_weak_defence_is_tested_once_per_deadline_however_long_the_world_sat(world):
    conn, now, player = world
    deadline = _first_deadline(now, retake=False)
    _hold_home(conn, now, 1, clock=deadline)                          # defence 3 against a crew of 4
    wd.settle_world(conn, deadline - timedelta(minutes=1))
    assert wd.history_events(conn, 1) == []                           # still inside the grace
    # Ten days unvisited is one test, not ten.
    later = deadline + 10 * wd.DAY
    wd.settle_world(conn, later)
    wd.settle_world(conn, later + timedelta(minutes=5))
    events = wd.history_events(conn, 1)
    home = next(e for e in wd.list_exchanges(conn) if e.id == HARBOR)
    assert len(events) == 1 and events[0].actor_handle == "Night Relay Union" and events[0].seen_at is None
    assert "your garrison held" in events[0].summary_text and "Post 1 more defence" in events[0].summary_text
    assert home.controller_user_id == 1
    assert wd.from_iso(home.npc_return_at) == later + wd.NPC_PUSHBACK_EVERY


def test_a_retake_pays_the_owner_sends_the_defenders_home_and_restations_the_operator(world):
    conn, now, player = world
    deadline = _first_deadline(now, retake=True)
    _hold_home(conn, now, 1, clock=deadline)
    before = wd.read_player(conn, 1)
    at = deadline + timedelta(hours=6)
    wd.settle_world(conn, at)
    after = wd.read_player(conn, 1)
    home = next(e for e in wd.list_exchanges(conn) if e.id == HARBOR)
    assert home.controller_user_id is None and home.npc_key == "relay" and home.garrison == 4
    assert after.crew == before.crew + 1                               # the defender came home
    hours = (at - now) // timedelta(hours=1)
    assert after.cash - before.cash == home.income_per_hour * hours    # paid up to the retake
    events = wd.history_events(conn, 1)
    assert len(events) == 1 and "Night Relay Union retook" in events[0].summary_text
    assert events[0].actor_handle == "Night Relay Union" and events[0].seen_at is None
    assert "NPC: Night Relay Union retook" in wd.read_scene(conn)[0]["summary"]
    # Nothing more is earned or tested once it is theirs again.
    wd.settle_world(conn, at + 3 * wd.DAY)
    assert wd.read_player(conn, 1).cash == after.cash and len(wd.history_events(conn, 1)) == 1


def test_a_home_held_since_before_the_rule_starts_its_grace_untested(world):
    conn, now, player = world
    _hold_home(conn, now, 1)                                           # no clock: an older world
    wd.settle_world(conn, now + 10 * wd.DAY)
    home = next(e for e in wd.list_exchanges(conn) if e.id == HARBOR)
    assert home.controller_user_id == 1
    assert wd.from_iso(home.npc_return_at) == now + 10 * wd.DAY + wd.NPC_PUSHBACK_GRACE
    assert wd.history_events(conn, 1) == []


def test_the_switchboard_names_a_home_that_is_short(world):
    conn, now, player = world
    _hold_home(conn, now, 1, clock=now + wd.NPC_PUSHBACK_GRACE)
    state = wd.dashboard_state(conn, 1, now)
    move = wd.next_move(state, now)
    assert "Harbor is 1 defence short" in move and "Night Relay Union" in move and "[G] Garrison" in move
    rows = _ANSI_RE.sub("", " ".join(wd.garrison_entry_rows(_palette(), state.holdings[0], state.player, 70)))
    assert "1 defence short of Night Relay Union's crew of 4" in rows


def test_an_orphaned_home_is_retaken_without_a_player_to_credit(world):
    conn, now, player = world
    deadline = _first_deadline(now, retake=True)
    _hold_home(conn, now, 1, clock=deadline)
    conn.execute("UPDATE exchanges SET controller_user_id=99 WHERE id=?", (HARBOR,))
    wd.settle_world(conn, deadline + timedelta(hours=1))
    home = next(e for e in wd.list_exchanges(conn) if e.id == HARBOR)
    assert home.controller_user_id is None and home.npc_key == "relay"
    assert "from a departed crew" in wd.read_scene(conn)[0]["summary"]
