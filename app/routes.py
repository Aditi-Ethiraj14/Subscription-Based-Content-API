import uuid
import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g, make_response

from .database import get_db
from .auth import hash_password, verify_password, create_token
from .middleware import login_required, premium_required, admin_required
from .logger import log_access

# ── Blueprints ────────────────────────────────────────────────────────────────
auth_bp    = Blueprint("auth",    __name__, url_prefix="/api/auth")
content_bp = Blueprint("content", __name__, url_prefix="/api/content")
sub_bp     = Blueprint("subs",    __name__, url_prefix="/api/subscriptions")
admin_bp   = Blueprint("admin",   __name__, url_prefix="/api/admin")


# ═════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email    = (data.get("email")    or "").strip().lower()
    password = data.get("password", "")

    errors = {}
    if not username or len(username) < 3:
        errors["username"] = "Must be at least 3 characters"
    if not email or "@" not in email:
        errors["email"] = "Invalid email address"
    if not password or len(password) < 6:
        errors["password"] = "Must be at least 6 characters"
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
            (username, email, hash_password(password)),
        )
        db.commit()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        token = create_token(user["id"], user["username"], user["role"])
        return jsonify({
            "message": "Registration successful",
            "token": token,
            "user": _user_dict(user),
        }), 201
    except Exception as e:
        if "UNIQUE" in str(e):
            field = "username" if "username" in str(e) else "email"
            return jsonify({"error": f"{field} already taken"}), 409
        return jsonify({"error": "Registration failed"}), 500
    finally:
        db.close()


@auth_bp.post("/login")
def login():
    data     = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password required"}), 422

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    db.close()

    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(user["id"], user["username"], user["role"])
    return jsonify({"message": "Login successful", "token": token, "user": _user_dict(user)})


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({"user": _user_dict(g.user)})


# ═════════════════════════════════════════════════════════════════════════════
# CONTENT ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@content_bp.get("/")
@login_required
def list_content():
    db   = get_db()
    role = g.user["role"]
    if role in ("premium", "admin"):
        rows = db.execute("SELECT id,title,tier,created_at FROM content ORDER BY id").fetchall()
    else:
        rows = db.execute(
            "SELECT id,title,tier,created_at FROM content WHERE tier='free' ORDER BY id"
        ).fetchall()
    db.close()
    return jsonify({"content": [dict(r) for r in rows], "count": len(rows)})


@content_bp.get("/free/<int:content_id>")
@login_required
def get_free_content(content_id):
    db  = get_db()
    row = db.execute(
        "SELECT * FROM content WHERE id=? AND tier='free'", (content_id,)
    ).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "Content not found"}), 404
    log_access(g.user["id"], content_id, request.path, 200)
    return jsonify({"content": dict(row)})


@content_bp.get("/premium/<int:content_id>")
@premium_required
def get_premium_content(content_id):
    db  = get_db()
    row = db.execute(
        "SELECT * FROM content WHERE id=? AND tier='premium'", (content_id,)
    ).fetchone()
    db.close()
    if not row:
        log_access(g.user["id"], content_id, request.path, 404)
        return jsonify({"error": "Content not found"}), 404
    log_access(g.user["id"], content_id, request.path, 200)
    return jsonify({"content": dict(row)})


@content_bp.post("/")
@admin_required
def create_content():
    data  = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    body  = (data.get("body")  or "").strip()
    tier  = data.get("tier", "free")

    if not title or not body:
        return jsonify({"error": "title and body are required"}), 422
    if tier not in ("free", "premium"):
        return jsonify({"error": "tier must be 'free' or 'premium'"}), 422

    db = get_db()
    cur = db.execute("INSERT INTO content (title,body,tier) VALUES (?,?,?)", (title, body, tier))
    db.commit()
    row = db.execute("SELECT * FROM content WHERE id=?", (cur.lastrowid,)).fetchone()
    db.close()
    return jsonify({"message": "Content created", "content": dict(row)}), 201


# ═════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@sub_bp.get("/status")
@login_required
def subscription_status():
    user = g.user
    exp  = user.get("expires_at")
    active = False
    if user["role"] in ("premium", "admin") and exp:
        active = datetime.fromisoformat(exp) > datetime.utcnow()
    return jsonify({
        "user_id":      user["id"],
        "username":     user["username"],
        "role":         user["role"],
        "subscribed_at":user["subscribed_at"],
        "expires_at":   exp,
        "is_active":    active,
    })


@sub_bp.post("/upgrade")
@login_required
def upgrade():
    data = request.get_json(silent=True) or {}

    # Simulate payment — accept any non-empty card number
    card = (data.get("card_number") or "").strip().replace(" ", "")
    if not card or len(card) < 12:
        return jsonify({"error": "Valid card_number is required (min 12 digits)"}), 422

    plan_months = int(data.get("months", 1))
    if plan_months not in (1, 3, 6, 12):
        return jsonify({"error": "months must be 1, 3, 6, or 12"}), 422

    amount_map = {1: 9.99, 3: 26.99, 6: 49.99, 12: 89.99}
    amount     = amount_map[plan_months]
    txn_ref    = str(uuid.uuid4())
    now        = datetime.utcnow()
    expires    = now + timedelta(days=30 * plan_months)

    db = get_db()
    # Record payment
    db.execute(
        "INSERT INTO payments (user_id,amount,status,transaction_ref) VALUES (?,?,?,?)",
        (g.user["id"], amount, "success", txn_ref),
    )
    # Upgrade user
    db.execute(
        """UPDATE users
              SET role='premium', subscribed_at=?, expires_at=?
            WHERE id=?""",
        (now.isoformat(), expires.isoformat(), g.user["id"]),
    )
    db.commit()
    db.close()

    return jsonify({
        "message":         "Subscription upgraded successfully",
        "plan_months":     plan_months,
        "amount_charged":  amount,
        "currency":        "USD",
        "transaction_ref": txn_ref,
        "subscribed_at":   now.isoformat(),
        "expires_at":      expires.isoformat(),
        "role":            "premium",
    }), 200


@sub_bp.post("/cancel")
@login_required
def cancel():
    db = get_db()
    db.execute(
        "UPDATE users SET role='free', subscribed_at=NULL, expires_at=NULL WHERE id=?",
        (g.user["id"],),
    )
    db.commit()
    db.close()
    return jsonify({"message": "Subscription cancelled. You now have free access."})


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@admin_bp.get("/logs")
@admin_required
def view_logs():
    limit  = min(int(request.args.get("limit", 50)), 500)
    offset = int(request.args.get("offset", 0))
    db     = get_db()
    rows   = db.execute(
        """SELECT al.*, u.username, c.title as content_title
             FROM access_logs al
        LEFT JOIN users   u ON al.user_id    = u.id
        LEFT JOIN content c ON al.content_id = c.id
            ORDER BY al.accessed_at DESC
            LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()
    total = db.execute("SELECT COUNT(*) FROM access_logs").fetchone()[0]
    db.close()
    return jsonify({"logs": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset})


@admin_bp.get("/logs/export")
@admin_required
def export_logs_csv():
    db   = get_db()
    rows = db.execute(
        """SELECT al.id, u.username, c.title as content_title,
                  al.endpoint, al.method, al.status_code,
                  al.ip_address, al.user_agent, al.accessed_at
             FROM access_logs al
        LEFT JOIN users   u ON al.user_id    = u.id
        LEFT JOIN content c ON al.content_id = c.id
            ORDER BY al.accessed_at DESC"""
    ).fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","username","content_title","endpoint","method",
                     "status_code","ip_address","user_agent","accessed_at"])
    for r in rows:
        writer.writerow(list(r))

    resp = make_response(output.getvalue())
    resp.headers["Content-Type"]        = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=access_logs.csv"
    return resp


@admin_bp.get("/users")
@admin_required
def list_users():
    db   = get_db()
    rows = db.execute(
        "SELECT id,username,email,role,subscribed_at,expires_at,created_at FROM users ORDER BY id"
    ).fetchall()
    db.close()
    return jsonify({"users": [dict(r) for r in rows], "count": len(rows)})


@admin_bp.get("/report/monthly")
@admin_required
def monthly_report():
    db   = get_db()
    rows = db.execute(
        """SELECT strftime('%Y-%m', accessed_at) as month,
                  COUNT(*) as total_accesses,
                  COUNT(DISTINCT user_id) as unique_users,
                  SUM(CASE WHEN status_code=200 THEN 1 ELSE 0 END) as successful,
                  SUM(CASE WHEN status_code!=200 THEN 1 ELSE 0 END) as failed
             FROM access_logs
            GROUP BY month
            ORDER BY month DESC"""
    ).fetchall()
    db.close()

    # CSV if requested
    if request.args.get("format") == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["month","total_accesses","unique_users","successful","failed"])
        for r in rows:
            writer.writerow(list(r))
        resp = make_response(output.getvalue())
        resp.headers["Content-Type"]        = "text/csv"
        resp.headers["Content-Disposition"] = "attachment; filename=monthly_report.csv"
        return resp

    return jsonify({"report": [dict(r) for r in rows]})


@admin_bp.post("/users/<int:user_id>/role")
@admin_required
def set_role(user_id):
    data = request.get_json(silent=True) or {}
    role = data.get("role", "")
    if role not in ("free", "premium", "admin"):
        return jsonify({"error": "role must be free, premium, or admin"}), 422
    db = get_db()
    db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    db.commit()
    user = db.execute(
        "SELECT id,username,email,role FROM users WHERE id=?", (user_id,)
    ).fetchone()
    db.close()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"message": f"Role updated to {role}", "user": dict(user)})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_dict(user):
    u = dict(user) if not isinstance(user, dict) else user
    u.pop("password_hash", None)
    return u
