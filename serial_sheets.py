"""Contact sheets magnified enough to read a serial number.

    python serial_sheets.py batch.json
    python serial_sheets.py batch.json --per 4 --out serials

WHY A SEPARATE PASS.

The normal contact sheet fits nine cards to a page so a batch can be
identified in a few looks. That is the right trade for "who is this and what
set" -- printed large across the card -- and the wrong one for a serial
number, which is a few millimetres of foil and can sit anywhere: under the
photo, beside the logo, on the back by the card number, tucked in a border.

A serial is roughly 3mm on an 89mm card, so about 3.5% of its height. At nine
to a page that is four pixels and a guess. At four to a page, drawn from the
full-resolution original rather than the downscaled copy, it is thirty pixels
and legible.

WHY IT READS THE ORIGINAL.

prep writes a 1700px copy for identification, and on those the card itself is
only ~800px because it does not fill the frame. Cropping to the card in the
12-megapixel original instead gives roughly 1500x2100 to work with -- the
detail is there, it was just being thrown away before the crop.

Both sides, because serials turn up on either.
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageOps


def card_box(im, pad=0.015):
    """Where the card is, found by where the picture stops looking like cloth.

    Standard deviation per row and column, not distance from a background
    colour: a card photographed on grey cloth defeats the second, because a
    white border IS close to grey cloth. Texture is what differs.
    """
    small = im.convert("L")
    small.thumbnail((400, 400))
    a = np.asarray(small, dtype=float)
    rows, cols = a.std(axis=1), a.std(axis=0)
    ys = np.where(rows > rows.mean() * 1.15)[0]
    xs = np.where(cols > cols.mean() * 1.15)[0]
    if len(xs) < 4 or len(ys) < 4:
        return None
    sx, sy = im.size[0] / float(a.shape[1]), im.size[1] / float(a.shape[0])
    px, py = im.size[0] * pad, im.size[1] * pad
    box = (max(0, int(xs[0] * sx - px)), max(0, int(ys[0] * sy - py)),
           min(im.size[0], int(xs[-1] * sx + px)),
           min(im.size[1], int(ys[-1] * sy + py)))
    w, h = box[2] - box[0], box[3] - box[1]
    # A box smaller than a card plausibly is means the detector lost it;
    # the whole frame is a worse answer than none, so say none.
    if w < im.size[0] * 0.12 or h < im.size[1] * 0.12:
        return None
    return box


def card_image(path, long_edge=1500):
    """The card alone, as big as the original will give."""
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    box = card_box(im)
    if box:
        im = im.crop(box)
    im.thumbnail((long_edge, long_edge), Image.LANCZOS)
    return im


def sheets(items, out_dir, per=4, cols=2, cell=(760, 1040), label=""):
    """Tile the cards, biggest that still fits a readable page."""
    os.makedirs(out_dir, exist_ok=True)
    made = []
    cw, ch = cell
    for start in range(0, len(items), per):
        chunk = items[start:start + per]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (cw + 10) + 10,
                                  rows * (ch + 34) + 10), (244, 244, 248))
        d = ImageDraw.Draw(sheet)
        for i, (caption, path) in enumerate(chunk):
            try:
                im = card_image(path)
            except OSError:
                continue
            im.thumbnail((cw, ch), Image.LANCZOS)
            r, c = divmod(i, cols)
            x, y = 10 + c * (cw + 10), 10 + r * (ch + 34)
            sheet.paste(im, (x + (cw - im.size[0]) // 2,
                             y + (ch - im.size[1]) // 2))
            d.text((x + 4, y + ch + 9), caption, fill=(20, 20, 30))
        p = os.path.join(out_dir, "%sserial-%02d.jpg"
                         % (label, start // per + 1))
        sheet.save(p, quality=95)
        made.append(p)
    return made


def main():
    ap = argparse.ArgumentParser(
        description="Contact sheets big enough to read a serial number.")
    ap.add_argument("batch", help="the batch json written by prep")
    ap.add_argument("--originals", default=r"G:\Scans",
                    help="where the raw files are (default G:\\Scans)")
    ap.add_argument("--per", type=int, default=4,
                    help="cards per sheet (default 4; more means smaller)")
    ap.add_argument("--out", help="folder for the sheets (default: the work "
                                  "folder in the batch)")
    a = ap.parse_args()

    with open(a.batch, encoding="utf-8") as fh:
        d = json.load(fh)
    work = d.get("work") or "."
    out = a.out or os.path.join(work, "serials")

    def find(stem):
        """The original if it is still there, else the converted copy."""
        for ext in (".DNG", ".dng", ".jpg", ".jpeg"):
            p = os.path.join(a.originals, stem + ext)
            if os.path.exists(p):
                return p
        p = os.path.join(work, stem + ".jpg")
        return p if os.path.exists(p) else None

    items = []
    for c in d["cards"]:
        who = str(c.get("name") or "").strip() or "?"
        for side in ("front", "back"):
            stem = c.get(side)
            if not stem:
                continue
            p = find(stem)
            if p:
                items.append(("%2d %-22s %-5s %s" % (c["n"], who[:22], side,
                                                     stem), p))

    if not items:
        sys.exit("no images found for %s" % a.batch)
    made = sheets(items, out, per=a.per)
    print("%d image(s) from %d card(s)" % (len(items), len(d["cards"])))
    print("%d sheet(s) at %d per page, in %s" % (len(made), a.per, out))
    for p in made[:6]:
        print("   %s" % p)
    if len(made) > 6:
        print("   ... and %d more" % (len(made) - 6))


if __name__ == "__main__":
    main()
