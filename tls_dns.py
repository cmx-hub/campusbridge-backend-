import socket
import ssl
from datetime import datetime


def analyze_tls_dns(domain):
    findings = []
    dns_resolved = False
    ip_addresses = []
    tls_info = {}

    # DNS analysis
    try:
        addresses = socket.getaddrinfo(
            domain,
            443,
            type=socket.SOCK_STREAM
        )

        ip_addresses = sorted(
            list(set(address[4][0] for address in addresses))
        )

        if ip_addresses:
            dns_resolved = True
            findings.append("Domain successfully resolves through DNS.")

    except socket.gaierror:
        findings.append("Domain could not be resolved through DNS.")

    # TLS certificate analysis
    try:
        context = ssl.create_default_context()

        with socket.create_connection(
            (domain, 443),
            timeout=5
        ) as sock:

            with context.wrap_socket(
                sock,
                server_hostname=domain
            ) as secure_socket:

                certificate = secure_socket.getpeercert()

                tls_info["subject"] = certificate.get("subject")
                tls_info["issuer"] = certificate.get("issuer")
                tls_info["expires"] = certificate.get("notAfter")

                expiry = certificate.get("notAfter")

                if expiry:
                    expiry_date = datetime.strptime(
                        expiry,
                        "%b %d %H:%M:%S %Y %Z"
                    )

                    tls_info["expired"] = expiry_date < datetime.utcnow()

                    if tls_info["expired"]:
                        findings.append(
                            "TLS certificate has expired."
                        )
                    else:
                        findings.append(
                            "TLS certificate is currently valid."
                        )

    except Exception:
        findings.append(
            "TLS certificate could not be verified."
        )

    return {
        "dns_resolved": dns_resolved,
        "ip_addresses": ip_addresses,
        "tls": tls_info,
        "findings": findings
    }
