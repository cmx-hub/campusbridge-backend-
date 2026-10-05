import os
from flask import Flask, jsonify
from flask_cors import CORS
from database import get_db_connection, init_db

app = Flask(__name__)

CORS(app)

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


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
