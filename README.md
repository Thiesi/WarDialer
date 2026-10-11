![War Dialer: rival crews, ten exchanges, one scene](art/banner.png)

# War Dialer

An asynchronous multiplayer door game for BBSes: rival crews compete for ten
phone exchanges across a season, in one shared world that every caller on the
board plays.

War Dialer is one Python file, `war_dialer.py`, with no dependencies beyond
Python 3.11's standard library. It needs a terminal of at least 40 columns by
12 rows. Every caller on one BBS shares one SQLite world.

The game was extracted byte-for-byte from NetBBS main after its administration
prerequisite ([NetBBS #1227](https://github.com/Thiesi/NetBBS/issues/1227)).
See the [migration provenance](docs/migration.md) for the source commit and hash.
NetBBS still ships its bundled copy. Classic drop files, CP437 output and
DOOR32 sockets are follow-up issues #3–#5.

## World and administration

Set `WAR_DIALER_DB_PATH` to an absolute world filename shared by all the nodes
of one BBS. NetBBS supplies its caller metadata through `NETBBS_DOOR_INFO`.
Without a host token, the first launch gives the world a random persistent
owner ID and marks it self-owned. Existing unbound standalone worlds are
adopted the same way. A NetBBS-bound world still requires its matching host
token on every launch. Use a separate world for each BBS.
Keep the world, its WAL files and its `.sessions` guard together; backups must
use SQLite's backup API, not a copy of a live `.db` file.

Administration needs no caller drop file:

```sh
python war_dialer.py --world /var/lib/wardialer/world.db --admin status --json
python war_dialer.py --world /var/lib/wardialer/world.db --admin maintenance on
python war_dialer.py --world /var/lib/wardialer/world.db --admin close-season \
  --confirm world.db --reason "Start the next competition"
python war_dialer.py --world /var/lib/wardialer/world.db --admin maintenance off
```

`reset` also clears receipts while retaining player identities, account age,
world ownership and the latest 100 audit entries. Both destructive commands
require maintenance on, the exact filename and a reason. They first create a
SQLite-consistent snapshot beside the world; `--snapshot` can name a different
new file. Existing snapshot files are refused. Maintenance stays on afterward.
Active game sessions prevent maintenance operations. NetBBS additionally
requires its own verified complete node backup through its wrapper.

## Development

```sh
python -m pip install pytest pytest-xdist tzdata
python -m pytest -q -n auto
python -m pytest -q -m timing_sensitive
python -I tools/check_stdlib_only.py
python tools/door_gallery.py --open
python scripts/war_dialer_balance.py --help
```

The gallery drives the real door and renders its screens at 80/64/40 columns
with the ANSI emulator in `tools/ansi_to_html.py`. Windows pipe launches do
not play a splash, so the Windows gallery omits that panel. A screen change
needs visual review as well as layout tests.
`tzdata` supplies named timezone data for tests on Windows; it is not a door
import dependency. Without system timezone data, the door falls back to UTC.

The [design](docs/design.md) and [engineering notes](docs/engineering-notes.md)
carry the game's decisions from NetBBS. Older source comments and those
documents refer to NetBBS issues; imported commit messages qualify those
references as `Thiesi/NetBBS#N`. Host runtime, resize, administration-wrapper
and node-backup tests remain in NetBBS.

## Releases

Tags matching `v*` run the suite on Linux and Windows with Python 3.11 and
3.13, then publish the tagged `war_dialer.py` byte-for-byte with `SHA256SUMS`.
The release job waits for all four test combinations to pass.

The banner is drawn from the game's own launch splash by `art/render_banner.py`
(`python art/render_banner.py war_dialer.py art/banner.png`).

## License

BSD 2-Clause, see [LICENSE](LICENSE).
