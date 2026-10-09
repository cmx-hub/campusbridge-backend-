import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from functools import wraps
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


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "Authentication token is required."
            }), 401

        token = auth_header.split(" ", 1)[1].strip()

        if not token:
            return jsonify({
                "error": "Authentication token is required."
            }), 401

        jwt_secret = os.environ.get("JWT_SECRET")

        if not jwt_secret:
            return jsonify({
                "error": "Authentication service is not configured."
            }), 500

        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "Authentication token has expired."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "error": "Invalid authentication token."
            }), 401

        request.current_user_id = int(payload["sub"])
        request.current_user_role = payload["role"]

        return f(*args, **kwargs)

    return decorated


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
        WHERE approval_status = 'approved'
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
        "created_at",
        "last_verified_at"
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
            last_verified_at
        FROM opportunities
        WHERE id = {placeholder} AND approval_status = 'approved'
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
        WHERE id = {placeholder} AND approval_status = 'approved'
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
@token_required
def submit_opportunity():
    if request.current_user_role not in {"organization", "institution"}:
        return jsonify({
            "success": False,
            "error": "Only organization or institution accounts can submit opportunities."
        }), 403
    data = request.get_json(silent=True) or {}

    required = [
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
                request.current_user_id
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
                request.current_user_id
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

    except Exception:
        connection.rollback()
        app.logger.exception("Unable to submit opportunity")
        return jsonify({
            "success": False,
            "error": "Unable to submit opportunity."
        }), 500

    finally:
        cursor.close()
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
    institution = data.get("institution", "").strip()
    field_of_study = data.get("field_of_study", "").strip()
    level = data.get("level", "").strip()
    skills = data.get("skills", "").strip()
    interests = data.get("interests", "").strip()

    if not all([
        name,
        email,
        password,
        institution,
        field_of_study,
        level,
        skills,
        interests
    ]):
        return jsonify({
            "error": "Name, email, password, institution, field of study, level, skills and interests are required."
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

        cursor.execute(
            "SELECT id FROM users WHERE email = %s"
            if os.environ.get("DATABASE_URL")
            else
            "SELECT id FROM users WHERE email = ?",
            (email,)
        )

        user_id = cursor.fetchone()[0]

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
            "message": "Student account and profile created successfully.",
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "role": "student"
            },
            "profile": {
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
            "error": "Unable to create account.",
            "details": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/api/auth/request-password-reset", methods=["POST"])
@limiter.limit("5 per minute")
def request_password_reset():
    # Recovery stays disabled until a secure email delivery provider is configured.
    # Never expose recovery codes in API responses.
    return jsonify({
        "error": "Password recovery is temporarily unavailable. Please contact support."
    }), 503


@app.route("/api/auth/reset-password", methods=["POST"])
@limiter.limit("5 per minute")
def reset_password():
    from werkzeug.security import generate_password_hash

    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    recovery_code = data.get("recovery_code", "").strip()
    new_password = data.get("new_password", "")

    if not email or not recovery_code or not new_password:
        return jsonify({
            "error": "Email, recovery code, and new password are required."
        }), 400

    if not recovery_code.isdigit() or len(recovery_code) != 6:
        return jsonify({
            "error": "Recovery code must be a 6-digit code."
        }), 400

    if len(new_password) < 8:
        return jsonify({
            "error": "New password must be at least 8 characters."
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor()

    placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"
    false_value = False if os.environ.get("DATABASE_URL") else 0

    cursor.execute(
        f"SELECT id FROM users WHERE email = {placeholder}",
        (email,)
    )
    user = cursor.fetchone()

    if not user:
        cursor.close()
        connection.close()
        return jsonify({"error": "Invalid recovery request."}), 400

    user_id = user[0]

    token_hash = hashlib.sha256(
        recovery_code.encode("utf-8")
    ).hexdigest()

    cursor.execute(
        f"""
        SELECT id
        FROM password_reset_tokens
        WHERE user_id = {placeholder}
          AND token_hash = {placeholder}
          AND used = {placeholder}
          AND expires_at > CURRENT_TIMESTAMP
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id, token_hash, false_value)
    )

    token = cursor.fetchone()

    if not token:
        cursor.close()
        connection.close()
        return jsonify({"error": "Invalid or expired recovery code."}), 400

    password_hash = generate_password_hash(new_password)

    cursor.execute(
        f"""
        UPDATE users
        SET password_hash = {placeholder}
        WHERE id = {placeholder}
        """,
        (password_hash, user_id)
    )

    cursor.execute(
        f"""
        UPDATE password_reset_tokens
        SET used = {placeholder}
        WHERE id = {placeholder}
        """,
        (True if os.environ.get("DATABASE_URL") else 1, token[0])
    )

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "message": "Password reset successfully."
    }), 200

@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("5 per minute")
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

        jwt_secret = os.environ.get("JWT_SECRET")

        if not jwt_secret:
            return jsonify({
                "error": "Authentication service is not configured."
            }), 500

        token = jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "exp": datetime.now(timezone.utc) + timedelta(hours=2)
            },
            jwt_secret,
            algorithm="HS256"
        )

        return jsonify({
            "message": "Login successful.",
            "token": token,
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
@token_required
def get_student_profile(user_id):
    if request.current_user_id != user_id:
        return jsonify({
            "error": "You are not authorized to view this profile."
        }), 403
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
@token_required
def get_student_applications(user_id):
    if request.current_user_id != user_id:
        return jsonify({
            "error": "You are not authorized to view these applications."
        }), 403

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





@app.route("/api/students/<int:user_id>/saved-opportunities", methods=["GET"])
@token_required
def get_saved_opportunities(user_id):
    if request.current_user_id != user_id:
        return jsonify({"error": "You are not authorized to view these saved opportunities."}), 403
    if request.current_user_role != "student":
        return jsonify({"error": "Only student accounts can access saved opportunities."}), 403

    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"
        cursor.execute(
            f"SELECT id, title, category, organization, description, source_url, location, deadline, status "
            f"FROM opportunities WHERE id IN ("
            f"SELECT opportunity_id FROM saved_opportunities WHERE user_id = {placeholder}) "
            f"ORDER BY title",
            (user_id,)
        )
        rows = cursor.fetchall()
        items = [{
            "id": row[0],
            "title": row[1],
            "category": row[2],
            "organization": row[3],
            "description": row[4],
            "source_url": row[5],
            "location": row[6],
            "deadline": row[7],
            "status": row[8]
        } for row in rows]
        return jsonify({"user_id": user_id, "saved_opportunities": items, "count": len(items)}), 200
    except Exception:
        app.logger.exception("Unable to retrieve saved opportunities")
        return jsonify({"error": "Unable to retrieve saved opportunities."}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.route("/api/students/<int:user_id>/saved-opportunities", methods=["POST"])
@token_required
def save_student_opportunity(user_id):
    if request.current_user_id != user_id:
        return jsonify({"error": "You are not authorized to save opportunities for this account."}), 403
    if request.current_user_role != "student":
        return jsonify({"error": "Only student accounts can save opportunities."}), 403

    data = request.get_json(silent=True) or {}
    opportunity_id = data.get("opportunity_id")
    if isinstance(opportunity_id, bool) or not isinstance(opportunity_id, int) or opportunity_id < 1:
        return jsonify({"error": "A valid integer opportunity_id is required."}), 400

    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"
        cursor.execute(
            f"SELECT id FROM opportunities WHERE id = {placeholder}",
            (opportunity_id,)
        )
        if not cursor.fetchone():
            return jsonify({"error": "Opportunity not found."}), 404

        cursor.execute(
            f"INSERT INTO saved_opportunities (user_id, opportunity_id) "
            f"VALUES ({placeholder}, {placeholder}) "
            f"ON CONFLICT (user_id, opportunity_id) DO NOTHING",
            (user_id, opportunity_id)
        )
        conn.commit()
        return jsonify({"message": "Opportunity saved.", "opportunity_id": opportunity_id}), 200
    except Exception:
        conn.rollback()
        app.logger.exception("Unable to save opportunity")
        return jsonify({"error": "Unable to save opportunity."}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.route("/api/students/<int:user_id>/saved-opportunities/<int:opportunity_id>", methods=["DELETE"])
@token_required
def unsave_student_opportunity(user_id, opportunity_id):
    if request.current_user_id != user_id:
        return jsonify({"error": "You are not authorized to modify these saved opportunities."}), 403
    if request.current_user_role != "student":
        return jsonify({"error": "Only student accounts can remove saved opportunities."}), 403

    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        placeholder = "%s" if os.environ.get("DATABASE_URL") else "?"
        cursor.execute(
            f"DELETE FROM saved_opportunities WHERE user_id = {placeholder} "
            f"AND opportunity_id = {placeholder}",
            (user_id, opportunity_id)
        )
        conn.commit()
        return jsonify({"message": "Saved opportunity removed.", "opportunity_id": opportunity_id}), 200
    except Exception:
        conn.rollback()
        app.logger.exception("Unable to remove saved opportunity")
        return jsonify({"error": "Unable to remove saved opportunity."}), 500
    finally:
        if cursor:
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
