"""Render a pixel-art banner from War Dialer's launch splash.

Reuses the splash's own masthead letters, phosphor ramp and shadow, dial-up
lines, tagline, ring of ten exchanges and crew colours, but composes them on a
real pixel canvas (320x160, scaled 4x to 1280x640, GitHub's social-preview size)
instead of terminal cells, behind the glass of a phosphor CRT.

usage: python art/render_banner.py war_dialer.py art/banner.png [scale]

No dependencies beyond the standard library; it writes the PNG itself.
"""
import importlib.util
import math
import struct
import sys
import zlib

src, out_path = sys.argv[1], sys.argv[2]
SCALE = int(sys.argv[3]) if len(sys.argv) > 3 else 4
spec = importlib.util.spec_from_file_location("war_dialer", src)
wd = importlib.util.module_from_spec(spec)
sys.modules["war_dialer"] = wd
spec.loader.exec_module(wd)

W, H = 320, 160
ROLE = {name: rgb for name, (rgb, _index) in wd.Palette.ROLES.items()}


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def shade(c, f):
    return tuple(max(0, min(255, round(v * f))) for v in c)


GLASS = (6, 16, 10)
img = [[GLASS for _ in range(W)] for _ in range(H)]
glow = [[None for _ in range(W)] for _ in range(H)]  # what the phosphor emits
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def put(x, y, c):
    if 0 <= x < W and 0 <= y < H and c is not None:
        img[y][x] = c
        glow[y][x] = c


def blend(x, y, c, a):
    if 0 <= x < W and 0 <= y < H:
        img[y][x] = mix(img[y][x], c, a)


def dither(x, y, c, a, levels=4):
    steps = a * levels
    whole = int(steps)
    if steps - whole > (BAYER[y % 4][x % 4] + 0.5) / 16:
        whole += 1
    if whole:
        blend(x, y, c, min(1.0, whole / levels))


F3 = {k: "".join(v.split()) for k, v in {
    "A": ".#. #.# ### #.# #.#", "C": "### #.. #.. #.. ###", "D": "##. #.# #.# #.# ##.",
    "E": "### #.. ##. #.. ###", "G": "### #.. #.# #.# ###", "H": "#.# #.# ### #.# #.#",
    "I": "### .#. .#. .#. ###", "K": "#.# #.# ##. #.# #.#", "L": "#.. #.. #.. #.. ###",
    "N": "##. #.# #.# #.# #.#", "O": "### #.# #.# #.# ###", "R": "##. #.# ##. #.# #.#",
    "S": "### #.. ### ..# ###", "T": "### .#. .#. .#. .#.", "V": "#.# #.# #.# .#. .#.",
    "W": "#.# #.# ### ### #.#", "X": "#.# #.# .#. #.# #.#", "Y": "#.# #.# .#. .#. .#.",
    "Z": "### ..# .#. #.. ###", "0": "### #.# #.# #.# ###", "1": ".#. ##. .#. .#. ###",
    "2": "### ..# ### #.. ###", "4": "#.# #.# ### ..# ..#", "5": "### #.. ### ..# ###",
    "3": "### ..# .## ..# ###", "6": "### #.. ### #.# ###", "7": "### ..# ..# .#. .#.",
    "8": "### #.# ### #.# ###", "9": "### #.# ### ..# ###", ".": "... ... ... ... .#.",
    "-": "... ... ### ... ...", " ": "... ... ... ... ...",
}.items()}


def text(x, y, s, color):
    for i, ch in enumerate(s):
        g = F3[ch]
        for r in range(5):
            for c in range(3):
                if g[r * 3 + c] == "#":
                    put(x + i * 4 + c, y + r, color)


def text_width(s):
    return len(s) * 4 - 1


cx = W // 2

# -- the call: the modem dials, screeches and connects -----------------------
text(16, 14, "ATZ", ROLE["phosphor"])
text(16 + text_width("ATZ ") + 1, 14, "OK", ROLE["grey"])
text(16, 22, "ATDT " + wd.SPLASH_NUMBER, ROLE["phosphor"])
seed = zlib.crc32(b"War Dialer") or 1
x = 16
tones = (ROLE["phosphor_dim"], ROLE["grey"], ROLE["cyan"], ROLE["mint"])
while x < 16 + 84:  # line noise: short runs of scratchy pixels
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    run, tone = 2 + seed % 5, tones[(seed >> 8) % len(tones)]
    for dx in range(run * 3):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        for dy in range(5):
            if (seed >> dy) & 3 == 0:
                put(x + dx, 30 + dy, shade(tone, 0.8))
    x += run * 3 + 2
text(16, 38, wd.SPLASH_CONNECT, ROLE["amber"])
for y in range(38, 43):  # the cursor, held after CONNECT
    for x in range(16 + text_width(wd.SPLASH_CONNECT) + 3, 16 + text_width(wd.SPLASH_CONNECT) + 6):
        put(x, y, ROLE["phosphor"])

# -- the masthead, burned in: the phosphor ramp row by row, a dark shadow ------
rows = wd._splash_word(wd._SPLASH_FONT, "WAR DIALER", 2, 4)
ramp = [(150, 255, 160), (95, 255, 90), (57, 255, 20), (40, 215, 30), (28, 175, 36)]
SHADOW = (16, 58, 30)
CW, CH = 3, 6  # one terminal cell: three pixels wide, six tall
logo_w = len(rows[0]) * CW
lx0, ly0 = cx - logo_w // 2, 52
ink = set()
for r, line in enumerate(rows):
    for c, ch in enumerate(line):
        if ch != " ":
            for dy in range(CH):
                for dx in range(CW):
                    ink.add((lx0 + c * CW + dx, ly0 + r * CH + dy))
for (x, y) in ink:
    if (x + CW, y + CH // 2) not in ink:
        put(x + CW, y + CH // 2, SHADOW)
SWEEP = ly0 + 2 * CH + 2  # the scanline that sweeps the tube, caught mid-pass
for (x, y) in ink:
    row = (y - ly0) // CH
    color = ramp[min(row, len(ramp) - 1)]
    if SWEEP <= y < SWEEP + 2:
        color = (190, 255, 205)
    put(x, y, color)

tagline = wd.SPLASH_TAGLINE.upper()
text(cx - text_width(tagline) // 2, ly0 + 5 * CH + 10, tagline, ROLE["mint"])

# -- the ring of ten exchanges, lit in the colours their crews hold them in ----
ry, rx_half, ry_half = 124, 92, 14
x0, x1, y0, y1 = cx - rx_half, cx + rx_half, ry - ry_half, ry + ry_half
R = 6  # corner radius


def loop_points():
    pts = []
    for x in range(x0 + R, x1 - R + 1):
        pts += [(x, y0), (x, y1)]
    for y in range(y0 + R, y1 - R + 1):
        pts += [(x0, y), (x1, y)]
    for (ccx, ccy, a0) in ((x0 + R, y0 + R, 180), (x1 - R, y0 + R, 270), (x1 - R, y1 - R, 0), (x0 + R, y1 - R, 90)):
        for step in range(0, 91, 3):
            a = math.radians(a0 + step)
            pts.append((round(ccx + R * math.cos(a)), round(ccy + R * math.sin(a))))
    return pts


for (x, y) in loop_points():
    near = (y - y0) / (y1 - y0)  # tilted toward the caller: the near edge is brighter
    put(x, y, shade((78, 138, 98), 0.6 + 0.4 * near))
stops = [x0 + round((x1 - x0) * (i + 1) / 5) for i in range(4)]
nodes = [(x, y0) for x in stops] + [(x1, ry)] + [(x, y1) for x in reversed(stops)] + [(x0, ry)]
for k, ((nx, ny), holder) in enumerate(zip(nodes, wd._SPLASH_HOLDERS)):
    color = ROLE[holder] if holder else ROLE["phosphor_dim"]
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            d = math.hypot(dx, dy)
            if holder and d <= 2.6:
                put(nx + dx, ny + dy, mix(color, (255, 255, 255), 0.35) if d < 1 else color)
            elif not holder and 1.6 <= d <= 2.7:
                put(nx + dx, ny + dy, color)
            elif not holder and d < 1.6:
                put(nx + dx, ny + dy, GLASS)
    label = f"{k + 1:02d}"
    if ny == y0:
        text(nx - 3, ny - 10, label, ROLE["grey"])
    elif ny == y1:
        text(nx - 3, ny + 6, label, ROLE["grey"])
    elif nx == x1:
        text(nx + 6, ny - 2, label, ROLE["grey"])
    else:
        text(nx - 13, ny - 2, label, ROLE["grey"])

chip = "SEASON 1"
chip_w = text_width(chip) + 16
text(cx - text_width(chip) // 2, ry - 2, chip, ROLE["amber"])
for sx in (cx - chip_w // 2 + 2, cx + chip_w // 2 - 3):  # the chip's two diamonds
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if abs(dx) + abs(dy) <= 2:
                put(sx + dx, ry + dy, ROLE["amber"])

# -- the tube: phosphor bloom, scanlines, a vignette, and the bezel ------------
bloomed = [[None] * W for _ in range(H)]
for y in range(H):
    for x in range(W):
        if glow[y][x] is not None:
            continue
        acc, weight = [0.0, 0.0, 0.0], 0.0
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and glow[yy][xx] is not None:
                    w_ = (1 - math.hypot(dx, dy) / 4.3) ** 2 if math.hypot(dx, dy) < 4.3 else 0
                    for i in range(3):
                        acc[i] += glow[yy][xx][i] * w_
                    weight += w_
        if weight:
            bloomed[y][x] = (tuple(round(v / weight) for v in acc), weight)
for y in range(H):
    for x in range(W):
        if bloomed[y][x]:
            color, weight = bloomed[y][x]
            dither(x, y, color, min(0.38, weight * 0.05))
BEZEL, INSET = (24, 26, 24), 7
for y in range(H):
    for x in range(W):
        if y % 2:
            img[y][x] = shade(img[y][x], 0.82)  # scanlines
        nx_, ny_ = (x - cx) / (W / 2), (y - H / 2) / (H / 2)
        img[y][x] = shade(img[y][x], 1 - 0.32 * max(0.0, (nx_ * nx_ + ny_ * ny_) - 0.35))
        # The bezel: a rounded window onto the glass.
        ix = min(x - INSET, W - 1 - INSET - x)
        iy = min(y - INSET, H - 1 - INSET - y)
        corner = 12
        outside = ix < 0 or iy < 0 or (ix < corner and iy < corner
                                         and math.hypot(corner - ix, corner - iy) > corner)
        if outside:
            edge = min(x, W - 1 - x, y, H - 1 - y)
            img[y][x] = shade(BEZEL, 0.75 + 0.05 * min(edge, 5))
# -- write a PNG with nothing but the standard library -------------------------
out = []
for y in range(H * SCALE):
    src_row = img[y // SCALE]
    line = bytearray(b"\x00")
    for x in range(W * SCALE):
        line.extend(bytes(src_row[x // SCALE]))
    out.append(bytes(line))


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W * SCALE, H * SCALE, 8, 2, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(b"".join(out), 9)) + chunk(b"IEND", b"")
with open(out_path, "wb") as f:
    f.write(png)
print(out_path, W * SCALE, H * SCALE)
