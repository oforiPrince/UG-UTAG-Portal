from types import SimpleNamespace

from starlette.requests import Request

from utag_api import dependencies


def request_from(peer: str, forwarded_for: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"x-forwarded-for", forwarded_for.encode()),
            ],
            "client": (peer, 1234),
        }
    )


def test_client_ip_discards_spoofed_values_before_trusted_proxies(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(trusted_proxy_cidrs=["127.0.0.1/32", "172.16.0.0/12"]),
    )
    request = request_from(
        "172.20.0.5",
        "198.51.100.99, 203.0.113.10, 172.20.0.4",
    )
    assert dependencies.client_ip(request) == "203.0.113.10"


def test_client_ip_ignores_forwarding_headers_from_untrusted_peers(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(trusted_proxy_cidrs=["127.0.0.1/32"]),
    )
    request = request_from("203.0.113.25", "198.51.100.99")
    assert dependencies.client_ip(request) == "203.0.113.25"
