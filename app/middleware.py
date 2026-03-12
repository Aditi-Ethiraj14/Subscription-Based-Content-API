from functools import wraps
from flask import request, jsonify, g
from .auth import decode_token
from .database import get_db
from datetime import datetime, timezone


def _get_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.args.get("token", "")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token()
        if not token:
            return jsonify({"error": "Authentication required", "code": "MISSING_TOKEN"}), 401
        try:
            payload = decode_token(token)
        except ValueError as e:
            return jsonify({"error": str(e), "code": "INVALID_TOKEN"}), 401

        # Refresh user from DB (handles role changes mid-session)
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (payload["sub"],)).fetchone()
        db.close()
        if not user:
            return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 401

        g.user = dict(user)
        return f(*args, **kwargs)
    return decorated


def premium_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token()
        if not token:
            return jsonify({"error": "Authentication required", "code": "MISSING_TOKEN"}), 401
        try:
            payload = decode_token(token)
        except ValueError as e:
            return jsonify({"error": str(e), "code": "INVALID_TOKEN"}), 401

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (payload["sub"],)).fetchone()
        db.close()
        if not user:
            return jsonify({"error": "User not found"}), 401

        g.user = dict(user)

        if user["role"] not in ("premium", "admin"):
            return jsonify({
                "error": "Premium subscription required",
                "code":  "SUBSCRIPTION_REQUIRED",
                "upgrade_url": "/api/subscriptions/upgrade"
            }), 403

        # Check expiry
        if user["expires_at"]:
            exp = datetime.fromisoformat(user["expires_at"])
            if exp < datetime.now(timezone.utc).replace(tzinfo=None):
                return jsonify({
                    "error": "Your subscription has expired",
                    "code":  "SUBSCRIPTION_EXPIRED",
                    "upgrade_url": "/api/subscriptions/upgrade"
                }), 403

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token()
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        try:
            payload = decode_token(token)
        except ValueError as e:
            return jsonify({"error": str(e)}), 401

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id=?", (payload["sub"],)).fetchone()
        db.close()
        if not user:
            return jsonify({"error": "User not found"}), 401
        if user["role"] != "admin":
            return jsonify({"error": "Admin access required", "code": "FORBIDDEN"}), 403

        g.user = dict(user)
        return f(*args, **kwargs)
    return decorated
