import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from database import get_db_connection, init_db, save_verification_record
from verification import verify_url

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://cmx-hub.github.io",
                "https://campusbridge-mu.vercel.app"
            ]
        }
    }
)

# Make sure the database and its tables exist
init_db()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "CampusBridge Backend",
        "message": "Backend is running successfully."
    })


@app.route("/api/opportunities", methods=["GET"])
def get_opportunities():
    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            title,
            category,
            organization,
            description,
            source_url,
            location,
            deadline,
            status,
            created_at
        FROM opportunities
        ORDER BY id DESC
    """)

    opportunities = cursor.fetchall()

    cursor.close()
    connection.close()

    # PostgreSQL returns tuples, so convert them using column names.
    if os.environ.get("DATABASE_URL"):
        columns = [
            "id",
            "title",
            "category",
            "organization",
            "description",
            "source_url",
            "location",
            "deadline",
            "status",
            "created_at"
        ]

        opportunities = [
            dict(zip(columns, opportunity))
            for opportunity in opportunities
        ]
    else:
        opportunities = [
            dict(opportunity)
            for opportunity in opportunities
        ]

    return jsonify(opportunities)


@app.route("/api/verify", methods=["POST"])
@limiter.limit("10 per minute")
def verify_opportunity():
    from flask import request

    data = request.get_json(silent=True) or {}
    url = data.get("url")

    if not isinstance(url, str) or not url.strip():
        return jsonify({
            "error": "A valid URL is required."
        }), 400

    organization = data.get("organization")

    if organization is not None and not isinstance(organization, str):
        return jsonify({
            "error": "Organization must be a string."
        }), 400

    result = verify_url(
        url.strip(),
        organization.strip() if organization else None
    )

    save_verification_record(result)

    return jsonify(result)


if __name__ == "__main__":
@app.route("/api/opportunities/submit", methods=["POST"])
def submit_opportunity():
    data = request.get_json(silent=True) or {}

    required = [
        "owner_id",
        "title",
        "category",
        "organization",
        "source_url"
    ]

    missing = [field for field in required if not data.get(field)]

    if missing:
        return jsonify({
            "success": False,
            "error": "Missing required fields",
            "missing": missing
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        if os.environ.get("DATABASE_URL"):
            cursor.execute("""
                INSERT INTO opportunities (
                    title, category, organization, description,
                    source_url, location, deadline, status,
                    owner_id, approval_status, verification_status, featured
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        'active', %s, 'pending', 'pending', FALSE)
                RETURNING id
            """, (
                data["title"],
                data["category"],
                data["organization"],
                data.get("description"),
                data["source_url"],
                data.get("location"),
                data.get("deadline"),
                data["owner_id"]
            ))
            opportunity_id = cursor.fetchone()[0]

        else:
            cursor.execute("""
                INSERT INTO opportunities (
                    title, category, organization, description,
                    source_url, location, deadline, status,
                    owner_id, approval_status, verification_status, featured
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, 'pending', 'pending', 0)
            """, (
                data["title"],
                data["category"],
                data["organization"],
                data.get("description"),
                data["source_url"],
                data.get("location"),
                data.get("deadline"),
                data["owner_id"]
            ))
            opportunity_id = cursor.lastrowid

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Opportunity submitted successfully and is pending review.",
            "opportunity_id": opportunity_id,
            "approval_status": "pending",
            "verification_status": "pending"
        }), 201

    except Exception as e:
        connection.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:
        connection.close()


    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )


@app.route("/api/verifications", methods=["GET"])
def verification_history():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            url,
            organization,
            risk_level,
            risk_score,
            source_verified,
            findings,
            risk_evidence,
            created_at
        FROM verification_records
        ORDER BY id DESC
        LIMIT 50
    """)

    rows = cursor.fetchall()

    records = []

    for row in rows:
        records.append({
            "id": row[0],
            "url": row[1],
            "organization": row[2],
            "risk_level": row[3],
            "risk_score": row[4],
            "source_verified": bool(row[5]),
            "findings": row[6],
            "risk_evidence": row[7],
            "created_at": str(row[8])
        })

    cursor.close()
    connection.close()

    return jsonify({
        "count": len(records),
        "records": records
    })
