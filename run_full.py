"""Detached full-drive build: Phase 1 (browsable catalog) then Phase 2 (AI judge).

Launched hidden via pythonw so it survives Claude session resumes (background
shell jobs do not). Logs to everything_run.log. Both phases reuse cached
thumbnails; Phase 2 is resumable via tags_cache.json, so a kill/restart picks
up where it stopped.
"""

import logging
import sys

sys.path.insert(0, r"C:\Users\computer\Desktop\AI\PhotoCataloger")

from photocat.catalog import build_catalog  # noqa: E402

OUT = r"C:\Users\computer\.claude\tmp\2026-06-25\photo_catalog\out"
ROOT = r"D:\My Drive"
LABEL = "everything"
LOG = r"C:\Users\computer\.claude\tmp\2026-06-25\photo_catalog\everything_run.log"

logging.basicConfig(level=logging.INFO, filename=LOG, filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_full")


def main():
    try:
        log.info("=== PHASE 1 (thumbnails + categorize, browsable now) ===")
        s1 = build_catalog(ROOT, OUT, LABEL, vision=False, workers=8)
        log.info("PHASE 1 DONE: %s", s1)

        log.info("=== PHASE 2 (AI judge every real photo, resumable) ===")
        s2 = build_catalog(ROOT, OUT, LABEL, vision=True, model="llava:7b", workers=8)
        log.info("PHASE 2 DONE: %s", s2)
        log.info("=== ALL DONE ===")
    except Exception as exc:  # last-resort: record why a detached run died
        log.exception("run_full crashed: %s", exc)
        raise


if __name__ == "__main__":
    main()
