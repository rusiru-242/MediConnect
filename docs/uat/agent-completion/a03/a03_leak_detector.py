"""pytest plugin (A03: delivery, payment and AI providers): block and count outbound connections to real delivery providers.

Loaded with -p a03_leak_detector. It never lets a connection through; it records the host, port and test id.
"""
import json
import os
import socket

_HOSTS = ("smtp.gmail.com", "api.twilio.com", "fcm.googleapis.com", "oauth2.googleapis.com",
          "api.stripe.com", "files.stripe.com", "generativelanguage.googleapis.com", "api.openai.com")
_attempts = []
_current = {"test": None}
_real_create = socket.create_connection
_real_getaddrinfo = socket.getaddrinfo


def _guard(host):
    if isinstance(host, str) and any(host == h or host.endswith("." + h) for h in _HOSTS):
        _attempts.append({"host": host, "test": _current["test"]})
        raise ConnectionRefusedError(f"A03 detector blocked {host}")


def _create(address, *args, **kwargs):
    _guard(address[0])
    return _real_create(address, *args, **kwargs)


def _gai(host, *args, **kwargs):
    _guard(host)
    return _real_getaddrinfo(host, *args, **kwargs)


socket.create_connection = _create
socket.getaddrinfo = _gai


def pytest_runtest_setup(item):
    _current["test"] = item.nodeid


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("A03_LEAK_OUT", "a03_leak_attempts.json")
    by_host = {}
    for a in _attempts:
        by_host[a["host"]] = by_host.get(a["host"], 0) + 1
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"blockedAttempts": len(_attempts), "byHost": by_host,
                   "tests": sorted({a["test"] for a in _attempts if a["test"]})}, fh, indent=1)
