#!/usr/bin/env python3
"""Render Amiga SimCity city files to PNG, like PrintCity does.

PrintCity (Maxis, 1989) builds the map from the 8x8 tiles stored in
SimData2 and sends it to printer.device. This script does the same
rendering, but saves a full-colour PNG instead of printing.

The tile file given with --tiles is recognised automatically:
  - SimData2 from the Amiga SimCity disk (8x8 tiles, 16 colours);
  - any image holding the 960 tiles, e.g. from Micropolis, the GPL
    release of SimCity: a grid of square tiles (tiles.png, 16x60 tiles)
    or a single column (tiles.xpm, tilessm.xpm).
Without --tiles, the Micropolis tiles bundled in tiles/micropolis/ are used.

Usage:
    simcity_render.py CITY [CITY ...] [--tiles FILE] [-o OUTDIR] [--scale N]
    simcity_render.py --tiles FILE --sheet tiles.png
"""
import argparse
import os
import struct
import sys

from PIL import Image

MAP_W, MAP_H = 120, 100
MAP_BYTES = MAP_W * MAP_H * 2
NTILES = 960
MICROPOLIS_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'tiles', 'micropolis', 'tiles.png')


def load_amiga_tiles(path):
    """SimData2: header (4 words), 16-colour Amiga RGB4 palette, then
    8x8 tiles, 4 bitplanes, plane-sequential (8 bytes per plane)."""
    d = open(path, 'rb').read()
    if d[:2] != b'\xd5\xdb':
        sys.exit(f'{path}: not a SimData2 file (bad magic)')
    words = struct.unpack('>20H', d[:40])
    pal = [((c >> 8 & 15) * 17, (c >> 4 & 15) * 17, (c & 15) * 17) for c in words[4:20]]
    data = d[40:]
    tiles = []
    for t in range(len(data) // 32):
        td = data[t * 32:t * 32 + 32]
        im = Image.new('RGB', (8, 8))
        px = im.load()
        for y in range(8):
            for x in range(8):
                c = sum(((td[p * 8 + y] >> (7 - x)) & 1) << p for p in range(4))
                px[x, y] = pal[c]
        tiles.append(im)
    return tiles


def read_xpm(path):
    """Minimal XPM reader. Pillow misreads 16-bit-per-channel colours
    (#RRRRGGGGBBBB, as in the Micropolis .xpm files)."""
    import re
    rows = re.findall(r'"((?:[^"\\]|\\.)*)"', open(path, encoding='latin1').read())
    w, h, ncol, cpp = map(int, rows[0].split()[:4])
    colours = {}
    for line in rows[1:1 + ncol]:
        key, spec = line[:cpp], line[cpp:].split()
        val = spec[spec.index('c') + 1] if 'c' in spec else spec[-1]
        if val.startswith('#'):
            hx = val[1:]
            n = len(hx) // 3
            colours[key] = tuple(int(hx[i * n:(i + 1) * n], 16) * 255 // (16 ** n - 1) for i in range(3))
        else:
            colours[key] = (0, 0, 0) if val.lower() == 'none' else Image.new('RGB', (1, 1), val).getpixel((0, 0))
    img = Image.new('RGB', (w, h))
    img.putdata([colours[r[x:x + cpp]] for r in rows[1 + ncol:1 + ncol + h] for x in range(0, w * cpp, cpp)])
    return img


def load_image_tiles(path):
    """Image holding the 960 tiles, in SimCity order: either a grid of
    square tiles read row by row (Micropolis tiles.png: 16 columns of
    16x16), or a single column of square tiles (tiles.xpm 16x16, tilessm.xpm 3x3)."""
    try:
        sheet = read_xpm(path) if open(path, 'rb').read(9) == b'/* XPM */' else Image.open(path)
        sheet = sheet.convert('RGB')
    except Exception:
        sys.exit(f'{path}: neither a SimData2 file nor a readable image')
    w, h = sheet.size
    size = round((w * h / NTILES) ** 0.5)
    if size and w % size == 0 and h % size == 0 and (w // size) * (h // size) == NTILES:
        tw = th = size
    elif h % NTILES == 0 and h // NTILES <= w:
        # single column; tiles are square, extra columns are padding
        # (tilessm.xpm: 3x3 tiles in a 4-pixel wide strip)
        tw = th = h // NTILES
    else:
        sys.exit(f'{path}: {w}x{h} image, cannot find {NTILES} tiles in it '
                 '(expected a grid of square tiles or a single column)')
    cols = w // tw
    return [sheet.crop((n % cols * tw, n // cols * th, n % cols * tw + tw, n // cols * th + th))
            for n in range(NTILES)]


def load_tiles(path):
    """Pick the loader from the file content."""
    with open(path, 'rb') as f:
        magic = f.read(2)
    if magic == b'\xd5\xdb':
        return 'SimData2', load_amiga_tiles(path)
    return 'image', load_image_tiles(path)


def load_city(path):
    """City file = MacBinary wrapper (128-byte header, type CITY, creator
    MCRP), then the data fork (27120 bytes), padded to a multiple of 128.
    Bare data forks (Micropolis .cty files) are accepted too.
    The map is the last 24000 bytes of the data fork: 120 columns of 100
    big-endian words, column-major; the low 10 bits are the tile number."""
    c = open(path, 'rb').read()
    if c[65:73] == b'CITYMCRP':
        name = c[2:2 + c[1]].decode('latin1')
        dlen = struct.unpack('>I', c[83:87])[0]
        fork = c[128:128 + dlen]
    else:  # bare data fork
        name = os.path.basename(path)
        fork = c
    if len(fork) < MAP_BYTES:
        sys.exit(f'{path}: too short for a city file')
    return name, struct.unpack('>%dH' % (MAP_W * MAP_H), fork[-MAP_BYTES:])


def render(tiles, cmap, scale=1):
    tw, th = tiles[0].size
    missing = Image.new('RGB', (tw, th), (255, 0, 255))
    out = Image.new('RGB', (MAP_W * tw, MAP_H * th))
    for x in range(MAP_W):
        for y in range(MAP_H):
            v = cmap[x * MAP_H + y] & 0x3ff
            out.paste(tiles[v] if v < len(tiles) else missing, (x * tw, y * th))
    if scale != 1:
        out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    return out


def tile_sheet(tiles, cols=32):
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rows * th))
    for i, im in enumerate(tiles):
        sheet.paste(im, (i % cols * tw, i // cols * th))
    return sheet


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cities', nargs='*', help='city files to render')
    ap.add_argument('-t', '--tiles', '--simdata2', metavar='FILE', default=MICROPOLIS_PNG,
                    help='SimData2 or tile image, detected automatically '
                         '(default: the bundled Micropolis tiles)')
    ap.add_argument('-o', '--outdir', default='.', help='output directory (default: .)')
    ap.add_argument('--scale', type=int, default=1, help='integer zoom factor')
    ap.add_argument('--sheet', metavar='PNG', help='also save a sheet of all tiles')
    a = ap.parse_args()

    kind, tiles = load_tiles(a.tiles)
    tw, th = tiles[0].size
    print(f'tiles: {a.tiles} ({kind}, {len(tiles)} tiles of {tw}x{th})')
    if not a.cities and not a.sheet:
        ap.error('nothing to do: give city files and/or --sheet')

    os.makedirs(a.outdir, exist_ok=True)
    if a.sheet:
        tile_sheet(tiles).save(a.sheet)
    for path in a.cities:
        name, cmap = load_city(path)
        fn = os.path.join(a.outdir, os.path.basename(path).replace(' ', '_') + '.png')
        render(tiles, cmap, a.scale).save(fn)
        print(f'{name}: {fn}')


if __name__ == '__main__':
    main()
