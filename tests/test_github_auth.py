import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import settings
from app.github import auth


def make_key(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    path = tmp_path / "app.pem"
    path.write_bytes(pem)
    return path, key.public_key()


def test_jwt_claims(tmp_path, monkeypatch):
    path, public_key = make_key(tmp_path)
    monkeypatch.setattr(settings, "github_app_id", "12345")
    monkeypatch.setattr(settings, "github_private_key_path", str(path))

    token = auth.create_app_jwt()
    claims = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_iat": False})

    assert claims["iss"] == "12345"
    assert claims["exp"] - claims["iat"] <= 10 * 60


def test_installation_token_is_cached(monkeypatch):
    calls = []

    def fake_request(installation_id):
        calls.append(installation_id)
        return "tok", time.time() + 3600

    auth._token_cache.clear()
    monkeypatch.setattr(auth, "_request_installation_token", fake_request)

    assert auth.get_installation_token(1) == "tok"
    assert auth.get_installation_token(1) == "tok"
    assert calls == [1]            # only one network call


def test_expiring_token_is_refreshed(monkeypatch):
    calls = []

    def fake_request(installation_id):
        calls.append(installation_id)
        return f"tok{len(calls)}", time.time() + 3600

    auth._token_cache.clear()
    auth._token_cache[7] = ("old", time.time() + 30)   # expires in 30s: too close
    monkeypatch.setattr(auth, "_request_installation_token", fake_request)

    assert auth.get_installation_token(7) == "tok1"