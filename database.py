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

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    database_url = os.environ.get("DATABASE_URL")

    connection = get_db_connection()
    cursor = connection.cursor()

    if database_url:
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM opportunities")
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.executemany("""
                INSERT INTO opportunities (
                    title,
                    category,
                    organization,
                    description,
                    source_url,
                    location,
                    deadline,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, OPPORTUNITIES)

    else:
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    connection.commit()
    cursor.close()
    connection.close()


if __name__ == "__main__":
    init_db()
    print("CampusBridge database initialized successfully.")
