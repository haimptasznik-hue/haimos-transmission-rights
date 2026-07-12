"""
linkedin_client.py — LinkedIn OAuth 2.0 + posting via the LinkedIn v2 API.

OAuth flow:
  1. GET /api/social/linkedin/auth  → redirects user to LinkedIn
  2. LinkedIn redirects back to /api/social/linkedin/callback with ?code=...
  3. We exchange the code for an access token + store it
  4. POST /api/social/linkedin/post  → posts approved draft

Scopes required: openid, profile, w_member_social
"""

import os
import json
import time
import secrets
import requests
from pathlib import Path
from typing import Optional, Dict

DATA_DIR      = Path(__file__).resolve().parent.parent.parent / "data" / "social"
TOKEN_FILE    = DATA_DIR / "linkedin_token.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

LINKEDIN_AUTH_URL  = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_UGC_URL   = "https://api.linkedin.com/v2/ugcPosts"
LINKEDIN_ME_URL    = "https://api.linkedin.com/v2/userinfo"

# Scopes needed for personal profile posting
SCOPES = "openid profile w_member_social"


def _get_credentials() -> tuple[str, str]:
    client_id     = os.environ.get("LINKEDIN_CLIENT_ID", "")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    return client_id, client_secret


def _get_redirect_uri() -> str:
    port = os.environ.get("HAIMOS_PORT", "8765")
    return f"http://localhost:{port}/api/social/linkedin/callback"


def get_auth_url() -> Dict:
    client_id, _ = _get_credentials()
    if not client_id:
        return {"error": "LINKEDIN_CLIENT_ID not set in .env"}

    state = secrets.token_urlsafe(16)
    # Store state temporarily for CSRF validation
    (DATA_DIR / "oauth_state.txt").write_text(state)

    params = {
        "response_type": "code",
        "client_id":     client_id,
        "redirect_uri":  _get_redirect_uri(),
        "state":         state,
        "scope":         SCOPES,
    }
    from urllib.parse import urlencode
    url = f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"
    return {"auth_url": url}


def handle_callback(code: str, state: str) -> Dict:
    """Exchange auth code for access token."""
    state_file = DATA_DIR / "oauth_state.txt"
    if state_file.exists():
        expected_state = state_file.read_text().strip()
        state_file.unlink()
        if state != expected_state:
            return {"error": "Invalid OAuth state — possible CSRF attack"}
    else:
        return {"error": "No pending OAuth state found"}

    client_id, client_secret = _get_credentials()
    if not client_id:
        return {"error": "LINKEDIN_CLIENT_ID not set"}

    resp = requests.post(LINKEDIN_TOKEN_URL, data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  _get_redirect_uri(),
        "client_id":     client_id,
        "client_secret": client_secret,
    }, timeout=15)

    if resp.status_code != 200:
        return {"error": f"Token exchange failed: {resp.text}"}

    token_data = resp.json()
    token_data["obtained_at"] = time.time()

    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    return {"success": True, "expires_in": token_data.get("expires_in")}


def _load_token() -> Optional[Dict]:
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
        obtained_at = data.get("obtained_at", 0)
        expires_in  = data.get("expires_in", 5184000)  # default 60 days
        if time.time() > obtained_at + expires_in - 300:
            return None  # expired (with 5-min buffer)
        return data
    except Exception:
        return None


def get_token_status() -> Dict:
    token = _load_token()
    if not token:
        return {"connected": False, "message": "Not connected — complete OAuth flow first"}

    # Fetch basic profile to verify token
    try:
        r = requests.get(LINKEDIN_ME_URL, headers={
            "Authorization": f"Bearer {token['access_token']}"
        }, timeout=10)
        if r.status_code == 200:
            profile = r.json()
            return {
                "connected": True,
                "name":      f"{profile.get('given_name', '')} {profile.get('family_name', '')}".strip(),
                "sub":       profile.get("sub"),
            }
    except Exception:
        pass

    return {"connected": False, "message": "Token present but profile fetch failed"}


def _get_profile_urn() -> Optional[str]:
    token = _load_token()
    if not token:
        return None
    try:
        r = requests.get(LINKEDIN_ME_URL, headers={
            "Authorization": f"Bearer {token['access_token']}"
        }, timeout=10)
        if r.status_code == 200:
            sub = r.json().get("sub")
            return f"urn:li:person:{sub}" if sub else None
    except Exception:
        return None


def post_to_linkedin(post_text: str, image_path: Optional[str] = None) -> Dict:
    """
    Post text (+ optional image) to LinkedIn personal profile.
    Returns dict with 'id' on success or 'error' on failure.
    """
    token = _load_token()
    if not token:
        return {"error": "Not authenticated — complete LinkedIn OAuth flow first"}

    access_token = token["access_token"]
    author_urn   = _get_profile_urn()
    if not author_urn:
        return {"error": "Could not resolve LinkedIn profile URN"}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # ── Upload image if provided ──────────────────────────────────────────────
    media_asset: Optional[str] = None
    if image_path and Path(image_path).exists():
        try:
            # Register upload
            reg_resp = requests.post(
                "https://api.linkedin.com/v2/assets?action=registerUpload",
                headers=headers,
                json={
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner":   author_urn,
                        "serviceRelationships": [{
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }]
                    }
                },
                timeout=15
            )
            if reg_resp.status_code == 200:
                reg_data     = reg_resp.json()
                upload_url   = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                media_asset  = reg_data["value"]["asset"]

                # Upload image bytes
                img_bytes = Path(image_path).read_bytes()
                requests.put(upload_url, data=img_bytes,
                             headers={"Authorization": f"Bearer {access_token}"},
                             timeout=30)
        except Exception:
            media_asset = None  # Fall back to text-only post

    # ── Build post payload ────────────────────────────────────────────────────
    if media_asset:
        payload = {
            "author":          author_urn,
            "lifecycleState":  "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status":      "READY",
                        "description": {"text": ""},
                        "media":       media_asset,
                    }]
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
    else:
        payload = {
            "author":          author_urn,
            "lifecycleState":  "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary":    {"text": post_text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }

    resp = requests.post(LINKEDIN_UGC_URL, headers=headers, json=payload, timeout=20)
    if resp.status_code in (200, 201):
        post_id = resp.headers.get("x-restli-id", resp.json().get("id", "unknown"))
        return {"success": True, "id": post_id}
    else:
        return {"error": f"LinkedIn API error {resp.status_code}: {resp.text[:300]}"}
