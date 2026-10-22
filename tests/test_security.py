"""Tests for SSRF guard and security validation in backend/security.py."""

import socket

from backend.security import validate_pasted_html, validate_url


def test_allowed_schemes_only():
    ok, err = validate_url("ftp://example.com/file")
    assert not ok
    assert "not allowed" in (err or "").lower()

    ok, err = validate_url("file:///etc/passwd")
    assert not ok
    assert "not allowed" in (err or "").lower()

    ok, err = validate_url("javascript:alert(1)")
    assert not ok
    assert "not allowed" in (err or "").lower()

    ok, err = validate_url("data:text/html,<h1>test</h1>")
    assert not ok
    assert "not allowed" in (err or "").lower()


def test_loopback_and_metadata_ip_blocked_by_default():
    # 127.0.0.1 without allowlist
    ok, err = validate_url("http://127.0.0.1:9999/secret", allowed_hosts=[])
    assert not ok
    assert "blocked" in (err or "").lower()

    # Cloud metadata IP
    ok, err = validate_url("http://169.254.169.254/latest/meta-data/", allowed_hosts=[])
    assert not ok
    assert "blocked" in (err or "").lower()

    # IPv6 loopback
    ok, err = validate_url("http://[::1]:8080/admin", allowed_hosts=[])
    assert not ok
    assert "blocked" in (err or "").lower()


def test_allowed_local_hosts_exemption():
    allowed = ["127.0.0.1:8000", "localhost:8000", "127.0.0.1:8001"]

    # Allowed port 8000
    ok, err = validate_url("http://127.0.0.1:8000/demo/page1.html", allowed_hosts=allowed)
    assert ok
    assert err is None

    # Allowed localhost
    ok, err = validate_url("http://localhost:8000/demo/page1.html", allowed_hosts=allowed)
    assert ok
    assert err is None

    # Disallowed port 9000 on 127.0.0.1
    ok, err = validate_url("http://127.0.0.1:9000/internal", allowed_hosts=allowed)
    assert not ok
    assert "blocked" in (err or "").lower()


def test_dns_rebinding_mock_private_resolution():
    def mock_dns_private(host, port, type=socket.SOCK_STREAM):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", port))]

    ok, err = validate_url(
        "http://internal.company.corp/admin",
        allowed_hosts=[],
        dns_resolver=mock_dns_private,
    )
    assert not ok
    assert "blocked" in (err or "").lower()


def test_dns_public_resolution_allowed():
    def mock_dns_public(host, port, type=socket.SOCK_STREAM):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    ok, err = validate_url(
        "http://example.com/index.html",
        allowed_hosts=[],
        dns_resolver=mock_dns_public,
    )
    assert ok
    assert err is None


def test_pasted_html_validation():
    ok, err = validate_pasted_html("<h1>Hello</h1>")
    assert ok

    # Empty string
    ok, err = validate_pasted_html("")
    assert not ok

    # Size limit
    huge_html = "x" * 1_000_001
    ok, err = validate_pasted_html(huge_html, max_bytes=1_000_000)
    assert not ok
    assert "exceeds" in (err or "").lower()
