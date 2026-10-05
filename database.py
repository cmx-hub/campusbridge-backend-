import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE = "campusbridge.db"


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    # Production: PostgreSQL on Render
    if database_url:
        connection = psycopg2.connect(database_url)
        return connection

    # Local development: SQLite
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    database_url = os.environ.get("DATABASE_URL")

    # PostgreSQL database on Render
    if database_url:
        connection = get_db_connection()

        cursor = connection.cursor()

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

        connection.commit()
        cursor.close()
        connection.close()

        return

    # SQLite database for local development
    connection = get_db_connection()

    connection.execute("""
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
    connection.close()


if __name__ == "__main__":
    init_db()
    print("CampusBridge database initialized successfully.")
