# Photo Cataloger

> Builds a browsable HTML contact sheet of a photo library, with optional AI tagging so you can find things later.

A two-phase Python pipeline: Phase 1 scans a folder (or several), makes thumbnails, and produces a fast browsable HTML catalog with no AI wait. Phase 2 optionally runs each photo through a local vision model (`llava` via Ollama) to generate AI tags, so the catalog becomes searchable by what's actually in the picture, not just filenames and folders.

## Features
- Fast, no-AI first pass: scans folders, generates thumbnails, and renders a browsable HTML contact sheet immediately (`photocat/scan.py`, `photocat/thumbs.py`, `photocat/render.py`).
- Optional AI tagging pass using a local vision model (`llava:7b` via Ollama) to classify and tag each photo (`photocat/classify.py`, `photocat/tagger.py`).
- Named folder presets (plants, camera uploads, sales, memories, "all photos") pointing at real Google-Drive-backed folders, or pass explicit `--folder` paths.
- `--all` sweeps an entire Drive root; results are cached so a second run reuses existing thumbnails/tags.
- Detached full-drive mode (`run_full.py`) that runs both phases hidden via `pythonw`, resumable if killed mid-run (`tags_cache.json`), and survives Claude session restarts.
- Configurable worker threads for thumbnail generation and an image cap for quick test runs.

## Stack
Python, Pillow (thumbnails), Ollama + `llava` (local vision-model tagging).

## Getting started
**Requirements** — Python, Pillow, a local Ollama install with the `llava:7b` model pulled for the `--vision` pass.

**Run**
```bash
pip install -r requirements.txt
python run_catalog.py --preset plants --label plants           # fast catalog, no AI
python run_catalog.py --preset plants --label plants --vision  # add AI tags (slow, ~5s/photo)
python run_full.py                                              # detached full-drive build, both phases
```

## Status
**Unmaintained / archived.** Personal project, published as-is — fork it, adapt it, take it over. No support or guarantees.

## License
[MIT](LICENSE) — free to use, fork, and build on.
