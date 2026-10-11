# War Dialer engineering notes

Extracted from the NetBBS worklog; issue references belong to NetBBS.

World adoption writes `meta.node_owner` and, for standalone worlds,
`meta.self_owned=1` together under the existing immediate transaction.
Legacy host worlds have an owner without the self-owned marker; never infer
self-ownership just because a launch supplies no host token. The game binds
or validates ownership before loading a player.

CP437 conversion happens at `out`, after layout. Authored replacements must
therefore preserve display columns. The source-literal test requires explicit
forms for new screen glyphs, while the separate arbitrary-name fallback
preserves wide/combining-character widths. Do not use low CP437 control bytes
as decorative symbols. NetBBS owns terminal conversion and always receives
UTF-8, even when a caller saved a CP437 preference outside the host.

Administration lives in `administer_world`, also called by `--admin`.
Mutations hold the exclusive session guard and record their audit in the same
transaction. A season close or reset first takes a SQLite backup, including
committed WAL pages, before opening the write transaction. Backing up from the
same connection inside its write transaction can stall. A failed mutation
rolls back its audit too; its completed snapshot remains for recovery.
`inspect_world` validates without creating, migrating or settling a world.
NetBBS retains node-path, ownership and complete-node-backup policy.

Windows input lookahead uses `PeekNamedPipe` before an unbuffered read.
Python 3.11 has no Windows `os.set_blocking`, and Windows `select` accepts
only sockets. Real-pipe tests cover idle timeout, queued control sequences
and closed-writer EOF; newer Python alone misses the compatibility failure.
The same non-consuming peek now enables the splash on idle Windows pipes.

DOOR32 type 2 borrows the inherited socket without changing its blocking
mode or calling shutdown: closing the door's handle must leave the host's
connection available when the game returns. Telnet parsing carries its small
state across timed reads and discards negotiation before the hotkey parser.
Output is encoded first, then IAC bytes are doubled. Carrier loss follows
the EOF exit path and releases the world session guard. Actions commit in
their existing domain transactions before result output; previews do not
write a partial action on disconnect. Real inherited-socket subprocess tests
cover a full visit and a carrier drop at an action preview.

Both bundled games require 40x12 and have one layout above it (issue Thiesi/NetBBS#495). The
second, stripped presentation they carried for terminals down to 20 columns is
what flattened them -- every "make it fit" decision was taken for a caller nobody
has, and the stripped result was what everybody saw. There is no compact variant
to add to a new screen: a screen that will not fit 40 columns is redesigned. The
refusal happens before a save directory or world is opened, so a caller who
resizes loses nothing. `tools/door_gallery.py` renders every screen at every
supported size into one page, and is how a presentation change is reviewed --
the suite can assert that a screen fits, never that it looks like anything.

**Color has to reach the body row, and that is a structural property, not a
coat of paint (issue Thiesi/NetBBS#494).** War Dialer's screens used to be built as plain
sentences, wrapped by a flattener that stripped ANSI by construction, and then
colored one color per row from outside the frame -- so nothing inside a row
could ever be a different color from anything else, and the whole game read as
one grey block inside a green box. The fix is that a component returns *styled*
rows and the frame leaves a row that already carries SGR exactly as it arrived.
Three invariants hold it in place, and each one is a test that can fail:

- Every body row a screen prints carries at least one SGR sequence. Check the
  row *between* the frame's sides: a screen that is grey inside a green box
  passes any assertion that looks at the whole row.
- A hotkey, a label, a value and the frame are four different colors, and an
  exchange's owner color is the same on the ring, in the table and in the feed,
  because one function (`owner_node`) decides it for all three.
- Segments are composed independently and each closes its own style. An SGR
  reset does not restore an outer color, so passing an already-styled value
  into a helper that wraps it in another color colors its head and then loses
  the color entirely at the first internal reset. `label_value` and `table`
  detect an already-styled argument and leave it alone for exactly this reason;
  a styled table cell also cannot be truncated (the cut would land inside an
  escape sequence), so its own width is the floor its column can shrink to.

**Rows are composed at the width the page budget was computed from.** A card
builds its rows with `compose`, which breaks *between* styled chunks, never
inside a gauge or a chip; `table` fits its columns; `prose_rows` wraps. The frame
clips an over-wide row rather than wrapping it, deliberately: a row that silently
became two would break the height budget already spent on it, and a frame with
one side missing is the worse failure. A card's opening rule costs a row of the
same budget as the rows under it -- a frame that draws rules nobody charged for
overflows its terminal by exactly the number of cards on the screen.

**Motion is allowed, under limits that keep it out of the way (issue Thiesi/NetBBS#494).**
It runs strictly after the commit, it is forward-only apart from one row it
clears the screen for and owns, and any key skips it -- which means the beat
between frames is a *read* with a timeout, not a sleep, so the keystroke that
interrupts it is consumed as the skip instead of being left in the buffer to act
as a hotkey on the screen underneath. Two traps: a carriage-return-rewritten row
looks like one enormous row to anything that splits output on `\r\n` only (the
visible row is what follows the last `\r`, which is why each frame is padded to
a constant width), and motion written *under* the screen the caller pressed a key
at spends rows that screen's height budget already owns.

**A skip key belongs to the screen behind it, or to nobody.** Handing the
keystroke that interrupted motion to the next reader is right where an
acknowledgement follows immediately -- a result screen -- and wrong where the
reveal has no reader of its own. The masthead's reveal is followed by whatever
screen the caller has not chosen yet, so handing its skip key on would
acknowledge a page of unread receipts or skip a page of the first-visit guide
that nobody pressed anything on. `reveal(..., hand_back=False)` marks that case.

**A preview's prominent summary has to be the stakes of the step being
committed, not of the flow it belongs to.** Two instances of the same mistake
came out of one shared stakes builder: an owner service previewed a Warez Hub's
Heat and bust roll at a Public PBX, whose service removes Heat and rolls for
nothing; and a three-step operation previewed the execution's odds, Heat and bust
above a Prepare step that has none and costs $50 the card showed as $0. A card
this prominent contradicting the terms directly under it is worse than no card.

**A picker's first page must offer a choice, and the screen's own summary card
is what gets given up for it.** How many entries fit a page depends on the
terminal, so a card above them that is affordable at eighty columns pushes every
choice onto page two at forty. `pick_record_page` measures the rows the *first*
selectable entry needs and drops the summary, then the heading, until it fits --
not "drop the summary when the whole list would then fit", which is the weaker
rule that let a three-entry approach picker open with nothing to press.

**A walk can name a place or an entry, never a page number.** The same
size-dependence makes a fixed key sequence wrong at some size: `I5` opened "Your
season reports" at eighty columns and pressed a key the picker was ignoring at
forty. `tools/door_gallery.py` therefore takes two suffixes -- `N*` presses
until the screen stops changing, and `5?` pages forward until the screen *says*
it will accept `5`. Read that from the hint row, not from the frame: Fast mode
has no frame, and an entry's own `[2]` marker is on the screen while the entry's
last row, and so its key, is on the next page.

**One width rule, or a budget is a guess.** `_dlen` and `_fit` each carried
their own "two columns above U+2E80" shortcut while `_wrap_output` measured with
`unicodedata.east_asian_width`. A Hangul choseong (U+1100) is two columns and
sits *below* the cutoff, and a combining accent is zero; a handle of either was
budgeted as one row, wrapped into two by `out_line`, and scrolled a twelve-row
terminal's footer away. Both now delegate to `_char_width`. Any new measuring
helper does the same -- a second rule reintroduces exactly this.

**A preset that changes the frame changes the width.** Fast mode is the one
unframed layout, so a screen that caches `_panel_width` across its own toggles
composes the next redraw for the wrong terminal: turning Fast off inside the
Display screen clipped the setting descriptions. Recompute after `apply_display`,
not before.

**The gallery fixture has to be far enough into the game to reach the screens.**
A brand-new War Dialer player owns nothing, so `G` was a panel of "No exchanges
held" at every size and preset while the garrison picker, Exchange Control, the
transfer preview and the owner service -- all rebuilt -- appeared nowhere. The
fixture's onboarding keys now capture exchange 1, which is unclaimed in a fresh
world and therefore a certainty rather than a dice roll. That also makes the
holdings and income gauges non-zero in every panel. The consequence to remember:
a walk's digits depend on the fixture's state -- `X1?` stopped working the moment
exchange 1 became the caller's own -- and `?` is what turns that into a failed
build instead of a panel of the wrong screen.

**Raid authorization is domain logic.** `resolve_raid` reaches
`raid_eligibility_reason` through `is_eligible_raid_target`, so the helper they
share cannot live below the file's UI-layer marker: a presentation-only edit
would otherwise be able to change whether a raid is permitted. A test asserts the
source order, because that is the actual invariant.

**A gauge that caps has to cap proportionally.** Clamping the filled count and
the total independently lit every dot for ten available crew beside ten posted --
a gauge reading "all of it" for exactly half, and showing no movement at all
across a large transfer. `dots` and `meter` both scale the fill to the capped
total, keeping "some is never none" and "not all is never all".

**A preview's Heat is a signed change, not an addition.** A Public PBX's Lay Low
*removes* up to fifteen, which is the whole reason a caller opens it; treating
every service as an addition left the prominent gauge at the Heat the terms
immediately below promised to reduce. And a warning chip is judged on what the
action would *leave*: at 79 Heat a trade crosses the threshold and rolls, so
"near bust" was the wrong word for it while the advice on the same screen already
told the caller to wait.

**A gallery fixture that grows invalidates any walk that names a number.** `X1?`
broke when the fixture captured exchange 1, and `X2?` broke when it captured 2 --
the picker marks the caller's own holdings `[-]`. A walk that wants *an* entry now
says `#` (press whichever key the screen offers, paging to find one) instead of
naming a digit. Keep a digit only where the identity matters, such as the scene
hub's seventh entry being the Display screen.

**A test that drives the door by reading its own output has to read what a caller
reads.** Once a bar is styled segment by segment, `[A] Act` is a hotkey in amber
followed by a label in mint and is no longer a contiguous run of bytes on the
wire; a scripted walk that matched raw bytes silently stopped finding it and
looped on the page it was already on. Both harnesses strip SGR before matching --
the in-process one with `_last_screen`, the subprocess one with a byte-offset
index so the raw bytes consumed are still tracked exactly -- and a walk that has
to accept a preview presses Next until the Act bar appears rather than assuming
the stakes fit on one page.

**A walk photographs one screen: the one it is looking at when its keys run
out.** Passing *through* a picker on the way somewhere else therefore reviews
nothing of it: a walk that ends on a preview reviews the preview, not the two
pickers it crossed to reach it. A screen on the way to another screen needs a walk
that stops there. A test reads the screen titles out of
the door's own source -- every `show_text_pages` and `pick_record_page` call, so
that a screen added tomorrow is found without anyone remembering to list it --
and fails unless each is either
photographed or excused in `UNREACHABLE` with the reason one cached fixture
cannot reach it (it cannot be both mid-operation and idle, both populated and
empty, both solvent and too poor to act). An excuse that stops being true fails
the test too, because a stale excuse hides the next gap.

**A caption is a claim about a picture, so the build checks it.** Every walk
declares in `SHOWS` what its screen must say, and the gallery reads the *painted*
panel back -- through the same emulator that renders it, because a styled heading
is not a contiguous run of bytes on the wire -- and refuses to publish a panel
that does not say it. Without that, a walk whose keys land somewhere else
publishes the wrong screen under the right caption and reads as a completed
review. A door with a `SHOWS` table must name every one of its walks, so a new
walk cannot be added unchecked.

**A page of a card stack is a screen, and fast-forwarding past it reviews
nothing.** `N*` presses Next until the screen stops changing and the gallery keeps
only what is on it at the end, so the switchboard published pages one, two and
fourteen of fourteen at forty columns: the scene, the feed, the orders and most of
the season card were in no panel at any size, and the rules were twenty-two pages
of which two were reviewed. The `%` suffix photographs the screen and every page
after it, one panel each, captioned with the page number. It is for the screens
where paging changes *what kind of information* is shown -- a card stack, the
rules, a preview's stakes and then its terms -- and deliberately not for a table,
where page two is the same drawing with the next rows in it and a second panel of
it costs a panel and teaches nothing.

**A panel's state is the fixture plus the keys a walk presses into its own copy of
it.** Every panel gets its own copy of the world, so a screen that exists only in
another state is reachable by playing into it: `SETUP` presses a whole operation --
contract, approach, preview, Act -- in a separate launch against that copy, at one
fixed size, and throws away what it draws, after which the photographed walk opens
the in-progress screens. "The fixture is not in that state" is therefore not a
reason to excuse a screen. What no sequence of keys reaches is: fifteen spent
turns, an emptied wallet, a season rollover, a world with no rivals in it.

**A skip of a transition is not an acknowledgement of what follows it.** A
reveal hands its skip key back, so one press both finishes the reveal and answers
the screen being revealed. The carrier sweep is the other case: what follows it is
the receipt for the turn just spent, whose bar takes any key, so handing the key
back meant a caller who skipped the animation never saw what their turn bought.
The sweep consumes the whole input unit instead. The rule that decides it is
whether the thing after the motion is the same screen the motion was drawing.

**A selector has to see the screen in every spelling it is drawn in.** The plain
preset draws the frame in ASCII, so an entry row starts `|` where Unicode starts
`┃`; stripping only the Unicode edge left a character before every `[K]` marker and
no walk that names an entry by what it is could find one. The whole build died on
the first such walk, under one preset out of four -- which is the argument for
building every preset rather than sampling one.

**"Until it stops changing" is the wrong end for a screen that leaves.** The
first-visit guide takes any key per page and then hands the caller the switchboard,
so paging it that way photographed the switchboard under the guide's name and then
pressed Enter at a prompt that answers nothing. War Dialer prints `page i/n` in the
border -- and in Fast mode's title row, which has no border -- precisely so a
scripted walk can know whether there is another page; `page_note`'s own docstring
says so. A paged walk now stops where the screen says it ends, and a screen that
prints no counter has exactly one page.

**"The fixture is not in that state" is not the same as "no walk can reach it".**
The cached fixture is past the first-visit guide by construction, which is a fact
about the fixture and not about the screen: a walk can ask for a world nobody has
played instead (`FRESH`), and the guide is one panel at eighty columns and four at
the forty-column floor. A fresh world has no tables to write a display preset
into, so such a walk builds the schema through the door's own `connect` first --
which registers nobody, leaving the caller new. An exemption has to name something
no sequence of keys can produce, not something the current fixture happens not to
be.

**A browsing screen quotes the figure the action will charge.** `adjusted_heat`
makes a capture's Heat specific to the caller -- Lookouts take five where a
Carrier Switch's table says eight, a Burner Kit can take none -- so a screen that
prints the role's base number disagrees with the preview of the very action it is
describing. Every surface a caller compares targets on uses the projected figure;
only a screen drawn for nobody falls back to the role's own.

**Where a screen depends on the world's clock, a walk cannot reach it by playing.**
Two around a season boundary can be reached by moving the anchor through the door's
own helpers against the panel's private copy: the receipt a closed season leaves
waiting, and the reset card that opens the switchboard in the last forty-eight
hours. The crackdown card itself cannot -- it is drawn when the world's season
advances *between two dashboard draws in one session*, which is a clock crossing a
boundary mid-session, not a state. That is the shape of a defensible exemption: a
timing condition, not a fixture that happens to be elsewhere. A refusal screen is
the other shape -- one sentence of domain prose in a frame, where a panel adds
nothing the fit and wrap tests at the floor already prove.

**A screen with three versions needs three panels.** The owner service is one
screen with three drawings -- a Public PBX's *negative* Heat gauge, a Warez Hub's
bust gauge, a Carrier Switch with neither -- and a single walk photographed
whichever role the fixture happened to hold. Each has its own walk, and each is
marked on its own service text rather than on the title the three share, so a panel
showing the wrong holding's service fails the build instead of passing it.

**Name a picker entry by what it is.** Which digit a Public PBX is depends on what
the caller holds, so `{X}` presses the key of the entry whose own rows say X. Two
pages can disagree about that: at forty columns the garrison list draws
`[2] Bay  WAREZ HUB` at the foot of page one while offering only `[1]`, and page
two offers `[2]` with the name nowhere on it -- so the selector remembers which
key the text belonged to and keeps paging until the screen will take it. A mark,
likewise, is matched against painted rows and must be short enough not to be
wrapped across two of them: "Warez outlet:" is broken in half at the floor.

**Heat reads to one decimal, because Heat decays.** `:g` prints a decayed figure
in full, so a gauge read `8 -7.86231 = 0` above the same screen's `Heat: 15.9 + 4 =
19.9`. `heat_amount` is the one formatter, and it drops a pointless `.0` so a whole
number still reads as one.

**A record is a card, or pagination will cut it in half.** Flattening every
retained season result into one `RETAINED RESULTS` block let `paginate_cards`
break wherever a page happened to end: the Hall of Fame put a winner's medal and
handle on page one and their season, Rank, placement and closing time alone on
page two, attached to nothing. One card per record keeps it together where it fits
and repeats its heading where it does not -- and the heading is the identity that
was being orphaned, which is the crew in the Hall and the season in a caller's own
history.

**A receipt's actor is the other party, not a name to compare.** Deciding "this
is mine" by comparing the handle stored on an event against the handle the caller
holds *now* turns their whole history hostile the day they rename on the BBS, and
makes a former rival's raids read as their own work if they take that handle.
Self-authored receipts record no actor at all, and `hostile` is "an actor is
named".

**A schema version is not a color correction.** Bumping one makes older game
binaries refuse the world outright, which is a real cost to a SysOp and a one-way
door; paying it to re-tone historical rows was not worth it, and any backfill that
reads a stored actor against a caller's current handle would erase the record that
an attack was an attack on a reused handle. Repairs to history need evidence the
history actually carries. Where there is none, leave it alone and fix the
behaviour going forward.

**A holding is not a target, and every screen that draws one has to agree.** An
exchange the caller controls has posted crew, income, an age and a service; a
capture price, root Heat and the odds of an attack on its own garrison describe an
action no screen will even offer them. That holds for the scene's exchange card,
the root picker's rows and the scene table's verb column alike -- the table's
`take` figure is the chance of *rooting* the exchange, so pairing it with the word
`raid` priced one action and named another. Each of the three has a walk or a test
covering both readings, because a half-applied rule reads as a fixed one.

**An entry a picker appends after a variable list is named as the last one, not
by a digit.** Exchange Control offers one transfer per move the holding can make
and then the owner service, so `3` meant the service only for as long as the
fixture happened to offer exactly two transfers -- after which the walk would
have published a garrison preview under the service's caption. The `$` suffix
pages to the last page and presses the last key offered there, which is what the
door actually guarantees about that entry.

## Shared-world domain and storage

Moved from the NetBBS worklog with Thiesi/NetBBS#1228; issue numbers refer to
NetBBS.

War Dialer session players are display snapshots. The action transaction must
load the actor as well as the victim/exchange, and include the turn cost before
commit. Reloading only the victim does not protect it from its own stale session
or from a stale attacker. Copy the committed actor back to the session only
after commit; there is no save-on-quit/disconnect path. Login settlement and
income timestamps must share the player-credit transaction too.

A zero-turn allowance uses an empty turn_day_start until the first action commits.
Preserve nonzero legacy anchors. heat_updated_at doubles as a per-player clock
high-water mark; settle before applying Heat and use the effective time for
capture/event timestamps too. Screen refresh must call refresh_player, while
read_player remains an unsettled storage read for transaction/observer use.
A menu's displayed allowance is a snapshot: still accept action keys after an
idle zero-turn screen so the transaction can recognize a refill.

An exchange can carry a later clock than the actor after a server clock correction.
Settle the actor through that exchange time before applying capture Heat and use
the actor's final timestamp for a new allowance anchor. Login/action season checks
must respect the persisted world season, not just recompute from a regressed
wall clock.

World rollover uses the action/read transaction's write lock. Reset all older
players and exchanges before writing active_season in meta; archive snapshots
must eventually precede those resets under the same lock. Preserve existing
current-season rows when adopting a mixed legacy world. Resource/board/rival
reads trigger settlement, while read_player and list_exchanges stay raw storage
reads for transaction orchestration and independent observers. An old snapshot
cannot authorize a new-season action. If that action rejects, its rollover is
rolled back with it; the next ordinary refresh commits and announces the reset.

Income uses integer rate-times-elapsed-microsecond units, with 3,600,000,000
units per dollar. Persist the remainder on the player, not an exchange whose
owner can change. On successful capture, settle the previous owner while the
database still records their ownership, then save that player, transfer the
exchange, and save the actor under one transaction. Collection timestamps never
move backwards. Exchange selection compares ownership, defense and displayed
stakes, excluding the collection timestamp so harmless collection does not
reject a caller's choice. Additive schema initialization is transactional too.

Initialization counts exchanges after obtaining the write lock. The regression
synchronizes two connections immediately before BEGIN, so moving the count
outside the transaction deterministically reproduces double seeding. Preserve
unexpected existing counts for manual repair instead of deleting duplicate
rows with potentially independent owners.

Input tests must include real standalone processes and real buffered stdin
wrappers: readiness checks cannot see bytes prefetched into Python's buffer.
Use bounded unbuffered reads. Stream test input larger than the OS pipe capacity
concurrently with its reader. Web scripted tests must send each War Dialer key
at its displayed screen; prequeuing a command string now exercises paste rejection
instead of normal navigation.

Event retention is per target, latest 500 committed IDs, including unread rows.
Insert and pruning share the action transaction; legacy pruning shares schema
initialization. History uses an ID cursor rather than offsets. A page carries an
acknowledgement ID only on an event's final wrapped line: partial records and
new arrivals must remain unread. Scope acknowledgements by both player and ID,
and commit a whole page together before advancing. Use display-column wrapping
for event text before styling, and reserve footer rows in the terminal height.

The switchboard reads player resources, owned exchanges and unread counts under
one settlement transaction. Paging refreshes that snapshot but never performs a
login reset or event acknowledgement. Full-screen redraws require an explicit
result/diagnostic acknowledgement; keep that input boundary in real-process tests.

Standings use the same lifetime-counter formula as rank_score, with stable account
IDs breaking ties; keep the SQL expression and domain formula aligned. Directory
reads settle the whole season before sorting/filtering, bound the fetched batch,
and expose the caller's global position independently of that batch. Two levels
of pagination (wrapped rows and database batches) must allow both directions
without skipping the preceding batch's last page.

Preview conflict checks compare the stored actor before elapsed settlement;
ordinary Heat decay must not invalidate every confirmation. Target checks remain
inside the same action transaction. Capture action-resource baselines after income
collection and publish deltas only after commit, so income is not called a payout
and failed commits never expose an apparent result. Preview rendering must not
consume RNG draws; all outcome rolls happen only on Act. Contract and approach
selection use a fixed bounded catalog, so no persistent offer cache is needed.
Preview and resolution share the same validated terms. Cautious prevents ordinary
failure crew loss, not a subsequent Heat bust; show and test these separately.
Drive both pickers in real-process preview/disconnect tests so they still reach
the final Act boundary after adding the contract board.

Crew specialty/support slots belong in actor preview conflict checks and atomic
player persistence. Calculate effective action Heat in the same pure helper for
preview and resolution, but consume support only inside the action transaction.
Zero added Heat still rolls a bust against existing Heat. A Cash Stash changes
only bust cash loss and survives ordinary failures; Burner Kit consumption is
bound to a committed job/raid/root attempt. Purchase rejection retains the draft
selection. Upgrade fixtures must remove later columns when reconstructing an old
schema, so tests exercise real shipped layouts rather than impossible hybrids.

Operation progress belongs in the actor preview conflict token. Case/Prepare
must not draw RNG; Execute consumes preparation, effects and its turn atomically.
Keep operation success Rank separate from ordinary job counts and align SQL
standings. Recon settles target income and commits its private snapshot with the
actor's turn; rollback must restore both. Re-observation replaces a rival's row
before applying the per-viewer ten-record cap, including equal timestamp ties.
Read snapshots through viewer, season and strict expiry filters; never substitute
live rival resources when rendering an earned dossier or raid preview.

Target selection binds digit keys only to complete visible entries. Keep those
keys separate from Back/Next/Prev and carry database-batch direction through local
row pagination. Regression coverage must drive the composed picker beyond fifty
crews, not only call the page reader. Action result pagination owns its pause;
the main loop must not append a second acknowledgement or clear it prematurely.


War Dialer schema adoption uses `PRAGMA user_version` in the same immediate
transaction as the numbered migration. Pin each shipped migration's layout;
future model fields must not silently redefine an older version. Check the
version, required table/column layout and SQLite integrity before switching
journal mode. Tests that reconstruct an unversioned fixture must set version zero;
missing columns in a versioned database are damage, not an upgrade request.
Exercise rollback by denying the version-marker write after schema changes.
Publish new worlds from a complete same-directory SQLite staging file using an
atomic no-replace hard link. Existing empty files are recovery input; treating
one as new would silently reset a truncated world. Keep a simultaneous initial
connect regression, because a check-then-create sequence exposes an empty file.
The world filesystem must support hard links (the normal NetBSD/NTFS paths do).

War Dialer's Windows input lookahead uses `PeekNamedPipe` before an unbuffered
read. Python 3.11 has no Windows `os.set_blocking`, and Windows `select` accepts
only sockets. Keep this path covered by real pipes, including idle timeout,
queued control sequences and closed-writer EOF; newer Python alone misses the
minimum-version compatibility failure.

War Dialer maintenance uses a separate rollback-journal SQLite file at
`<world>.sessions`. Play retains a read transaction for the complete process;
maintenance retains BEGIN EXCLUSIVE. Do not use WAL for this guard: WAL readers
do not block an exclusive writer. Never rename/delete this sidecar during world
restore. Test an idle session and killed subprocess, not only active world writes.
How a host snapshots and restores worlds around this guard is the host's policy;
NetBBS's lives in its own worklog.


Shared-crew worlds use schema 2 even though the physical columns are unchanged:
version 1 `players.crew` was the whole real crew, whereas version 2 stores available
members and adds assigned garrisons to obtain the total. Keep v1 migration code
immutable. Conversion, income settlement, released holdings, receipts and version
marker must roll back together. Validate host ownership before this conversion.
Capture must return the previous garrison exactly once under the same action lock;
otherwise a stale session can lose or duplicate defenders. Action deltas report
available and assigned changes separately so reinforcement is not narrated as death.
Version 2 abandonment markers remain compatible migration data; schema 3 uses
the player capture ledger for the stronger once-per-season award rule.

Raid recovery is target-wide: persist its deadline in the same transaction as
any committed attempt, losses, receipt and turn. Login and acknowledgement must
not clear it. Real SQLite concurrency tests must show exactly one accepted
attempt when distinct attackers race one unshielded target. The last-attacker
identity is historical data, not the eligibility key; an old marker migrates to
one day of recovery because its original attempt time is unavailable.

Economy schema 3 keeps an explicit bounded list of rewarded exchange IDs per
player: aggregate capture counts or the latest 500 receipts cannot reconstruct
all previous ownership. Legacy captures retain their old Rank through a season
credit and exhaust capture awards until rollover. Do not infer missing history
as evidence that an exchange was never captured.

Control Rank uses the same integer microsecond boundary as cash settlement, with
a separate per-player remainder. Transfer/withdrawal must save both before
changing ownership; standings settle the at-most-ten owners, including absent
ones, before SQL ordering. Keep SQL Rank aligned with Python. Migration pays old
stored rates before replacing them and awards no control Rank for pre-upgrade
time. Schema 1 and 2 migrations remain immutable; their shared helpers must still
work before schema 3 columns exist.

Exchange security is derived defense, never a stored crew assignment. Use the
same effective defense in previews and capture resolution; return only real
stationed defenders on transfer. Neighbor ownership affects price without changing
the target row: re-read the ring under the action lock and compare the selected
discount separately from target identity. Owner services use the same action lock
and fresh ownership check. Schema 7 preserves the ten exchange IDs/order and their
stored rates; roles survive competition reset. Do not edit older migrations or
require role columns in helpers used before version 7 exists.

Neutral occupancy is separate from `controller_user_id`; a null human owner is
not sufficient to infer guaranteed capture. Use `exchange_occupied` for contest
odds and `exchange_owner` for presentation. NPC garrisons never feed player income,
Rank, standings or released-defender credit. Capture clears neutral occupancy and
its return deadline atomically; last-defender withdrawal starts the 24-hour return.
World settlement checks only the three fixed homes and never overwrites human
ownership. Schema 8 helpers must not run before its columns exist; legacy upgrade
fixtures must remove those columns when reconstructing older layouts. Exercise
restart, simultaneous returns and a return between preview and Act with real SQLite.

Public scene history is an allowlist of three territory events, not a copy of
private receipts. Capture, abandonment and neutral stationing publish and prune
inside their mutation transaction; a failed bulletin write must roll back the
underlying action. Keep at most 500 rows, order by committed ID, bound stored
names/text and sanitize before display. Do not backfill fictional activity on
upgrade. Ordinary rollover retains the bounded, season-labeled history; explicit
competition reset clears it after world settlement. Insignia are noncompetitive
identity: fresh actor reads and season/reset saves must retain them, including
when another session changes the cosmetic choice during an action preview.

Archive final territory Rank before resetting the world, using the season cutoff
rather than a late visitor's current time. Do not call a public refresh helper
from the archiver: it would recurse into rollover. Settle existing owners directly,
then snapshot all season players with the same Rank expression and account-ID tie
rule used by live standings. NPCs have no player row and cannot receive medals.
Archive, income settlement, reset and active marker share one transaction. Keep
at most twelve headers and their result rows; skip replay of unretained inactive
seasons after long absences. Snapshot handles/insignia rather than joining live
identity fields when rendering old results. SysOp advance/reset settles overdue
natural seasons before changing the anchor, then closes the current season at
the confirmed operator boundary. Moving the anchor first changes past cutoffs
and permanently miscounts territory Rank in a quiet world.
Private finale receipts share the archive/reset transaction and ordinary receipt
retention/acknowledgement rules. A receipt write failure must roll back final
earnings and archives too; otherwise a returning dormant caller can lose their
only private explanation of the reset. Recognition views read archive snapshots,
never recompute awards or mutate receipt acknowledgement state.
For rollover recovery, abrupt child-process exit after archive insertion proves
SQLite rollback before commit; exit just after settlement proves a fresh process
does not duplicate awards or receipts after commit. Separate process contenders
exercise the same file and writer lock. These complement the bounded skip,
retention, historical-identity and world-component backup/restore checks; they
do not substitute for a hands-on restore or a live season-transition exercise.
Display preferences are a separate per-caller metadata object, with only three
boolean keys. Cosmetic toggles read the latest object under the write lock and
never save the caller's competitive snapshot. Keep ASCII conversion limited to
authored decorations; never encode whole output with replacement, which loses
Unicode handles. Strip SGR for monochrome while retaining terminal navigation.
On Windows, writing to a closed anonymous output pipe can raise `OSError(22)`
instead of `BrokenPipeError`. Normalize failures at the output writer, so they
take the disconnect path instead of the storage-error path. Redirect the dead
stdout descriptor to the null device before Python's final flush. Real-pipe
tests must cover loss before any action and after commit but before its result;
the latter must retain the paid action with no duplicate spend or traceback.

`python scripts/war_dialer_balance.py` runs bounded deterministic policy probes
against disposable SQLite worlds through the actual action resolvers. The default
is fourteen days and seeds 362/363/364; use `--scenario NAME`, `--days 1..21`, and
`--seeds ...` to reproduce a smaller comparison. JSON records the game source hash,
policy, daily resources/Rank/holdings, actions and rejected attempts. Never point
these probes at a live world. Daily observations settle a database copy: collecting
income or logging absent players in for reporting would change the experiment.

Fixed caller order deliberately exposes first-mover effects; these policies are
neither optimal strategies nor a population model. Burst/spaced probes take the
same first exchange and trade thereafter, isolating low-Heat collection cadence.
Repeated-victim probes start with mature accounts and alternate attackers against
an absent target. Bust recovery uses an explicitly depleted fixture and an actual
forced bust; its recovery counter excludes that bust turn. Finite seeds and these
fixtures identify incentives and recovery paths, not fairness or fun. Agree balance
targets and retain separate human playtests before calling a tuned economy balanced.
