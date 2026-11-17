import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env (gitignored) holds deployment-specific settings; real env vars
# set on the host (e.g. Render) take precedence since override defaults False.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")

# Browser origins allowed to call this API, comma-separated. Set in .env
# locally and as an env var on Render; unset means only localhost is allowed.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

# Local dev: Expo/Metro's web port varies by machine/run, so match any
# localhost port instead of hardcoding one.
CORS_ORIGIN_REGEX = os.environ.get(
    "CORS_ORIGIN_REGEX", r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
)

# Encryption in transit. On when deployed (set FORCE_HTTPS=true on Render):
# plain-HTTP requests are redirected to HTTPS and responses carry HSTS so
# browsers refuse to downgrade. Off locally, where uvicorn serves plain HTTP.
FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "").lower() in {"1", "true", "yes"}
