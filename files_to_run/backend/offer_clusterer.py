from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# ---------- Data structures ----------

@dataclass
class OcrWord:
    text: str
    x0: int
    y0: int
    x1: int
    y1: int
    conf: int

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    @property
    def w(self) -> int:
        return self.x1 - self.x0

    @property
    def h(self) -> int:
        return self.y1 - self.y0


@dataclass
class OfferCluster:
    page_index: int
    bbox: Tuple[int, int, int, int]  # x0,y0,x1,y1
    anchor_text: str
    words: List[OcrWord]

    def text_block(self) -> str:
        # Sort roughly top-to-bottom then left-to-right
        ws = sorted(self.words, key=lambda w: (w.y0, w.x0))
        return " ".join(w.text for w in ws if w.text).strip()


# ---------- Patterns / config ----------

PRICE_DOLLAR_RE = re.compile(r"^\$?\d{1,3}(?:\.\d{2})$")  # 6.97 or $6.97
MULTIBUY_RE = re.compile(r"^\d+\s*/\s*\$?\d{1,3}(?:\.\d{2})?$")  # 2/$5 or 3/10.00
CENTS_RE = re.compile(r"^\d{1,2}¢$")  # 99¢ (sometimes appears as 99¢)

def default_store_knobs() -> Dict[str, dict]:
    """
    Per-store tuning knobs.
    Start with conservative defaults; we’ll tune from debug images.
    """
    return {
        "wegmans": {
            "min_word_conf": 35,
            "anchor_conf": 40,
            "radius_px": 260,             # “how far to grab nearby words”
            "pad_px": 18,                 # crop padding around cluster bbox
            "min_words_per_offer": 4,
            "max_offers_per_page": 250,   # safety
            "ignore_regex": re.compile(r"^(ng|fp)$", re.IGNORECASE),  # little badge letters
        },
        "shaws": {
            "min_word_conf": 25,
            "anchor_conf": 35,
            "radius_px": 380,             # Shaw’s is noisier; allow a bit larger radius
            "pad_px": 3530,
            "min_words_per_offer": 3,
            "max_offers_per_page": 400,
            "ignore_regex": re.compile(r"^(u|club|app|qr)$", re.IGNORECASE),
        },
    }


def looks_like_price_token(t: str) -> bool:
    t = (t or "").strip()
    if not t:
        return False
    # normalize common OCR variants
    t = t.replace(" ", "")
    t = t.replace("S", "$") if t.startswith("S") and len(t) <= 6 else t
    if PRICE_DOLLAR_RE.match(t):
        return True
    if MULTIBUY_RE.match(t):
        return True
    if CENTS_RE.match(t):
        return True
    return False


def dist(a: OcrWord, b: OcrWord) -> float:
    return math.hypot(a.cx - b.cx, a.cy - b.cy)


def merge_bbox(b1: Tuple[int,int,int,int], b2: Tuple[int,int,int,int]) -> Tuple[int,int,int,int]:
    x0,y0,x1,y1 = b1
    a0,b0,a1,b1_ = b2
    return (min(x0,a0), min(y0,b0), max(x1,a1), max(y1,b1_))


def iou(b1: Tuple[int,int,int,int], b2: Tuple[int,int,int,int]) -> float:
    x0,y0,x1,y1 = b1
    a0,b0,a1,b1_ = b2
    ix0, iy0 = max(x0,a0), max(y0,b0)
    ix1, iy1 = min(x1,a1), min(y1,b1_)
    iw, ih = max(0, ix1-ix0), max(0, iy1-iy0)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area1 = max(1, (x1-x0)) * max(1, (y1-y0))
    area2 = max(1, (a1-a0)) * max(1, (b1_-b0))
    return inter / float(area1 + area2 - inter)


def build_offers_from_words(
    page_index: int,
    words: List[OcrWord],
    store_knobs: dict,
) -> List[OfferCluster]:
    """
    Price-anchored clustering:
    - find “price-like” words (anchors)
    - for each anchor, gather nearby words within radius
    - merge overlapping clusters
    """
    min_word_conf = store_knobs["min_word_conf"]
    anchor_conf = store_knobs["anchor_conf"]
    radius = store_knobs["radius_px"]
    min_words = store_knobs["min_words_per_offer"]
    max_offers = store_knobs["max_offers_per_page"]
    ignore_re = store_knobs.get("ignore_regex")

    usable = []
    for w in words:
        if w.conf < min_word_conf:
            continue
        if ignore_re and ignore_re.match((w.text or "").strip()):
            continue
        # drop pure junk tokens
        if len((w.text or "").strip()) == 0:
            continue
        usable.append(w)

    anchors = []
    for w in usable:
        if w.conf < anchor_conf:
            continue
        t = (w.text or "").strip()
        if looks_like_price_token(t):
            anchors.append(w)

    clusters: List[OfferCluster] = []

    for a in anchors:
        members = []
        bbox = (a.x0, a.y0, a.x1, a.y1)

        for w in usable:
            if dist(a, w) <= radius:
                members.append(w)
                bbox = merge_bbox(bbox, (w.x0, w.y0, w.x1, w.y1))

        # basic sanity: don’t keep tiny clusters
        if len(members) < min_words:
            continue

        clusters.append(
            OfferCluster(
                page_index=page_index,
                bbox=bbox,
                anchor_text=a.text,
                words=members,
            )
        )
        if len(clusters) >= max_offers:
            break

    # Merge clusters that are essentially the same offer (overlap a lot)
    merged: List[OfferCluster] = []
    clusters = sorted(clusters, key=lambda c: (c.bbox[1], c.bbox[0]))  # top-left sort

    for c in clusters:
        found = False
        for m in merged:
            if iou(c.bbox, m.bbox) >= 0.35:
                # merge into m
                m.bbox = merge_bbox(m.bbox, c.bbox)
                # union words (by coords+text)
                key = {(w.x0,w.y0,w.x1,w.y1,(w.text or "")) for w in m.words}
                for w in c.words:
                    k = (w.x0,w.y0,w.x1,w.y1,(w.text or ""))
                    if k not in key:
                        m.words.append(w)
                        key.add(k)
                found = True
                break
        if not found:
            merged.append(c)

    # Final cleanup: sort words inside each offer
    for m in merged:
        m.words = sorted(m.words, key=lambda w: (w.y0, w.x0))

    return merged
