from __future__ import annotations

from supabase import Client, create_client

_client: Client | None = None


def get_db(*, url: str, service_role_key: str) -> Client:
    """Return a Supabase service-role client (lazy singleton).

    Raises RuntimeError if url or service_role_key is empty.
    """
    global _client
    if _client is None:
        if not url or not service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _client = create_client(url, service_role_key)
    return _client


def get_db_optional(*, url: str | None, service_role_key: str | None) -> Client | None:
    """Return a Supabase client if config is available, else None."""
    if not url or not service_role_key:
        return None
    return get_db(url=url, service_role_key=service_role_key)


def reset_client() -> None:
    """Reset the singleton (useful in tests)."""
    global _client
    _client = None
