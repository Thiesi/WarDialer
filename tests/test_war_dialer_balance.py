"""Validate that balance probes exercise real play without changing it to measure it."""
import importlib.util
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "war_dialer_balance.py"
spec = importlib.util.spec_from_file_location("war_dialer_balance", SCRIPT)
balance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(balance)


@pytest.mark.parametrize("name", balance.SCENARIOS)
def test_scenarios_reproduce_and_respect_daily_allowance(name):
    result = balance.run_scenario(name, days=4)
    assert result == balance.run_scenario(name, days=4)
    for day in result["daily"]:
        for player in day["players"].values():
            assert player["turns_spent"] <= (day["day"] + 1) * balance.wd.TURNS_PER_DAY
    assert sum(a.get("turns", 0) for a in result["actions"].values()) > 0


def test_late_arrivals_and_absent_victim_are_real_absences():
    late = balance.run_scenario("late_arrivals", days=4)
    assert all(set(day["players"]) == {"1"} for day in late["daily"][:3])
    assert set(late["daily"][3]["players"]) == {"1", "2", "3"}
    victim = balance.run_scenario("repeated_victim", days=4)
    assert victim["actions"]["3"] == {}
    assert victim["daily"][-1]["players"]["3"]["turns_spent"] == 0
    assert sum(victim["actions"][uid].get("raid", 0) for uid in ("1", "2")) == 4
    assert victim["rejections"]  # Alternating attackers cannot bypass the shield.


def test_income_comparison_changes_cadence_without_changing_actions_or_pay():
    burst = balance.run_scenario("income_burst", days=4)
    spaced = balance.run_scenario("income_spaced", days=4)
    assert burst["actions"] == spaced["actions"]
    assert burst["daily"] == spaced["daily"]


def test_recovery_probe_reports_an_actual_bust_and_return_to_starting_crew():
    result = balance.run_scenario("bust_recovery", days=4)
    assert result["fixture"]["busted"] is True
    assert result["fixture"]["after"]["crew"] == 1
    assert 1 <= result["recovery_turns_after_bust"] <= 4 * balance.wd.TURNS_PER_DAY


def test_observation_does_not_collect_income_or_reset_protection_in_live_world(tmp_path):
    wd = balance.wd
    conn = wd.connect(tmp_path / "world.db")
    try:
        wd.ensure_schema(conn)
        wd.get_or_create_season_anchor(conn, balance.START)
        wd.ensure_exchanges_seeded(conn, 1, balance.START)
        player = wd.load_or_create_player(conn, 1, "Caller", balance.START, 1)
        wd.resolve_root_exchange(conn, player, 1, balance.START, balance._BustRoll(0))
        conn.execute("UPDATE players SET last_raided_by=2 WHERE user_id=1")
        before = list(conn.iterdump())
        frame = balance.observe(conn, {1}, {1: Counter(turns=1)}, balance.START + timedelta(days=3))
        assert frame["1"]["cash"] > player.cash
        assert list(conn.iterdump()) == before
    finally:
        conn.close()



def test_mixed_visit_uses_paid_development_operations_and_all_fifteen_turns():
    result = balance.run_scenario('mixed_visit', days=4)
    assert not result['rejections']
    actions = result['actions']['1']
    assert actions['train'] == 1
    assert all(actions[name] > 0 for name in ('recruit', 'case', 'prepare', 'execute'))
    assert actions['operation_successes'] > 0
    assert all(day['players']['1']['turns_spent'] == (day['day'] + 1) * 15 for day in result['daily'])
    assert all(day['players']['1']['cash'] >= 0 for day in result['daily'])
    assert result['daily'][0]['players']['1']['specialty'] == 'phreakers'


def test_dialer_sweeps_hacks_and_buys_a_rig_within_the_allowance():
    result = balance.run_scenario('dialer', days=6)
    assert not result['rejections']
    actions = result['actions']['1']
    assert all(actions[name] > 0 for name in ('sweep', 'carrier', 'rig', 'recruit'))
    assert actions['carriers_found'] >= actions['sweep']         # a sweep always finds one
    assert 0 < actions['carrier_successes'] <= actions['carrier']
    assert all(day['players']['1']['turns_spent'] == (day['day'] + 1) * 15 for day in result['daily'])
    last = result['daily'][-1]['players']['1']
    assert last['rig'] >= 1 and last['bonus_rank'] > 0 and last['cash'] >= 0


def test_the_probes_measure_the_plain_rules():
    """A line condition would change a payout with the date the probe ran on."""
    assert balance.os.environ["DOOR_LINES"] == "0"
    assert balance.wd.lines_switched_off()


def _finish(name, days=12):
    result = balance.run_scenario(name, days=days)
    return result['daily'][-1]['players']['1'], result['actions']['1']


def test_managed_risk_beats_both_careful_and_reckless_play():
    """The three risk profiles, measured rather than assumed.

    Heat is a budget with a cliff at the bust line. A caller who never spends
    it leaves Rank on the table, one who ignores it is busted most days and
    ends with a crew of a handful, and one who rides it to the line and stops
    out-ranks both. A rule change that reorders these three has changed what
    the game rewards, and should say so.
    """
    careful, _ = _finish('dialer')
    reckless, reckless_actions = _finish('greedy')
    rider, rider_actions = _finish('rider')
    assert rider['rank'] > careful['rank'] > reckless['rank']
    assert reckless_actions['busts'] >= 6 and reckless['total_crew'] <= 5
    assert rider_actions.get('busts', 0) <= 2 and rider['total_crew'] >= 10


def test_digging_is_worth_it_and_is_a_gamble():
    """The best play includes digs, and a dig is lost often enough to be one.

    A digger takes the first two digs on a line while they fit under the bust
    line. It has to out-rank a caller who spends the same Heat on more hacks,
    or nobody chasing Rank would dig; and it has to lose what it carries on a
    real share of its digs, or the dig is a bonus and not a decision.
    """
    rider, _ = _finish('rider')
    digger, actions = _finish('digger')
    assert digger['rank'] > rider['rank']
    assert actions['digs'] >= 20 and actions['dig_rank'] > 0
    assert 0.15 <= actions['traces'] / actions['digs'] <= 0.45
    assert actions.get('busts', 0) <= 2                       # it never digs past the line
    # Paid in Rank, a dig floods no economy: the first design paid cash and
    # ran crews past 130.
    assert digger['total_crew'] <= 90


def test_digging_every_line_out_costs_busts_and_crew():
    digger, _ = _finish('digger')
    gambler, actions = _finish('gambler')
    assert actions['digs'] > 0 and actions.get('busts', 0) >= 2
    assert gambler['total_crew'] < digger['total_crew']


def test_a_three_day_a_week_caller_plays_every_visit_and_keeps_climbing():
    casual, actions = _finish('casual')
    assert actions['turns'] == 6 * 15                      # days 0, 2, 4, 7, 9 and 11
    assert casual['rank'] >= 700                           # Hacker inside two weeks
    assert casual['rig'] >= 1 and actions['sweep'] > 0 and actions['carrier'] > 0
