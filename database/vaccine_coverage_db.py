import sqlite3
from typing import List, Dict, Any


class VaccineCoverageDB:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_all_items(self) -> List[Dict[str, Any]]:
        cursor = self.conn.execute("SELECT * FROM items")
        return [dict(row) for row in cursor.fetchall()]

    def get_item_by_key(self, key: str) -> Dict[str, Any]:
        cursor = self.conn.execute("SELECT * FROM items WHERE key = ?", (key,))
        return dict(cursor.fetchone())

    def get_attachments_for_item(self, item_key: str) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM attachments WHERE parent_key = ?", (item_key,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_pdf_content(self, attachment_key: str) -> bytes:
        cursor = self.conn.execute(
            "SELECT content FROM attachments WHERE key = ?", (attachment_key,)
        )
        result = cursor.fetchone()
        return result["content"] if result else None

    def save_pdf_to_file(self, attachment_key: str, output_path: str) -> bool:
        pdf_content = self.get_pdf_content(attachment_key)
        if pdf_content:
            try:
                with open(output_path, "wb") as f:
                    f.write(pdf_content)
                return True
            except Exception as e:
                print(f"Error saving PDF: {str(e)}")
                return False
        else:
            print(f"No PDF content found for attachment key: {attachment_key}")
            return False

    def close(self):
        self.conn.close()
