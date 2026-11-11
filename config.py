import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Read the small KEY=VALUE subset used by .env.example without adding a runtime package.
env_file = ROOT / ".env"
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


class Config:
    SECRET_KEY = os.environ.get("SMARTSPEND_SECRET", "local-development-key-change-me")
    DATABASE = os.environ.get("SMARTSPEND_DATABASE", str(ROOT / "instance" / "smartspend.sqlite3"))
    UPLOAD_DIR = os.environ.get("SMARTSPEND_UPLOAD_DIR", str(ROOT / "instance" / "avatars"))
    C_LIBRARY = os.environ.get("SMARTSPEND_C_LIBRARY", str(ROOT / "c_core" / "build" / "smartspend.dll"))
    DEBUG = os.environ.get("SMARTSPEND_DEBUG", "0") == "1"
    MAX_CONTENT_LENGTH = 3 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SMARTSPEND_HTTPS", "0") == "1"
