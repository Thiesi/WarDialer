"""Keep subprocess visits deterministic; splash and scene tests explicitly opt back in."""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def pytest_configure(config):
    """Refuse runs that would grow unbounded local scratch (tests/scratch_guard.py)."""
    if hasattr(config, "workerinput"):
        # xdist workers get <basetemp>/popen-gwN; the controller already checked.
        return
    from tests.scratch_guard import basetemp_problem, scratch_problem, temp_problem
    problem = basetemp_problem(config.option.basetemp, REPO_ROOT) or scratch_problem(REPO_ROOT) or temp_problem()
    if problem:
        raise pytest.UsageError(problem)
    if config.option.basetemp:
        Path(config.option.basetemp).resolve().parent.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def no_door_splash(monkeypatch):
    monkeypatch.setenv("DOOR_SPLASH", "0")
    monkeypatch.setenv("DOOR_SCENES", "0")


def pytest_collection_modifyitems(config, items):
    if hasattr(config, "workerinput"):
        skip = pytest.mark.skip(reason="timing_sensitive: run serially with -m timing_sensitive")
        for item in items:
            if "timing_sensitive" in item.keywords:
                item.add_marker(skip)
