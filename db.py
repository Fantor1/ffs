import sqlite3

def get_connection():
    return sqlite3.connect("bot_database.db")

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Create a table called todolist with the required columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todolist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT NOT NULL,
            is_done BOOLEAN DEFAULT 0,
            week INTEGER,
            dp BOOLEAN DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
# Initialize the database when this module is imported
init_db()
