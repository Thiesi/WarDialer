"""Keep subprocess visits deterministic; splash tests explicitly opt back in."""
import pytest


@pytest.fixture(autouse=True)
def no_door_splash(monkeypatch):
    monkeypatch.setenv("DOOR_SPLASH", "0")


def pytest_collection_modifyitems(config, items):
    if hasattr(config, "workerinput"):
        skip = pytest.mark.skip(reason="timing_sensitive: run serially with -m timing_sensitive")
        for item in items:
            if "timing_sensitive" in item.keywords:
                item.add_marker(skip)
