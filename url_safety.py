import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}


def is_private_or_internal_ip(ip):
    try:
        address = ipaddress.ip_address(ip)

        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        )

    except ValueError:
        return True


def validate_target_url(url):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False, "Only HTTP and HTTPS URLs are allowed."

    hostname = parsed.hostname

    if not hostname:
        return False, "URL does not contain a valid hostname."

    hostname = hostname.lower().rstrip(".")

    if hostname in BLOCKED_HOSTNAMES:
        return False, "Internal or localhost targets are not allowed."

    try:
        ipaddress.ip_address(hostname)

        if is_private_or_internal_ip(hostname):
            return False, "Private or internal IP addresses are not allowed."

    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM
        )

        for address in addresses:
            resolved_ip = address[4][0]

            if is_private_or_internal_ip(resolved_ip):
                return False, (
                    "Hostname resolves to a private or internal IP address."
                )

    except socket.gaierror:
        pass

    return True, "Target URL passed SSRF safety checks."
