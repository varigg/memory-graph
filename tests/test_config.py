"""Tests for config.py — infrastructure layer."""
import os
import sys



def _reload_config():
    """Force-reload config module so env-var patches take effect."""
    if "config" in sys.modules:
        del sys.modules["config"]
    import config  # noqa: PLC0415
    return config


# ---------------------------------------------------------------------------
# DB_PATH
# ---------------------------------------------------------------------------

class TestDbPath:
    def test_db_path_default_is_memory_db(self, monkeypatch):
        monkeypatch.delenv("MEMORY_DB_PATH", raising=False)
        cfg = _reload_config()
        assert cfg.Config.DB_PATH.endswith("memory.db")

    def test_db_path_default_under_claude_dir(self, monkeypatch):
        monkeypatch.delenv("MEMORY_DB_PATH", raising=False)
        cfg = _reload_config()
        assert ".claude" in cfg.Config.DB_PATH

    def test_db_path_is_string(self, monkeypatch):
        monkeypatch.delenv("MEMORY_DB_PATH", raising=False)
        cfg = _reload_config()
        assert isinstance(cfg.Config.DB_PATH, str)

    def test_db_path_overridden_by_env_var(self, monkeypatch, tmp_path):
        custom = str(tmp_path / "custom.db")
        monkeypatch.setenv("MEMORY_DB_PATH", custom)
        cfg = _reload_config()
        assert custom == cfg.Config.DB_PATH

    def test_db_path_env_var_takes_precedence_over_default(self, monkeypatch, tmp_path):
        custom = str(tmp_path / "override.db")
        monkeypatch.setenv("MEMORY_DB_PATH", custom)
        cfg = _reload_config()
        assert os.path.expanduser("~/.claude/memory.db") != cfg.Config.DB_PATH


# ---------------------------------------------------------------------------
# PORT
# ---------------------------------------------------------------------------

class TestPort:
    def test_port_default_is_7777(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        cfg = _reload_config()
        assert cfg.Config.PORT == 7777

    def test_port_is_int(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        cfg = _reload_config()
        assert isinstance(cfg.Config.PORT, int)

    def test_port_is_valid_unprivileged_port(self, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        cfg = _reload_config()
        assert 1024 <= cfg.Config.PORT <= 65535

    def test_port_can_be_overridden_via_memory_port(self, monkeypatch):
        monkeypatch.setenv("MEMORY_PORT", "8787")
        cfg = _reload_config()
        assert cfg.Config.PORT == 8787

    def test_invalid_memory_port_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("MEMORY_PORT", "not-an-int")
        monkeypatch.delenv("PORT", raising=False)
        cfg = _reload_config()
        assert cfg.Config.PORT == 7777


# ---------------------------------------------------------------------------
# HOST
# ---------------------------------------------------------------------------

class TestHost:
    def test_host_default_is_all_interfaces(self, monkeypatch):
        monkeypatch.delenv("HOST", raising=False)
        cfg = _reload_config()
        assert cfg.Config.HOST == "0.0.0.0"

    def test_host_is_string(self, monkeypatch):
        monkeypatch.delenv("HOST", raising=False)
        cfg = _reload_config()
        assert isinstance(cfg.Config.HOST, str)

    def test_host_is_non_empty(self, monkeypatch):
        monkeypatch.delenv("HOST", raising=False)
        cfg = _reload_config()
        assert cfg.Config.HOST

    def test_host_can_be_overridden_via_memory_host(self, monkeypatch):
        monkeypatch.setenv("MEMORY_HOST", "127.0.0.1")
        cfg = _reload_config()
        assert cfg.Config.HOST == "127.0.0.1"


class TestBodySizeLimit:
    def test_max_content_length_default_is_1mb(self, monkeypatch):
        monkeypatch.delenv("MEMORY_MAX_CONTENT_LENGTH", raising=False)
        monkeypatch.delenv("MAX_CONTENT_LENGTH", raising=False)
        cfg = _reload_config()
        assert cfg.Config.MAX_CONTENT_LENGTH == 1024 * 1024

    def test_max_content_length_override(self, monkeypatch):
        monkeypatch.setenv("MEMORY_MAX_CONTENT_LENGTH", "2048")
        cfg = _reload_config()
        assert cfg.Config.MAX_CONTENT_LENGTH == 2048


class TestCorsOrigins:
    def test_cors_origins_default_is_wildcard(self, monkeypatch):
        monkeypatch.delenv("MEMORY_CORS_ORIGINS", raising=False)
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        cfg = _reload_config()
        assert cfg.Config.CORS_ORIGINS == "*"

    def test_cors_origins_parses_csv_list(self, monkeypatch):
        monkeypatch.setenv(
            "MEMORY_CORS_ORIGINS",
            "http://localhost:3000, https://app.example.com",
        )
        cfg = _reload_config()
        assert cfg.Config.CORS_ORIGINS == [
            "http://localhost:3000",
            "https://app.example.com",
        ]


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

class TestApiKeys:
    def test_openai_api_key_none_when_not_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.Config.OPENAI_API_KEY is None

    def test_openai_api_key_read_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
        cfg = _reload_config()
        assert cfg.Config.OPENAI_API_KEY == "sk-test-openai"

    def test_google_api_key_none_when_not_set(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.Config.GOOGLE_API_KEY is None

    def test_google_api_key_read_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test-google")
        cfg = _reload_config()
        assert cfg.Config.GOOGLE_API_KEY == "gk-test-google"

    def test_both_keys_can_be_none_simultaneously(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.Config.OPENAI_API_KEY is None
        assert cfg.Config.GOOGLE_API_KEY is None


# ---------------------------------------------------------------------------
# EMBEDDING_PROVIDER
# ---------------------------------------------------------------------------

class TestEmbeddingProvider:
    def test_embedding_provider_openai_when_openai_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.Config.EMBEDDING_PROVIDER == "openai"

    def test_embedding_provider_gemini_when_only_google_key_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        cfg = _reload_config()
        assert cfg.Config.EMBEDDING_PROVIDER == "gemini"

    def test_embedding_provider_none_when_no_keys_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.Config.EMBEDDING_PROVIDER is None

    def test_embedding_provider_openai_takes_precedence_over_google(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        cfg = _reload_config()
        assert cfg.Config.EMBEDDING_PROVIDER == "openai"

    def test_embedding_provider_is_string_or_none(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.Config.EMBEDDING_PROVIDER is None or isinstance(
            cfg.Config.EMBEDDING_PROVIDER, str
        )
