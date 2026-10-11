"""Check that the distributed door imports only Python's standard library."""
import ast
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[1] / "war_dialer.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
modules = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        modules.update(alias.name.split(".")[0] for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        if node.level:
            sys.exit("war_dialer.py must not depend on relative imports")
        if node.module:
            modules.add(node.module.split(".")[0])
outside = sorted(modules - sys.stdlib_module_names)
if outside:
    sys.exit(f"war_dialer.py imports non-stdlib modules: {', '.join(outside)}")
print(f"war_dialer.py imports only the standard library ({len(modules)} modules)")
