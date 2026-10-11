# Migration provenance

The migration branch imports 171 filtered commits using `git filter-repo`.
The game has only one historical path in NetBBS:
`src/netbbs/doors/bundled/war_dialer.py`, renamed to `war_dialer.py` here.
The domain, presentation, splash, balance and new administration tests came
with their history, as did the balance script, gallery and ANSI emulator.
Unqualified `#N` references in imported commit messages were rewritten to
`Thiesi/NetBBS#N`; author attribution was retained.

The source is NetBBS main commit
`52311ebfa0757b13d619695c0035ddb48227f8ea`, which merges
[NetBBS #1229](https://github.com/Thiesi/NetBBS/pull/1229).
The prerequisite implements NetBBS #1227 and fixes Windows Python 3.11 pipe
input before extraction.
The imported game is byte-identical to that committed source; its SHA-256 is:

```text
0fa9970785c7d9c78fb2aab7fa7fee83a4b707a72e301c37dd32033b5adbf936
```

The standalone adaptation changes test/tool paths and removes their NetBBS
imports. It leaves the game unchanged. Host runtime, resize, wrapper and
backup tests remain in NetBBS. The design and engineering notes were copied
from that prerequisite; host world-path, ownership, node-backup and legacy
path-migration policy stays with NetBBS.

The byte-for-byte comparison against that merged main commit was verified
on 2026-10-11. CI validates Linux and Windows with Python 3.11 and 3.13.

NetBBS vendoring and removal of its migrated material belong to its subsequent
issue #1228. No release tag is part of this preparation.
