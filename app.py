import os
from flask import request, Flask, jsonify
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

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    location = request.args.get("location", "").strip()
    status = request.args.get("status", "").strip()

    is_postgres = bool(os.environ.get("DATABASE_URL"))
    placeholder = "%s" if is_postgres else "?"

    query = """
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
        WHERE 1=1
    """

    params = []

    like_operator = "ILIKE" if is_postgres else "LIKE"

    if search:
        query += f"""
            AND (
                title {like_operator} {placeholder}
                OR organization {like_operator} {placeholder}
                OR description {like_operator} {placeholder}
            )
        """
        search_value = f"%{search}%"
        params.extend([search_value, search_value, search_value])

    if category:
        query += f" AND category = {placeholder}"
        params.append(category)

    if location:
        query += f" AND location {like_operator} {placeholder}"
        params.append(f"%{location}%")

    if status:
        query += f" AND status = {placeholder}"
        params.append(status)

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    opportunities = cursor.fetchall()

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

    if is_postgres:
        opportunities = [
            dict(zip(columns, opportunity))
            for opportunity in opportunities
        ]
    else:
        opportunities = [
            dict(opportunity)
            for opportunity in opportunities
        ]

    cursor.close()
    connection.close()

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


@app.route("/api/opportunities/<int:opportunity_id>", methods=["GET"])
def get_opportunity(opportunity_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"

    cursor.execute(f"""
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
            created_at,
            verification_status,
            verification_risk_score,
            last_verified_at,
            verification_status,
            verification_risk_score,
            last_verified_at
        FROM opportunities
        WHERE id = {placeholder}
    """, (opportunity_id,))

    opportunity = cursor.fetchone()

    cursor.close()
    connection.close()

    if not opportunity:
        return jsonify({"error": "Opportunity not found"}), 404

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
        "created_at",
        "verification_status",
        "verification_risk_score",
        "last_verified_at"
    ]

    if os.environ.get("DATABASE_URL"):
        opportunity = dict(zip(columns, opportunity))
    else:
        opportunity = dict(opportunity)

    return jsonify(opportunity)


@app.route("/api/opportunities/<int:opportunity_id>/verify", methods=["POST"])
@limiter.limit("10 per minute")
def verify_specific_opportunity(opportunity_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"

    cursor.execute(f"""
        SELECT source_url, organization
        FROM opportunities
        WHERE id = {placeholder}
    """, (opportunity_id,))

    opportunity = cursor.fetchone()

    cursor.close()
    connection.close()

    if not opportunity:
        return jsonify({"error": "Opportunity not found"}), 404

    if os.environ.get("DATABASE_URL"):
        source_url, organization = opportunity
    else:
        source_url = opportunity["source_url"]
        organization = opportunity["organization"]

    if not source_url:
        return jsonify({
            "error": "This opportunity has no source URL."
        }), 400

    result = verify_url(
        source_url,
        organization
    )

    risk_level = result.get("risk_level", "UNKNOWN")
    risk_score = int(result.get("risk_score", 0))

    connection = get_db_connection()
    cursor = connection.cursor()

    placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"

    cursor.execute(
        f"""
        UPDATE opportunities
        SET verification_status = {placeholder},
            verification_risk_score = {placeholder},
            last_verified_at = CURRENT_TIMESTAMP
        WHERE id = {placeholder}
        """,
        (risk_level.lower(), risk_score, opportunity_id)
    )

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "opportunity_id": opportunity_id,
        "verification": result,
        "saved": True
    })


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

@app.route("/api/auth/register", methods=["POST"])
def register_student():
    from werkzeug.security import generate_password_hash

    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required."
        }), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters."
        }), 400

    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({
            "error": "Please provide a valid email address."
        }), 400

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email = %s"
            if os.environ.get("DATABASE_URL")
            else "SELECT id FROM users WHERE email = ?",
            (email,)
        )

        if cursor.fetchone():
            return jsonify({
                "error": "An account with this email already exists."
            }), 409

        password_hash = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash, role, status)
            VALUES (%s, %s, %s, %s, %s)
            """
            if os.environ.get("DATABASE_URL")
            else
            """
            INSERT INTO users (name, email, password_hash, role, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, email, password_hash, "student", "active")
        )

        conn.commit()

        return jsonify({
            "message": "Student account created successfully.",
            "user": {
                "name": name,
                "email": email,
                "role": "student"
            }
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({
            "error": "Unable to create account.",
            "details": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()

@limiter.limit("5 per minute")
@app.route("/api/auth/login", methods=["POST"])
def login_student():
    from werkzeug.security import check_password_hash

    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "error": "Email and password are required."
        }), 400

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, email, password_hash, role, status FROM users WHERE email = %s"
            if os.environ.get("DATABASE_URL")
            else
            "SELECT id, name, email, password_hash, role, status FROM users WHERE email = ?",
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({
                "error": "Invalid email or password."
            }), 401

        user_id, name, user_email, password_hash, role, status = user

        if status != "active":
            return jsonify({
                "error": "This account is not active."
            }), 403

        if not password_hash or not check_password_hash(password_hash, password):
            return jsonify({
                "error": "Invalid email or password."
            }), 401

        return jsonify({
            "message": "Login successful.",
            "user": {
                "id": user_id,
                "name": name,
                "email": user_email,
                "role": role
            }
        }), 200

    finally:
        cursor.close()
        conn.close()



@app.route("/api/students/<int:user_id>/profile", methods=["POST"])
def create_student_profile(user_id):
    data = request.get_json(silent=True) or {}

    institution = data.get("institution", "").strip()
    field_of_study = data.get("field_of_study", "").strip()
    level = data.get("level", "").strip()
    skills = data.get("skills", "").strip()
    interests = data.get("interests", "").strip()

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, role FROM users WHERE id = %s"
            if os.environ.get("DATABASE_URL")
            else
            "SELECT id, role FROM users WHERE id = ?",
            (user_id,)
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Student account not found."}), 404

        if user[1] != "student":
            return jsonify({"error": "Only student accounts can create student profiles."}), 403

        cursor.execute(
            "SELECT id FROM student_profiles WHERE user_id = %s"
            if os.environ.get("DATABASE_URL")
            else
            "SELECT id FROM student_profiles WHERE user_id = ?",
            (user_id,)
        )

        if cursor.fetchone():
            return jsonify({"error": "Student profile already exists."}), 409

        cursor.execute(
            """
            INSERT INTO student_profiles
            (user_id, institution, field_of_study, level, skills, interests)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            if os.environ.get("DATABASE_URL")
            else
            """
            INSERT INTO student_profiles
            (user_id, institution, field_of_study, level, skills, interests)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                institution,
                field_of_study,
                level,
                skills,
                interests
            )
        )

        conn.commit()

        return jsonify({
            "message": "Student profile created successfully.",
            "profile": {
                "user_id": user_id,
                "institution": institution,
                "field_of_study": field_of_study,
                "level": level,
                "skills": skills,
                "interests": interests
            }
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({
            "error": "Unable to create student profile.",
            "details": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()



@app.route("/api/students/<int:user_id>/profile", methods=["GET"])
def get_student_profile(user_id):
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                u.id,
                u.name,
                u.email,
                u.role,
                sp.institution,
                sp.field_of_study,
                sp.level,
                sp.skills,
                sp.interests
            FROM users u
            LEFT JOIN student_profiles sp ON u.id = sp.user_id
            WHERE u.id = %s
            """
            if os.environ.get("DATABASE_URL")
            else
            """
            SELECT
                u.id,
                u.name,
                u.email,
                u.role,
                sp.institution,
                sp.field_of_study,
                sp.level,
                sp.skills,
                sp.interests
            FROM users u
            LEFT JOIN student_profiles sp ON u.id = sp.user_id
            WHERE u.id = ?
            """,
            (user_id,)
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Student account not found."}), 404

        if user[3] != "student":
            return jsonify({"error": "Student account required."}), 403

        return jsonify({
            "user": {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "role": user[3]
            },
            "profile": {
                "institution": user[4],
                "field_of_study": user[5],
                "level": user[6],
                "skills": user[7],
                "interests": user[8]
            }
        }), 200

    finally:
        cursor.close()
        conn.close()



@app.route("/api/students/<int:user_id>/profile", methods=["PUT"])
def update_student_profile(user_id):
    data = request.get_json(silent=True) or {}

    institution = data.get("institution", "").strip()
    field_of_study = data.get("field_of_study", "").strip()
    level = data.get("level", "").strip()
    skills = data.get("skills", "").strip()
    interests = data.get("interests", "").strip()

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, role FROM users WHERE id = %s"
            if os.environ.get("DATABASE_URL")
            else
            "SELECT id, role FROM users WHERE id = ?",
            (user_id,)
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Student account not found."}), 404

        if user[1] != "student":
            return jsonify({
                "error": "Only student accounts can update student profiles."
            }), 403

        cursor.execute(
            "SELECT id FROM student_profiles WHERE user_id = %s"
            if os.environ.get("DATABASE_URL")
            else
            "SELECT id FROM student_profiles WHERE user_id = ?",
            (user_id,)
        )

        if not cursor.fetchone():
            return jsonify({"error": "Student profile not found."}), 404

        cursor.execute(
            """
            UPDATE student_profiles
            SET institution = %s,
                field_of_study = %s,
                level = %s,
                skills = %s,
                interests = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
            """
            if os.environ.get("DATABASE_URL")
            else
            """
            UPDATE student_profiles
            SET institution = ?,
                field_of_study = ?,
                level = ?,
                skills = ?,
                interests = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                institution,
                field_of_study,
                level,
                skills,
                interests,
                user_id
            )
        )

        conn.commit()

        return jsonify({
            "message": "Student profile updated successfully.",
            "profile": {
                "user_id": user_id,
                "institution": institution,
                "field_of_study": field_of_study,
                "level": level,
                "skills": skills,
                "interests": interests
            }
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            "error": "Unable to update student profile.",
            "details": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()



@app.route("/api/students/<int:user_id>/applications", methods=["POST"])
def submit_student_application(user_id):
    data = request.get_json(silent=True) or {}
    opportunity_id = data.get("opportunity_id")
    notes = data.get("notes", "").strip()

    if not opportunity_id:
        return jsonify({"error": "opportunity_id is required."}), 400

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"

        cursor.execute(
            f"SELECT id, role FROM users WHERE id = {placeholder}",
            (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Student account not found."}), 404

        if user[1] != "student":
            return jsonify({
                "error": "Only student accounts can submit applications."
            }), 403

        cursor.execute(
            f"SELECT id, title, status FROM opportunities WHERE id = {placeholder}",
            (opportunity_id,)
        )
        opportunity = cursor.fetchone()

        if not opportunity:
            return jsonify({"error": "Opportunity not found."}), 404

        if opportunity[2] != "active":
            return jsonify({
                "error": "This opportunity is not currently active."
            }), 400

        cursor.execute(
            f"""
            SELECT id FROM applications
            WHERE user_id = {placeholder}
            AND opportunity_id = {placeholder}
            """,
            (user_id, opportunity_id)
        )

        if cursor.fetchone():
            return jsonify({
                "error": "You have already applied to this opportunity."
            }), 409

        cursor.execute(
            f"""
            INSERT INTO applications
            (user_id, opportunity_id, status, notes)
            VALUES ({placeholder}, {placeholder}, 'submitted', {placeholder})
            """,
            (user_id, opportunity_id, notes)
        )

        conn.commit()

        cursor.execute(
            f"""
            SELECT id, status, notes, applied_at
            FROM applications
            WHERE user_id = {placeholder}
            AND opportunity_id = {placeholder}
            """,
            (user_id, opportunity_id)
        )

        application = cursor.fetchone()

        return jsonify({
            "message": "Application submitted successfully.",
            "application": {
                "id": application[0],
                "user_id": user_id,
                "opportunity_id": opportunity_id,
                "opportunity_title": opportunity[1],
                "status": application[1],
                "notes": application[2],
                "applied_at": str(application[3])
            }
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({
            "error": "Unable to submit application.",
            "details": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()



@app.route("/api/students/<int:user_id>/applications", methods=["GET"])
def get_student_applications(user_id):
    conn = get_db_connection()

    try:
        cursor = conn.cursor()
        placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"

        cursor.execute(
            f"SELECT id, name, email, role FROM users WHERE id = {placeholder}",
            (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Student account not found."}), 404

        if user[3] != "student":
            return jsonify({
                "error": "Only student accounts can view student applications."
            }), 403

        cursor.execute(
            f"""
            SELECT
                a.id,
                a.opportunity_id,
                o.title,
                o.organization,
                a.status,
                a.notes,
                a.applied_at,
                a.updated_at
            FROM applications a
            JOIN opportunities o ON a.opportunity_id = o.id
            WHERE a.user_id = {placeholder}
            ORDER BY a.applied_at DESC
            """,
            (user_id,)
        )

        rows = cursor.fetchall()

        applications = []

        for row in rows:
            applications.append({
                "id": row[0],
                "opportunity_id": row[1],
                "opportunity_title": row[2],
                "organization": row[3],
                "status": row[4],
                "notes": row[5],
                "applied_at": str(row[6]),
                "updated_at": str(row[7])
            })

        return jsonify({
            "user_id": user_id,
            "applications": applications,
            "count": len(applications)
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Unable to retrieve applications.",
            "details": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()



@app.route("/api/students/<int:user_id>/applications/<int:application_id>", methods=["PUT"])
def update_student_application(user_id, application_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status", "").strip().lower()
    notes = data.get("notes")

    allowed_statuses = {
        "submitted",
        "reviewing",
        "accepted",
        "rejected"
    }

    if status and status not in allowed_statuses:
        return jsonify({
            "error": "Invalid application status.",
            "allowed_statuses": sorted(allowed_statuses)
        }), 400

    if not status and notes is None:
        return jsonify({
            "error": "Provide a status or notes to update."
        }), 400

    conn = get_db_connection()

    try:
        cursor = conn.cursor()
        placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"

        cursor.execute(
            f"""
            SELECT id, status, notes
            FROM applications
            WHERE id = {placeholder}
            AND user_id = {placeholder}
            """,
            (application_id, user_id)
        )

        application = cursor.fetchone()

        if not application:
            return jsonify({
                "error": "Application not found."
            }), 404

        new_status = status if status else application[1]
        new_notes = notes if notes is not None else application[2]

        cursor.execute(
            f"""
            UPDATE applications
            SET status = {placeholder},
                notes = {placeholder},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = {placeholder}
            AND user_id = {placeholder}
            """,
            (new_status, new_notes, application_id, user_id)
        )

        conn.commit()

        cursor.execute(
            f"""
            SELECT id, opportunity_id, status, notes, applied_at, updated_at
            FROM applications
            WHERE id = {placeholder}
            AND user_id = {placeholder}
            """,
            (application_id, user_id)
        )

        updated = cursor.fetchone()

        return jsonify({
            "message": "Application updated successfully.",
            "application": {
                "id": updated[0],
                "opportunity_id": updated[1],
                "status": updated[2],
                "notes": updated[3],
                "applied_at": str(updated[4]),
                "updated_at": str(updated[5])
            }
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            "error": "Unable to update application.",
            "details": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
