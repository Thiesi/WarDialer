# Migration provenance

The migration branch imports 170 filtered commits using `git filter-repo`.
The game has only one historical path in NetBBS:
`src/netbbs/doors/bundled/war_dialer.py`, renamed to `war_dialer.py` here.
The domain, presentation, splash, balance and new administration tests came
with their history, as did the balance script, gallery and ANSI emulator.
Unqualified `#N` references in imported commit messages were rewritten to
`Thiesi/NetBBS#N`; author attribution was retained.

The source is NetBBS prerequisite commit
`5fd6a051` on `codex/war-dialer-admin`, based on main
`4106900f943202182606e9296f82b4a48fb1d189`.
The prerequisite implements NetBBS #1227 before extraction.
The imported game is byte-identical to that committed source; its SHA-256 is:

```text
1605d18d4f2081db7a7bb0e15bbdc2b95be611d55dba4004d3a9046e568da989
```

The standalone adaptation changes test/tool paths and removes their NetBBS
imports. It leaves the game unchanged. Host runtime, resize, wrapper and
backup tests remain in NetBBS. The design and engineering notes were copied
from that prerequisite; host world-path, ownership, node-backup and legacy
path-migration policy stays with NetBBS.

Before completing issue #1:

1. Land NetBBS #1227 on NetBBS main. If review changes the door, import those
   changes and their history before proceeding.
2. Compare `war_dialer.py` byte-for-byte with that main commit and update this
   provenance record to name the final source.
3. Run the Linux/Windows Python 3.11/3.13 CI matrix. Local Windows validation
   does not establish Linux or either target Python version's result.

NetBBS vendoring and removal of its migrated material belong to its subsequent
issue #1228. No release tag is part of this preparation.
