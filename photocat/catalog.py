"""Orchestrate scan -> thumbnail -> classify (-> optional vision) -> HTML.

Thumbnails run in parallel threads (PIL releases the GIL during decode).
Vision tagging, when enabled, runs serially afterward — one GPU, one model.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import classify as classify_mod
from . import scan as scan_mod
from . import tagger as tagger_mod
from . import thumbs as thumbs_mod
from .classify import _JUNK_FOLDER, _JUNK_NAME, _has
from .render import render_html

log = logging.getLogger(__name__)

_REC_KEYS = ("path", "name", "folder", "ext", "size", "mtime")


def _load_cache(path):
    """Load the per-image vision-tag cache (thumb_id -> tag). {} if absent/bad."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.warning("tag cache unreadable (%s); starting fresh", exc)
        return {}


def _save_cache(path, cache):
    """Atomically persist the tag cache so an interrupted run can resume."""
    try:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.warning("could not write tag cache %s: %s", path, exc)


def worth_vision(rec: dict) -> bool:
    """Skip the slow vision call on obvious junk (screenshots, meme/game folders)."""
    if _has(rec["folder"], _JUNK_FOLDER):
        return False
    if _has(rec["name"], _JUNK_NAME):
        return False
    return True


def _summary(items, label, vision, vcount, vfail=0):
    s = {"label": label, "total": len(items), "vision": vision,
         "vision_tagged": vcount, "vision_failed": vfail, "website": 0,
         "reel": 0, "post": 0, "junk": 0, "cactus_plant": 0, "product": 0,
         "thumb_failed": 0}
    for d in items:
        if d.get("website") is True:
            s["website"] += 1
        if d.get("reel") in (True, None):
            s["reel"] += 1
        if d.get("post") in (True, None):
            s["post"] += 1
        if d.get("junk") is True:
            s["junk"] += 1
        if d.get("category") == "cactus_plant":
            s["cactus_plant"] += 1
        if d.get("category") == "product":
            s["product"] += 1
        if d.get("thumb_err"):
            s["thumb_failed"] += 1
    return s


def build_catalog(roots, out_dir, label, *, vision=False, model="llava:7b",
                  limit=None, skip_dir_hints=(), thumb_size=360, workers=8,
                  progress_every=100):
    """Build a catalog under out_dir/label/ (thumbs/, catalog.json, index.html).

    Returns a summary dict (also written to summary.json).
    """
    out_dir = Path(out_dir)
    base = out_dir / label
    thumbs_dir = base / "thumbs"
    base.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)  # create once, not per-thread

    recs = scan_mod.scan(roots, skip_dir_hints=skip_dir_hints, max_files=limit)
    log.info("scanned %d images", len(recs))
    if not recs:
        log.warning("no images found under %s", roots)

    # 1) thumbnails (parallel)
    def _thumb(rec):
        tp, dims, err = thumbs_mod.make_thumb(rec, thumbs_dir, size=thumb_size)
        return rec, tp, dims, err

    thumbed = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, res in enumerate(ex.map(_thumb, recs), 1):
            thumbed.append(res)
            if i % progress_every == 0:
                log.info("thumbnailed %d/%d (%.0fs)", i, len(recs), time.time() - t0)
    log.info("thumbnails done: %d in %.0fs", len(thumbed), time.time() - t0)

    # 2) classify (+ optional vision, serialized & resumable via tag cache)
    cache_path = base / "tags_cache.json"
    tag_cache = _load_cache(cache_path) if vision else {}
    if vision and tag_cache:
        log.info("resuming: %d images already judged (cache hit)", len(tag_cache))
    items = []
    vcount = 0   # new llava calls this run
    vfail = 0
    vcached = 0  # reused from a prior run
    vt0 = time.time()
    for rec, tp, dims, err in thumbed:
        tag = {}
        if vision and tp and worth_vision(rec):
            tid = thumbs_mod.thumb_id(rec)
            cached = tag_cache.get(tid)
            if cached is not None:
                tag = cached
                vcached += 1
            else:
                tag = tagger_mod.tag_image(tp, model=model)
                tag_cache[tid] = tag
                vcount += 1
                if tag.get("error"):
                    vfail += 1
                if vcount % progress_every == 0:
                    _save_cache(cache_path, tag_cache)
                    log.info("vision-tagged %d new (%d cached, %d failed, %.0fs)",
                             vcount, vcached, vfail, time.time() - vt0)
        c = classify_mod.classify(rec, tag)
        rel = ("thumbs/" + Path(tp).name) if tp else None
        items.append({**{k: rec[k] for k in _REC_KEYS},
                      "thumb": rel, "dims": dims, "thumb_err": err, **c})
    if vision:
        _save_cache(cache_path, tag_cache)
        log.info("vision done: %d new, %d cached, %d failed in %.0fs",
                 vcount, vcached, vfail, time.time() - vt0)

    # 3) write data + html
    (base / "catalog.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8")
    html_path = render_html(items, label, base / "index.html")
    summary = _summary(items, label, vision, vcount, vfail)
    (base / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["html"] = str(html_path)
    summary["json"] = str(base / "catalog.json")
    return summary
