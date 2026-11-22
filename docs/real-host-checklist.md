# Real-host checklist

Everything in this repository is verified against the ANSI emulator in
`tools/ansi_to_html.py` and against the door driven as a subprocess. That
proves what the door writes. It does not prove what a caller's terminal draws,
what a BBS does to the bytes on the way, or how the door feels over a real
line. This list is the part that needs a host, a terminal and a person.

Run it on the release you intend to announce. Note the host, its version, the
terminal and its font beside anything that fails: most findings here are about
one combination.

## Hosts

| Host | Setup | Covers |
| --- | --- | --- |
| NetBBS | the bundled door, or `profiles/netbbs.json` imported with **[J] Import JSON** | UTF-8, truecolor, resize, game events |
| One classic host (Synchronet, Mystic or ENiGMA½) | the README's "Classic host setup" | DOOR.SYS or DOOR32.SYS, CP437, sixteen colors, stdio |
| The same classic host with DOOR32 communication type 2, if it offers it | pass the socket to the Python process | the socket transport and its telnet filtering |

## Terminals

| Terminal | Size | Checks |
| --- | --- | --- |
| A modern terminal (Windows Terminal, iTerm2, kitty) over telnet or SSH | 132x40 and 80x24 | truecolor, quarter-block art, the wide console |
| SyncTERM | 80x25 | CP437, sixteen colors, the classic frame |
| NetRunner or another CP437 terminal | 80x25 | a second CP437 font |
| Any terminal resized small | 40x12 | the floor: every screen pages rather than wraps |

## What to look at

Play one full day of turns on each terminal. On each screen below, the
question is the same: does it look like the pictures in `docs/review/`, and
is anything cut off, doubled, misaligned or the wrong color?

- [ ] **Launch splash and masthead.** The dial-out, `CONNECT`, the wordmark.
      Any key skips it and is not passed to the next screen.
- [ ] **First visit** on a caller the world has never seen.
- [ ] **Switchboard.** The frame closes on every row; the ring's stems meet
      its nodes; the TODAY card names a condition; on 132x40 the wordmark sits
      above the cockpit.
- [ ] **War dialer.** The modem lamps, the black book's two-row entries, the
      tier badges' four colors.
- [ ] **A sweep** with scenes on: the dial log scrolls, carriers light.
- [ ] **A carrier hack**, won and lost: the login scene, the result stamp.
- [ ] **A dig**, held and traced: the LINE OPEN card and its bar.
- [ ] **A bust.** The sirens are red and blue, not two reds.
- [ ] **A tier-up.** The pixel letters are whole.
- [ ] **Map, an exchange card, Rank, Rivals, Log, Help, Scene and each of its
      screens, the rap sheet.**
- [ ] **Sign-off.** `NO CARRIER`, tonight's Rank and cash.
- [ ] **In CP437**: no `?` where a glyph should be, and no row a column long
      or short. Compare with `python tools/cp437_gallery.py`.
- [ ] **Display options**: ASCII decorations, monochrome and Fast mode each
      change what they say they change, and survive a reconnect.

## How it behaves

- [ ] **Single keys only.** Every menu answers one key with no Enter.
- [ ] **Paste is refused.** Pasting several keys ends the visit with the
      sentence that says why; it does not run them as commands.
- [ ] **Arrow keys and function keys** do nothing at a menu and never act as
      a letter.
- [ ] **Resize** (NetBBS): the switchboard redraws at the new size.
- [ ] **Hang up mid-preview.** Reconnect: no turn was spent.
- [ ] **Hang up on a dig offer.** Reconnect and act: the Rank carried was
      kept, and the line is closed.
- [ ] **Hang up during a scene.** Reconnect: the action it showed is
      committed, exactly once.
- [ ] **Latency.** A turn (key, preview, Act, scene, result) feels prompt on
      the slowest link you expect callers to use. Note the round trip if not.

## More than one caller

- [ ] **Two callers at once** on two nodes: one roots an exchange the other is
      previewing; the second is told the exchange changed and spends nothing.
- [ ] **The same caller on two nodes**: an action on one makes the other's
      open preview stale, and a dig offer on one cannot be dug from the other.
- [ ] **A raid and its strike back**: the raided caller's receipt says they
      may strike back, and the raider's shield does not stop it.
- [ ] **An operator's home**: hold one under-defended for two days and confirm
      the retake receipt and the "messages waiting" scene at next login.

## The host's side

- [ ] **NetBBS game events** switched on: a new tier, a capture, a hard badge
      (crack an ice carrier) and a season's medals each reach chat once, and
      `!top wardialer` matches the game's own standings.
- [ ] **`--admin status` and `--admin stats`** run against the live world
      without stopping it, and `stats` names no caller.
- [ ] **A backup** of the world, its WAL files and its `.sessions` guard
      restores to a playable world.
- [ ] **An upgrade** from the previous release's world: the door opens it,
      and nobody's cash, crew or Rank moves.

## Balance, from real play

After a week with real callers, run `--admin stats --json` and compare it
with the probe figures in the design notes: turns per caller, how a hundred
turns were spent, busts per hundred turns, and the share of digs that were
traced. The rules were tuned against scripted policies; this is the first
measurement of people.
