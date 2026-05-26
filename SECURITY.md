# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly via email to **security@domelayer.com**. Do not open a public issue.

## Secret Management

This repository contains **no secrets**. It is a library package with no deployment credentials. Backends that consume dome-core manage their own secrets via environment variables (never committed to git).

## Key Classes

This package has no secret env vars of its own. Consumers must provide:
- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` — passed to `dome_core.db`
- `ANTHROPIC_API_KEY` — passed to `dome_core.llm.claude.ClaudeProvider`
- `SENTRY_DSN` — read from env by `dome_core.sentry.init_sentry()`

## Rotation Policy

Not applicable — dome-core holds no keys. Each consuming service maintains its own rotation schedule documented in its `SECURITY.md`.
