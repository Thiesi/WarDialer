"""war_dialer.py travels alone (NetBBS vendors it, SysOps copy it), so it carries its own notice (#36)."""
from pathlib import Path

DOOR = Path(__file__).resolve().parent.parent / "war_dialer.py"


def test_the_door_states_its_copyright_and_license_near_the_top():
    head = DOOR.read_text(encoding="utf-8").splitlines()[:3]
    notice = next((line for line in head if "Copyright (c)" in line), "")
    assert "Thiesi" in notice and "BSD-2-Clause" in notice, head
