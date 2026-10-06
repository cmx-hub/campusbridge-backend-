import re
from urllib.parse import urlparse
from rapidfuzz import fuzz


def normalize_domain(domain):
    domain = domain.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def domain_similarity(domain, official_domain):
    domain = normalize_domain(domain)
    official_domain = normalize_domain(official_domain)

    domain_name = domain.split(".")[0]
    official_name = official_domain.split(".")[0]

    score = fuzz.ratio(domain_name, official_name)

    suspicious_terms = [
        "apply",
        "application",
        "scholarship",
        "grant",
        "funding",
        "2026",
        "2027",
        "2028",
        "official",
        "login",
        "verify"
    ]

    matched_terms = [
        term for term in suspicious_terms
        if term in domain_name
    ]

    return {
        "similarity_score": round(score, 2),
        "suspicious_terms": matched_terms
    }


def analyze_domain(domain, official_domains):
    domain = normalize_domain(domain)

    results = []

    for official_domain in official_domains:
        analysis = domain_similarity(domain, official_domain)

        if domain == normalize_domain(official_domain):
            analysis["match"] = True
            analysis["reason"] = "Domain exactly matches the official source."
        else:
            analysis["match"] = False
            analysis["reason"] = "Domain differs from the official source."

        results.append({
            "official_domain": normalize_domain(official_domain),
            **analysis
        })

    return results
