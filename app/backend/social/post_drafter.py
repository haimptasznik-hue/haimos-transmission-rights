"""
post_drafter.py — Uses OpenAI GPT-4o to draft LinkedIn posts from news articles,
and DALL-E 3 to generate a matching image for each post.
"""

import os
import json
import uuid
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from openai import OpenAI

VAULT_ROOT  = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR    = Path(__file__).resolve().parent.parent.parent / "data" / "social"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DRAFTS_FILE = DATA_DIR / "drafts.json"
IMAGES_DIR  = DATA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

LINKEDIN_PERSONA = """
You are drafting LinkedIn posts for Haim Ptasznik — a renewable energy specialist, 
entrepreneur, and investor based in Australia. He tracks the NEM (National Electricity Market), 
battery storage, solar, hydrogen, EVs, and clean energy across Australia, NZ, and the USA.

His tone is: confident, insightful, direct, occasionally thought-provoking. 
He shares professional perspectives, not just news summaries. Posts should feel like 
expert commentary, not press releases. He engages with his network of energy professionals, 
investors, and policy makers.
"""

POST_PROMPT = """
Based on this news article, draft a compelling LinkedIn post (200-280 words max):

Title: {title}
Source: {source} ({region})
Summary: {summary}
Link: {link}

Requirements:
- Open with a strong hook (no clichés like "Exciting news!")
- Include 1–2 sharp insights or questions that provoke engagement
- Reference the relevance to Australia / NEM where possible
- End with a call to action or open question to drive comments
- Include 4–6 relevant hashtags at the end (e.g. #RenewableEnergy #NEM #BESS)
- Do NOT include the URL in the post body — it will be added separately

Return ONLY the post text, no extra labels or commentary.
"""

IMAGE_PROMPT_TEMPLATE = """
Create a clean, professional, modern illustration for a LinkedIn post about:
"{title}"

Style: Sleek data-visualization aesthetic with deep navy blue and electric blue tones. 
Minimalist infographic style. No text overlays. High contrast. Would look great 
as a LinkedIn post header image. 16:9 aspect ratio feel.
"""


def _load_drafts() -> List[Dict]:
    if DRAFTS_FILE.exists():
        try:
            return json.loads(DRAFTS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_drafts(drafts: List[Dict]):
    DRAFTS_FILE.write_text(json.dumps(drafts, indent=2))


def draft_posts_from_articles(articles: List[Dict], max_drafts: int = 6) -> List[Dict]:
    """Generate LinkedIn post drafts + AI images for top N articles."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")

    client = OpenAI(api_key=api_key)
    existing = _load_drafts()
    existing_links = {d["source_link"] for d in existing}

    new_drafts = []
    count = 0

    for article in articles:
        if count >= max_drafts:
            break
        if article["link"] in existing_links:
            continue

        # ── Draft the post ────────────────────────────────────────────────────
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": LINKEDIN_PERSONA},
                    {"role": "user",   "content": POST_PROMPT.format(**article)}
                ],
                temperature=0.75,
                max_tokens=500,
            )
            post_text = resp.choices[0].message.content.strip()
        except Exception as e:
            post_text = f"[Draft failed: {e}]"

        # ── Generate image ────────────────────────────────────────────────────
        image_path: Optional[str] = None
        try:
            img_resp = client.images.generate(
                model="dall-e-3",
                prompt=IMAGE_PROMPT_TEMPLATE.format(title=article["title"]),
                size="1792x1024",
                quality="standard",
                response_format="b64_json",
                n=1,
            )
            img_b64   = img_resp.data[0].b64_json
            img_bytes = base64.b64decode(img_b64)
            img_file  = IMAGES_DIR / f"{uuid.uuid4().hex}.png"
            img_file.write_bytes(img_bytes)
            image_path = str(img_file)
        except Exception:
            image_path = None

        draft_id = str(uuid.uuid4())
        draft = {
            "id":           draft_id,
            "status":       "pending",       # pending | approved | rejected | posted
            "post_text":    post_text,
            "source_title": article["title"],
            "source_link":  article["link"],
            "source_name":  article["source"],
            "region":       article["region"],
            "image_path":   image_path,
            "created_at":   datetime.now(timezone.utc).isoformat(),
            "posted_at":    None,
            "linkedin_id":  None,
        }
        new_drafts.append(draft)
        count += 1

    all_drafts = new_drafts + existing
    # Keep at most 50 drafts to avoid unbounded growth
    all_drafts = all_drafts[:50]
    _save_drafts(all_drafts)

    return new_drafts


def get_all_drafts() -> List[Dict]:
    return _load_drafts()


def update_draft(draft_id: str, updates: Dict) -> Optional[Dict]:
    drafts = _load_drafts()
    for i, d in enumerate(drafts):
        if d["id"] == draft_id:
            drafts[i].update(updates)
            _save_drafts(drafts)
            return drafts[i]
    return None


def delete_draft(draft_id: str) -> bool:
    drafts = _load_drafts()
    new = [d for d in drafts if d["id"] != draft_id]
    if len(new) < len(drafts):
        _save_drafts(new)
        return True
    return False


# ── Vault-aware custom draft ──────────────────────────────────────────────────

def search_vault(subject: str, max_files: int = 8) -> str:
    """Full-text search vault markdown files for content relevant to subject."""
    import re
    keywords = [w.lower() for w in re.split(r'\W+', subject) if len(w) > 2]
    hits = []
    for md_file in VAULT_ROOT.rglob("*.md"):
        try:
            text = md_file.read_text(errors="ignore")
        except Exception:
            continue
        lower = text.lower()
        score = sum(lower.count(k) for k in keywords)
        if score > 0:
            hits.append((score, md_file, text))
    hits.sort(reverse=True)
    if not hits:
        return ""
    # Take top files, truncate each to 600 chars
    snippets = []
    for _, fpath, text in hits[:max_files]:
        clean = text.strip()[:600].replace("\n", " ")
        snippets.append(f"[{fpath.name}]: {clean}")
    return "\n\n".join(snippets)


CUSTOM_POST_PROMPT = """
You are drafting a LinkedIn post for Haim Ptasznik on the subject: "{subject}"

{vault_context_section}

Requirements:
- Open with a strong hook (no clichés like "Exciting news!" or "I'm thrilled")
- 200–280 words max
- Include Haim's perspective and relevant experience where the vault context supports it
- Include 1–2 sharp insights or questions that provoke engagement  
- Reference relevance to Australia / NEM / global clean energy where appropriate
- End with an open question to drive comments
- Include 4–6 relevant hashtags at the end
- Sound like expert commentary, not a press release

Return ONLY the post text, no extra labels or commentary.
"""


def draft_post_from_subject(subject: str) -> Dict:
    """Generate a single LinkedIn post draft from a subject + vault context."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")

    client = OpenAI(api_key=api_key)

    vault_snippets = search_vault(subject)
    vault_context_section = (
        f"Use the following context from Haim's personal knowledge vault to make the post specific and authentic:\n\n{vault_snippets}"
        if vault_snippets
        else "No specific vault context found — draw on general renewable energy knowledge."
    )

    prompt = CUSTOM_POST_PROMPT.format(
        subject=subject,
        vault_context_section=vault_context_section,
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": LINKEDIN_PERSONA},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.75,
            max_tokens=500,
        )
        post_text = resp.choices[0].message.content.strip()
    except Exception as e:
        post_text = f"[Draft failed: {e}]"

    # Generate image
    image_path: Optional[str] = None
    try:
        img_resp = client.images.generate(
            model="dall-e-3",
            prompt=IMAGE_PROMPT_TEMPLATE.format(title=subject),
            size="1792x1024",
            quality="standard",
            response_format="b64_json",
            n=1,
        )
        img_b64   = img_resp.data[0].b64_json
        img_bytes = base64.b64decode(img_b64)
        img_file  = IMAGES_DIR / f"{uuid.uuid4().hex}.png"
        img_file.write_bytes(img_bytes)
        image_path = str(img_file)
    except Exception:
        image_path = None

    draft = {
        "id":           str(uuid.uuid4()),
        "status":       "pending",
        "post_text":    post_text,
        "source_title": subject,
        "source_link":  "",
        "source_name":  "Custom",
        "region":       "Custom",
        "image_path":   image_path,
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "posted_at":    None,
        "linkedin_id":  None,
    }
    existing = _load_drafts()
    all_drafts = [draft] + existing
    _save_drafts(all_drafts[:50])
    return draft
