import os

import requests


def get_provider():
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return None


def embed(text: str):
    provider = get_provider()
    if provider == "openai":
        return _embed_openai(text)
    if provider == "gemini":
        return _embed_gemini(text)
    return None


def _embed_openai(text: str):
    key = os.environ.get("OPENAI_API_KEY")
    try:
        resp = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-ada-002", "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except requests.exceptions.RequestException:
        return None


def _embed_gemini(text: str):
    key = os.environ.get("GOOGLE_API_KEY")
    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent",
            headers={
                "x-goog-api-key": key,
                "Content-Type": "application/json",
            },
            json={"content": {"parts": [{"text": text}]}},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]
    except requests.exceptions.RequestException:
        return None
