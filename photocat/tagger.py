"""Local vision tagging via Ollama (llava). Free, offline, $0/image.

Sends the *thumbnail* (not the full-res original) to keep it fast, and asks
for a tiny JSON of raw observations. The brand buckets (website/reel/post) are
NOT decided here — that's classify.py's job — so this stays a dumb, reusable
"what's in the picture" describer.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.request

log = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llava:7b"

_PROMPT = (
    "Label this personal photo for a cactus/plant creator brand. "
    "Reply with ONLY compact JSON using these exact keys, no other prose:\n"
    'desc (a short sentence describing what is shown), '
    'is_plant (true/false), is_screenshot (true/false), '
    'is_product (true/false), has_person (true/false), '
    'quality (good/ok/poor).\n'
    'Example: {"desc":"a potted cactus on a windowsill","is_plant":true,'
    '"is_screenshot":false,"is_product":false,"has_person":false,"quality":"good"}\n'
    "is_plant=true only when a cactus or plant is the MAIN subject. "
    "is_screenshot=true for app screens, chat logs, game frames, documents or memes. "
    "is_product=true when an item looks staged for sale. Output JSON only."
)

_EMPTY = {"desc": "", "is_plant": None, "is_screenshot": None,
          "is_product": None, "has_person": None, "quality": None}


def _coerce_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "1"):
            return True
        if s in ("false", "no", "0"):
            return False
    return None


def _extract_obj(raw: str):
    """Best-effort pull of a single flat JSON object out of llava's reply.

    Handles: plain object, ```json fenced blocks, and a JSON *array* of objects
    (llava sometimes returns one element per imagined photo) — takes the first.
    Returns a dict or None.
    """
    s = raw.strip()
    # drop code fences ```json ... ```
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()
    # try the whole thing first
    try:
        v = json.loads(s)
        if isinstance(v, dict):
            return v
        if isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    return item
    except Exception:
        pass
    # fallback: first flat {...} (no nested braces) anywhere in the text
    m = re.search(r"\{[^{}]*\}", s, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def _parse(raw: str) -> dict:
    """Normalize llava's reply into the fixed observation shape."""
    out = dict(_EMPTY)
    d = _extract_obj(raw)
    if not isinstance(d, dict):
        log.debug("tagger: unparseable reply: %s", raw[:120])
        out["desc"] = re.sub(r"```|<[^>]*>", "", raw).strip()[:200]
        out["error"] = "parse: no json object"
        return out
    desc = str(d.get("desc", ""))
    # llava sometimes echoes the prompt's placeholder text — strip any <...>.
    desc = re.sub(r"<[^>]*>", "", desc).strip()
    out["desc"] = desc[:240]
    for k in ("is_plant", "is_screenshot", "is_product", "has_person"):
        out[k] = _coerce_bool(d.get(k))
    q = str(d.get("quality", "")).strip().lower()
    out["quality"] = q if q in ("good", "ok", "poor") else None
    return out


def tag_image(thumb_path: str, model: str = DEFAULT_MODEL, timeout: int = 180) -> dict:
    """Return raw observations for one image. On any failure returns the empty
    shape plus an 'error' key (never raises — one bad image must not stop a run)."""
    try:
        with open(thumb_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError as exc:
        log.warning("tag: cannot read thumb %s: %s", thumb_path, exc)
        return {**_EMPTY, "error": f"read: {exc}"}

    body = json.dumps({
        "model": model,
        "prompt": _PROMPT,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read())
    except Exception as exc:
        log.warning("tag: ollama call failed for %s: %s", thumb_path, exc)
        return {**_EMPTY, "error": f"ollama: {exc}"}
    return _parse(resp.get("response", ""))


def ollama_ready(model: str = DEFAULT_MODEL) -> bool:
    """True if the Ollama server answers and has the requested model."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            tags = json.loads(r.read())
    except Exception as exc:
        log.warning("ollama not reachable: %s", exc)
        return False
    names = [m.get("name", "") for m in tags.get("models", [])]
    # Exact-tag match only: a loose "llava*" prefix could match llava:13b, which
    # exceeds the 8GB VRAM budget and hangs Ollama. If the caller passed a bare
    # base name (no ':'), allow any tag of that family.
    if ":" in model:
        return model in names
    return any(n == model or n.startswith(model + ":") for n in names)
