"""
Run once to create an admin user:
    python seed_admin.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import init_db, get_db
from app.auth import hash_password

def seed():
    init_db()
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if existing:
        print("Admin user already exists.")
        db.close()
        return

    db.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
        ("admin", "admin@example.com", hash_password("admin123"), "admin"),
    )
    db.commit()
    db.close()
    print("✅  Admin created: username=admin  password=admin123")
    print("    Change the password after first login!")

if __name__ == "__main__":
    seed()
