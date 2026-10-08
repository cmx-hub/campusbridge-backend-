import os
import sqlite3
import psycopg2


DATABASE = "campusbridge.db"


OPPORTUNITIES = [
    (
        "205 Algerian Government Scholarships",
        "Scholarship",
        "MINESUP Cameroon",
        "Scholarship opportunities announced for eligible Cameroonian students.",
        "https://www.minesup.gov.cm/index.php/2026/08/13/",
        "Algeria",
        "See official announcement",
        "active"
    ),
    (
        "150 Indian University Scholarships",
        "Scholarship",
        "MINESUP Cameroon / IAESTE",
        "Scholarship opportunities involving Indian universities.",
        "https://www.minesup.gov.cm/index.php/2026/06/05/communique-de-presse-press-release-3/",
        "India",
        "See official announcement",
        "active"
    ),
    (
        "Brazil Scholarships — Master's & PhD",
        "Scholarship",
        "MINESUP Cameroon",
        "Scholarship opportunities for Master's and PhD studies in Brazil.",
        "https://www.minesup.gov.cm/index.php/page/4/?lang=en",
        "Brazil",
        "See official announcement",
        "active"
    ),
    (
        "Mastercard Foundation Scholars Program — Cambridge",
        "Scholarship",
        "Mastercard Foundation / University of Cambridge",
        "Scholarship opportunities through the Mastercard Foundation Scholars Program at Cambridge.",
        "https://www.mastercardfoundation.fund.cam.ac.uk/news/2027-applications-now-open",
        "United Kingdom",
        "See official announcement",
        "active"
    ),
    (
        "Mastercard Foundation Scholars Program — Partner Institutions",
        "Scholarship",
        "Mastercard Foundation",
        "Scholarship opportunities available through participating partner institutions.",
        "https://mastercardfdn.org/en/what-we-do/our-programs/mastercard-foundation-scholars-program/where-to-apply/",
        "Multiple countries",
        "See official announcement",
        "active"
    ),
    (
        "CAMTEL Academic & Professional Internships",
        "Internship",
        "CAMTEL",
        "Academic and professional internship information.",
        "https://omdes.org/metiers/stages/19/",
        "Cameroon",
        "Archived",
        "archived"
    ),
    (
        "SOPECAM Academic Internships",
        "Internship",
        "SOPECAM",
        "Academic internship information.",
        "https://omdes.org/metiers/stages/23/",
        "Cameroon",
        "Archived",
        "archived"
    ),
    (
        "CCAA Academic & Professional Internships",
        "Internship",
        "CCAA",
        "Academic and professional internship information.",
        "https://omdes.org/metiers/stages/21/",
        "Cameroon",
        "Archived",
        "archived"
    ),
    (
        "237HackFest 2026",
        "Competition",
        "237HackFest",
        "Cybersecurity hackathon and competition taking place in Cameroon.",
        "https://237hackfest.com/",
        "Douala, Cameroon",
        "5–6 November 2026",
        "active"
    )
]


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)

    return sqlite3.connect("campusbridge.db")

def init_db():
    database_url = os.environ.get("DATABASE_URL")

    connection = get_db_connection()
    cursor = connection.cursor()

    if database_url:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                role TEXT NOT NULL CHECK(role IN ('student', 'organization', 'institution', 'admin')),
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_status TEXT DEFAULT 'unverified',
                verification_risk_score INTEGER DEFAULT 0,
                last_verified_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                institution TEXT,
                field_of_study TEXT,
                level TEXT,
                skills TEXT,
                interests TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                organization_name TEXT NOT NULL,
                website TEXT,
                description TEXT,
                verification_status TEXT NOT NULL DEFAULT 'pending',
                verified_at TIMESTAMP,
                verified_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'inactive',
                amount INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'XAF',
                starts_at TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organization_services (
                id SERIAL PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                service_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                amount INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'XAF',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organization_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_records (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                organization TEXT,
                risk_level TEXT,
                risk_score INTEGER,
                source_verified BOOLEAN,
                findings TEXT,
                risk_evidence TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_status TEXT DEFAULT 'unverified',
                verification_risk_score INTEGER DEFAULT 0,
                last_verified_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                organization TEXT,
                description TEXT,
                source_url TEXT NOT NULL,
                location TEXT,
                deadline TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_status TEXT DEFAULT 'unverified',
                verification_risk_score INTEGER DEFAULT 0,
                last_verified_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                opportunity_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'submitted',
                notes TEXT DEFAULT '',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (opportunity_id) REFERENCES opportunities(id),
                UNIQUE (user_id, opportunity_id)
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM opportunities")
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.executemany("""
                INSERT INTO opportunities (
                    title, category, organization, description,
                    source_url, location, deadline, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, OPPORTUNITIES)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                organization TEXT,
                risk_level TEXT,
                risk_score INTEGER,
                source_verified INTEGER,
                findings TEXT,
                risk_evidence TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_status TEXT DEFAULT 'unverified',
                verification_risk_score INTEGER DEFAULT 0,
                last_verified_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                organization TEXT,
                description TEXT,
                source_url TEXT NOT NULL,
                location TEXT,
                deadline TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_status TEXT DEFAULT 'unverified',
                verification_risk_score INTEGER DEFAULT 0,
                last_verified_at TIMESTAMP
            )
        """)

    connection.commit()
    cursor.close()
    connection.close()


if __name__ == "__main__":
    init_db()
    print("CampusBridge database initialized successfully.")


    init_business_tables()
def save_verification_record(result):
    import json

    connection = get_db_connection()
    cursor = connection.cursor()

    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        cursor.execute("""
            INSERT INTO verification_records (
                url,
                organization,
                risk_level,
                risk_score,
                source_verified,
                findings,
                risk_evidence
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            result.get("url"),
            result.get("organization"),
            result.get("risk_level"),
            result.get("risk_score"),
            result.get("source_verified"),
            json.dumps(result.get("findings", [])),
            json.dumps(result.get("risk_evidence", []))
        ))

    else:
        cursor.execute("""
            INSERT INTO verification_records (
                url,
                organization,
                risk_level,
                risk_score,
                source_verified,
                findings,
                risk_evidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            result.get("url"),
            result.get("organization"),
            result.get("risk_level"),
            result.get("risk_score"),
            result.get("source_verified"),
            json.dumps(result.get("findings", [])),
            json.dumps(result.get("risk_evidence", []))
        ))

    connection.commit()
    cursor.close()
    connection.close()
