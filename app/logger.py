from flask import request
from .database import get_db


def log_access(user_id, content_id, endpoint, status_code):
    db = get_db()
    db.execute(
        """INSERT INTO access_logs
               (user_id, content_id, endpoint, method, status_code, ip_address, user_agent)
           VALUES (?,?,?,?,?,?,?)""",
        (
            user_id,
            content_id,
            endpoint,
            request.method,
            status_code,
            request.remote_addr,
            request.headers.get("User-Agent", ""),
        ),
    )
    db.commit()
    db.close()
