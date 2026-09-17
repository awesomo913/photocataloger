"""Photo Cataloger CLI.

Examples:
  # fast browsable catalog of the plant folder (no AI wait)
  py run_catalog.py --preset plants --label plants

  # several folders at once
  py run_catalog.py --preset plants,sales,allphotos --label website_gold

  # add AI tags (slow: ~5s/photo on llava) — usually run in the background
  py run_catalog.py --preset plants --label plants --vision
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from photocat.catalog import build_catalog

# Friendly preset name -> Google Drive (D:) folder.
PRESETS = {
    "plants": r"D:\My Drive\Plant tips, info, information, pictures and anything else pertaining to plants",
    "camera2026": r"D:\My Drive\Camera Pictures\Camera uploads 2026",
    "camera": r"D:\My Drive\Camera Pictures",
    "sales": r"D:\My Drive\Sales pictures",
    "allphotos": r"D:\My Drive\All Photos",
    "memories": r"D:\My Drive\Pictures of Memories",
}

DEFAULT_OUT = r"C:\Users\computer\.claude\tmp\2026-06-25\photo_catalog\out"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a browsable, AI-tagged photo catalog.")
    ap.add_argument("--folder", action="append", default=[],
                    help="explicit Drive folder path (repeatable)")
    ap.add_argument("--preset", help="comma list of: " + ", ".join(PRESETS))
    ap.add_argument("--all", action="store_true",
                    help=r"catalog every image under D:\My Drive (the whole pile)")
    ap.add_argument("--label", required=True, help="output subfolder name")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--vision", action="store_true", help="run llava AI tagging (slow)")
    ap.add_argument("--model", default="llava:7b")
    ap.add_argument("--limit", type=int, help="cap number of images (testing)")
    ap.add_argument("--workers", type=int, default=8, help="thumbnail threads")
    a = ap.parse_args(argv)

    roots = list(a.folder)
    if a.all:
        roots.append(r"D:\My Drive")
    if a.preset:
        for key in a.preset.split(","):
            key = key.strip()
            if key not in PRESETS:
                ap.error(f"unknown preset '{key}'. choices: {', '.join(PRESETS)}")
            roots.append(PRESETS[key])
    if not roots:
        ap.error("give --folder, --preset, or --all")

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    summary = build_catalog(roots, a.out, a.label, vision=a.vision,
                            model=a.model, limit=a.limit, workers=a.workers)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
