"""Tests for embeddings.py — provider detection and embed() behaviour."""
import sys
from unittest.mock import MagicMock, patch

import pytest


def _reload_embeddings():
    """Force-reload embeddings module so env-var patches take effect."""
    if "embeddings" in sys.modules:
        del sys.modules["embeddings"]
    if "config" in sys.modules:
        del sys.modules["config"]
    import embeddings  # noqa: PLC0415
    return embeddings


# ---------------------------------------------------------------------------
# get_provider
# ---------------------------------------------------------------------------

class TestGetProvider:
    def test_returns_openai_when_openai_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        assert emb.get_provider() == "openai"

    def test_returns_gemini_when_only_google_key_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        assert emb.get_provider() == "gemini"

    def test_returns_none_when_no_keys_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        assert emb.get_provider() is None

    def test_openai_takes_precedence_over_google(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        assert emb.get_provider() == "openai"


# ---------------------------------------------------------------------------
# embed — no provider configured
# ---------------------------------------------------------------------------

class TestEmbedNoProvider:
    def test_embed_returns_none_when_no_keys_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        result = emb.embed("some text")
        assert result is None

    def test_embed_does_not_raise_when_no_provider(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        try:
            emb.embed("test")
        except Exception as exc:
            pytest.fail(f"embed() raised unexpectedly: {exc}")

    def test_embed_returns_none_for_empty_string_no_provider(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        assert emb.embed("") is None


# ---------------------------------------------------------------------------
# embed — OpenAI provider
# ---------------------------------------------------------------------------

class TestEmbedOpenAI:
    """embed() calls the OpenAI embeddings API when OPENAI_API_KEY is set."""

    _OPENAI_RESPONSE = {
        "data": [{"embedding": [0.1, 0.2, 0.3]}],
        "model": "text-embedding-3-small",
    }

    def _mock_ok_response(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = self._OPENAI_RESPONSE
        resp.raise_for_status.return_value = None
        return resp

    def _mock_error_response(self):
        import requests  # noqa: PLC0415
        resp = MagicMock()
        resp.status_code = 429
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
        return resp

    def test_embed_calls_openai_endpoint(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()) as mock_post:
            emb.embed("hello openai")
        call_args = mock_post.call_args
        assert call_args is not None
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "openai" in url.lower() or "embeddings" in url.lower()

    def test_embed_returns_list_on_success(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()):
            result = emb.embed("hello openai")
        assert isinstance(result, list)
        assert result == pytest.approx([0.1, 0.2, 0.3])

    def test_embed_sends_text_in_request_body(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()) as mock_post:
            emb.embed("my special input text")
        call_kwargs = mock_post.call_args
        body = str(call_kwargs)
        assert "my special input text" in body

    def test_embed_returns_none_on_http_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_error_response()):
            result = emb.embed("trigger error")
        assert result is None

    def test_embed_does_not_raise_on_http_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_error_response()):
            try:
                emb.embed("trigger error")
            except Exception as exc:
                pytest.fail(f"embed() raised on HTTP error: {exc}")

    def test_embed_sends_authorization_header(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-my-key")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()) as mock_post:
            emb.embed("auth check")
        call_kwargs = mock_post.call_args
        assert "sk-my-key" in str(call_kwargs)


# ---------------------------------------------------------------------------
# embed — Gemini provider
# ---------------------------------------------------------------------------

class TestEmbedGemini:
    """embed() calls the Gemini embeddings API when only GOOGLE_API_KEY is set."""

    _GEMINI_RESPONSE = {
        "embedding": {"values": [0.4, 0.5, 0.6]},
    }

    def _mock_ok_response(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = self._GEMINI_RESPONSE
        resp.raise_for_status.return_value = None
        return resp

    def _mock_error_response(self):
        import requests  # noqa: PLC0415
        resp = MagicMock()
        resp.status_code = 500
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
        return resp

    def test_embed_calls_gemini_endpoint(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()) as mock_post:
            emb.embed("hello gemini")
        call_args = mock_post.call_args
        assert call_args is not None
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "google" in url.lower() or "gemini" in url.lower() or "googleapis" in url.lower()

    def test_embed_returns_list_on_success(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()):
            result = emb.embed("hello gemini")
        assert isinstance(result, list)
        assert result == pytest.approx([0.4, 0.5, 0.6])

    def test_embed_includes_api_key_in_request(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-my-key")
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()) as mock_post:
            emb.embed("key check")
        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("x-goog-api-key") == "gk-my-key"
        assert "params" not in call_kwargs or "key" not in call_kwargs.get("params", {})

    def test_embed_returns_none_on_http_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_error_response()):
            result = emb.embed("trigger error")
        assert result is None

    def test_embed_does_not_raise_on_http_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_error_response()):
            try:
                emb.embed("trigger error")
            except Exception as exc:
                pytest.fail(f"embed() raised on HTTP error: {exc}")

    def test_embed_sends_text_in_gemini_request(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        with patch("requests.post", return_value=self._mock_ok_response()) as mock_post:
            emb.embed("my gemini input text")
        call_kwargs = mock_post.call_args
        assert "my gemini input text" in str(call_kwargs)


# ---------------------------------------------------------------------------
# embed — network-level failures (connection error, timeout)
# ---------------------------------------------------------------------------

class TestEmbedNetworkErrors:
    def test_embed_returns_none_on_connection_error_openai(self, monkeypatch):
        import requests  # noqa: PLC0415
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", side_effect=requests.ConnectionError("refused")):
            result = emb.embed("conn error")
        assert result is None

    def test_embed_returns_none_on_timeout_openai(self, monkeypatch):
        import requests  # noqa: PLC0415
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        emb = _reload_embeddings()
        with patch("requests.post", side_effect=requests.Timeout("timed out")):
            result = emb.embed("timeout")
        assert result is None

    def test_embed_returns_none_on_connection_error_gemini(self, monkeypatch):
        import requests  # noqa: PLC0415
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        emb = _reload_embeddings()
        with patch("requests.post", side_effect=requests.ConnectionError("refused")):
            result = emb.embed("conn error gemini")
        assert result is None
