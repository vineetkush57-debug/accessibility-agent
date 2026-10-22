"""Security module: URL validation, SSRF guard, and resource limits."""

import ipaddress
import socket
from urllib.parse import urlparse

from backend.config import settings


class SecurityError(Exception):
    """Raised when security boundaries or limits are violated."""


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP is loopback, private, link-local, multicast, or unspecified."""
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def validate_url(
    url: str,
    allowed_hosts: list[str] | None = None,
    dns_resolver=None,
) -> tuple[bool, str | None]:
    """Validate a URL against SSRF and scheme attacks.

    Returns:
        (is_valid, error_message_or_none)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string."

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False, "Invalid URL format."

    if parsed.scheme.lower() not in ("http", "https"):
        return (
            False,
            f"Scheme '{parsed.scheme}' is not allowed. Only HTTP and HTTPS are supported.",
        )

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must include a valid hostname."

    port = parsed.port
    if port is None:
        port = 80 if parsed.scheme.lower() == "http" else 443

    # Check allowed local hosts first
    effective_allowed = allowed_hosts if allowed_hosts is not None else settings.allowed_hosts_list
    host_port = f"{hostname}:{port}"
    host_only = hostname

    is_explicitly_allowed = False
    for allowed in effective_allowed:
        allowed_clean = allowed.strip()
        if allowed_clean in (host_port, host_only):
            is_explicitly_allowed = True
            break
        # Also check with normalized 127.0.0.1 vs localhost
        if hostname in ("127.0.0.1", "localhost") and allowed_clean.startswith(
            ("127.0.0.1", "localhost")
        ):
            allowed_parts = allowed_clean.split(":")
            allowed_port = (
                int(allowed_parts[1])
                if len(allowed_parts) > 1
                else (80 if parsed.scheme.lower() == "http" else 443)
            )
            if allowed_port == port:
                is_explicitly_allowed = True
                break

    if is_explicitly_allowed:
        return True, None

    # Resolve IP addresses for the hostname
    try:
        resolver = dns_resolver if dns_resolver else socket.getaddrinfo
        addr_infos = resolver(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False, f"Could not resolve host '{hostname}'."
    except Exception as e:
        return False, f"Host resolution error: {e!s}"

    if not addr_infos:
        return False, f"No IP address found for host '{hostname}'."

    for addr in addr_infos:
        ip_str = addr[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if is_ip_blocked(ip_obj):
                return (
                    False,
                    f"Access to private/local/reserved IP address '{ip_str}' is blocked.",
                )
        except ValueError:
            return False, f"Invalid IP address '{ip_str}'."

    return True, None


def validate_pasted_html(html: str, max_bytes: int = 1_000_000) -> tuple[bool, str | None]:
    """Validate pasted HTML content and size."""
    if not html or not isinstance(html, str):
        return False, "Pasted HTML must be a non-empty string."

    byte_len = len(html.encode("utf-8"))
    if byte_len > max_bytes:
        return (
            False,
            f"HTML size ({byte_len} bytes) exceeds the maximum allowed limit of {max_bytes} bytes.",
        )

    return True, None
