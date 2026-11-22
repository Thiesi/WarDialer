"""Deterministic policy probes for issue #362; measurements, not proof of fun.

Uses the actual synchronous game actions and disposable SQLite worlds. No live
world path is accepted. Policies are deliberately simple and stated in the report;
they do not establish optimal play or replace human season/playtesting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# The plain rules are what these probes measure: a line condition changes a
# payout or a Heat gain with the date. Set DOOR_LINES=1 to measure with them.
os.environ.setdefault("DOOR_LINES", "0")
import war_dialer as wd

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SCENARIOS = {
    "quiet_node": "One daily territory-first caller; no human opposition.",
    "three_callers": "Three daily territory-first callers in fixed visit order.",
    "eight_callers": "Eight daily territory-first callers in fixed visit order.",
    "late_arrivals": "One caller starts day 0; two territory rivals join day 3.",
    "low_attendance": "Three territory callers visit every 1, 3 and 7 days.",
    "trade_only": "One caller spends every available turn trading.",
    "jobs_only": "One caller repeats the easiest contract with the Standard approach.",
    "mixed_visit": "One caller trains Phreakers once, alternates recruitment with Cautious operations at >=60% execution odds, and trades when preparation is unaffordable.",
    "jobs_ladder": "One caller alternates recruitment with the highest-paying contract at >=60% odds, using Cautious.",
    "income_burst": "One exchange captured initially; subsequent turns trade in a short daily visit.",
    "income_spaced": "Same capture and RNG as income_burst; subsequent turns spread across 23 hours.",
    "capture_trading": "Two callers alternate contests for exchange 1; owning caller recruits/trades.",
    "repeated_victim": "Two mature callers alternate raids on one mature victim who never logs in again.",
    "bust_recovery": "Depleted-crew fixture takes an actual forced bust, then recruits when affordable or trades.",
    "dialer": "One caller buys the next rig when it leaves $150, hacks the best carrier at >=55% odds, sweeps while the book holds under three, recruits when able, else runs the best Cautious contract at >=60%.",
    "casual": "The dialer policy, visiting three days a week (days 0, 2 and 4 of each seven).",
    "greedy": "One caller chases payout and ignores Heat: buys the next rig when it leaves $100, hacks the best-paying carrier at >=30% odds, sweeps while the book holds under three, recruits every third turn when able, else runs the best Bold contract at >=45%.",
    "rider": "The greedy policy while the action's Heat keeps the caller at or under the bust line; past it, the hottest contract approach that still fits, then a sweep, a recruit, and a Trade last.",
    "digger": "The rider policy, which also takes the first two digs on every open line while a dig keeps it at or under the bust line.",
    "gambler": "The rider policy, which also digs every open line out, all three digs, whatever the Heat.",
}


class _BustRoll(random.Random):
    def random(self):
        return 0.0

    def randint(self, low, high):
        return low


def observe(conn, joined, totals, at):
    """Settle a disposable copy so measurements never act as player visits."""
    snapshot = sqlite3.connect(":memory:", isolation_level=None)
    snapshot.row_factory = sqlite3.Row
    try:
        conn.backup(snapshot)
        frame = {}
        for uid in sorted(joined):
            player = wd.refresh_player(snapshot, uid, at)
            holdings = [e for e in wd.list_exchanges(snapshot) if e.controller_user_id == uid]
            frame[str(uid)] = {
                "cash": player.cash, "crew": player.crew, "rank": wd.rank_score(player),
                "assigned_crew": sum(e.garrison for e in holdings),
                "total_crew": player.crew + sum(e.garrison for e in holdings),
                "holdings": len(holdings), "income_per_hour": sum(e.income_per_hour for e in holdings),
                "turns_spent": totals[uid]["turns"], "newcomer_protected": wd.is_in_grace(player, at),
                "capture_rank": player.exchanges_taken_total * wd.CAPTURE_RANK,
                "control_rank": player.control_rank,
                "operation_stage": player.operation_stage, "successful_operations": player.successful_operations,
                "specialty": player.specialty, "support": player.support,
                "rig": player.rig, "bonus_rank": player.bonus_rank,
            }
        return frame
    finally:
        snapshot.close()


def run_scenario(name: str, *, days: int = 14, seed: int = 362) -> dict:
    if name not in SCENARIOS or not 1 <= days <= 21:
        raise ValueError("Choose a known scenario and 1-21 days (within one season).")
    count = 8 if name == "eight_callers" else 3 if name in {
        "three_callers", "late_arrivals", "low_attendance", "repeated_victim"
    } else 2 if name == "capture_trading" else 1
    rngs = {uid: random.Random(seed + uid * 1009) for uid in range(1, count + 1)}
    totals = {uid: Counter() for uid in rngs}
    rejections = Counter()
    joined = set()
    daily = []
    recovery_turn = None
    fixture = None
    with tempfile.TemporaryDirectory(prefix="wardialer-balance-") as temporary:
        conn = wd.connect(Path(temporary) / "world.db")
        try:
            wd.ensure_schema(conn)
            wd.get_or_create_season_anchor(conn, START)
            wd.ensure_exchanges_seeded(conn, 1, START)

            def login(uid, now):
                player = wd.load_or_create_player(conn, uid, f"Caller{uid}", now, 1)
                joined.add(uid)
                return player

            if name == "repeated_victim":
                for uid in rngs:
                    login(uid, START - timedelta(days=3))
            if name == "bust_recovery":
                player = login(1, START)
                # A valid but deliberately depleted stress fixture, not a claim
                # that a new player naturally starts with these resources.
                conn.execute("UPDATE players SET cash=0, crew=1, heat=95 WHERE user_id=1")
                player = wd.refresh_player(conn, 1, START)
                delta = wd.ActionDelta()
                _, busted = wd.resolve_trade_warez(conn, player, START, _BustRoll(0), delta=delta)
                totals[1].update(turns=delta.turns, trade=1, busts=int(busted),
                                 action_cash_delta=delta.cash, rank_gained=delta.rank)
                fixture = {"before": {"cash": 0, "crew": 1, "heat": 95},
                           "after": {"cash": player.cash, "crew": player.crew, "heat": player.heat},
                           "busted": busted}

            for day in range(days):
                schedule = []
                for uid in rngs:
                    if name == "repeated_victim" and uid == 3:
                        continue
                    join_day = 3 if name == "late_arrivals" and uid > 1 else 0
                    period = {1: 1, 2: 3, 3: 7}.get(uid, 1) if name == "low_attendance" else 1
                    if day < join_day or (day - join_day) % period:
                        continue
                    if name == "casual" and day % 7 not in (0, 2, 4):
                        continue
                    # Fixed caller order is explicit; the two exploit probes
                    # interleave their actors so repeated targeting/captures occur.
                    interleaved = name in {"capture_trading", "repeated_victim"}
                    for turn in range(wd.TURNS_PER_DAY):
                        seconds = (turn * count + uid - 1) * 30 if interleaved else (uid - 1) * 1200 + turn * 30
                        if name == "income_spaced":
                            seconds = turn * 23 * 3600 / (wd.TURNS_PER_DAY - 1)
                        schedule.append((START + day * wd.DAY + timedelta(seconds=seconds), uid, turn))
                for now, uid, turn in sorted(schedule):
                    player = login(uid, now) if turn == 0 else wd.refresh_player(conn, uid, now)
                    if player.turns_used >= wd.TURNS_PER_DAY:
                        continue
                    exchanges = wd.list_exchanges(conn, uid)
                    action, target = "trade", None
                    if name == "repeated_victim":
                        action, target = "raid", 3
                    elif name == "capture_trading":
                        if exchanges[0].controller_user_id != uid and player.crew >= 2 and player.cash >= wd.capture_cost(exchanges[0]):
                            action, target = "root", exchanges[0].id
                        elif player.cash >= wd.recruit_cost(player):
                            action = "recruit"
                    elif name == "mixed_visit":
                        if not player.specialty and player.cash >= 150:
                            action = "train"
                        elif turn % 4 == 0 and player.cash >= wd.recruit_cost(player):
                            action = "recruit"
                        elif player.operation_stage != 1 or player.cash >= 50:
                            action = ("case", "prepare", "execute")[player.operation_stage]
                    elif name in {"greedy", "rider", "digger", "gambler"}:
                        leads = wd.read_leads(conn, uid, now)
                        # The rider only takes what leaves it at or under the bust line.
                        room = wd.HEAT_BUST_THRESHOLD - player.heat if name != "greedy" else 10_000
                        ready = [lead for lead in leads
                                 if wd.success_chance(player.crew, lead.difficulty) >= .30
                                 and wd.adjusted_heat(player, "job", wd.lead_terms(lead)[3]) <= room]
                        if (player.rig < len(wd.RIGS) - 1
                                and player.cash >= wd.RIGS[player.rig + 1][1] + 100):
                            action = "rig"
                        elif ready:
                            action, target = "carrier", max(ready, key=lambda lead: wd.lead_terms(lead)[2][1])
                        elif len(leads) < 3 and wd.DIAL_HEAT <= room:
                            action = "sweep"
                        elif turn % 3 == 0 and player.cash >= wd.recruit_cost(player):
                            action = "recruit"
                        elif wd.adjusted_heat(player, "job", wd.JOB_APPROACHES[0][2]) <= room:
                            action = "job"
                        elif player.cash >= wd.recruit_cost(player):
                            action = "recruit"
                    elif name in {"dialer", "casual"}:
                        leads = wd.read_leads(conn, uid, now)
                        ready = [lead for lead in leads
                                 if wd.success_chance(player.crew, lead.difficulty) >= .55]
                        if (player.rig < len(wd.RIGS) - 1
                                and player.cash >= wd.RIGS[player.rig + 1][1] + 150):
                            action = "rig"
                        elif ready:
                            action, target = "carrier", max(ready, key=lambda lead: wd.lead_terms(lead)[4])
                        elif len(leads) < 3:
                            action = "sweep"
                        elif player.cash >= wd.recruit_cost(player):
                            action = "recruit"
                        else:
                            action = "job"
                    elif name in {"jobs_only", "jobs_ladder"}:
                        action = "job"
                        if name == "jobs_ladder" and turn % 2 == 0 and player.cash >= wd.recruit_cost(player):
                            action = "recruit"
                    elif name == "bust_recovery":
                        action = "recruit" if player.cash >= wd.recruit_cost(player) else "trade"
                    elif name.startswith("income_"):
                        if exchanges[0].controller_user_id is None:
                            action, target = "root", exchanges[0].id
                    elif name != "trade_only":
                        available = [e for e in exchanges if e.controller_user_id != uid]
                        if available and player.crew >= 2:
                            chosen = min(available, key=lambda e: (wd.exchange_occupied(e), wd.exchange_defense(e),
                                                                  -e.income_per_hour, e.id))
                            if player.cash >= wd.capture_cost(chosen):
                                action, target = "root", chosen.id
                        elif player.cash >= wd.recruit_cost(player):
                            action = "recruit"
                    delta = wd.ActionDelta()
                    try:
                        if action == "train":
                            wd.resolve_crew_purchase(conn, player, now, wd.CrewChoice("phreakers"), delta=delta)
                            busted = False
                        elif action == "rig":
                            wd.resolve_crew_purchase(conn, player, now, wd.CrewChoice("rig"), delta=delta)
                            busted = False
                        elif action == "sweep":
                            found, busted = wd.resolve_dial(conn, player, now, rngs[uid], delta=delta)
                            totals[uid]["carriers_found"] += len(found)
                        elif action == "carrier":
                            success, _, busted = wd.resolve_lead(conn, player, target, now, rngs[uid], delta=delta)
                            totals[uid]["carrier_successes"] += int(success)
                            totals[uid][f"carrier_tier_{wd.lead_tier(target)}"] += 1
                        elif action in {"case", "prepare", "execute"}:
                            candidates = [i for i, (_, difficulty, _) in enumerate(wd.JOBS)
                                          if min(.9, wd.success_chance(player.crew, difficulty) + .15) >= .6]
                            choice = wd.JobChoice(max(candidates, default=0), 0)
                            result = wd.resolve_operation(conn, player, now, action, rngs[uid], choice=choice, delta=delta)
                            busted = bool(result and result[3])
                            if result: totals[uid]["operation_successes"] += int(result[1])
                        elif action == "root":
                            success, _, busted = wd.resolve_root_exchange(conn, player, target, now, rngs[uid], delta=delta)
                            totals[uid]["captures"] += int(success)
                        elif action == "raid":
                            success, amount, busted = wd.resolve_raid(conn, player, target, now, rngs[uid], delta=delta)
                            totals[uid].update(raid_successes=int(success), stolen_cash=amount if success else 0)
                        elif action == "job":
                            choice = wd.JobChoice()
                            if name in {"jobs_ladder", "dialer", "casual"}:
                                candidates = [i for i, (_, difficulty, _) in enumerate(wd.JOBS)
                                              if wd.success_chance(player.crew, difficulty) >= .6]
                                choice = wd.JobChoice(max(candidates, default=0), 0)
                            elif name in {"greedy", "rider", "digger", "gambler"}:
                                candidates = [i for i, (_, difficulty, _) in enumerate(wd.JOBS)
                                              if wd.success_chance(player.crew, difficulty) >= .45]
                                room = wd.HEAT_BUST_THRESHOLD - player.heat if name != "greedy" else 10_000
                                # Bold while it fits; then the hottest approach that still does.
                                fits = [index for index, (_, _, heat, _) in enumerate(wd.JOB_APPROACHES)
                                        if wd.adjusted_heat(player, "job", heat) <= room]
                                choice = wd.JobChoice(max(candidates, default=0), max(fits, default=0))
                            _, success, _, busted = wd.resolve_job(conn, player, now, rngs[uid], choice=choice, delta=delta)
                            totals[uid][f"contract_{choice.contract + 1}"] += 1
                            totals[uid]["job_successes"] += int(success)
                        elif action == "recruit":
                            wd.resolve_recruit(conn, player, now, delta=delta)
                            busted = False
                        else:
                            _, busted = wd.resolve_trade_warez(conn, player, now, rngs[uid], delta=delta)
                    except wd.ActionRejected as exc:
                        rejections[str(exc)] += 1
                        continue
                    totals[uid].update({action: 1, "turns": delta.turns, "busts": int(busted),
                                        "action_cash_delta": delta.cash, "rank_gained": delta.rank})
                    # A hack that landed left its line open; the two digging
                    # policies press it, each to its own limit.
                    while name in {"digger", "gambler"} and wd.dig_terms(player) and (
                            name == "gambler" or (player.line_depth < 2 and player.heat + wd.DIG_HEAT
                                                  <= wd.HEAT_BUST_THRESHOLD)):
                        dug = wd.ActionDelta()
                        held, _, dig_bust = wd.resolve_dig(conn, player, now, rngs[uid], delta=dug)
                        totals[uid].update(digs=1, traces=int(not held), busts=int(dig_bust),
                                           dig_rank=dug.rank, rank_gained=dug.rank)
                    if player.line_banked:
                        carried = wd.resolve_hang_up(conn, player, now)
                        totals[uid].update(dig_rank=carried, rank_gained=carried)
                    if name == "bust_recovery" and recovery_turn is None and player.crew >= wd.STARTING_CREW:
                        recovery_turn = totals[uid]["turns"] - 1  # Exclude the fixture's bust turn.
                at = START + (day + 1) * wd.DAY - timedelta(microseconds=1)
                frame = observe(conn, joined, totals, at)
                daily.append({"day": day, "players": frame})
            return {"scenario": name, "policy": SCENARIOS[name], "days": days, "seed": seed,
                    "crew_policy": "Territory policies pay capture costs, recruit when able, and trade when capture/recruitment is unaffordable; they do not reinforce holdings.",
                    "daily": daily, "actions": {str(uid): dict(sorted(total.items())) for uid, total in totals.items()},
                    "rejections": dict(sorted(rejections.items())), "recovery_turns_after_bust": recovery_turn, "fixture": fixture}
        finally:
            conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14, choices=range(1, 22))
    parser.add_argument("--seeds", type=int, nargs="+", default=[362, 363, 364])
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    args = parser.parse_args(argv)
    if not 1 <= len(args.seeds) <= 20:
        parser.error("choose 1-20 seeds")
    source = Path(wd.__file__).read_bytes().replace(b"\r\n", b"\n")
    report = {"game_source_sha256": hashlib.sha256(source).hexdigest(),
              "limits": "Scripted policies and finite seeds; no claim of optimal play, fairness or fun.",
              "results": [run_scenario(name, days=args.days, seed=seed)
                          for name in args.scenario or SCENARIOS for seed in args.seeds]}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
