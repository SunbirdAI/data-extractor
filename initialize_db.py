import sqlite3
import json
import os
from config import DB_PATH, METADATA_FILE, PDF_DIR


def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS items (
        key TEXT PRIMARY KEY,
        title TEXT,
        abstract TEXT,
        authors TEXT,
        year INTEGER,
        doi TEXT
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS attachments (
        key TEXT PRIMARY KEY,
        parent_key TEXT,
        content BLOB,
        FOREIGN KEY (parent_key) REFERENCES items (key)
    )
    """
    )

    conn.commit()
    conn.close()


def populate_database():
    if not os.path.exists(METADATA_FILE):
        print(f"Metadata file not found: {METADATA_FILE}")
        return

    with open(METADATA_FILE, "r") as f:
        metadata = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for item_key, item_data in metadata.items():
        metadata = item_data["metadata"]
        cursor.execute(
            """
        INSERT OR REPLACE INTO items (key, title, abstract, authors, year, doi)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                item_key,
                metadata["title"],
                metadata["abstract"],
                metadata["authors"],
                metadata["year"],
                metadata["doi"],
            ),
        )

        pdf_path = item_data.get("pdf_path")
        if pdf_path:
            full_pdf_path = os.path.join(PDF_DIR, os.path.basename(pdf_path))
            if os.path.exists(full_pdf_path):
                with open(full_pdf_path, "rb") as pdf_file:
                    pdf_content = pdf_file.read()
                    cursor.execute(
                        """
                    INSERT OR REPLACE INTO attachments (key, parent_key, content)
                    VALUES (?, ?, ?)
                    """,
                        (os.path.basename(pdf_path), item_key, pdf_content),
                    )
            else:
                print(f"PDF file not found: {full_pdf_path}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_database()
    populate_database()
    print("Database initialized and populated.")
