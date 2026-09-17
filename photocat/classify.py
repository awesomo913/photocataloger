"""Turn raw vision observations (+ folder/filename evidence) into brand buckets.

Output per image: booleans for website / reel / post / junk, a primary
`category`, a `confidence` (high/med/low), and a short `why` for every decision
— built from the actual evidence so Jacob can see *why* each photo landed where
it did.

Quality rule of thumb — precedence of evidence:
  1. What the AI actually SAW (description keywords) and its is_* flags win.
  2. The folder name is only a tie-breaker, and never overrides a clear AI "no".
That stops a "stone carving" in the plant folder from being called a cactus.

Brand context:
  website = revolutionarydesigns.io Cactus Codex (cactus/plant + product shots)
  reel    = ReVo Lue Shin reel content (best plant/product, sharp, on-brand)
  post    = a static social photo worth posting (presentable + on-brand)
  junk    = screenshots, memes, game frames, app/UI, docs, drawings, throwaways
"""

from __future__ import annotations

# Folder-name fragments that mark a pile as non-photo / skip-by-default.
_JUNK_FOLDER = ("meme", "screenshot", "snreenshot", "wii backup", "homebrew",
                "gemini apps", "takeout", "my activity", "manuals",
                "pokefirered", "pokedex", "door_anims", "graphics",
                "nvidiafortnite", "downloads")

# Filename prefixes that are almost always not real photos.
_JUNK_NAME = ("screenshot", "thumbnail_", "fb_img", "received_",
              "img-", "screen shot", "snapchat", "story_")

# Folder fragments that signal plant/cactus content.
_PLANT_FOLDER = ("plant", "cactus", "loph", "trich", "diffusa", "williamsii",
                 "succulent")

# Folder fragments that signal product/sales content.
_PRODUCT_FOLDER = ("sales", "product", "for sale", "listing", "content pictured")

# Descriptions that mean "sensitive document" — never a website/post candidate.
_SENSITIVE_DESC = ("driver", "license", "licence", "passport", "social security",
                   "ssn", "credit card", "debit card", "bank statement",
                   "birth certificate", "identification card", "id card",
                   "national id", "tax form", "w-2", "1099", "medical record")

# --- description keyword evidence (the real quality lever) -------------------
# A plant/cactus is the subject.
_PLANT_WORDS = ("cactus", "cacti", "cactaceae", "succulent", "agave", "aloe",
                "peyote", "lophophora", "trichocereus", "san pedro", "pachanoi",
                "potted plant", "houseplant", "seedling", "seedlings", "sprout",
                "nursery", "greenhouse", "garden", "flowering plant", "bloom",
                "areole", "spines", "prickly pear", "plant in a pot",
                "plant on", "plants on", "plant with", "green plant",
                "seeds", "seed packet", "terracotta", "plant pot", "flower pot")

# Screen/doc/art content — not a real photo of a real thing → junk.
_SCREEN_WORDS = ("screenshot", "screen shot", "a screen", "app ", "application",
                 "menu", "website", "web page", "webpage", "browser",
                 "text message", "chat", "conversation", "messaging", "document",
                 "spreadsheet", "a graph", "a chart", "dialog", "settings page",
                 "user interface", "login", "video game", "game screen",
                 "emulator", "keyboard", "social media", "instagram", "facebook",
                 "a tweet", "advertisement", "a meme", "a logo", "an icon",
                 "diagram", "a map", "a drawing", "a sketch", "cartoon",
                 "a painting", "illustration", "comic")

# People-dominant (real photo, but off the cactus brand).
_PERSON_WORDS = ("a person", "a man", "a woman", "men ", "women ", "people",
                 "selfie", "a face", "a child", "children", "a baby", "a boy",
                 "a girl", "crowd", "portrait", "group of")


def _has(text: str, frags) -> str | None:
    """Return the first fragment found in text, else None."""
    t = text.lower()
    for f in frags:
        if f in t:
            return f
    return None


def _result(category, desc, quality, tag_failed, confidence,
            website, website_why, reel, reel_why, post, post_why,
            junk, junk_why):
    return {
        "category": category, "desc": desc, "quality": quality,
        "tag_failed": tag_failed, "confidence": confidence,
        "website": website, "website_why": website_why,
        "reel": reel, "reel_why": reel_why,
        "post": post, "post_why": post_why,
        "junk": junk, "junk_why": junk_why,
    }


def classify(rec: dict, tag: dict) -> dict:
    """Return bucket flags + reasons for one image record + its vision tag."""
    folder = rec.get("folder", "")
    name = rec.get("name", "")
    desc = (tag.get("desc") or "").strip()
    quality = tag.get("quality")
    is_plant = tag.get("is_plant")
    is_shot = tag.get("is_screenshot")
    is_product = tag.get("is_product")
    has_person = tag.get("has_person")
    ai_ran = not (bool(tag.get("error")) or
                  (is_plant is None and is_shot is None and not desc))

    junk_folder = _has(folder, _JUNK_FOLDER)
    junk_name = _has(name, _JUNK_NAME)
    plant_folder = _has(folder, _PLANT_FOLDER)
    product_folder = _has(folder, _PRODUCT_FOLDER)

    # Evidence mined straight from what the AI described.
    plant_word = _has(desc, _PLANT_WORDS)
    screen_word = _has(desc, _SCREEN_WORDS)
    person_word = _has(desc, _PERSON_WORDS)

    # ---- SENSITIVE short-circuit (IDs/docs) ----------------------------
    sensitive = _has(desc, _SENSITIVE_DESC)
    if sensitive:
        return _result(
            "sensitive", desc, quality, not ai_ran, "high",
            False, f"NO — sensitive document ('{sensitive}')",
            False, "no — sensitive document, never publish",
            False, "no — sensitive document, never publish",
            True, f"sensitive/ID document ('{desc}') — excluded from all picks")

    # ---- JUNK (screens/docs/art/meme folders) --------------------------
    junk = False
    junk_why = ""
    if is_shot is True:
        junk, junk_why = True, f"AI read it as a screenshot/app/doc ('{desc}')"
    elif screen_word:
        junk, junk_why = True, f"AI describes screen/doc/art content ('{screen_word}…')"
    elif junk_folder:
        junk, junk_why = True, f"lives in a skip folder ('…{junk_folder}…')"
    elif junk_name:
        junk, junk_why = True, f"filename looks like a screenshot/share ('{junk_name}…')"
    elif ai_ran and quality == "poor" and not (plant_word or product_folder):
        junk, junk_why = True, "AI rated it poor quality and it's not a plant/product shot"

    # ---- PLANT subject (AI evidence beats folder) ----------------------
    plant_denied = ai_ran and (is_plant is False) and not plant_word
    if plant_word or is_plant is True:
        plant_subject, plant_conf = True, "high"
        plant_why = f"AI sees a plant/cactus ('{desc}')"
    elif plant_folder and not plant_denied and not screen_word and not person_word:
        plant_subject, plant_conf = True, "med" if ai_ran else "low"
        plant_why = f"in your plant folder ('…{plant_folder}…')" + (
            "" if ai_ran else "; not AI-checked yet")
    else:
        plant_subject, plant_conf = False, None
        plant_why = ("AI says it's not a plant" if plant_denied else "")

    # ---- PRODUCT subject ----------------------------------------------
    product_denied = ai_ran and (is_product is False) and not product_folder
    # Only count a product if it's plant-related OR in a sales folder — a generic
    # "item staged for sale" (e.g. a trading card) is off the cactus brand.
    if is_product is True and (plant_word or product_folder):
        product_subject, prod_conf = True, "high"
        product_why = "AI sees a plant/cactus product staged for sale"
    elif product_folder and not product_denied and not screen_word:
        product_subject, prod_conf = True, "med"
        product_why = f"in a sales/product folder ('…{product_folder}…')"
    else:
        product_subject, prod_conf = False, None
        product_why = ("generic item, not clearly a cactus/plant product"
                       if is_product is True else "")

    confidence = plant_conf or prod_conf or ("high" if ai_ran else "low")

    # ---- WEBSITE -------------------------------------------------------
    website = (not junk) and (plant_subject or product_subject) and quality != "poor"
    if website:
        bits = [b for b in (plant_why, product_why) if b]
        website_why = f"[{confidence}] cactus/product fit — " + "; ".join(bits)
    elif junk:
        website_why = f"no — flagged junk ({junk_why})"
    elif not (plant_subject or product_subject):
        website_why = "no — " + (plant_why or "not a cactus/plant or product photo")
    else:
        website_why = "no — AI rated quality poor"

    # ---- REEL (tighter: only the strong, sharp, on-brand) --------------
    strong = website and confidence == "high"
    if strong and quality == "good":
        reel, reel_why = True, "AI-confirmed plant/product, sharp — strong reel material"
    elif website and quality in ("good", "ok"):
        reel, reel_why = None, "maybe — on-brand but folder-guessed or just-ok quality; eyeball it"
    else:
        reel, reel_why = False, "no — not strong enough for a reel"

    # ---- POST ----------------------------------------------------------
    if junk:
        post, post_why = False, "no — junk"
    elif website:
        post, post_why = True, "yes — on-brand, fine as a feed/story post"
    elif (has_person is True or person_word) and quality != "poor":
        post, post_why = None, "personal/lifestyle shot — postable but off the cactus brand"
    else:
        post, post_why = False, "no — not presentable/on-brand"

    # ---- primary category ---------------------------------------------
    if junk:
        category = "junk"
    elif plant_subject:
        category = "cactus_plant"
    elif product_subject:
        category = "product"
    elif has_person is True or person_word:
        category = "person"
    elif desc:
        category = "scene"
    else:
        category = "unknown"

    return _result(category, desc, quality, not ai_ran, confidence,
                   website, website_why, reel, reel_why, post, post_why,
                   junk, junk_why)
