# War Dialer engineering notes

Extracted from the NetBBS worklog; issue references belong to NetBBS.

Administration lives in `administer_world`, also called by `--admin`.
Mutations hold the exclusive session guard and record their audit in the same
transaction. A season close or reset first takes a SQLite backup, including
committed WAL pages, before opening the write transaction. Backing up from the
same connection inside its write transaction can stall. A failed mutation
rolls back its audit too; its completed snapshot remains for recovery.
`inspect_world` validates without creating, migrating or settling a world.
NetBBS retains node-path, ownership and complete-node-backup policy.

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
