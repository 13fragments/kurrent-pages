"""Engine-side removal of scan furniture before reading (ship plan WP2). Fixed image rules, no learned detector.

Furniture (BENCHMARK_PROTOCOL §3.2 item 9): colour and grey charts, rulers, label cards beside the leaf, and footers,
logos, links, and copyright lines that the imaging adds. Marks on the leaf (stamps, pasted labels, foliation,
letterheads) stay.

Method: the furniture is painted over; the image keeps its size (the screen of EXP-20261112-furniture-screen tested
painting, not cropping). All rules run on a working copy with a long side of 500 px.

Colours. Paper: the median of the brighter 60 % of the image centre (35-65 % of each side). Surround: the median of
the outer 2 % frame. Paper-like pixel: brightness within 50 of the paper, yellow-blue tone ((R+G)/2-B) and red-green
tone (R-G) each within 25. Near the paper (a colour): brightness within 20, both tones within 12. A scan surround exists
when the surround colour is not near the paper.

Protected leaf box. The paper-like objects (closed with 5 px; with a scan surround, only pixels that differ from the
surround by more than 28) of at least 25 % of the largest one (both leaves of a spread), plus 1.5 %. Nothing inside
this box is ever painted: every box of the rules below is cut to its parts outside it. Every qualifying object is
protected, whatever rule 2 finds. Rule 2 boxes are found on the unpainted copy; a chart box wholly inside the
protected box is not painted and is listed in the notes. Fail-safe: when the box covers
under 30 % of the image, nothing is painted.

Rules, in this order:
  1. Footer band. At the bottom edge only: a run of rows (5-row median) in which at least 50 % of the pixels are
     within 30 of the colour of the outermost 3 rows, 1.5-25 % of the height, ending at a straight full-width edge
     (in at least 80 % of the columns the colour changes by more than 25 within 2 rows), and whose colour is not near
     the paper, is painted in its own colour. These are the footer banners that libraries add.
  2. Charts beside the leaf, only with a scan surround. A chart is marked by at least 3 adjacent lines (columns or
     rows) that each cross at least 3 hues (12 bins) as solid runs of at least 5 px of saturated pixels (HSV
     saturation > 0.45, value > 0.25); ink and stamps cross one or two hues in short runs. Painted: the object that
     holds the patches (pixels that differ from the surround by more than 28, closed with 3 px), joined with objects in
     line with it (the ruler part: at least half of their width or height inside the chart's strip, each at least
     0.2 % and under 25 % of the image), when the box, before and after the join, covers at most 25 % of the image
     (margin 1 %); else, when the
     strip from the patches to the nearest image edge is at most 15 % of the image wide (or high) and holds at most
     35 % paper-like pixels, that strip (margin 2 %). Fill: the surround colour. Charts lying on the leaf, grey charts,
     and rulers without colour patches are not found by this rule (ship plan WP2b); the notes list chart marks that
     were not painted.
  3. Margins outside the leaf, only with a scan surround. From each side, lines (rows or columns) in which under 12 %
     of the pixels are paper-like and not painted by rules 1-2 are off the leaf; the scan goes inward until the first
     line on the leaf, at most 45 % of the size. The off-leaf lines, less a margin of 1.5 %, are painted in their
     median colour. Fail-safe: when the remaining leaf box is under 30 % of the image, rule 3 paints nothing.
A page with no painted box is passed unchanged (the original file). Every painted box is returned in the record, in
pixels of the original image. Dependencies: numpy and Pillow only.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

VERSION = "fp-v16"
WORK = 500
LEAF_SHARE = 0.12


def _labels(mask: np.ndarray):
    """4-connected components of a boolean mask (run-length union-find): list of {area, box=(x0, y0, x1, y1)}."""
    parent: list[int] = []

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    prev: list[tuple[int, int, int]] = []
    runs_all = []
    for y in range(mask.shape[0]):
        row = mask[y]
        if not row.any():
            prev = []
            continue
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        cur, j = [], 0
        for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
            lab = len(parent)
            parent.append(lab)
            while j < len(prev) and prev[j][1] <= s:
                j += 1
            k = j
            while k < len(prev) and prev[k][0] < e:
                a, b = find(prev[k][2]), find(lab)
                if a != b:
                    parent[max(a, b)] = min(a, b)
                k += 1
            cur.append((s, e, lab))
            runs_all.append((y, s, e, lab))
        prev = cur
    comps: dict[int, dict] = {}
    for y, s, e, lab in runs_all:
        c = comps.setdefault(find(lab), {"area": 0, "box": [int(s), y, int(e), y + 1]})
        c["area"] += int(e - s)
        b = c["box"]
        b[0], b[1], b[2], b[3] = min(b[0], int(s)), min(b[1], y), max(b[2], int(e)), max(b[3], y + 1)
    return list(comps.values())


def _close(mask: np.ndarray, size: int) -> np.ndarray:
    m = Image.fromarray(mask.astype(np.uint8) * 255)
    return np.asarray(m.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))) > 0


def _overlap(c, b):
    return c["box"][0] < b[2] and c["box"][2] > b[0] and c["box"][1] < b[3] and c["box"][3] > b[1]


def _union(cs):
    return (min(c["box"][0] for c in cs), min(c["box"][1] for c in cs), max(c["box"][2] for c in cs),
            max(c["box"][3] for c in cs))


def _median5(v: np.ndarray) -> np.ndarray:
    p = np.pad(v, 2, mode="edge")
    return np.median(np.stack([p[i:i + len(v)] for i in range(5)]), axis=0)


def _longest_run(v: np.ndarray) -> int:
    if not v.any():
        return 0
    d = np.diff(np.concatenate([[0], v.astype(np.int8), [0]]))
    return int((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).max())


def _tone(x):
    x = np.asarray(x, float)
    return x.mean(axis=-1), (x[..., 0] + x[..., 1]) / 2 - x[..., 2], x[..., 0] - x[..., 1]


def _band(a: np.ndarray, side: str):
    """Rule 1. Returns (y0, y1, colour) in working pixels, or None."""
    H = a.shape[0]
    rows = a if side == "bottom" else a[::-1]
    col = np.median(rows[-3:].reshape(-1, 3), axis=0)
    close = _median5((np.abs(rows - col).max(axis=2) <= 30).mean(axis=1))
    n = 0
    for y in range(H - 1, -1, -1):
        if close[y] < 0.5:
            break
        n += 1
    if not (0.015 * H <= n <= 0.25 * H):
        return None
    e = H - n
    lo, hi = max(1, e - 2), min(H - 1, e + 2)
    grad = np.abs(np.diff(rows[lo - 1:hi + 1], axis=0)).max(axis=2).max(axis=0)
    if (grad > 25).mean() < 0.8:
        return None
    return (e, H, col) if side == "bottom" else (0, n, col)


def _chart_seeds(sm: Image.Image, h: int, w: int):
    """Rule 2 marks: [(kind, box)] with the bounding box of the saturated pixels on the marked lines."""
    hsv = np.asarray(sm.convert("HSV")).astype(float)
    sat = (hsv[..., 1] / 255 > 0.45) & (hsv[..., 2] / 255 > 0.25)
    if not sat.any():
        return []
    hb = (hsv[..., 0] // 21.34).astype(int)
    seeds = []
    for kind, n in (("column", w), ("row", h)):
        hits = []
        for i in range(n):
            ls = sat[:, i] if kind == "column" else sat[i]
            if ls.sum() < 10:
                continue
            lh = hb[:, i] if kind == "column" else hb[i]
            if sum(1 for b in range(12) if _longest_run(ls & (lh == b)) >= 5) >= 3:
                hits.append(i)
        groups, cur = [], []
        for i in hits:
            if cur and i - cur[-1] > 3:
                groups.append(cur)
                cur = []
            cur.append(i)
        if cur:
            groups.append(cur)
        for g in groups:
            if len(g) < 3:
                continue
            lo, hi = g[0], g[-1] + 1
            m = np.zeros_like(sat)
            if kind == "column":
                m[:, lo:hi] = sat[:, lo:hi]
            else:
                m[lo:hi] = sat[lo:hi]
            ys, xs = np.nonzero(m)
            seeds.append((kind, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)))
    return seeds


def _chart_boxes(a, sm, h, w, surround, has_surround, paper):
    """Rule 2: ([(rule, box)] in working pixels, [notes]). Only charts beside the leaf are painted."""
    seeds = _chart_seeds(sm, h, w)
    if not seeds:
        return [], []
    if not has_surround:
        return [], [f"chart mark {kind} {list(sb)}: no scan surround: not painted" for kind, sb in seeds]
    out, notes = [], []
    obj_comps = _labels(_close(np.abs(a - surround).max(axis=2) > 28, 3))
    for kind, sb in seeds:
        hit = [c for c in obj_comps if _overlap(c, sb)]
        if hit:
            x0, y0, x1, y1 = _union(hit)
            if (x1 - x0) * (y1 - y0) <= 0.25 * h * w:
                for c in obj_comps:
                    if c in hit or c["area"] < 0.002 * h * w:
                        continue
                    cx0, cy0, cx1, cy1 = c["box"]
                    if (cx1 - cx0) * (cy1 - cy0) > 0.25 * h * w:
                        continue
                    ov = (min(x1, cx1) - max(x0, cx0)) / max(1, cx1 - cx0) if kind == "column" \
                        else (min(y1, cy1) - max(y0, cy0)) / max(1, cy1 - cy0)
                    if ov > 0.5:
                        x0, y0, x1, y1 = min(x0, cx0), min(y0, cy0), max(x1, cx1), max(y1, cy1)
                if (x1 - x0) * (y1 - y0) <= 0.25 * h * w:  # the joined box is checked again
                    out.append((f"chart_{kind}_object", (x0 - 0.01 * w, y0 - 0.01 * h, x1 + 0.01 * w, y1 + 0.01 * h)))
                else:
                    notes.append(f"chart mark {kind} {list(sb)}: joined chart box over 25 % of the image: not painted")
                continue
        mx, my = 0.02 * w, 0.02 * h
        if kind == "column":
            strip = (0, 0, sb[2] + mx, h) if (sb[0] + sb[2]) / 2 < w / 2 else (sb[0] - mx, 0, w, h)
            narrow = strip[2] - strip[0] <= 0.15 * w
        else:
            strip = (0, 0, w, sb[3] + my) if (sb[1] + sb[3]) / 2 < h / 2 else (0, sb[1] - my, w, h)
            narrow = strip[3] - strip[1] <= 0.15 * h
        sx0, sy0, sx1, sy1 = [int(max(0, v)) for v in strip]
        if narrow and paper[sy0:sy1, sx0:sx1].mean() <= 0.35:
            out.append((f"chart_{kind}_strip", strip))
        else:
            notes.append(f"chart mark {kind} {list(sb)}: touches the leaf, not beside it: not painted")
    return out, notes


def preprocess(img: Image.Image):
    """Return (painted copy, record). The record lists every painted box in original pixels. With no box, the copy
    equals the input and the caller passes the original file."""
    img = img.convert("RGB")
    W0, H0 = img.size
    k = WORK / max(W0, H0)
    sm = img.resize((max(1, round(W0 * k)), max(1, round(H0 * k))), Image.BILINEAR)
    a = np.asarray(sm).astype(float)
    h, w = a.shape[:2]
    boxes, notes = [], []
    done = np.zeros((h, w), bool)  # painted so far; never counts as leaf

    core = None  # the protected leaf box (set below); nothing inside it is ever painted

    def add(rule, x0, y0, x1, y1, fill):
        """Paint the parts of the box outside the protected leaf box; return the number of parts painted."""
        n = 0
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        parts = [(x0, y0, x1, y1)]
        if core is not None:  # keep only the parts outside the protected leaf box (at most four rectangles)
            cx0, cy0, cx1, cy1 = core
            parts = [(x0, y0, x1, min(y1, cy0)), (x0, max(y0, cy1), x1, y1),
                     (x0, max(y0, cy0), min(x1, cx0), min(y1, cy1)), (max(x0, cx1), max(y0, cy0), x1, min(y1, cy1))]
        for px0, py0, px1, py1 in parts:
            if px1 - px0 < 1 or py1 - py0 < 1:
                continue
            ob = [int(px0 / k), int(py0 / k), min(W0, int(np.ceil(px1 / k))), min(H0, int(np.ceil(py1 / k)))]
            boxes.append({"rule": rule, "box": ob, "fill": [int(v) for v in fill]})
            a[int(py0):int(np.ceil(py1)), int(px0):int(np.ceil(px1))] = fill
            done[int(py0):int(np.ceil(py1)), int(px0):int(np.ceil(px1))] = True
            n += 1
        return n

    cen = a[int(0.35 * h):int(0.65 * h), int(0.35 * w):int(0.65 * w)].reshape(-1, 3)
    Yc = cen.mean(axis=1)
    paper_col = np.median(cen[Yc >= np.percentile(Yc, 40)], axis=0)
    Yp, YBp, RGp = _tone(paper_col)

    def paperlike(x):
        Y, YB, RG = _tone(x)
        return (np.abs(Y - Yp) <= 50) & (np.abs(YB - YBp) <= 25) & (np.abs(RG - RGp) <= 25)

    def near_paper(c):
        Y, YB, RG = _tone(c)
        return abs(Y - Yp) <= 20 and abs(YB - YBp) <= 12 and abs(RG - RGp) <= 12

    f = max(2, int(0.02 * min(h, w)))
    frame = np.concatenate([a[:f].reshape(-1, 3), a[-f:].reshape(-1, 3), a[:, :f].reshape(-1, 3), a[:, -f:].reshape(-1, 3)])
    surround = np.median(frame, axis=0)
    has_surround = not near_paper(surround)

    # protected leaf box: the paper-like objects (closed with 5 px; with a surround, only pixels that differ from it
    # by more than 28) of at least 25 % of the largest one (both leaves of
    # a spread), plus 1.5 %; fail-safe: under 30 % of the image, nothing is painted
    leafpix = paperlike(a)
    if has_surround:  # a surround close in tone to the paper (grey card on grey) is not leaf
        leafpix &= np.abs(a - surround).max(axis=2) > 28
    comps = _labels(_close(leafpix, 5))
    if not comps:
        notes.append("no paper-like object: nothing painted")
        return img.copy(), {"version": VERSION, "size": [W0, H0], "boxes": [], "notes": notes, "painted_share": 0.0}
    big = max(comps, key=lambda c: c["area"])
    # every paper-like object of at least 25 % of the largest is protected, whatever the chart rule finds
    keep = [c for c in comps if c["area"] >= 0.25 * big["area"]]
    cb, cn = _chart_boxes(a.copy(), sm, h, w, surround, has_surround, paperlike(a))
    notes.extend(cn)
    lx0, ly0, lx1, ly1 = _union(keep)
    if (lx1 - lx0) * (ly1 - ly0) < 0.3 * h * w:
        notes.append("protected leaf box under 30 % of the image: nothing painted")
        return img.copy(), {"version": VERSION, "size": [W0, H0], "boxes": [], "notes": notes, "painted_share": 0.0}
    core = (max(0, lx0 - 0.015 * w), max(0, ly0 - 0.015 * h), min(w, lx1 + 0.015 * w), min(h, ly1 + 0.015 * h))


    # Rule 1: bands
    r = _band(a, "bottom")
    if r and not near_paper(r[2]):
        add("band_bottom", 0, r[0], w, r[1], r[2])
    elif r:
        notes.append("band_bottom near the paper colour: not painted")

    # Rule 2: charts (boxes found above)
    for rule, box in cb:
        if not add(rule, *box, surround):
            notes.append(f"{rule} {[round(v) for v in box]}: inside the protected leaf box: not painted")

    # Rule 3: off-leaf margins
    paper = paperlike(a) & ~done
    share_r, share_c = paper.mean(axis=1), paper.mean(axis=0)

    def scan(share, n):
        i = 0
        while i < int(0.45 * n) and share[i] < LEAF_SHARE:
            i += 1
        return i

    top, bot = scan(share_r, h), scan(share_r[::-1], h)
    left, right = scan(share_c, w), scan(share_c[::-1], w)
    if not has_surround:
        notes.append("no scan surround: no margin painted")
    elif (w - right - left) * (h - bot - top) < 0.3 * h * w:
        notes.append("leaf box under 30 %: no margin painted")
    else:
        mx, my = 0.015 * w, 0.015 * h
        for name, (x0, y0, x1, y1) in (("top", (0, 0, w, top - my)), ("bottom", (0, h - bot + my, w, h)),
                                        ("left", (0, 0, left - mx, h)), ("right", (w - right + mx, 0, w, h))):
            if x1 - x0 >= 1 and y1 - y0 >= 1:
                fill = np.median(a[int(y0):int(np.ceil(y1)), int(x0):int(np.ceil(x1))].reshape(-1, 3), axis=0)
                add(f"margin_{name}", x0, y0, x1, y1, fill)

    out = img.copy()
    d = ImageDraw.Draw(out)
    painted = np.zeros((H0, W0), bool)
    for b in boxes:
        x0, y0, x1, y1 = b["box"]
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=tuple(b["fill"]))
        painted[y0:y1, x0:x1] = True
    rec = {"version": VERSION, "size": [W0, H0], "boxes": boxes, "notes": notes,
           "painted_share": round(float(painted.mean()), 4)}
    return out, rec
