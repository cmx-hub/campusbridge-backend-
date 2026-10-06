from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import re


RISK_PATTERNS = {
    "payment_request": [
        r"application fee",
        r"registration fee",
        r"pay.*fee",
        r"payment required",
        r"send money",
        r"pay.*scholarship"
    ],
    "credential_request": [
        r"password",
        r"login.*password",
        r"account password",
        r"verify.*password"
    ],
    "financial_information": [
        r"bank account",
        r"bank details",
        r"credit card",
        r"debit card",
        r"card number",
        r"cvv",
        r"mobile money"
    ],
    "sensitive_information": [
        r"national id",
        r"identity card",
        r"passport number",
        r"social security",
        r"date of birth"
    ],
    "urgency": [
        r"act now",
        r"apply immediately",
        r"limited time",
        r"urgent",
        r"last chance",
        r"offer expires"
    ]
}


def analyze_content(url):
    findings = []
    matched_categories = []
    risk_score = 0
    risk_evidence = []

    try:
        request = Request(
            url,
            headers={
                "User-Agent": "CampusBridge-Security-Scanner/1.0"
            }
        )

        response = urlopen(request, timeout=5)
        content = response.read(500000).decode(
            "utf-8",
            errors="ignore"
        ).lower()

        response.close()

        for category, patterns in RISK_PATTERNS.items():
            matches = []

            for pattern in patterns:
                if re.search(pattern, content):
                    matches.append(pattern)

            if matches:
                matched_categories.append(category)

        if "payment_request" in matched_categories:
            risk_score += 30
            risk_evidence.append({
                "category": "payment_request",
                "points": 30,
                "reason": "Page appears to request application or other payments."
            })
            findings.append(
                "Page appears to request application or other payments."
            )

        if "credential_request" in matched_categories:
            risk_score += 30
            risk_evidence.append({
                "category": "credential_request",
                "points": 30,
                "reason": "Page appears to request account credentials."
            })
            findings.append(
                "Page appears to request account credentials."
            )

        if "financial_information" in matched_categories:
            risk_score += 30
            risk_evidence.append({
                "category": "financial_information",
                "points": 30,
                "reason": "Page appears to request financial information."
            })
            findings.append(
                "Page appears to request financial information."
            )

        if "sensitive_information" in matched_categories:
            risk_score += 20
            risk_evidence.append({
                "category": "sensitive_information",
                "points": 20,
                "reason": "Page appears to request sensitive personal information."
            })
            findings.append(
                "Page appears to request sensitive personal information."
            )

        if "urgency" in matched_categories:
            risk_score += 10
            risk_evidence.append({
                "category": "urgency",
                "points": 10,
                "reason": "Page contains urgency or pressure-related language."
            })
            findings.append(
                "Page contains urgency or pressure-related language."
            )

        if not matched_categories:
            findings.append(
                "No major application-risk patterns were detected in the page content."
            )

    except (HTTPError, URLError, TimeoutError):
        findings.append(
            "Page content could not be retrieved for application-risk analysis."
        )
    except Exception:
        findings.append(
            "An unexpected error occurred during content analysis."
        )

    return {
        "risk_score": min(risk_score, 100),
        "matched_categories": matched_categories,
        "risk_evidence": risk_evidence,
        "findings": findings
    }
