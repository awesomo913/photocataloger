"""Generate small JPG thumbnails (cached by source path + mtime).

HEIC/HEIF support is opportunistic: if pillow-heif is installed it registers
the opener; otherwise those files are reported as failures (not silently lost).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC_OK = True
except Exception as exc:  # pragma: no cover - depends on env
    HEIC_OK = False
    log.warning("pillow-heif unavailable (%s); HEIC/HEIF thumbnails will fail", exc)


def thumb_id(rec: dict) -> str:
    """Stable id from path + mtime, so edits re-thumbnail but moves don't dup."""
    key = f"{rec['path']}|{rec['mtime']}".encode("utf-8", "replace")
    return hashlib.sha1(key).hexdigest()[:16]


def make_thumb(rec: dict, out_dir, size: int = 360):
    """Write a <=size px JPG thumbnail for rec. Returns (thumb_path, dims, error).

    thumb_path/dims are None on failure; error holds the reason. Cached: an
    existing thumbnail is reused (dims re-read cheaply from the thumb).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{thumb_id(rec)}.jpg"
    if dest.exists():
        try:
            with Image.open(dest) as t:
                return str(dest), list(t.size), None
        except Exception as exc:
            log.warning("thumb cache unreadable %s: %s", dest, exc)
            # fall through and regenerate
    try:
        with Image.open(rec["path"]) as im:
            orig = list(im.size)
            im = ImageOps.exif_transpose(im)          # respect phone rotation
            im = im.convert("RGB")
            im.thumbnail((size, size))
            im.save(dest, "JPEG", quality=82, optimize=True)
        return str(dest), orig, None
    except Exception as exc:
        log.warning("thumb failed for %s: %s", rec["path"], exc)
        return None, None, str(exc)
