"""
reset_db.py — Clears published_signals so the bot reprocesses recent messages.
Run this when: bot missed signals, DB is stale, or after major code changes.

Usage:  python reset_db.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "aurumflow.db")

if not os.path.exists(DB_PATH):
    print("DB not found — nothing to reset.")
    exit()

with sqlite3.connect(DB_PATH) as conn:
    count = conn.execute("SELECT COUNT(*) FROM published_signals").fetchone()[0]
    conn.execute("DELETE FROM published_signals")
    conn.commit()
    print(f"✅ Cleared {count} entries from published_signals.")
    print("   Active signals (result tracker) kept intact.")
    print()
    print("Now run:  python main.py")
