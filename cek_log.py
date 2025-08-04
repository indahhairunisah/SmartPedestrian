import sqlite3

DB_NAME = "instance/database.db"

def get_all_logs():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM detector_log ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows
