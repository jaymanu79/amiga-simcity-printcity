#!/usr/bin/env python3
"""Render Amiga SimCity city files to PNG, like PrintCity does.

PrintCity (Maxis, 1989) builds the map from the 8x8 tiles stored in
SimData2 and sends it to printer.device. This script does the same
rendering, but saves a full-colour PNG instead of printing.

Two tile sets are available:
  amiga       8x8 tiles from SimData2 (from your own SimCity disk)
  micropolis  16x16 tiles from Micropolis, the GPL release of SimCity,
              bundled in tiles/micropolis/

Usage:
    simcity_render.py CITY [CITY ...] --simdata2 SimData2 [-o OUTDIR]
    simcity_render.py CITY [CITY ...] --tileset micropolis [-o OUTDIR]
    simcity_render.py --tileset micropolis --sheet tiles.png
"""
import argparse
import os
import struct
import sys

from PIL import Image

MAP_W, MAP_H = 120, 100
MAP_BYTES = MAP_W * MAP_H * 2
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


def load_micropolis_tiles(path):
    """Micropolis tiles.png: 16 columns x 60 rows of 16x16 tiles,
    tile n at column n % 16, row n // 16 (same numbering as SimCity)."""
    sheet = Image.open(path).convert('RGB')
    size = sheet.width // 16
    return [sheet.crop((n % 16 * size, n // 16 * size, n % 16 * size + size, n // 16 * size + size))
            for n in range(16 * (sheet.height // size))]


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
    t = tiles[0].width
    missing = Image.new('RGB', (t, t), (255, 0, 255))
    out = Image.new('RGB', (MAP_W * t, MAP_H * t))
    for x in range(MAP_W):
        for y in range(MAP_H):
            v = cmap[x * MAP_H + y] & 0x3ff
            out.paste(tiles[v] if v < len(tiles) else missing, (x * t, y * t))
    if scale != 1:
        out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    return out


def tile_sheet(tiles, cols=32):
    t = tiles[0].width
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * t, rows * t))
    for i, im in enumerate(tiles):
        sheet.paste(im, (i % cols * t, i // cols * t))
    return sheet


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cities', nargs='*', help='city files to render')
    ap.add_argument('-t', '--tileset', choices=('amiga', 'micropolis'), default='amiga',
                    help='tile set (default: amiga)')
    ap.add_argument('--simdata2', metavar='FILE', help='SimData2 file (needed for --tileset amiga)')
    ap.add_argument('--micropolis-png', metavar='FILE', default=MICROPOLIS_PNG,
                    help='Micropolis tiles.png (default: the bundled copy)')
    ap.add_argument('-o', '--outdir', default='.', help='output directory (default: .)')
    ap.add_argument('--scale', type=int, default=1, help='integer zoom factor')
    ap.add_argument('--sheet', metavar='PNG', help='also save a sheet of all tiles')
    a = ap.parse_args()

    if a.tileset == 'amiga':
        if not a.simdata2:
            ap.error('--tileset amiga needs --simdata2 (or use --tileset micropolis)')
        tiles = load_amiga_tiles(a.simdata2)
    else:
        tiles = load_micropolis_tiles(a.micropolis_png)
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
