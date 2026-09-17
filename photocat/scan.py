"""Walk folder trees and collect image-file records.

Pure I/O: returns a list of plain dicts. No conversion, no tagging.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

IMG_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif",
           ".bmp", ".webp", ".tiff", ".tif", ".ico"}

# Folder-name fragments whose contents are almost never real photos worth
# cataloguing. Used only to skip during scan when skip_junk=True.
JUNK_DIR_HINTS = (
    "wii backup", "homebrew", "gemini apps", "takeout", "my activity",
    "pokefirered", "pokedex", "door_anims", "graphics", "nvidiafortnite",
)


def scan(roots, exts=IMG_EXT, skip_dir_hints=(), max_files=None):
    """Return image records under each root.

    roots: a path or iterable of paths.
    skip_dir_hints: lowercase substrings; any path containing one is skipped.
    max_files: stop after this many records (None = no cap).
    Each record: {path, name, folder, ext, size, mtime}.
    """
    if isinstance(roots, (str, Path)):
        roots = [roots]
    hints = tuple(h.lower() for h in skip_dir_hints)
    out: list[dict] = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            log.warning("scan: path does not exist: %s", root)
            continue
        try:
            walker = root.rglob("*")
        except OSError as exc:
            log.warning("scan: cannot walk %s: %s", root, exc)
            continue
        for p in walker:
            if max_files is not None and len(out) >= max_files:
                return out
            try:
                if p.suffix.lower() not in exts:
                    continue
                low = str(p).lower()
                if hints and any(h in low for h in hints):
                    continue
                if not p.is_file():
                    continue
                st = p.stat()
            except OSError as exc:
                log.warning("scan: stat failed for %s: %s", p, exc)
                continue
            out.append({
                "path": str(p),
                "name": p.name,
                "folder": str(p.parent),
                "ext": p.suffix.lower().lstrip("."),
                "size": st.st_size,
                "mtime": int(st.st_mtime),
            })
    return out
