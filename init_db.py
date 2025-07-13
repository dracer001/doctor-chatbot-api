import sqlite3

with sqlite3.connect("chat_history.db") as conn:
    with open("schema.sql") as f:
        conn.executescript(f.read())

print("✅ chat_history.db initialized.")
