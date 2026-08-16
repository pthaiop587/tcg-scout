"""Cut a flatbed scan of a whole page into one image per card.

The Brother scans a full sheet -- 8.5x11 at 300 dpi -- however many cards you
laid on the glass. Nothing downstream wants a page; eBay wants one picture per
card. This finds each card in the page, straightens it, and writes it out on
its own.

    python crop_scans.py                    # photos/scans -> photos/crops
    python crop_scans.py --src "C:/Users/pthai/Documents/Scans"
    python crop_scans.py --preview          # also write a marked-up page
    python crop_scans.py --move             # clear the source once it worked

Multi-page PDFs are the normal case, because that is what scan-to-folder
writes. Plain images work too, so a phone photo goes through the same path.

Crops come out in READING ORDER -- top row left to right, then the next row.
That is not cosmetic. The next step is

    python add_photos.py --src photos/crops --assign CRH-0001,CRH-0002 --pairs

which maps files onto SKUs by filename order, so if the order were the order
OpenCV happened to find the contours, photos would land on the wrong cards.

The crops carry no EXIF, same reasoning as add_photos.py: a phone photo knows
where it was taken and these end up in a public repo.
"""

import argparse
import os
import sys

import cv2
import numpy as np

SCANS = os.path.join("photos", "scans")
CROPS = os.path.join("photos", "crops")

IMG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
PAGE_EXTS = IMG_EXTS | {".pdf"}

# Detection runs on a shrunk copy. A card edge is a big feature; nothing is
# gained by hunting for it across 8 megapixels, and it costs a second a page.
WORK_EDGE = 1200

# A card is 2.5 x 3.5 inches -- short/long = 0.714. Toploaders, slabs and
# oversized inserts widen that, so the band is deliberately loose. What it
# still throws out is dust, a strip of shadow, and the sheet itself.
ASPECT_MIN = 0.55
ASPECT_MAX = 0.95

# Physical bounds in inches, applied only when we know the dpi (always true
# for a PDF, since we choose the raster dpi ourselves).
SHORT_IN = (1.2, 4.5)
LONG_IN = (1.8, 6.5)

# Fractions of the page, applied always. The upper bound is what stops the
# page itself being returned as one enormous card.
MIN_AREA_FRAC = 0.010
MAX_AREA_FRAC = 0.85

# How square-cornered a blob has to be to count. Cards are rectangles; a
# spill of glare or a shadow is not.
MIN_RECTANGULARITY = 0.80

# What share of the page counts as edge.
#
# This was 92, which is far too generous once a scan has grain on it: 8% of a
# page is a lot of scattered speckle, the close welds it into one page-sized
# blob, and either the card vanishes or a speck stuck to it stretches its
# convex hull until the rectangularity test throws it out. 98 is enough edge
# to outline four cards on a sheet and still finds a white border against a
# white lid, which is the faintest line this has to see.
#
# A floor at a multiple of the median gradient was tried instead and dropped.
# It worked, but a multiple of the median is a different threshold in each
# implementation -- the browser's downscale smooths more, so its median ran
# about a third of the script's and the same constant admitted four times as
# much. A percentile picks a *share*, so both ends agree by construction,
# which is the property that actually matters when two croppers must find the
# same cards on the same page.
EDGE_PERCENTILE = 98

# And a floor, because a percentile always admits its share: a page with one
# card on it, whose real edge is well under 2% of the page, otherwise drags
# the threshold down into the paper grain. The floor reads the noise level off
# the median gradient -- grain sits near it, a card edge is orders of
# magnitude above. Measured here it changes nothing at any value from 0 to 40,
# because cv2.GaussianBlur returns uint8 and those gradients already tie
# heavily past the threshold; in the browser, where the blur is float and
# nothing ties, it is the difference between finding one card and finding
# none. Kept in both, at the same value, so the two cannot drift apart.
EDGE_NOISE_MULT = 20.0

JPEG_QUALITY = 95

# A card in a toploader measures 3 x 4 inches, not 2.5 x 3.5, because the
# holder is what has the outer edge -- so the crop keeps the holder's rim.
# That is deliberate. Three ways of trimming to the card inside were tried
# (background threshold, contours on the crop, brightness and ink projection
# profiles) and none could separate "plastic beyond the card" from "the
# card's own white border" reliably, because on a flatbed they are the same
# thing: a flat pale margin. Guessing wrong cuts the border off, and border
# and centring are the first things a buyer inspects. A rim of plastic in
# the photo costs nothing and shows the card is protected. Use --pad with a
# negative number to trim a fixed amount by hand.


class Card(object):
    """One detected card: where it is on the page, and how sure we are."""

    def __init__(self, rect, rectangularity):
        self.rect = rect                      # ((cx, cy), (w, h), angle)
        self.rectangularity = rectangularity

    @property
    def centre(self):
        return self.rect[0]

    @property
    def size(self):
        return self.rect[1]


def imread_any(path):
    """cv2.imread cannot open a path with a non-ASCII character on Windows."""
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not an image OpenCV can read")
    return img


def imwrite_any(path, img, quality=JPEG_QUALITY):
    ext = os.path.splitext(path)[1] or ".jpg"
    ok, buf = cv2.imencode(ext, img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("could not encode %s" % path)
    buf.tofile(path)


def load_pages(path, dpi=300):
    """Every page of a scan as a BGR array, with the dpi if we know it.

    Returns a list of (page_number, image, dpi_or_None). dpi is None for a
    plain image, because a photo off a phone has no meaningful one and
    guessing would silently change what counts as card-sized.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        import fitz                            # PyMuPDF, only needed for PDFs

        out = []
        with fitz.open(path) as doc:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=dpi)
                buf = np.frombuffer(pix.samples, dtype=np.uint8)
                img = buf.reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                elif pix.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                else:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                out.append((i + 1, img, dpi))
        return out
    return [(1, imread_any(path), None)]


def background_colour(bgr):
    """The lid, sampled from a ring round the edge of the page.

    Cards get laid somewhere near the middle of the glass, so the outermost
    band is background almost by definition. Median, not mean, so one card
    pushed right to the edge cannot drag the estimate.
    """
    h, w = bgr.shape[:2]
    band = max(2, int(min(h, w) * 0.02))
    ring = np.concatenate([
        bgr[:band].reshape(-1, 3),
        bgr[-band:].reshape(-1, 3),
        bgr[:, :band].reshape(-1, 3),
        bgr[:, -band:].reshape(-1, 3),
    ])
    return np.median(ring, axis=0)


def card_mask(bgr):
    """Where the page is not lid.

    Two signals, because either one alone has a blind spot.

    The colour signal -- pixels far from the background -- is strong and
    solid, but a card with a white border on a white lid is invisible to it,
    and that is half of Topps. Alone it would crop the art and cut the border
    off, which is exactly the part a buyer inspects for centring.

    The edge signal catches that border, because a card sits a millimetre
    above the glass and always throws a faint line. Alone it is a hollow
    outline with gaps in it, so it gets closed up and filled.

    That edge is found by taking the top slice of the gradient rather than by
    Canny. Canny's thresholds are absolute, and the line where a white border
    meets a white lid is worth only a few levels of grey -- measured on a
    white-bordered fixture, Canny locked onto the artwork window and returned
    78% of the card, shearing the border clean off. A percentile adapts to
    whatever contrast the scan actually has and gets the whole card.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0).astype(np.float32)

    mag = cv2.magnitude(cv2.Scharr(blur, cv2.CV_32F, 1, 0),
                        cv2.Scharr(blur, cv2.CV_32F, 0, 1))
    thr = max(float(np.percentile(mag, EDGE_PERCENTILE)),
              EDGE_NOISE_MULT * float(np.median(mag)))
    edges = (mag > thr).astype(np.uint8) * 255

    bg = background_colour(bgr)
    diff = np.abs(bgr.astype(np.int16) - bg.astype(np.int16)).max(axis=2)
    colour = (diff > 22).astype(np.uint8) * 255

    mask = cv2.bitwise_or(edges, colour)

    # Seal the gaps in the edge outline, then fill what is now a closed ring.
    # The kernel is a fraction of the page so it behaves the same whatever
    # resolution the scan came in at.
    k = max(3, int(min(mask.shape[:2]) * 0.012) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    return mask


def normalise_rect(rect):
    """Force a rotated rect portrait, with the angle that gets it there.

    minAreaRect is free to call the same rectangle 750x1050 at 0 degrees or
    1050x750 at 90. Cards are portrait, so we pick that reading and the crop
    comes out the way up you would hold it.
    """
    (cx, cy), (w, h), angle = rect
    if w > h:
        w, h = h, w
        angle += 90.0
    while angle >= 90.0:
        angle -= 180.0
    while angle < -90.0:
        angle += 180.0
    return ((cx, cy), (w, h), angle)


def detect_cards(bgr, dpi=None):
    """Find the cards on one page, in reading order."""
    h, w = bgr.shape[:2]
    scale = WORK_EDGE / float(max(h, w))
    if scale < 1.0:
        small = cv2.resize(bgr, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_AREA)
    else:
        scale, small = 1.0, bgr

    mask = card_mask(small)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    page_area = float(small.shape[0] * small.shape[1])
    found = []
    for c in contours:
        rect = normalise_rect(cv2.minAreaRect(c))
        (cx, cy), (cw, ch), angle = rect
        if cw < 1 or ch < 1:
            continue

        area = cw * ch
        if area < page_area * MIN_AREA_FRAC or area > page_area * MAX_AREA_FRAC:
            continue
        if not ASPECT_MIN <= cw / ch <= ASPECT_MAX:
            continue
        if cv2.contourArea(c) / area < MIN_RECTANGULARITY:
            continue
        if dpi:
            short_in, long_in = cw / scale / dpi, ch / scale / dpi
            if not SHORT_IN[0] <= short_in <= SHORT_IN[1]:
                continue
            if not LONG_IN[0] <= long_in <= LONG_IN[1]:
                continue

        full = ((cx / scale, cy / scale), (cw / scale, ch / scale), angle)
        found.append(Card(full, cv2.contourArea(c) / area))

    return reading_order(found)


def reading_order(cards):
    """Top row left to right, then the next row down.

    Cards laid on glass are never in a tidy grid, so rows are banded rather
    than assumed: anything whose centre sits within half a card height of the
    row it is being compared to belongs to that row. Sorting on y alone would
    interleave two side-by-side cards whenever one was nudged a few
    millimetres higher than the other.
    """
    if not cards:
        return []
    heights = [c.size[1] for c in cards]
    band = float(np.median(heights)) * 0.5

    rows = []
    for card in sorted(cards, key=lambda c: c.centre[1]):
        for row in rows:
            if abs(card.centre[1] - row[0].centre[1]) <= band:
                row.append(card)
                break
        else:
            rows.append([card])

    out = []
    for row in rows:
        out.extend(sorted(row, key=lambda c: c.centre[0]))
    return out


def extract(bgr, card, pad=0):
    """Straighten one card off the page and return it upright."""
    (cx, cy), (w, h), angle = card.rect
    w, h = w + pad * 2, h + pad * 2
    src = cv2.boxPoints(((cx, cy), (w, h), angle)).astype(np.float32)

    # boxPoints starts at the lowest corner and runs clockwise, which is not
    # a fixed corner. Order it by geometry instead so the card never lands
    # rotated by a quarter turn.
    src = order_corners(src)
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
                   dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(bgr, M, (int(round(w)), int(round(h))))


def order_corners(pts):
    """Corners as top-left, top-right, bottom-right, bottom-left."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([
        pts[np.argmin(s)],      # top-left has the smallest x+y
        pts[np.argmin(d)],      # top-right has the smallest y-x
        pts[np.argmax(s)],      # bottom-right has the largest x+y
        pts[np.argmax(d)],      # bottom-left has the largest y-x
    ], dtype=np.float32)


def turn(bgr, degrees):
    """Rotate a crop by a quarter turn. Lossless -- no resampling."""
    degrees %= 360
    if degrees == 0:
        return bgr
    if degrees == 90:
        return cv2.rotate(bgr, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(bgr, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError("rotate must be 0, 90, 180 or 270")


def preview(bgr, cards):
    """The page with every crop outlined and numbered, so you can check it."""
    out = bgr.copy()
    thick = max(2, int(max(out.shape[:2]) * 0.003))
    for i, card in enumerate(cards, 1):
        box = cv2.boxPoints(card.rect).astype(np.int32)
        cv2.drawContours(out, [box], 0, (0, 200, 0), thick)
        cx, cy = int(card.centre[0]), int(card.centre[1])
        cv2.putText(out, str(i), (cx - 20, cy), cv2.FONT_HERSHEY_SIMPLEX,
                    thick * 0.9, (0, 0, 255), thick + 1, cv2.LINE_AA)
    return out


def process(path, out_dir, dpi=300, want_preview=False, pad=0,
            rotate=0):
    """Cut one scan file into cards. Returns the paths written."""
    stem = os.path.splitext(os.path.basename(path))[0]
    written = []
    for page_no, img, page_dpi in load_pages(path, dpi):
        cards = detect_cards(img, page_dpi)
        if not cards:
            print("   %s page %d: found no cards" % (stem, page_no))
            continue
        for i, card in enumerate(cards, 1):
            crop = extract(img, card, pad)
            crop = turn(crop, rotate)
            name = "%s-p%d-%02d.jpg" % (stem, page_no, i)
            dest = os.path.join(out_dir, name)
            imwrite_any(dest, crop)
            written.append(dest)
        print("   %s page %d: %d card%s" %
              (stem, page_no, len(cards), "" if len(cards) == 1 else "s"))
        if want_preview:
            shot = os.path.join(out_dir, "%s-p%d-PREVIEW.jpg" % (stem, page_no))
            imwrite_any(shot, preview(img, cards))
    return written


def main():
    p = argparse.ArgumentParser(
        description="Cut a page scan into one image per card.")
    p.add_argument("files", nargs="*",
                   help="scans to cut; default is everything in photos/scans")
    p.add_argument("--src", default=SCANS,
                   help="folder of scans (default photos/scans)")
    p.add_argument("--out", default=CROPS,
                   help="where the crops go (default photos/crops)")
    p.add_argument("--dpi", type=int, default=300,
                   help="raster dpi for PDFs, and the size hint (default 300)")
    p.add_argument("--pad", type=int, default=0,
                   help="pixels of margin to keep around each card")
    p.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270],
                   help="turn every crop, for when the cards went on the "
                        "glass upside down (scan one page and look first)")
    p.add_argument("--preview", action="store_true",
                   help="also write the page with the crops outlined")
    p.add_argument("--move", action="store_true",
                   help="delete each scan once its cards are written")
    a = p.parse_args()

    files = list(a.files)
    if not files:
        if not os.path.isdir(a.src):
            os.makedirs(a.src, exist_ok=True)
            print("made %s -- put your scans in there and run this again."
                  % a.src)
            return 0
        files = [os.path.join(a.src, f) for f in sorted(os.listdir(a.src))
                 if os.path.splitext(f)[1].lower() in PAGE_EXTS]
    if not files:
        print("nothing to cut in %s" % a.src)
        return 0

    os.makedirs(a.out, exist_ok=True)
    total = 0
    for path in files:
        try:
            written = process(path, a.out, a.dpi, a.preview, a.pad,
                              a.rotate)
        except Exception as e:                # one bad scan must not stop the rest
            print("   %s: %s" % (os.path.basename(path), e))
            continue
        total += len(written)
        if written and a.move:
            os.remove(path)

    print("\nwrote %d crop%s to %s" % (total, "" if total == 1 else "s", a.out))
    if total:
        print("check them, then file them onto SKUs in that order:")
        print("   python add_photos.py --src %s --assign CRH-0001,CRH-0002 "
              "--pairs" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
