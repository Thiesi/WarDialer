"""Keep local test scratch bounded (docs/engineering-notes.md, local disk hygiene).

On this host, scratch left behind by test runs once grew to several
million files across a sibling project's worktrees and took the machine
down. Moved to the system temp folder, it later passed half a million
entries there too. This checkout had the same habit: one
`build/pytest-<name>` folder per run, each an explicit --basetemp that
pytest never cleans because the name is never reused.

Three checks run before any test:
- an explicit --basetemp inside the worktree must be `.test-tmp/pytest`,
  the one fixed name, so each run replaces the last;
- the worktree's ignored scratch (`.test-tmp`, `.pytest_cache`, `build`)
  must hold at most SCRATCH_LIMIT files. Above that, run
  `python scripts/clean_scratch.py` first;
- this project's `wardialer-*` entries in the system temp folder must hold
  at most SCRATCH_LIMIT files. Above that, run
  `python scripts/clean_scratch.py --temp` first.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

SCRATCH_DIRS = ('.test-tmp', '.pytest_cache', 'build')
LOCAL_BASETEMP = Path('.test-tmp') / 'pytest'
DEFAULT_LIMIT = 50_000
# Every temp folder this project's tools make starts with this prefix.
# pytest-of-* is left out: pytest bounds it itself (pyproject.toml).
TEMP_PREFIX = 'wardialer-'
TEMP_PATTERNS = (TEMP_PREFIX + '*',)


def scratch_limit() -> int:
    return int(os.environ.get('WARDIALER_SCRATCH_LIMIT', DEFAULT_LIMIT))


def count_files(root: Path, stop_after: int) -> int:
    """Files under root, counting at most stop_after + 1 so a huge tree stays cheap."""
    count, pending = 0, [root]
    while pending:
        try:
            entries = os.scandir(pending.pop())
        except OSError:
            continue
        with entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                        continue
                except OSError:
                    continue
                count += 1
                if count > stop_after:
                    return count
    return count


def basetemp_problem(basetemp: str | os.PathLike[str] | None, root: Path) -> str | None:
    if not basetemp:
        return None
    path, root = Path(basetemp).resolve(), root.resolve()
    if not path.is_relative_to(root) or path == (root / LOCAL_BASETEMP).resolve():
        return None
    return (f'--basetemp {path} is inside the worktree under a name that is never cleaned. '
            f'Omit --basetemp (pytest then uses the system temp folder and keeps only failed runs) '
            f'or use --basetemp={LOCAL_BASETEMP.as_posix()}, which every run replaces.')


def scratch_problem(root: Path, limit: int | None = None) -> str | None:
    limit = scratch_limit() if limit is None else limit
    total = 0
    for name in SCRATCH_DIRS:
        if (root / name).is_dir():
            total += count_files(root / name, limit - total)
            if total > limit:
                return (f'This worktree holds more than {limit:,} scratch files in '
                        f'{", ".join(SCRATCH_DIRS)}. Run `python scripts/clean_scratch.py` '
                        f'(keep any evidence you need in docs/ or on the PR first; build/ '
                        f'outside pytest-* is yours to prune). '
                        f'WARDIALER_SCRATCH_LIMIT raises the limit for one run.')
    return None


def temp_folders(temp: Path | None = None) -> list[Path]:
    temp = Path(tempfile.gettempdir()) if temp is None else temp
    return sorted(path for pattern in TEMP_PATTERNS for path in temp.glob(pattern))


def temp_files(temp: Path | None = None, stop_after: int = 10**9) -> int:
    total = 0
    for path in temp_folders(temp):
        # A link counts as one entry: its target isn't this project's scratch.
        total += count_files(path, stop_after - total) if path.is_dir() and not path.is_symlink() else 1
        if total > stop_after:
            break
    return total


def temp_problem(temp: Path | None = None, limit: int | None = None) -> str | None:
    limit = scratch_limit() if limit is None else limit
    if temp_files(temp, limit) > limit:
        return (f'This project holds more than {limit:,} files in the system temp folder '
                f'({", ".join(TEMP_PATTERNS)}). The temp folder is not storage, and past half a million '
                f'entries it has taken this host down. Run `python scripts/clean_scratch.py --temp`, '
                f'and keep any evidence you need on the PR or in docs/ first. That keeps folders written '
                f'to in the last 24 hours; once no gallery is running, `--temp --older-than 0` removes them too. '
                f'WARDIALER_SCRATCH_LIMIT raises the limit for one run.')
    return None
