import os


def _int_env(primary: str, fallback: str, default: int) -> int:
    raw = os.environ.get(primary, os.environ.get(fallback, str(default)))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _cors_origins():
    raw = os.environ.get("MEMORY_CORS_ORIGINS", os.environ.get("CORS_ORIGINS", "*")).strip()
    if raw == "*":
        return "*"
    # Comma-separated origins: "http://localhost:3000,https://app.example"
    return [o.strip() for o in raw.split(",") if o.strip()]


class Config:
    DB_PATH = os.environ.get("MEMORY_DB_PATH", os.path.expanduser("~/.claude/memory.db"))
    PORT = _int_env("MEMORY_PORT", "PORT", 7777)
    HOST = os.environ.get("MEMORY_HOST", os.environ.get("HOST", "0.0.0.0"))
    MAX_CONTENT_LENGTH = _int_env("MEMORY_MAX_CONTENT_LENGTH", "MAX_CONTENT_LENGTH", 1024 * 1024)
    CORS_ORIGINS = _cors_origins()
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    EMBEDDING_PROVIDER = (
        "openai"
        if os.environ.get("OPENAI_API_KEY")
        else "gemini"
        if os.environ.get("GOOGLE_API_KEY")
        else None
    )
