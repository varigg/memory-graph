# Phase 2A — Hardening and Runtime Configuration

## Goal

Harden runtime behavior, improve deployment flexibility, and return JSON for
common framework-level errors.

## Implemented

- Added env-driven configuration for:
  - `MEMORY_HOST`
  - `MEMORY_PORT`
  - `MEMORY_MAX_CONTENT_LENGTH`
  - `MEMORY_CORS_ORIGINS`
- Configured Flask request size guard with `MAX_CONTENT_LENGTH`.
- Added JSON error handlers for:
  - `404 Not Found`
  - `405 Method Not Allowed`
  - `413 Request Entity Too Large`
  - Existing `500` handler retained.
- Updated embedding provider integration security:
  - Gemini API key is sent via `x-goog-api-key` header.
  - API key is no longer put in URL query string.

## Why this matters

- Safer defaults for production-like deployment and reverse proxies.
- Better client UX (no HTML fallback pages for common API errors).
- Reduced credential leak risk in logs and telemetry.

## Validation

- Added/updated tests for env config parsing and JSON error behavior.
- Full suite passed after phase completion.
