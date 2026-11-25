"""Database target safety checks shared by the test suite, UAT seeding and operational scripts (P04-N01).

The application settings load backend/.env, which may point at a shared or remote cluster. Anything that
creates or deletes data for testing must prove that its target is a local MongoDB server and an isolated
database before it connects. A plain prefix test such as ``uri.startswith("mongodb://localhost")`` is not
enough: ``mongodb://localhost.example.com``, ``mongodb://127.0.0.1.nip.io`` and multi-host seed lists such as
``mongodb://localhost:27017,cluster.example.net:27017`` all pass it. These helpers parse every host instead.
Nothing here connects to a database or prints credentials.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import unquote

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _hosts(uri: str) -> Optional[List[str]]:
    """Return the lower-cased host names of a ``mongodb://`` URI, or None when it cannot be parsed safely."""
    if not isinstance(uri, str) or not uri.strip().startswith("mongodb://"):
        return None  # mongodb+srv:// resolves hosts through DNS, so it is never treated as local.
    rest = uri.strip()[len("mongodb://"):]
    authority = rest.split("/", 1)[0].split("?", 1)[0]
    if "@" in authority:
        authority = authority.rsplit("@", 1)[1]  # drop user:password@
    hosts: List[str] = []
    for part in authority.split(","):
        part = unquote(part.strip())
        if not part:
            return None
        if part.startswith("["):  # [::1]:27017
            end = part.find("]")
            if end < 0:
                return None
            host = part[1:end]
        else:
            host = part.rsplit(":", 1)[0] if part.count(":") == 1 else part
        hosts.append(host.lower())
    return hosts or None


def uri_database_name(uri: str) -> Optional[str]:
    """Database name written in the URI path (``mongodb://host/<name>``), if any."""
    rest = (uri or "").strip()[len("mongodb://"):] if (uri or "").strip().startswith("mongodb://") else ""
    if "/" not in rest:
        return None
    path = rest.split("/", 1)[1].split("?", 1)[0]
    return unquote(path) or None


def is_local_mongodb_uri(uri: str) -> bool:
    """True only when every host in the URI is a loopback host."""
    hosts = _hosts(uri)
    return bool(hosts) and all(h in LOCAL_HOSTS for h in hosts)


def isolation_error(uri: str, database_name: str, required_suffix: str) -> Optional[str]:
    """Explain why ``uri``/``database_name`` is not an isolated local target, or return None when it is."""
    if not is_local_mongodb_uri(uri):
        return "MONGODB_URI must be a mongodb:// URI whose hosts are all localhost/127.0.0.1/::1."
    name = (database_name or "").strip()
    if not name.endswith(required_suffix):
        return f"DATABASE_NAME must end with '{required_suffix}'."
    in_uri = uri_database_name(uri)
    if in_uri and not in_uri.endswith(required_suffix):
        return f"The database named in MONGODB_URI must also end with '{required_suffix}'."
    return None


def redacted_target(uri: str, database_name: str) -> Dict[str, Any]:
    """Metadata that is safe to print: scheme, host names and database name. Never credentials."""
    hosts = _hosts(uri)
    scheme = (uri or "").split("://", 1)[0] if "://" in (uri or "") else None
    return {
        "scheme": scheme,
        "hosts": hosts if hosts is not None else "unparsed (treated as remote)",
        "database": (database_name or "").strip() or None,
        "local": is_local_mongodb_uri(uri),
    }
