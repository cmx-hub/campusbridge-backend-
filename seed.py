from database import get_db_connection


opportunities = [
    {
        "title": "205 Algerian Government Scholarships",
        "category": "Scholarship",
        "organization": "MINESUP Cameroon",
        "description": "Scholarship opportunities announced for eligible Cameroonian students.",
        "source_url": "https://www.minesup.gov.cm/index.php/2026/08/13/",
        "location": "Algeria",
        "deadline": "See official announcement",
        "status": "active"
    },
    {
        "title": "150 Indian University Scholarships",
        "category": "Scholarship",
        "organization": "MINESUP Cameroon / IAESTE",
        "description": "Scholarship opportunities involving Indian universities.",
        "source_url": "https://www.minesup.gov.cm/index.php/2026/06/05/communique-de-presse-press-release-3/",
        "location": "India",
        "deadline": "See official announcement",
        "status": "active"
    },
    {
        "title": "Brazil Scholarships — Master's & PhD",
        "category": "Scholarship",
        "organization": "MINESUP Cameroon",
        "description": "Scholarship opportunities for Master's and PhD studies in Brazil.",
        "source_url": "https://www.minesup.gov.cm/index.php/page/4/?lang=en",
        "location": "Brazil",
        "deadline": "See official announcement",
        "status": "active"
    },
    {
        "title": "Mastercard Foundation Scholars Program — Cambridge",
        "category": "Scholarship",
        "organization": "Mastercard Foundation / University of Cambridge",
        "description": "Scholarship opportunities through the Mastercard Foundation Scholars Program at Cambridge.",
        "source_url": "https://www.mastercardfoundation.fund.cam.ac.uk/news/2027-applications-now-open",
        "location": "United Kingdom",
        "deadline": "See official announcement",
        "status": "active"
    },
    {
        "title": "Mastercard Foundation Scholars Program — Partner Institutions",
        "category": "Scholarship",
        "organization": "Mastercard Foundation",
        "description": "Scholarship opportunities available through participating partner institutions.",
        "source_url": "https://mastercardfdn.org/en/what-we-do/our-programs/mastercard-foundation-scholars-program/where-to-apply/",
        "location": "Multiple countries",
        "deadline": "See official announcement",
        "status": "active"
    },
    {
        "title": "CAMTEL Academic & Professional Internships",
        "category": "Internship",
        "organization": "CAMTEL",
        "description": "Academic and professional internship information.",
        "source_url": "https://omdes.org/metiers/stages/19/",
        "location": "Cameroon",
        "deadline": "Archived",
        "status": "archived"
    },
    {
        "title": "SOPECAM Academic Internships",
        "category": "Internship",
        "organization": "SOPECAM",
        "description": "Academic internship information.",
        "source_url": "https://omdes.org/metiers/stages/23/",
        "location": "Cameroon",
        "deadline": "Archived",
        "status": "archived"
    },
    {
        "title": "CCAA Academic & Professional Internships",
        "category": "Internship",
        "organization": "CCAA",
        "description": "Academic and professional internship information.",
        "source_url": "https://omdes.org/metiers/stages/21/",
        "location": "Cameroon",
        "deadline": "Archived",
        "status": "archived"
    },
    {
        "title": "237HackFest 2026",
        "category": "Competition",
        "organization": "237HackFest",
        "description": "Cybersecurity hackathon and competition taking place in Cameroon.",
        "source_url": "https://237hackfest.com/",
        "location": "Douala, Cameroon",
        "deadline": "5–6 November 2026",
        "status": "active"
    }
]


connection = get_db_connection()

for opportunity in opportunities:
    connection.execute(
        """
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            opportunity["title"],
            opportunity["category"],
            opportunity["organization"],
            opportunity["description"],
            opportunity["source_url"],
            opportunity["location"],
            opportunity["deadline"],
            opportunity["status"]
        )
    )

connection.commit()
connection.close()

print(f"{len(opportunities)} opportunities added successfully.")
