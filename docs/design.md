# War Dialer design

Extracted from NetBBS section 16. Issue references below belong to NetBBS.
Host world ownership, node backups and legacy path migration remain in the
[NetBBS design](https://github.com/Thiesi/NetBBS/blob/main/docs/NetBBS-design-doc.md).

## Standalone world ownership (WarDialer #2)

Before loading a player, an unbound world is adopted in one transaction.
With `war_dialer_owner`, it becomes host-bound. Without that token, it receives
a random 128-bit owner ID and a self-owned marker. Later standalone launches
trust the stored ID only when that marker is present. An existing host-bound
world still requires the matching token on every launch. Adoption preserves
all existing player rows; each BBS uses its own world shared by its nodes.

## Terminal encoding (WarDialer #4)

Classic drop files default to CP437; standalone launches default to UTF-8.
Display offers Automatic, UTF-8 and CP437, saved per caller alongside existing
display preferences and retained across season/competition resets. NetBBS
always receives UTF-8 and owns caller-side conversion; its encoding row is
informational. CP437 substitutes for authored symbols are explicit and retain
their display columns. Unsupported caller-name characters are transliterated
only on output, leaving the stored Unicode name intact. Input remains menu
hotkeys; crew names and insignia are chosen rather than entered as text.

## Classic host metadata (WarDialer #3)

A positional DOOR32.SYS or DOOR.SYS filename supplies caller identity, terminal
height and available communications metadata. NetBBS JSON takes precedence
when its environment variable is set, including when the file is unreadable.
Malformed classic metadata refuses the launch before a world is opened;
multiplayer callers must never silently share a Guest identity. Classic hosts
default to 16 colors (or monochrome for non-graphics callers). A launch without
host metadata uses Local branding; NetBBS behavior and its richer palette stay
unchanged. Parser details follow Voidrunner's classic-host implementation.

## Mid-game scenes

Following Voidrunner's scenes and Retro Trivia's finales, ten short scenes
reuse the launch splash's stage and its motion rules. They play only after the
commit they show, and each ends on a caption that the result screen repeats.

| Scene | When it plays |
|---|---|
| Patch In | A Root the Exchange is won or held; an unclaimed exchange gets the short version |
| Raid | A raid scores or bounces |
| Sweep | A sweep; the dial log scrolls until each carrier found answers |
| Contract hack | A job or a carrier; the contract or the system sets the banner and the payoff |
| Operation | The Execute step only; case and prepare get no scene |
| Busted | A bust, replacing that turn's own scene, so one turn gets one scene |
| Tier Up | The turn's Rank crosses a tier, after the outcome scene |
| Fed Crackdown | An unseen crackdown receipt at login, or a season change mid-session |
| Cracktro | That same login, if the caller medalled in the closed season |
| Messages Waiting | Unseen receipts from a rival at login |

Trade Warez, recruiting, garrison and crew purchases keep the carrier sweep;
Trade is the most frequent action, and the rest are bookkeeping. A scene
replaces the sweep whenever it plays. Each scene holds its caption for about
three seconds, and the hint changes from "any key skips" to "key continues".
A key during the motion ends the scene and the rest of its chain. A key during
the hold ends only that hold, so a promotion still follows its bust. The key is
never handed to the screen behind. Login scenes key off
unseen receipts: once the log marks them read, they do not replay. A season
change seen mid-session may replay its crackdown at the next login, because its
receipt is still unread. `DOOR_SCENES=0` turns scenes off independently of
`DOOR_SPLASH`. The fast, monochrome and plain presets never get them.

## Carrier Detect presentation (issue #24)

War Dialer is a phreaker's phosphor terminal patched into the switched
telephone network, so everything on it reads as a signal on a wire. Where
Lunar Lander paints a scene and instruments over it, War Dialer is a
luminous information console. Its beauty is in its type, its diagrams and
its signal, and pixel art is kept for marquee moments. The overhaul is
presentation only: every key, number, wording, screen order and page counter
is unchanged, and hotkeys still print as `[K]`.

- **Glass.** A framed screen is a slab of dark green glass, every other row
  a shade deeper (the tube's scanlines, which also stripe a table). The title
  is a lit tab. Section rules glow beside their label and cool to chrome.
  Corners are arcs, the splash ring's own. Keys sit on amber plates and badges
  on chips. Controls stay under the glass.
- **Signal.** Meters resolve to an eighth of a cell. Heat's ramp lies along
  the whole track, phosphor to the bust line's red, so a half-full gauge
  already shows amber at its tip.
- **The switch ring.** From 50 columns the ten exchanges are a lit loop with
  their numbers on the nodes, their names beside them and the owner counts
  inside. A link between two neighbours one crew holds is drawn in that crew's
  color. `scene_map` remains the compact map below that width.
- **Wide console.** Up to 99 columns the layout and page budgets are what
  they were. From 100 columns a screen grows to 104 columns, centred. The
  switchboard then sets the crew's instruments and the ring side by side
  (`Split` cards, with `┬`/`┴` joints), on one page at 132x40.
- **Hayes codes.** A result is stamped CONNECT (the roll won), NO CARRIER (it
  lost), OK (no roll: trades, purchases, transfers) or BUSTED, above the
  headline that says the same in words. The stamp needs 20 rows. Leaving the
  door ends on NO CARRIER.
- **Attract mode.** The large splash dials, then sweeps the exchange for
  carriers: busy, voice, fax, the odd carrier, and finally 555-0142. Then
  CONNECT, the tube clears, the quarter-block wordmark burns in, and the
  tagline and ring follow. On a terminal bigger than the composition the scan
  stays around it as a dim backdrop whose carriers glint during the hold. It
  takes about 3.6 seconds and any key skips it, as before.
- **Scenes** play on a pane of the same glass with a lower-third caption
  band. Tier-up letters and the cracktro's wordmark are pixel art. The
  cracktro keeps its black starfield.

Pixel art is quarter blocks, two pixels across and two down a cell, each
cell showing the two colors that lose least (Lunar Lander's encoder, copied).
It falls back to half blocks when NetBBS reports `quadrants: false` or a
CP437/ASCII charset, when the output encoding is CP437, or when
`DOOR_PIXELS=half` is set. Any RGB has an xterm-256 reading (cube or grey ramp)
and a sixteen-color reading by hue family. Backgrounds (glass, plates, scene
panes) need 256 colors or truecolor. Sixteen-color callers keep the classic
frame, whole-cell meters and pixel art as a silhouette. ASCII decorations get
text where art would be, monochrome gets no SGR, and Fast mode stays unframed.

## The overhaul: war dialing, a living wire and a record that lasts (world schema 12)

A review of the whole game found the presentation in good order and the play
underneath it thin in four specific ways. Each was measured before it was
changed, with `scripts/war_dialer_balance.py` over twenty-one days.

- **The door was named after a sweep nobody could run.** War dialing was the
  splash and nothing else. Every action was a menu, a preview and a roll.
- **Nothing varied.** Five fixed contracts, the same every day of every
  season, and no event of any kind: a caller's second week was their first.
- **Cash was solved in days and crew was the only stat.** At a flat $75 the
  probes recruited 160 to 180 times in three weeks, ten Rank a turn with no
  risk and no decision, and banked up to $17,000 with nothing to spend it on.
- **A board with one caller was finished in two days.** All ten exchanges
  held by one defender each, and nothing in the world that could ever take
  one back. The feed, the log and the "messages waiting" scene never fired.

Everything below answers one of those. The rules the rest of this document
locks in are unchanged unless a paragraph here says otherwise: one turn and one
transaction an action, a free preview that is refused once it is stale, nothing
spent by a rejection, lazy settlement with no background task.

**War dialing.** `[D] Dial` opens one screen for both halves of a loop: the
black book, and `[S] Sweep`, which fills it. A sweep costs one turn and 2 Heat
with the ordinary bust roll. One carrier always answers, a second half the
time, and each rig tier adds a 10% chance of a third. Each carrier is a system
that can be hacked once, from the same screen: win or lose the number is
burned, and an unused one goes cold after 72 hours. The book holds six; a
sweep into a full book drops the oldest, which the preview says first.

| Tier | Difficulty | Payout | Heat | Rank | Crew lost on failure |
| --- | --- | --- | --- | --- | --- |
| Soft | 0.4 x living crew, at least 1 | 1.3 x the contract curve | +6 | +20 | 0 |
| Warm | 0.8 x, at least 3 | 1.5 x | +10 | +30 | 1 |
| Hard | 1.4 x, at least 8 | 1.8 x | +14 | +45 | 1 |
| Ice | 2.4 x, at least 16 | 2.3 x | +18 | +70 | 1 |

Difficulty is sized on the finder's *living* crew, posted members included, and
the odds on the crew available when the hack is made: sized on available crew
alone, posting everyone to a garrison before a sweep would buy soft numbers at
any tier's Rank. Recruiting between the find and the hack is the intended
play. The floor is what stops a number found by a crew of three from being a
ninety-percent ticket once that crew has grown. The contract curve is
`45 + 11 x difficulty`, the line the five standing contracts already sit on,
and the top of the range is 1.55 times the bottom. A carrier counts as a
contract for Heat: Phreakers, Fixers and a Burner Kit apply.

About a third of carriers carry a perk, shown in the book before anything is
committed: a recruit (+1 crew), a cold trail (no Heat added and 10 removed, and
a Burner Kit is not spent on it), calling-card codes (a free Burner Kit, or $40
with the slot full) or a doubled payout. On the stock rig a sweep's answers are
40/35/18/7 soft to ice out of a hundred; each rig tier moves six from soft to
the two hardest. The standing contracts and operations are untouched and are
the reliable alternative: the `dialer` probe lands within a few percent of
`jobs_ladder` on Rank, with far more variety in how it gets there.

**The rig.** Cash keeps buying one thing. `[S] Kit` sells the modem above the
one held: 1200 baud ($250, +20 Rank), 2400 ($600, +40), 9600 ($1,500, +80),
14.4k ($3,500, +150) and 28.8k ($8,000, +300). A rig costs a turn, lasts the
season and improves every sweep. It is why a Bold approach is worth its Heat
again: there is finally something to spend the difference on.

**Recruiting scales.** The first five living members cost $75 each, as before,
which is what bust recovery is sized on. Each member past five adds $10 to the
next one's price. A Carrier Switch recruits for $10 under whatever the boards
charge that crew. Recruits in the probes fell from 160-180 to about 80 over
three weeks, and late cash now has two uses that compete.

**Line conditions.** Each day of a season has one condition, the same for every
caller, named on the switchboard's TODAY card with the time until it changes.
It is chosen from the world's owner ID, the season and the day, so it cannot
be rerolled and needs no storage. A season's first day is always clear, and no
two days running are the same. Each is a bonus or a trade and none is only a
penalty: Trades pay $15 more; contracts and carriers pay 25% more; Heat gains
are 2 lower; Heat gains are 3 higher while hack payouts are 50% higher; capture
attempts cost $15 less; recruits cost $20 less; sweeps find one more carrier;
clean hacks earn 5 more Rank. The day is part of a preview's state, so a
preview taken under yesterday's wire is refused without spending. `DOOR_LINES=0`
pins a clear wire for a SysOp who wants the plain rules; the test suite and the
balance probes set it, because a rule that changes with the date cannot be
pinned by one.

**Operators push back (supersedes "NPCs never take a human holding").** The
three neutral operators still raid nobody, hold no cash and earn no Rank. But a
caller who takes an operator's home now has that crew to answer to. From 48
hours after the capture, and once a day from then on, the operator tests a
defence weaker than its own crew of 2, 4 or 6, with the ordinary odds of crew
against defence. A defence that matches the crew is never tested, so the rule
a caller has to remember is one number per home, and a Carrier Switch's two
security points count toward it. A successful test pays the owner what the
exchange earned, sends the defenders home and restations the operator; either
outcome leaves an unread receipt in the operator's name. One test per deadline
however long the world sat unvisited, and the roll is drawn from the exchange
and the deadline, so it is the same roll whoever's visit settles it. The
switchboard's next move and the garrison screen both name a home that is short.

**Bonus Rank.** Carriers, rigs and the Scene Meet condition add to one new
monotonic counter, `bonus_rank`, which joins the Rank sum in Python and in the
standings SQL alike and resets with the season.

**The rap sheet.** A season takes cash, crew and Rank. The rap sheet is the one
record that only grows: lifetime counts (sweeps, carriers, contracts,
operations, captures, raids, recruits, busts, seasons, medals), four high-water
marks, and sixteen badges, each earned once. It is written inside the
transaction that did the deed, so a rolled-back action leaves no trace. A badge
is announced on the result that earned it and leaves a read receipt. Unearned
badges are listed with what earns them. None of it is power. It survives a
season and a SysOp's competition reset. `[I] Scene / Your rap sheet`.

**Fewer keys, fewer words.** A result offers `[A] Again` beside its any-key
continue for Trade, Recruit and a standing contract: it returns to the same
preview, never past it, so a repeated contract is two keys instead of five and
the Heat it shows is current. A preview's TERMS no longer repeat the cost the
head card states or the Heat sum the gauge draws. The switchboard's first page
is the whole cockpit at 80x24: who you are, TODAY (the wire and one next move),
the instruments with RIG and BOOK, the ring and the feed. The awards rule and
the tour of `[I] Scene` moved to Help, where they already were; an operation's
budget is said only while one is saved. The first-visit guide is the fantasy,
three keys to press tonight and the two rules that shape every decision.

**Presentation.** A console tall enough to hold the whole switchboard with
rows to spare wears the pixel wordmark on it. The dialer shows the modem's
front-panel lamps as a reading, not a decoration: MR and TR always, CD while a
number waits, AA while there is a turn to sweep with, HS from the 9600 up. A
carrier's preview opens on the line itself: `ATDT`, `CONNECT` at the rig's
speed, and the system's own greeting waiting for an answer. The sweep has its
own scene, a dial log scrolling past busy signals and fax tones until a modem
answers, and a carrier's hack plays on the contract scene under the system's
own banner. Sign-off says what tonight was worth and when fresh turns arrive.
A result's closing line is drawn from a small pool by the turn, so the
fifteenth turn of a night does not read like the first.

**Schema 12** adds `players.rig` and `players.bonus_rank`, the bounded
`leads` table and the `career` table, all empty: nobody is handed carriers
they did not dial, a rig they did not buy or a badge for play nobody counted.
The upgrade and its version marker commit together. A world at schema 11 can
still be settled and archived by the SysOp's commands without being upgraded.
Operators' clocks reuse `exchanges.npc_return_at`, which a caller-held home
never used before; a home held since before the rule starts its grace at the
first settle rather than being tested at once.

## Pressing your luck (world schema 13)

The measurement below found Heat working as a budget with a cliff and the best
play a calculation: spend it to the line and stop. Four changes follow from
that. Each was probed before it was kept, and one was thrown out on its
numbers.

**Digging.** A contract, a carrier or an operation that lands, without a bust,
leaves its line open. Its result offers `[D] Dig deeper` beside the any-key
continue; any other key hangs up. A dig costs no turn, adds 6 Heat with the
ordinary bust roll, and is allowed with no turns left.

| Dig | The trace lands | Adds to what is carried |
| --- | --- | --- |
| 1 | 25% | 50% of the hack's own Rank |
| 2 | 35% | 100% |
| 3 | 55% | 150% |

What a dig adds is *carried*, not credited. It becomes Rank when the caller
hangs up: any other key on the offer, any later action, a season closing, or
the third dig holding, which is the last and hangs up for them. A trace loses
everything carried, adds 12 Heat and drops the line; so does a bust on the
Heat a dig adds. Rank that has been credited is never taken back, so Rank
stays monotonic, and the hack's own Rank and payout were earned before the
first dig and are never at stake. The first two digs are worth taking in
expectation and the third is a long shot on purpose.

Each dig is its own committed transaction, so nothing happens between a
decision and its commit, and a caller who drops carrier on the offer has hung
up with what they carried. The offer is validated against the line that is
still open: a second session acting in between hangs it up, and one dig is
never committed twice.

Digs were first paid in cash, as a share of the hack's payout, and measured.
At these shares the digging probe banked up to $77,000 over three weeks and
ran crews past 130, because a carrier's payout already scales with crew. At
half of them it finished *behind* a caller who spent the same Heat on more
hacks, so nobody chasing Rank would dig. Rank has no economy to flood and is
what a caller is there for.

**Trade cools.** A Trade takes 3 Heat off instead of adding 2, never below
zero, and above the line still rolls on what is left. Measured, a Trade was
what every policy fell back on with the Heat budget spent, and then it made
the Heat worse. Now the fallback is also the way back under the line. The
Heat chip beside the gauge is judged on where Heat stands, where it used to
be judged on what a Trade would leave.

**Operations can case a carrier.** Three turns on a standing contract earned
less Rank a turn than running it cold, and carriers widened that. An
operation's target is now a contract, as before, or a carrier from the black
book, offered after the five contracts, hardest first. A cased number is
pinned: it does not go cold and a sweep into a full book does not drop it,
and it cannot be hacked cold while the operation holds it. Executing it has
the operation's edge: +15 points of odds to the 90% cap, double the payout,
and the operation's +30 Rank beside the carrier's own. A failed execution
keeps the number and its casing, where a cold hack burns the number, which is
what three turns on one number buy. Abandoning unpins it.

**Raids are no longer blind, and a raided crew may strike back.** A rival's
crew is public as a rough size (a handful, a small crew, a full crew, a big
crew, an army) and never as a number. A raid's preview turns that into a range
of odds that always holds the real figure. Exact strength and all cash stay
private until recon buys them. This relaxes "available crew remains private"
by exactly that much. For 48 hours after a raid on it, win or lose, the crew
that was hit may raid its raider once whatever their shields or tier, at +10
points of odds. A strike back hands none in return, so a feud is one exchange
and not a loop. The window is read off the shield the raid left, so it needs
no stored state.

With all four in, twenty-one days over four seeds:

| Policy | Rank | Busts | Crew at the end |
| --- | --- | --- | --- |
| `dialer`, careful | 3,100-3,415 | 0 | 71-80 |
| `rider`, spends Heat to the line | 3,675-4,160 | 0 | 35-54 |
| `digger`, also takes the first two digs while they fit | 4,371-5,242 | 0 | 64-82 |
| `gambler`, digs every line out whatever the Heat | 3,505-4,829 | 6-10 | 14-37 |
| `greedy`, ignores Heat on the hacks themselves | 2,455-2,805 | 19-24 | 1-3 |

The best play now includes real gambles: the digger loses what it carries on
about three digs in ten. Digging every line out is competitive but swings
widely and wrecks the crew, and ignoring Heat outright is still the worst.

**Schema 13** adds four player columns, all zero: `line_rank`, `line_depth`
and `line_banked` (the open line: what the hack was worth, how many digs have
held, and the Rank they carry), and `operation_lead` (the carrier an operation
has cased). Nobody starts with a line open or a carrier cased.

## Measuring play

Rules are changed against measurements, and two kinds exist.

**Probes.** `scripts/war_dialer_balance.py` plays scripted policies through the
real actions. Three of them are the game's risk profiles, and the order they
finish in is a property the suite holds:

| Policy | What it does | Twenty-one days, four seeds |
| --- | --- | --- |
| `dialer` | Careful: carriers at 55% odds or better, Cautious contracts | Rank 3,100-3,415, no busts, crew 71-80 |
| `greedy` | Reckless: best-paying carrier at 30% or better, Bold contracts, ignores Heat | Rank 2,455-2,805, 19-24 busts, crew 1-3 |
| `rider` | The greedy choices while the action's Heat keeps it at or under the bust line | Rank 3,875-4,110, 0-3 busts, crew 35-51 |

So Heat does bite, hard, but only past a cliff: it is a second budget beside
turns. A caller who never spends it leaves a fifth of their Rank on the table,
one who ignores it is busted most days and ends with a handful of crew, and
the best play is to spend it to the line and stop. That best play is a
calculation, though, not a gamble: nothing in it is decided under uncertainty.
`casual` plays the careful policy three days a week and reaches Hacker inside
two weeks. The table above is as these three stood before "Pressing your
luck", which is what they led to; that section has the figures since.

**Real play.** `--admin stats` sums every caller's rap sheet, read-only and
without naming anyone: how a hundred turns were spent, how often one ended in
a bust, success rates, badge holders and the shape of the standings. For that
the sheet counts attempts beside wins (turns, trades, and tries at contracts,
carriers, operations, raids and roots). They are on the sheet and not on the
caller's screen. The rules note each attempt and each bust on the acting
player object as they run, and the action's transaction reads the tally once
it commits, so a rejected action counts nothing.

## NetBBS game events (issue #16)

NetBBS door API 5 lets a door report what a caller earned. War Dialer reports
four things:
- **`rank`** when the session's caller crosses into a new `RANK_TIERS` tier.
- **`medal`** for a closed season's medallists, gold first.
- **`capture`** for each captured exchange, titled `the <exchange name>`.
- **Standings:** the current season's top ten by Rank, with ties broken by
  ascending account ID. `value` is the Rank score and `label` is the tier name.

Callers with no Rank yet are left out of the standings, so a fresh season's
table is `"rows": []`. Abandons and neutral-operator scene events are never
reported. Throttling, consent and wording belong to NetBBS (decision #1378).

`_GameEvents` holds the rules:
- **Off by default.** It is inert unless `door_api` is at least 5 and
  `outbound.events` is present.
- **After commit.** Reports are queued inside the write transaction that earns
  them. They are renamed into the drop directory only after COMMIT, and a
  rollback discards them.
- **Live only.** `arm` takes a baseline after login settlement. A tier that
  already held when the session started is not news.
- **Table at start.** `arm` also sends the standings as they stand, so `!top`
  agrees with the game from the first session that reports (issue #19). It
  skips that send only if this session already sent the same table, such as
  the empty one after a season closed at login.
- **Medals once.** A season's medals come from the session whose settlement
  archives it, which may name callers who are not playing.
- **Standings on change.** A snapshot is sent whenever the table changes:
  order, a score or a tier.
- **Ordered names.** Requests are named `wardialer-<NNNNNN>-<kind>.json`, so
  name order is write order.
- **Never in the way.** Failures to write are swallowed, and receipts are not
  read.

## Issue Thiesi/NetBBS#200 — War Dialer: async multiplayer BBS-crew door game — closed

**Goal:** decide the design for a second door-game genre alongside
Voidrunner's single-player persistent model — an asynchronous,
play-by-post multiplayer game in the LORD/TradeWars BBS-door lineage,
where actions taken by one player affect another player's persistent
state regardless of whether that player is online, and the target finds
out via a summary on their next login.

**Decision 1 (locked in) — no platform or door-API changes.** §Phase 7
already states doors run with real filesystem access and no enforced
isolation. This game owns its own SQLite database (WAL mode) keyed by
the door API's stable numeric user ID, the same pattern Voidrunner
already uses for its own save state. Cross-player shared state is
therefore the door's own responsibility, not a new NetBBS capability —
issue Thiesi/NetBBS#63's "single-player, session-scoped only" boundary for the
platform itself is unaffected.

**Decision 2 (locked in) — resolution is synchronous, not tick-based.**
Every action resolves inside the acting player's own live door session.
No cron/daemon, matching the fact that a door process only exists while
someone is logged in. Passive accrual (territory income, Heat decay) is
computed lazily from elapsed wall-clock time whenever next read, the
standard idle-game pattern, rather than requiring a background tick.

**Decision 3 (locked in) — theme is 80s/90s BBS-scene hacker/phreaker
crews, not a generic crime-syndicate reskin.** Rival crews (Legion of
Doom/Masters of Deception energy) fighting over "exchanges" (phone
NPA-NXX prefixes); "Heat" is literal federal attention
(Sundevil-era Secret Service/FBI); this reads as the platform's own
history rather than the genre's default reskin, which every existing
Discord clone already uses.

**Decision 4 (locked in) — Rank is a single, monotonic metric doing
double duty as leaderboard score and PvP bracket gate.** Tiers Newbie/
Wannabe/Script Kiddie/Hacker/Elite/Legend. Never decreasing within a
season was the deciding constraint: a raw balance that could drop would
let a strong player deliberately sandbag into a weaker bracket to prey
on newcomers. Direct PvP (Raid) is gated to your own tier ±1; territory
contests (Root the Exchange) are intentionally *not* gated, since a
district's defense is the controller's committed garrison rather than
their full Rank, keeping territory contestable by newcomers even
against a top-bracket controller.

Rank sums season achievements, never current cash, available crew or holdings:
`crew_recruited_total*10 + exchanges_taken_total*50 + successful_raids*25 +
successful_jobs*15 + successful_operations*30 + control_rank + legacy_rank`. The capture counter records
rewarded first captures; control Rank is earned time, retained after losing a
holding. `legacy_rank` preserves previously earned capture points during upgrade
and resets with the season. Python and SQL standings scores must agree. Tiers
begin at 0, 100, 300, 700, 1,400 and 2,800 points, scaled to a four-week season
without capture farming. Rank never decreases within a season; the existing raid
bracket rule and ungated territory contests remain.

**Decision 5 (locked in) — seasons (4 weeks), separate from Rank
brackets, because they solve a different problem.** Brackets prevent
moment-to-moment exploitation (a veteran farming a specific weak
player); they do nothing about long-run stagnation, where early players
simply compound the largest crews/territory indefinitely and a
newcomer has no on-ramp. A season boundary resets
Rank/cash/crew/exchange-control, flavored in-fiction as a Fed crackdown
wiping the scene's boards.

**Decision 6 (locked in) — bounded action economy and a self-limiting
risk curve, no separate anti-snowball mechanic.** 15 turns/day on a
rolling 24h window. Base Heat gain per action (Trade Warez +2, Root Exchange
+8, Raid +10, Run a Job +5/+15/+25 by approach) decays −5/real-hour; above 80, each
heat-gaining action rolls a bust chance of `(Heat−80)×2%`, capped ~40%,
normally costing 25% cash and 20% crew and resetting Heat to 0. The adopted
crew specialty/support rules below adjust added Heat, failure recovery and bust
cash loss; zero added Heat does not remove an existing bust risk. Success chance
for both PvE and PvP actions is `attacker_crew / (attacker_crew +
defender_crew)`, clamped to [10%, 90%] so nothing is ever a guaranteed
win or loss. New accounts get 48h Raid immunity. Under the adopted slice 5
rule, every committed raid attempt grants its target 24 hours of immunity
against all attackers; login and receipt acknowledgement do not clear it.

Explicitly out of scope for v1: procedural exchange generation, a
multi-resource economy, factions/alliances, and an item/weapon shop —
plausible v2 additions once the core loop is proven, not part of this
vertical.

The original five-action game is implemented in
`src/netbbs/doors/bundled/war_dialer.py`, registered in `BUNDLED_DOORS`.
Issue Thiesi/NetBBS#362 tracks its ordered reliability and product overhaul.

**Shared-world actions (issue Thiesi/NetBBS#362, slice 1).** Duplicate sessions for a
player are allowed and serialize their actions against the same current
database row. There is no per-session allowance or exclusive-session lease.
Each action re-reads its actor and affected target/exchange under
`BEGIN IMMEDIATE`, revalidates allowance, cash, raid protection/bracket,
season and ownership as applicable, and commits all effects, events and its
one-turn cost together before result output. A target changed since selection
is rejected without cost. Login settlement also holds one write transaction.
Refresh, quit and disconnect never save a session snapshot; ordinary refresh
does not clear target-wide raid recovery.

World initialization checks for existing exchanges under the same write lock
as seeding. An existing nonempty world with an unexpected exchange count is
preserved and refused for explicit operator repair; automatic deletion cannot
safely reconcile conflicting ownership or earned rewards.

Every menu and pause uses one bounded input decoder. CSI/SS3 and other terminal
sequences never supply action letters. Bracketed paste and unframed bursts are
discarded; use separate single keys, since rapid queued commands are deliberately
not macros. Incomplete or excessive sequences end the session with a diagnostic,
rather than letting delayed suffixes select an action. A standalone Escape can
dismiss a pause and is ignored at menus.

**Clock settlement (issue Thiesi/NetBBS#362, slice 2).** Screen refresh and action transactions
settle Heat and the turn allowance without clearing raid recovery.
An unused allowance has no running window; the first committed action anchors
its 24 hours. Reading, login, an unaffordable attempt and cancellation do not
start it. Existing nonzero allowances keep their stored anchor; expiry leaves
the new allowance unanchored until used.

The player's last observed timestamp never moves backwards. A clock rollback
freezes elapsed-time benefits until that time is reached again; it cannot replay
Heat decay, shorten a new turn window or backdate a capture. Heat settles before
an action adds new Heat, so a reconnect cannot decay that addition over the
earlier idle interval. A session waiting at a zero-turn menu can use an action
key after refill; commit-time state decides whether that action is available.

The exchange world's stored season also prevents season-number regression after
a clock correction, including for new and dormant callers. A capture respects
both the exchange's timestamps and the actor's clocks; the effective capture time
anchors newly incurred Heat and any newly started allowance too.


**Exchange income (issue Thiesi/NetBBS#362, slice 2).** Login, menu refresh and committed
actions collect elapsed income. Sub-dollar earnings are retained as integer
units on the player, so frequent visits pay the same as one longer interval.
A successful capture credits the previous owner's earnings through transfer
before changing ownership, in the same transaction as the action and turn.
The previous owner keeps fractional earnings even after losing every exchange.
Neither collection nor transfer moves an exchange's income timestamp backwards.
An income-only collection does not invalidate an otherwise unchanged selection.

Existing worlds receive an additive, transactional player-column upgrade with
zero initial remainder; fractions discarded by older versions cannot be
reconstructed. Season resets clear the remainder with the other season resources.

**Atomic seasons (issue Thiesi/NetBBS#362, slice 2).** Login, resource refresh, world/rival
views and actions settle the shared season under the same write lock as their
state access. All prior-season players, including dormant crews, reset together
with exchange ownership and garrisons. Account IDs, handles and original creation
times remain; the 48-hour newcomer grace is never renewed for a veteran.

A persisted active-season marker commits with the resets and never regresses.
Existing mixed-season worlds are adopted without erasing already-current-season
progress. Skipped seasons advance directly to the current season; there is no
old ownership income or competitive power carried through the reset. Failed
rollover writes preserve the entire previous world. Schema 10 archives the
outgoing season and final territory Rank before resetting, in this same transaction
(see season results below).

A selection made with an old-season snapshot is rejected without spending
resources. The next menu refresh shows the crackdown notice and fresh resources,
and the caller can continue in the same session. A rejected action transaction
can roll back its attempted settlement too; the following read commits rollover.
Later gameplay decisions remain governed by the locked rules above until an
explicit design pass adopts their replacements.

**Event history (issue Thiesi/NetBBS#362, slice 2).** Keep the latest 500 events per player,
ordered by their committed IDs, with no age expiry. New receipts remove the
oldest, including unread receipts beyond that limit. Existing unbounded history
is trimmed transactionally on upgrade. Reads use target/history and target/unseen
indexes and fetch at most 500 records.

The login summary shows unread events oldest first; free `[H]istory` replays
retained events newest first with UTC timestamps and NEW/READ labels. Both views
paginate for terminal width and height down to the 40x12 floor and show the
retention limit.
Smaller terminals receive a size diagnostic without acknowledging anything.
Continuing a summary page accepts only records whose final line was displayed;
Back and disconnect leave that page unread. History navigation does not acknowledge
records; `[A]ck page` does so explicitly. Acknowledgement updates only the displayed
player/record IDs atomically, so events arriving while a page is open remain unread.
Onboarding and summary disconnects exit cleanly.

**Switchboard dashboard (issue Thiesi/NetBBS#362, slice 3).** The main screen shows settled
cash, crew, Heat and turns; current holdings and hourly income; monotonic Rank
and the next tier's threshold; unread event count; newcomer and target-wide raid-recovery
protection; turn refill and season end time. The read obtains these from one
world transaction and never clears raid protection or acknowledges events.
The countdowns are snapshots refreshed when navigating or returning from an action.

Next/Prev pages keep action and free-browsing keys visible at 80x24, 40x12 and
40x12. Smaller terminals receive an explicit minimum-size response before opening
the world. Action outcomes, rejected actions and season-change notices wait for
acknowledgement before the dashboard clears them. Cancelling a target selection
returns directly. Detailed action previews remain a subsequent slice 3 bullet.

**Free browsing (issue Thiesi/NetBBS#362, slice 3).** `[B]Rank` opens current-season standings,
ordered by descending Rank, then ascending stable account ID for ties. Your exact
position is shown even outside the current batch. `[E]Map` shows exchange ownership,
defenses and hourly income; `[V]Rivals` lists other crews in account-ID order with
their Rank/tier and current raid eligibility reason. This directory exposes no
additional crew-strength or cash intelligence; slice 5 deliberately keeps them private.
`[H]Log` replays events and `[?]Help` opens the rules. Every view is content-first
with Back, and costs no turns or cash. World reads still settle elapsed resources.

Standings and rivals fetch ten players per batch; Next/Prev traverses both wrapped
terminal pages and batches, reaching crews beyond the old random fifty-row sample.
Each batch is a fresh current-season snapshot, so standings can move during a visit.
Help and territory use the same width/height-aware pagination, including onboarding
help. Viewing directories does not reset raid protection or acknowledge receipts.

**Action previews (issue Thiesi/NetBBS#362, slice 3).** Every action opens a free preview before
spending a turn. The final page offers `[A]Act`; Back and disconnect commit no action.
Previews show turn/cash cost, success stakes, Heat and bust probability. Exchange
odds use public garrisons; raids explicitly retain uncertainty about private crew
strength and cash. Jobs use the fixed contract and approach selected by the caller;
only their outcome is rolled on commitment.
Recruitment has no Heat/bust roll. Failed actions show the actual crew-loss floor.

Commit revalidates the actor's previewed cash, crew, turns, season and Rank as well
as the target selection. A conflicting action or incoming loss requires a fresh
preview. Ordinary elapsed Heat decay can lower the advertised risk. Action deltas
are calculated inside the committed transaction after income collection and include
bust losses; narration distinguishes gross payout from net cash/crew/Heat/Rank/turn
changes. Receiving an outcome never depends on another session-snapshot save.

**Contract board (issue Thiesi/NetBBS#362, slice 6; maintainer approved).** Run a Job opens
five fixed, repeatable contracts in ascending difficulty. The ladder is dial-up
access (difficulty 2, $60-$100 Standard payout), software warehouse (6, $100-$170),
billing database (12, $170-$280), bank transfer (20, $260-$400), and payroll
(30, $380-$560). Success probability is available crew divided by available crew
plus difficulty, bounded to 10%-90%; every success earns 15 season Rank.

After selecting a contract, choose Cautious (70% payout, +5 Heat, no ordinary
failure crew loss), Standard (100%, +15 Heat, one available member lost on failure),
or Bold (140%, +25 Heat, one available member lost on failure). Payout range ends
are rounded down to whole dollars. Approaches change stakes, not success odds.
Every attempt costs one turn and no upfront cash; the one-member floor applies.
A subsequent Heat bust can still take cash and crew, including after Cautious
failure, and its risk and losses are shown separately before Act.

The contract and approach pickers are free, content-first screens with Back.
The final preview shows selected terms, current odds, payout, failure losses and
Heat/bust stakes. Only Act spends or draws randomness, under the existing fresh
actor validation and atomic action transaction. A caller with no turns can still
inspect every offer and preview. Browsing, cancellation and reconnect never
reroll offers; fixed repeatability needs no persistent offer cache or migration.

**Crew development (issue Thiesi/NetBBS#362, slice 6; maintainer approved).** `[S]Kit` opens
the crew's specialty and support choices; `[C]rew` retains direct recruitment.
One crew-wide specialty is active at a time. Training or switching costs $150
and one turn: Phreakers reduce contract Heat by 3; Fixers recover $20 on a failed
contract, before any bust and without Rank; Lookouts reduce raid/root Heat by 3.
Training persists through ordinary crew losses and assignments until switched
or the competitive season resets. Buying the already-active specialty is rejected.

One consumable support slot holds either a $40 Burner Kit or a $75 Cash Stash;
each purchase also costs one turn. Occupied slots cannot be replaced or stacked.
A Burner Kit removes up to 10 added Heat after specialty reductions, floored at
zero, on the next committed job/raid/root attempt, win or lose. That attempt
consumes it even if fewer than 10 Heat were removed. Trade, recruitment, garrison
transfers and purchases do not consume it. Existing Heat still causes an ordinary
bust roll even if added Heat is zero. A Cash Stash is consumed only by a bust,
changing that bust's cash loss from 25% to 10%; crew losses remain unchanged.
Fixer recovery cash is included before bust losses. Neither purchases nor support
use earn Rank. Season reset clears specialty and support with competitive state.

The content-first crew screen shows effects, prices and current slots. A selection
is a draft until its final preview and Act. Stale-resource rejection retains that
selection for a refreshed preview. Cancelling and disconnecting purchase nothing.
Action previews account for specialty, support, its consumption and actual bust
stakes. Revalidation includes both slots; purchases and consumption share the
same transaction as action resources and turn cost. Schema 5 adds two bounded
choice columns, initially empty, without changing existing player resources or
identity. Upgrades and the version marker are atomic; earlier migrations remain
unchanged. Manual stop-session and verified-backup upgrade guidance applies.

**Recon and persistent operations (issue Thiesi/NetBBS#362, slice 6; maintainer approved).**
`[O]Ops` opens the operation slot, rival recon and private dossiers. Rival recon
costs one turn, no cash or Heat, with no bust roll or support consumption. It
settles the observed rival's elapsed resources and saves their cash and available
crew at commitment. Newcomer/raid protection does not prohibit recon and is not
removed by it. Only the observing caller can read the snapshot; its timestamp,
24-hour expiry and last-known status are always visible. This is not a live view
or a guarantee of current raid odds. Keep the latest ten distinct rival dossiers
per caller; another paid observation replaces that rival's prior snapshot. Free
inspection and raid previews use only unexpired earned intelligence. Season reset
clears dossiers, including dormant callers' data.

One PvE operation slot binds an existing fixed contract and approach when Case
commits. Case costs one turn, no cash or Heat; Prepare costs one turn and $50,
without Heat. Neither rolls outcomes nor consumes support. Execute costs one
turn and uses the ordinary approach's Heat/failure rules, including specialties,
Burner Kits and Cash Stashes. Success odds gain 15 percentage points, capped at
90%; success payout range endpoints double and success earns 30 Rank through a
separate monotonic operation counter. Fixer recovery on failure remains $20.

Success clears the slot. Failure returns it to cased: progress is useful, but
another Prepare ($50 and one turn) is required before retrying Execute. Abandon
is free, forfeits progress without refund, and requires its own final Act. Case,
Prepare and Execute each have a content-first preview and Act. Progress survives
visits and reconnects without forced waiting; browsing performs no random draws.
The slot and paid steps share the action transaction and stale-preview checks,
so racing sessions cannot use one preparation twice. Ordinary contract jobs remain
available independently. Season reset clears operation progress and its Rank.

Schema 6 adds operation progress/counters and a bounded indexed dossier table.
New state defaults empty; upgrades preserve existing identities, age, resources
and purchased crew/support state. Failed upgrades roll back the version and data
together. Backup/restore includes progress and dossiers; SysOp competition reset
and season advance clear them. The manual stop-sessions/verified-backup upgrade
procedure applies before activating this version.

**Short visits (issue Thiesi/NetBBS#362, slice 6).** Direct Trade, Recruit and Job keys remain
available alongside the optional operation hub. The switchboard and hub show
the minimum budget to the next execution: a new operation needs three turns and
$50, cased needs two and $50, prepared needs one and no further upfront cash.
These are attempt budgets, not promises of success; failure still needs paid
preparation. If turns or cash are short, the saved next step stays visible and
the caller is told that progress can wait. Zero-turn callers retain free browsing
of contracts, operations and dossiers. First-visit advice includes a one-turn
Cautious contract. No setup prompt or compulsory operation blocks ordinary play.

The deterministic mixed-visit probe combines specialty training, recruitment and
saved operations within fifteen paid turns per day. It measures the actual
transaction path and reports policy, outcomes and saved stage. Passing the probe
establishes bounded turn use and reachable progression; human satisfaction,
pace and multi-day balance remain separate acceptance gates in issue Thiesi/NetBBS#362.

**Compact action screens (issue Thiesi/NetBBS#362, slice 3).** Target pickers, results,
rejections and season notices use terminal-height pagination as well as width
wrapping. Digits 1-9/0 choose a complete visible target entry and open its preview;
Next/Prev traverses pages and Back returns without spending. A split entry cannot
be selected until its final line is visible. Already-owned exchanges and ineligible
rivals show their reason and have no active selection key.

Raid selection uses the same stable, bounded directory batches as browsing, so all
eligible crews are reachable beyond the former random fifty-row sample. Result
pages retain every net resource change until continued or left with Back. These
paths support 80x24, 48x14 and 40x12, including long names, wide/combining text and
large resource values; manual terminal/transport validation remains slice 9.

**First visit and recovery (issue Thiesi/NetBBS#362, slice 3).** New callers receive a short,
content-first guide to the map, action previews, trade/recruitment and free browsing;
the full rules stay in Help. The switchboard gives contextual next steps for no
turns, insufficient recruit cash, one remaining crew member, missing territory
income and high Heat. High-Heat guidance shows the cooldown until Trade adds no
bust roll; recruitment remains a no-Heat option, not an automatic recovery action.

Unavailable raid/root actions explain the refill before opening a target picker.
Recruit previews show the actual cash shortfall; empty rival worlds explain the
available non-PvP alternatives. Advice does not grant resources, spend turns,
change protection, or imply a waiting caller's snapshot updates continuously.

**Raid recovery and public intelligence (issue Thiesi/NetBBS#362, slice 5; maintainer approved).**
Every committed raid attempt gives its target a 24-hour recovery shield against
all attackers, whether the raid succeeds or fails. Rejected or cancelled choices
spend nothing and grant no shield. Eligibility, transfer/losses, shield, receipt
and turn cost share the action transaction: racing or alternating attackers cannot
bypass recovery. Login, resource refresh and receipt acknowledgement never remove
or extend it. At expiry the ordinary eligibility rules apply again. The existing
48-hour lifetime-account newcomer shield and own-tier +/-1 bracket remain; season
reset clears competitive recovery but never renews veteran newcomer grace.

Public intelligence is handle, season Rank/tier, protection reasons and exact
UTC expiry. The dashboard also shows remaining recovery time. Available crew and
cash remain private, so raid previews explicitly describe uncertain odds and
percentage stakes. Exchange ownership, garrison and income remain public;
raid recovery does not block territory contests. Paid recon grants only the
private, timestamped and expiring snapshots defined above; public directories
continue to withhold cash and available crew.

Schema 4 adds the recovery deadline. An old last-attacker marker has no attempt
timestamp, so upgrade preserves its protection for 24 hours from upgrade against
all attackers and leaves an explanatory receipt. Empty old markers grant no new
shield. Migration is atomic and idempotent; ordinary login does not clear the
last-attacker record or recovery deadline. No service or background timer is needed.

**Economy targets and rules (issue Thiesi/NetBBS#362, slice 5; maintainer approved).**
The full map must earn no more passive cash per day than fifteen average trades;
a player cannot receive repeat capture Rank from one exchange within a season;
recovery from a bust to three available members fits within fifteen low-risk
turns; defended territory retains the 10% minimum capture chance. These are
measurable constraints, not proof of fun or fair balance. Human multi-day
playtests remain required.

The ten hourly rates are $2, $2, $2, $3, $1, $2, $3, $2, $1 and $2 in map order:
$480/day for the entire map versus $495 expected gross from fifteen trades. A
capture attempt costs one turn and the role-specific cash price below, win or lose;
success additionally commits one available member. Ordinary recruitment costs
$75/turn; an owned Carrier Switch offers the service below. Expansion competes with
recruitment and defense for the same cash budget. Trade pays $20-$60 without
a cash prerequisite for the first three Trades of a turn-day; each later Trade in
the same turn-day lowers the top of the range by $5, to $20-$40, and the count
resets with the turns (issue Thiesi/NetBBS#649, world schema 11). Twelve Trades in a row had
taken a first visit from $300 to $728 with no bust risk, so cash was a solved
problem from the first session even though Trade earns no Rank. Only the top
moves: the $20 minimum is what bust recovery is sized on, and the taper keeps
fifteen Trades above the map's $480. A steeper cut ($5 off both ends per Trade,
to $5-$15) was rejected because it broke both targets. After a bust resets Heat,
even minimum trade payouts fund recovery from one to three available crew within
ten turns.

A first successful capture awards 50 Rank per player/exchange/season. Holding
territory earns one Rank per six exchange-hours, combining fractional time across
holdings and visits. Transfers pay the prior owner's earned cash/control Rank in
the same transaction and retain fractional credit. Losing, withdrawing or busting
does not remove earned Rank. Offline owners are settled before standings and raid
brackets are presented; commit checks settled raid eligibility. Cash settlement
and control time share the ownership timestamp, so inspection cannot multiply
rewards. Normal season reset clears the new counters and capture IDs.

Schema 3 pays accrued income at the old stored rates before installing new rates;
control Rank starts at that boundary, without retroactive awards. Existing capture
Rank is preserved with a legacy credit of 450 points per old rewarded capture.
The old aggregate counter cannot identify every previously captured exchange and
retained receipts are not a complete ledger: players with prior capture awards
therefore receive no additional capture awards until next season, when all ten
become available again. A history receipt explains this transition. Cash, real
crew assignments, identities and account age survive, subject to ordinary overdue
season reset. All changes and the version marker commit together.

**Exchange identities (issue Thiesi/NetBBS#362, slice 7; maintainer approved).** The existing
ten exchanges form a fixed ring in stable ID order, including the last-to-first
link. Every exchange remains attackable regardless of adjacency, tier or raid
shield. Owning either linked neighbor discounts a capture attempt by $10;
owning both does not stack. Ownership and the selected price are checked again
inside the capture transaction. The map shows real links, current owners,
assigned crew, security, effective defense, income, prices and services.

| Role | Sites / income | Capture cash / base Heat | Owner-only service |
| --- | --- | --- | --- |
| Public PBX | Two, $1/hour each | $25 / +4 | Lay Low: one turn removes up to 15 Heat, floor zero |
| Carrier Switch | Six, $2/hour each | $50 / +8 | Recruit one available member for $65 and one turn; +10 Rank |
| Warez Hub | Two, $3/hour each | $75 / +12 | Warez outlet: one turn, $30-$70 gross payout, +4 Heat; no Rank |

Owned Carrier Switches add two visible security points to capture defense.
Security is not living crew: it cannot be withdrawn, does not return to a
displaced owner and does not multiply the shared crew pool. Unclaimed sites
retain guaranteed capture; defended contests retain the 10% chance floor.
Capture Heat still applies Lookouts/Burner benefits. Services require ownership
at Act and preview their stakes. Lay Low and recruitment have no bust roll or
support consumption. The outlet uses ordinary trade bust rules: Burner and
specialty benefits do not apply; Cash Stash applies and is consumed only on a
bust. No additional passive bonus is introduced. Cash, turns, Heat, crew, Rank
and support changes share the existing action transaction.

Schema 7 assigns roles in original map order, retaining IDs, names, hourly rates,
ownership, crew, earned resources and receipts. It rejects a nonempty map with
other than ten sites without mutation. Roles and ring identity survive season
reset; ownership and competitive resources reset as before. The version marker
and role assignment commit together; shipped migrations remain unchanged.

**Neutral operators (issue Thiesi/NetBBS#362, slice 7; maintainer approved).** Three fixed,
explicitly labeled NPC crews defend home sites at season start: Patch Panel
Society at Thiesi/NetBBS#5 Public PBX (2 defenders), Night Relay Union at Thiesi/NetBBS#6 Carrier Switch
(4 defenders plus its ordinary 2 security), and Spool Archive Collective at Thiesi/NetBBS#7
Warez Hub (6 defenders). Home positions follow original stable map order. NPCs
use exchange state, never synthetic player accounts: they have no cash, income,
Rank, human standings entry, raid eligibility or available crew pool. They never
attack callers and never take a human-owned exchange. (Superseded for their own
homes by "Operators push back" in the overhaul section: an operator tests a home
whose defence is weaker than its crew. They still raid nobody.)

Capturing an NPC home uses the ordinary role price, neighbor discount, Heat,
crew losses and once-per-player/exchange/season Rank award. Defense is public and
previews show exact odds, including the ordinary 10% floor. Displaced NPC guards
leave the scene; they cannot become human recruits. A captured home is an ordinary
human holding with its income and service. Withdrawing its final defender leaves
it unclaimed for 24 hours; the map shows the return deadline. If still unclaimed,
its fixed NPC crew returns with its original defenders. A human capture cancels
the pending return. Homes start defended again at season reset. Non-home sites
never receive neutral crews.

At each normal world boundary, at most three home rows are checked under the
existing write transaction. Returns require no background task, random draw or
per-missed-day replay, and cannot reroll a defense through browsing/reconnect.
A return between preview and Act rejects stale capture terms without spending.
Fixed repeatable jobs and operations remain available with no humans to raid or
unclaimed sites to take. These rules provide bounded PvE contention without
inventing human activity; they do not establish whole-season balance.

Schema 8 adds neutral occupancy and a return deadline. Upgrade places NPCs only
in their unclaimed homes, preserving every human holding, identity and resource.
Fresh worlds and rollover populate the same three homes. Deadline, occupancy,
defenders and version marker commit atomically; backups preserve them and SysOp
competition reset uses the same season boundary. Older migrations stay immutable.

**Scene and crew identity (issue Thiesi/NetBBS#362, slice 7; maintainer approved).** A caller
chooses one of four fixed ASCII insignia: Modem `[::]`, Relay `<-->`, Signal
`=||=`, or Archive `{##}`. The default is Modem. It is a free cosmetic choice,
previewed before Act, with no turn, cash, Heat or Rank cost. It remains part of
identity through ordinary seasons and explicit competition reset. Identity also
shows the existing handle, current Rank/tier and trained specialty; no new
player-authored text is introduced.

The free `[I]Scene` screen offers insignia, three neutral-operator dossiers and
public territory bulletins. Dossiers combine fixed fictional biographies with
actual home ownership, defense and any pending return deadline. A human-held
home is described as displaced, never as an NPC takeover in progress. Cosmetic
identity, static biography and current facts must remain distinguishable.

Only committed captures, final-defender abandonment and NPC stationing create
public bulletins, in the same transaction as the underlying change. Each includes
UTC time, season and bounded sanitized names; no cash, available crew, recon,
job results or private receipts are published. Keep the latest 500 per world,
ordered by committed row ID, without age expiry. Normal rollover retains this
bounded history and labels new-season events; explicit SysOp competition reset
clears it with private receipts. Empty/old worlds get an honest empty bulletin
board: migration never fabricates historical events. NPC initial stationing and
actual returns are labeled NPC activity, with no synthetic human accounts.

Schema 9 adds the persistent insignia and bounded scene table transactionally.
Backup/restore includes both; reset retains insignia and clears scene history.
Synchronous storage rules and free, content-first paginated browsing remain.

**Season results and awards (issue Thiesi/NetBBS#362, slice 8; maintainer approved).** Before
rollover, publish the UTC end time and the existing standings order: descending
season Rank, then ascending account ID. Award cosmetic Gold, Silver and Bronze
to the first three placements with positive Rank. Fewer than three qualifying
players means fewer medals; zero Rank never receives one. Medals grant no money,
crew, protection or other permanent gameplay advantage.

Under the existing rollover write lock, settle each existing human owner's final
territory earnings through the outgoing season's cutoff before computing final
Rank. Archive one snapshot for every player in that season, including dormant
players: account ID, historical handle (bounded to 80 sanitized characters), Rank,
placement, medal and insignia. Cash and available crew are not in the public
archive. Later renames, deletion of a live game row, resource changes or cosmetic
choices do not rewrite historical results. An orphaned exchange cannot credit a
missing player; reset still clears that stale holding.

Archive insertion, final earnings, competitive reset, neutral-home population and
active-season marker commit together. Any failure preserves the previous world.
Repeated/concurrent boundary visits must produce exactly one result per player.
Keep the latest twelve completed season numbers, deleting their result rows with
evicted headers. For skipped, unmaterialized seasons record only an inactive
header with no players or invented winners; process at most the retained twelve
headers regardless of absence length. Upgrade creates no fictional past results.

Schema 10 creates the archive tables. The current standings and dashboard publish
awards in advance; `[I]Scene / Season results` shows retained season status, cutoff,
podium and the viewing caller's placement. Archive records are snapshots, never
updated by ordinary play. Existing stop-sessions/verified-backup procedures apply.
SysOp advance/reset first settles overdue seasons at their published natural
cutoffs, then closes the current season at the operator-selected boundary
and retains cosmetic archive recognition while resetting competitive resources.
Older worlds remain operable before upgrade; unknown past results are not backfilled.

Each archived player receives an unread private crackdown receipt with season,
final Rank, placement and medal, committed with the archive/reset transaction.
The existing latest-500 receipt limit applies. Explicit SysOp competition reset
clears these receipts while preserving archived cosmetic recognition.
From `[I]Scene`, `Your season reports` lists the caller's historical results,
retained medal counts and best retained Rank/placement; `Hall of Fame` lists the
actual positive-Rank medal winners grouped by season. Both are free, paginated
views of the same latest-twelve-season archive, with historical handles and
insignia and no new scoring or gameplay advantage. Empty archives explain when
results arrive. The crackdown screen points callers back to the switchboard's
Log and Scene for the receipt and recognition; reading these views does not
acknowledge private receipts or spend turns.

During the final 48 hours, the first switchboard page starts with a compact reset
countdown. Subsequent lines explain the end time, a Cautious-job
entry point needing no rival or territory, and the expiry of competitive resources
including territory, assigned crew, training, support and all saved operation
progress (cased or prepared). Zero-Rank fresh-season
callers with unused turns see their current resources and actionable job/trade routes.
Help explains that newcomer protection follows preserved account age and is not
renewed by rollover. These cues change no payout, protection, award or reset rule.

**The War Dialer presentation contract (issue Thiesi/NetBBS#494; supersedes the issue Thiesi/NetBBS#362
slice 9 wording).** The door is a phosphor terminal, not a page of sentences.

*Palette.* Nine roles, truecolor as the design target, each with a deliberate
256-color index beside it rather than whatever a converter would pick:
`phosphor` `Thiesi/NetBBS#39ff14` (your holdings, positive deltas, the scanline's glow),
`phosphor-dim` `Thiesi/NetBBS#4e8a62` (the frame, ring links, gauge tracks), `mint` `Thiesi/NetBBS#7dffb0` (headings,
your handle, the cursor), `amber` `#ffb000` (money and hotkeys), `cyan`
`Thiesi/NetBBS#38d6ff` (NPC operators and neutral data), `magenta` `#ff3caa` (rival crews and
raids against you), `alarm` `#ff4d4d` (losses and bust risk), `ink` `#d7ffe9`
(values) and `grey` `Thiesi/NetBBS#8a8fc4` (labels). A hotkey is always amber and bold. An
exchange's owner color is the same on the ring, in the table and in the feed.
Chrome never shares a color with content.

The label role is the one that must not be drawn from the screen's own hue
(issue Thiesi/NetBBS#519). It was `Thiesi/NetBBS#7f9a8c` -- 256-index 108, which is `Thiesi/NetBBS#87af87`, sage green
-- so labels were specified as a green to sit on a green screen and vanished
into it: measured on the switchboard, phosphor, phosphor-dim, mint, ink and
that label color were 78.5% of visible characters in one narrow band. A cool
slate is off-hue from every green and clear of the established meanings of
amber, cyan, magenta and alarm.

The frame is chrome, and chrome wears `phosphor-dim` (issue Thiesi/NetBBS#519, the second
half). It was drawn in `phosphor` -- the same color as a holding or a gain,
and the brightest green on the screen -- so the border was 36.7% of the
switchboard's visible characters and the rule that chrome never shares a color
with content did not hold for the frame itself. `phosphor-dim` was retuned from
`Thiesi/NetBBS#1f7a3f`, a dark fully-saturated green, to a desaturated mid green so a border
is legible but recedes; `phosphor` now means only what a caller reads. The
scanline still fades mint to phosphor to phosphor-dim, and the ring's links and
every gauge's empty half stay in the chrome role they always had. The
switchboard before and after is kept as
`docs/images/door-chrome-519-war-dialer-switchboard.png`, and the four chrome
colors side by side as `door-chrome-519-swatch.png`.

*Glyph vocabulary.* Frames `┌─┐ │ └─┘ ├─┤`; owner nodes `◆ ◈ ◉ ◇`; crew `●○`;
turns `▮▯`; meters `█░`; the scanline's ramp `▓▒░`; sparklines `▁▂▃`; insignia
and badges `⟦ ⟧`; ring links `═ ║`; the brand `▚`; the prompt `›`. Every one has
an ASCII substitute, and the `ascii_art`/`plain` preset is the one place that
can prove none was forgotten.

Frames are **light**, not heavy (issue Thiesi/NetBBS#517). A run of heavy `━` shows visible
gaps at the cell seams in many monospace fonts, so the border read as a failed
render rather than a box -- reported from a real terminal on which Voidrunner's
light frame is clean. The scanline draws the ramp above rather than the frame's
own glyph: it used to be a run of `━` inset two columns and joined to nothing
between two borders made of the same character, which read as a border that had
failed to draw. Block elements are full-cell by construction, so they cannot
show those seams, and a ramp fades in density as well as color -- which is the
only fade that survives the monochrome preset, where a role returns no SGR at
all and the old three-band version was perfectly flat.

The ring closes. Its stems stand in the same columns as the nodes they join --
a node cell is three columns and a link two, so node `i` begins at `i * 5` --
rather than at the row's extreme ends, where they sat two columns past the last
node and left the loop reading as two chains with a pair of verticals floating
between them. No corner glyphs are needed: the node glyph is its own corner.

*Components.* The door carries its own copy, like every other helper in its one
self-contained file: `meter`, `pips`, `dots`, `sparkline`, `label_value`/`chip`,
`badge`, `progress_chain`, `owner_node`, `scene_map`, `table`, `feed`, `key_bar`,
`compose` and `prose_rows`. Each returns *styled* rows. The frame leaves a row
that already carries SGR exactly as its component built it; wrapping every row
through a plain-text flattener and coloring the whole line from outside is what
turned the game into one grey block inside a green box. Rows are composed at the
frame's own inner width, because the rows a card produces are the rows its page
budget is computed from.

*Layout.* The switchboard is a card stack, not a paragraph list: an operator card
with a rank gauge, a resources card of meters and chips, the ten exchanges as the
ring they actually are, the latest receipts as a toned feed, then orders and the
season's absolute deadlines. A card's opening rule costs a row of the same height
budget as the rows under it. Numbers are right-aligned in their column and a
table's columns start at the same display column on every row; a table chooses
which columns it can carry at the width it has, and everything a narrow terminal
gives up is on the record's own card one digit away. Action bars live outside the
frame, where the cursor waits.

*Clocks.* Every absolute instant is shown in the node's display timezone, which
the drop file supplies as an IANA name (`timezone`, door_api 2), and names the
zone it is showing -- a deadline in unlabelled local time is more ambiguous than
one marked UTC, not less. One helper converts, so a new screen cannot
reintroduce a fixed zone by copying the line above it, which is how fifteen of
them came to print UTC while the rest of the node showed local time. An absent
or unresolvable zone falls back to UTC and still renders: `zoneinfo` has no
system database on Windows and depends on the `tzdata` package, so a door that
raised there would fail on a healthy node. Relative durations carry no zone and
are unaffected.

*Motion.* This replaces "there are no animation delays". Reveals and the carrier
sweep that plays while a committed result comes back are in, under three hard
limits: any key skips whatever is playing, Fast mode and the monochrome/plain
presets omit it entirely, and nothing animates between a caller's decision and
the commit -- a result is written to the database first and only then revealed.
Motion is forward-only except for one row it rewrites in place and owns, so the
screen a caller is left looking at is identical whether motion played, was
skipped, or was never enabled.

*Launch splash.* The one exception to forward-only motion is the splash a
session opens with: the call dialing out, the handshake, `CONNECT`, the
masthead burning in and the ring of ten exchanges lighting in its holders'
colors, drawn by cursor-addressed cell updates for about two and a half
seconds. Left to run to its end it holds its last frame, with "press any
key" where "any key skips" stood, until a key is pressed or input ends; it
is then cleared, so it leaves nothing behind on the screens that follow. Any
key ends it and is consumed whole; it is omitted under every preset
that omits motion, and whenever input is already waiting or stdin cannot be
polled without reading it, so it never takes a keystroke meant for a later
screen. A frame is written at least every 50 ms until the last one: the
animation is never silent, so a driver that waits for output to settle does not
type into it. Only the finished picture is quiet, and that is a screen waiting
for its key like any other.

*Presets.* Scene offers a free Display screen with immediate ASCII-decoration,
monochrome and Fast-mode toggles. Back writes nothing. Store one bounded boolean
preference object per caller in world metadata; preserve it across season and
competition resets and include it in the world backup. No competitive state or
archive row is modified. ASCII mode substitutes for every glyph in the vocabulary
while preserving caller names; monochrome removes color at the source -- a role
returns no SGR at all -- while retaining the screen controls the terminal UI
needs. Every status, stake and outcome is readable without color. Fast mode is
the one deliberately unframed layout: it omits optional art, flavour and motion
and keeps every stake and net delta, and its title row carries the page counter
the border would otherwise hold. Normal action results may add a short fictional
vignette. War Dialer reads the optional boolean `unicode_style` from the launch
metadata every door receives (§6, the `door_info.json` contract). False
defaults to ASCII decorations; true or omission preserves the rich default. An
explicit in-game ASCII choice wins. Changing monochrome/Fast alone does not
freeze the inherited Unicode default. The native-door JSON boundary and
supervision are otherwise unchanged.

*Review.* A screen is reviewed by looking at it. `scripts/door_gallery.py
war_dialer` renders every screen at 80x24, 64x20 and 40x12 in every preset, and
a change to a screen comes with that page attached. The suite can assert that
color reaches every body row, that hotkey, label, value and frame are four
different colors, that an exchange reads the same color everywhere, and that a
table's columns do not wander -- what it can never assert is that a screen is
worth looking at, which is why the pictures are required.

**Screen framing and one hotkey style (issue Thiesi/NetBBS#487; extended by Thiesi/NetBBS#494).** Every
screen under the masthead -- the switchboard, the help and first-visit text, the
event log and the record picker -- draws its body inside the door's frame, with
its title in the top border and the action bar outside, below it. The switchboard
overhaul had left the masthead framed and everything under it an unindented wall
of rows. The frame costs two rows and four columns, charged to each screen's own
page budget, and is dropped only in Fast mode, which is deliberately text-only:
there is no narrower terminal to drop it for, since 40x12 is the floor (issue
Thiesi/NetBBS#495). One frame holds a stack of cards: the screen's title goes in the top
border and each card after the first is opened by a `├─ HEADING ─┤` rule, which
costs a row of the same budget as the rows under it. The border's right-hand end
carries the page counter first -- always spelled `page N/M`, and the handle a
scripted walk uses to know whether there is another page -- and then whatever
else the screen wants to say, for as long as it fits whole; a counter cut in half
tells a caller nothing, so the screen's own name is the half that truncates.
Hotkeys are written `[K] Label` everywhere the door prints, the rule Voidrunner
adopted in issue Thiesi/NetBBS#400: the key is not always the label's first letter
(`[E] Map`, `[X] Root`), so that is the only spelling that carries every case.
The switchboard's action bar is laid out on a grid rather than hand-typed or
packed to the width (issue Thiesi/NetBBS#517): every cell begins a column, so the keys line
up down the screen instead of landing wherever the previous label happened to
end. Columns are sized to their own contents, not to one global cell -- a single
wide label among short ones would otherwise pad every column to its width. Full
labels first, short labels when the full ones would not leave the page a row to
stand on, and full labels kept when shortening would not actually save a row:
spending the labels *and* the row is the worst of both. Every key keeps a name at
every supported size; the keys-only tier below that went with the terminals it
was for (issue Thiesi/NetBBS#495). A key is never dropped. Alignment costs a row where packing
fit one more entry per line, and that row comes out of the page's content budget:
fifteen entries with full labels need eight columns to fit two rows, and eight
columns of their own widths do not fit eighty. Paging shares the switchboard's prompt row rather than its action bar,
which is already four rows of a twelve-row terminal. A bar written with
`out_prompt` leaves its row unterminated on purpose, so whatever reads it has to
close that row before the next screen draws; the first visit every caller saw had
printed the Back bar and the switchboard's own title on one row.

**Shared crew defense (issue Thiesi/NetBBS#362, slice 5; maintainer accepted).** A player's
living crew is the available crew plus the members assigned across their owned
exchanges. Capture requires at least two available members and commits one to the
new garrison. Available crew alone determine job, raid and territory-attack
strength, and take failed-action/bust losses. Assigned crew defend only their own
exchange. Defenders displaced by capture return to their owner's available pool
in the same transaction as ownership transfer and earned income. This gives an
offline loser a recovery resource without duplicating members or raising Rank.

`[G]arrison` is a content-first owned-exchange picker followed by bounded crew
transfer choices and an explicit action preview. Reinforcement/withdrawal costs
one ordinary turn, no cash or Heat, and earns no Rank. One member must remain
available. Withdrawing the last defender abandons ownership after paying earned
income; it cannot leave a free, unstaffed income source. Capture awards are once
per player/exchange per season, including recaptures
after another owner or voluntary abandonment. The persistent per-player list has
at most ten exchange IDs; only a successful first capture adds an ID.
Previews show the actual Rank award, both pools,
the resulting defense and abandonment. Commit rechecks resources, season and
ownership. Back/disconnect spends nothing. The dashboard shows available and
assigned crew separately; action results distinguish transfers from losses.
Voluntary transfer receipts are retained as read history, avoiding an unread
self-notification; incoming rival and upgrade receipts remain unread.

Version 2 converts legacy copied garrisons atomically, after any normal overdue
season reset. For each remaining owner, preserve the real crew total, reserve one
available member, and retain as many holdings as can receive at least one defender.
Priority is descending hourly income then exchange ID. Divide the remaining crew
budget evenly among retained holdings, giving remainder members in that order.
Pay earned income before releasing unstaffable holdings and leave a history
receipt with assigned/available and released counts. Cash, monotonic Rank, IDs,
handles and account age survive conversion; no copied garrison becomes a recruit.
The version marker and all conversion changes share one transaction. Old processes
must be stopped and a verified backup taken before activation. Host ownership and
maintenance checks precede conversion. Defense alone does not establish balanced play.

**World schema compatibility.** SQLite `user_version=1` identifies the original
War Dialer schema; the current version is 13. `user_version=2` added shared-crew
resource semantics without
changing its column layout. A complete unversioned world is adopted through a
numbered migration; its additive fields, retained history and version marker
commit together or roll back together. New empty worlds use the same migration.
Future schema versions, incomplete/unrelated layouts and failed SQLite integrity
checks are refused before initialization or journal-mode changes. Startup never
replaces an unreadable world with an empty one. Recovery preserves the original;
use compatible game code or a verified backup, with sessions stopped.
