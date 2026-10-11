"""Render the encoding test's complete screen walk from actual CP437 output.

Run with the development test dependencies installed:
    python tools/cp437_gallery.py --out build/cp437-gallery
The full gallery and small review sheets use the normal ANSI emulator.
"""
import argparse
import html
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest
from tests.test_war_dialer_presentation import wd, _painted_world, _walk_screens
from tools.door_gallery import to_html


def render(width, height, directory):
    """Exercise the production renderers, output mapping and strict wire codec."""
    with pytest.MonkeyPatch.context() as patch:
        raw = io.BytesIO()
        terminal = io.TextIOWrapper(raw, encoding="cp437", newline="")
        patch.setattr(wd, "sys", SimpleNamespace(**{**vars(sys), "stdout": terminal}))
        patch.delenv("NETBBS_DOOR_INFO", raising=False)
        patch.setattr(wd, "_DEFAULT_ENCODING", "cp437")
        conn, _ = _painted_world(directory, f"gallery-{width}.db")
        try:
            values = {"encoding": "cp437"}
            conn.execute("INSERT INTO meta(key,value) VALUES ('display:1',?)", (json.dumps(values),))
            palette = wd.Palette(False, color_depth="16")
            wd.apply_display(palette, values)
            output = wd.out
            screens = _walk_screens(conn, palette, width, height, patch)
            result = []
            for screen in screens:
                raw.seek(0)
                raw.truncate()
                output(screen)
                result.append(raw.getvalue().decode("cp437", "strict"))
            return result
        finally:
            conn.close()


def page(screens, width, height, title):
    styles = {}
    panels = [f'<figure><figcaption>{width}×{height} · CP437 · 16 colors · {index}</figcaption>'
              f'<pre>{to_html(screen, width, height, styles)}</pre></figure>'
              for index, screen in enumerate(screens, 1)]
    colors = "\n".join(f"i.{name}{{{style}}}" for style, name in styles.items())
    return f'''<!doctype html><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body{{margin:24px;background:#080b12;color:#d5dde9;font:14px system-ui}}
h1{{font-size:22px;margin:0 0 8px}}p{{color:#9baabd;margin:0 0 20px}}
main{{display:flex;flex-wrap:wrap;gap:24px}}figure{{margin:0}}
figcaption{{font-size:12px;color:#9baabd;margin-bottom:8px}}
pre{{margin:0;padding:16px;background:#05070b;border:1px solid #263343;
font:14px/1.25 Consolas,monospace;white-space:pre}}
pre i{{display:inline-block;width:1ch;font-style:normal}}
{colors}</style><h1>{html.escape(title)}</h1>
<p>Production screen renderers → CP437 bytes → ANSI terminal emulator.</p>
<main>{''.join(panels)}</main>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build/cp437-gallery")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cp437-gallery-") as temporary:
        for width, height in ((40, 12), (64, 20), (80, 24)):
            screens = render(width, height, Path(temporary))
            (args.out / f"all-{width}.html").write_text(
                page(screens, width, height, "War Dialer — CP437 screen walk"), encoding="utf-8")
            selected = [next(s for s in screens if "SWITCHBOARD" in wd._strip_ansi(s)),
                        next(s for s in screens if "Encoding:" in wd._strip_ansi(s))]
            target = args.out / f"review-{width}.html"
            target.write_text(page(selected, width, height, "War Dialer — CP437"), encoding="utf-8")
            print(f"{width}x{height}: {len(screens)} screens; {target}")


if __name__ == "__main__":
    main()
