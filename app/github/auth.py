import time
from pathlib import Path

import httpx
import jwt  # PyJWT

from app.config import settings
from app.worker.exceptions import PermanentError, TransientError

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# installation_id -> (token, expires_at_epoch)
_token_cache: dict[int, tuple[str, float]] = {}


def _private_key() -> str:
    path = Path(settings.github_private_key_path)
    if not path.exists():
        raise PermanentError(f"GitHub private key not found at {path}")
    return path.read_text()


def create_app_jwt() -> str:
    """Short-lived JWT proving we are the App (RS256, max 10 minutes)."""
    if not settings.github_app_id:
        raise PermanentError("GITHUB_APP_ID is not set")
    now = int(time.time())
    payload = {
        "iat": now - 60,        # backdate 60s to tolerate clock drift
        "exp": now + 9 * 60,    # under GitHub's 10 minute limit
        "iss": str(settings.github_app_id),
    }
    return jwt.encode(payload, _private_key(), algorithm="RS256")


def _check(resp: httpx.Response) -> None:
    """Map HTTP failures to retryable vs permanent errors."""
    if resp.status_code < 400:
        return
    if resp.status_code in (429, 502, 503, 504) or resp.status_code >= 500:
        raise TransientError(f"GitHub {resp.status_code}: {resp.text[:200]}")
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise TransientError("GitHub rate limit hit")
    raise PermanentError(f"GitHub {resp.status_code}: {resp.text[:200]}")


def _request_installation_token(installation_id: int) -> tuple[str, float]:
    headers = {**HEADERS, "Authorization": f"Bearer {create_app_jwt()}"}
    try:
        resp = httpx.post(
            f"{API}/app/installations/{installation_id}/access_tokens",
            headers=headers,
            timeout=15,
        )
    except httpx.RequestError as e:
        raise TransientError(f"network error talking to GitHub: {e}") from e
    _check(resp)
    data = resp.json()
    # expires_at looks like "2026-10-29T14:00:00Z"
    expires = time.mktime(time.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    return data["token"], expires


def get_installation_token(installation_id: int) -> str:
    """Cached installation token; refreshed 2 minutes before it expires."""
    cached = _token_cache.get(installation_id)
    if cached and cached[1] - time.time() > 120:
        return cached[0]
    token, expires = _request_installation_token(installation_id)
    _token_cache[installation_id] = (token, expires)
    return token


def get_installation_id(repo_full_name: str) -> int:
    """Look up the installation for a repo (fallback when the webhook lacked one)."""
    headers = {**HEADERS, "Authorization": f"Bearer {create_app_jwt()}"}
    try:
        resp = httpx.get(f"{API}/repos/{repo_full_name}/installation", headers=headers, timeout=15)
    except httpx.RequestError as e:
        raise TransientError(f"network error talking to GitHub: {e}") from e
    _check(resp)
    return resp.json()["id"]