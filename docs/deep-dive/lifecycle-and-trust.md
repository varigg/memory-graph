# Lifecycle And Trust

This document summarizes the non-CRUD semantics carried by memory records.

## Core Record Semantics

Each memory row includes operational fields that affect retrieval and mutation:

- `visibility`: `shared` or `private`
- `owner_agent_id`: mutation authority anchor
- `status`: `active`, `archived`, or `invalidated`
- verification fields: `verification_status`, `verification_source`, `verified_at`
- operational context: `run_id`, `idempotency_key`, `tags`, `metadata_json`

## Ownership Rules

Lifecycle mutations are owner-restricted unless the action is explicitly
shared-safe.

- owner is required for archive, invalidate, verify, and promote
- relation operations (`merge`, `supersede`) require source ownership
- private target memories in relation operations are accessible only to the
  same owner

## Lifecycle Transitions

Status transitions are intentionally narrow:

- `active -> archived` is allowed
- `active -> invalidated` is allowed
- `invalidated` is terminal
- idempotent repeat transitions return current state without extra mutation

`merge` and `supersede` write both relation row and source status update as one
transactional unit.

- `merge` implies source status `archived`
- `supersede` implies source status `invalidated`

## Verification Model

Verification is a separate lifecycle action, not a create-time write concern.

- new memories default to `verification_status=unverified`
- updates accept `unverified`, `verified`, or `disputed`
- `verified` sets `verified_at`; non-verified states clear it

This keeps provenance and review state explicit for downstream retrieval and
audit workflows.

## Private Memory Retention Cleanup

`POST /memory/cleanup-private` applies retention policy only to private rows
older than the computed cutoff.

- `dry_run=true` reports candidates without mutation
- `dry_run=false` deletes matching private rows and returns deterministic
  summary fields
- optional filters: `owner_agent_id`, `status` (`active|archived|invalidated|all`)

Shared rows are out of scope for this cleanup flow.