from urllib.parse import urlparse
from official_sources import OFFICIAL_SOURCES
from domain_intelligence import analyze_domain
from tls_dns import analyze_tls_dns
from content_risk import analyze_content
from url_safety import validate_target_url
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError


class SafeRedirectHandler(HTTPRedirectHandler):
    max_redirects = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirect_count = getattr(req, "_campusbridge_redirects", 0)

        if redirect_count >= self.max_redirects:
            raise URLError(
                "Redirect limit exceeded. Too many redirects."
            )

        safe_target, safety_message = validate_target_url(newurl)

        if not safe_target:
            raise URLError(
                f"Unsafe redirect blocked: {safety_message}"
            )

        new_request = super().redirect_request(
            req, fp, code, msg, headers, newurl
        )

        if new_request is not None:
            new_request._campusbridge_redirects = redirect_count + 1

        return new_request


def verify_url(url, organization=None):
    findings = []
    risk_score = 0
    risk_evidence = []
    domain_intelligence = []

    def add_risk(points, category, reason):
        nonlocal risk_score

        risk_score += points

        risk_evidence.append({
            "category": category,
            "points": points,
            "reason": reason
        })

    safe_target, safety_message = validate_target_url(url)

    if not safe_target:
        return {
            "url": url,
            "valid": False,
            "https": False,
            "domain": None,
            "organization": organization,
            "source_verified": False,
            "redirects": [],
            "domain_intelligence": [],
            "tls_dns": {},
            "content_risk": {},
            "risk_score": 100,
            "risk_level": "HIGH",
            "findings": [safety_message]
        }

    # 1. Validate URL
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {
            "url": url,
            "valid": False,
            "https": False,
            "domain": None,
            "redirects": [],
            "risk_score": 100,
            "risk_level": "HIGH",
            "findings": ["Invalid or unsupported URL."]
        }

    domain = parsed.hostname.lower()

    # 2. HTTPS check
    uses_https = parsed.scheme == "https"

    if not uses_https:
        add_risk(
            25,
            "transport_security",
            "Website does not use HTTPS."
        )
        findings.append("Website does not use HTTPS.")
    else:
        findings.append("HTTPS is enabled.")

    # 3. Official source verification
    source_verified = None

    if organization:
        official_domains = OFFICIAL_SOURCES.get(organization)

        if official_domains:
            source_verified = any(
                domain == official_domain or
                domain.endswith("." + official_domain)
                for official_domain in official_domains
            )

            domain_intelligence = analyze_domain(
                domain,
                official_domains
            )

            if source_verified:
                findings.append(
                    f"Domain matches the known official source for {organization}."
                )
            else:
                add_risk(
                    35,
                    "source_verification",
                    f"Domain does not match the known official source for {organization}."
                )
                findings.append(
                    f"Domain does not match the known official source for {organization}."
                )

                for analysis in domain_intelligence:
                    if analysis["suspicious_terms"]:
                        findings.append(
                            "Suspicious domain terms detected: "
                            + ", ".join(analysis["suspicious_terms"])
                            + "."
                        )
        else:
            domain_intelligence = []

            findings.append(
                "Organization is not currently in the CampusBridge official-source database."
            )

    # 3. Basic domain checks
    if domain.replace(".", "").isdigit():
        add_risk(
            25,
            "domain_structure",
            "URL uses an IP address instead of a domain name."
        )
        findings.append("URL uses an IP address instead of a domain name.")

    if "@" in url:
        add_risk(
            30,
            "url_structure",
            "URL contains an @ character, which can hide the real destination."
        )
        findings.append("URL contains an @ character, which can hide the real destination.")

    # 4. Redirect inspection
    redirects = []

    tls_dns = analyze_tls_dns(domain)

    for finding in tls_dns["findings"]:
        findings.append(finding)

    content_risk = analyze_content(url)

    risk_score += content_risk["risk_score"]

    for evidence in content_risk.get("risk_evidence", []):
        risk_evidence.append(evidence)

    for finding in content_risk["findings"]:
        findings.append(finding)

    try:
        request = Request(
            url,
            headers={"User-Agent": "CampusBridge-Security-Scanner/1.0"}
        )

        opener = build_opener(SafeRedirectHandler)
        response = opener.open(request, timeout=5)

        final_url = response.geturl()

        if final_url != url:
            redirects.append(final_url)
            findings.append("URL redirects to another destination.")

            final_domain = urlparse(final_url).hostname

            if final_domain:
                normalized_original = domain.lower().removeprefix("www.")
                normalized_final = final_domain.lower().removeprefix("www.")

                if normalized_final == normalized_original:
                    findings.append(
                        "Redirect stays within the same organizational domain."
                    )
                else:
                    risk_score += 20
                    findings.append(
                        "Redirect destination uses a different domain."
                    )

        response.close()

    except HTTPError as error:
        findings.append(
            f"Website responded with HTTP status {error.code}."
        )

        if error.code >= 400:
            risk_score += 10

    except (URLError, TimeoutError):
        add_risk(
            10,
            "connection_failure",
            "Website could not be reached during verification."
        )
        findings.append(
            "Website could not be reached during verification."
        )

    except Exception:
        risk_score += 10
        findings.append(
            "An unexpected error occurred during verification."
        )

    # 5. Keep the risk score within the 0–100 range.
    risk_score = min(100, max(0, risk_score))

    # 6. Determine risk level
    if risk_score >= 60:
        risk_level = "HIGH"
    elif risk_score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "url": url,
        "valid": True,
        "https": uses_https,
        "domain": domain,
        "organization": organization,
        "source_verified": source_verified,
        "domain_intelligence": domain_intelligence,
        "tls_dns": tls_dns,
        "content_risk": content_risk,
        "risk_evidence": risk_evidence,
        "redirects": redirects,
        "risk_score": min(risk_score, 100),
        "risk_level": risk_level,
        "findings": findings
    }
