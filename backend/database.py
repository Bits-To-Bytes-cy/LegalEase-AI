import sqlite3
import os
from backend.config import Config
from backend.utils import safe_log

def get_db_connection():
    db_path = Config.DATABASE_URI.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    safe_log("info", "Initializing database...")
    db_path = Config.DATABASE_URI.replace("sqlite:///", "")
    directory = os.path.dirname(db_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    conn = get_db_connection()
    # Create tables
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            status TEXT NOT NULL,
            document_type TEXT,
            jurisdiction_country TEXT,
            jurisdiction_region TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            page_number INTEGER,
            clause_number TEXT,
            clause_title TEXT,
            content TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS risk_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            clause_number TEXT,
            risk_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            evidence TEXT,
            page_number INTEGER,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()
    safe_log("info", "Database initialized successfully.")
