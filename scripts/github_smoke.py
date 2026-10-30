import sys

import httpx

from app.github.auth import API, HEADERS, create_app_jwt, get_installation_id, get_installation_token

repo = sys.argv[1] if len(sys.argv) > 1 else "Ish200565/test_repo"
pr = sys.argv[2] if len(sys.argv) > 2 else "1"

# 1. Authenticate as the App itself
app = httpx.get(f"{API}/app", headers={**HEADERS, "Authorization": f"Bearer {create_app_jwt()}"})
print("App JWT ok:", app.status_code, app.json().get("name"))

# 2. Find the installation and get a token
inst = get_installation_id(repo)
print("Installation id:", inst)
token = get_installation_token(inst)
print("Installation token ok:", token[:8] + "...")

# 3. Use the token to read the PR
r = httpx.get(
    f"{API}/repos/{repo}/pulls/{pr}",
    headers={**HEADERS, "Authorization": f"Bearer {token}"},
)
print("PR fetch:", r.status_code, "|", r.json().get("title"))