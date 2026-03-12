# Subscription-Based Content API

A production-ready REST API built with **Python + Flask + PostGresSQLite** that enforces subscription-based access control, simulates payment processing, and provides full activity logging.

---

## Features

| Feature | Details |
|---|---|
| User roles | `free`, `premium`, `admin` |
| JWT authentication | HS256 tokens, 24 h expiry |
| Protected content | Middleware blocks free users from premium endpoints |
| Subscription upgrade | Simulated payment, 1 / 3 / 6 / 12-month plans |
| Subscription expiry | Premium access expires after chosen plan duration |
| Activity logging | Every access logged with IP, user-agent, status code |
| Admin dashboard | View logs, list users, change roles |
| CSV export | Monthly usage reports & raw log export |

---

## Quick Start

### 1. Prerequisites

- Python 3.9+
- pip

### 2. Install dependencies

```bash
cd subscription_api
pip install -r requirements.txt
```

### 3. Create the admin user (optional but recommended)

```bash
python seed_admin.py
# Admin credentials: admin / admin123
```

### 4. Run the server

```bash
python main.py
# Server starts at http://127.0.0.1:5000
```

### 5. Run tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-...` | JWT signing key — **change in production** |
| `DB_PATH` | `subscription_api.db` | SQLite database file path |

---

## API Reference

### Base URL: `http://127.0.0.1:5000`

All protected endpoints require:
```
Authorization: Bearer <token>
```

---

### 🔐 Auth

#### Register
```
POST /api/auth/register
Content-Type: application/json

{
  "username": "alice",
  "email":    "alice@example.com",
  "password": "secret123"
}
```

**Response 201:**
```json
{
  "message": "Registration successful",
  "token": "<jwt>",
  "user": { "id": 1, "username": "alice", "role": "free", ... }
}
```

---

#### Login
```
POST /api/auth/login
Content-Type: application/json

{
  "username": "alice",
  "password": "secret123"
}
```

**Response 200:**
```json
{ "token": "<jwt>", "user": { ... } }
```

---

#### Get Current User
```
GET /api/auth/me
Authorization: Bearer <token>
```

---

### 📄 Content

#### List Available Content
```
GET /api/content/
Authorization: Bearer <token>
```
Free users see only free content. Premium/admin see all.

---

#### Get Free Content
```
GET /api/content/free/{id}
Authorization: Bearer <token>
```

---

#### Get Premium Content ⭐
```
GET /api/content/premium/{id}
Authorization: Bearer <token>
```
**403** if user is not premium:
```json
{
  "error": "Premium subscription required",
  "code": "SUBSCRIPTION_REQUIRED",
  "upgrade_url": "/api/subscriptions/upgrade"
}
```

---

#### Create Content (admin only)
```
POST /api/content/
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "title": "My Article",
  "body":  "Full content here...",
  "tier":  "premium"
}
```

---

### 💳 Subscriptions

#### Check Status
```
GET /api/subscriptions/status
Authorization: Bearer <token>
```
```json
{
  "role": "premium",
  "subscribed_at": "2026-03-01T10:00:00",
  "expires_at":    "2026-04-01T10:00:00",
  "is_active": true
}
```

---

#### Upgrade to Premium
```
POST /api/subscriptions/upgrade
Authorization: Bearer <token>
Content-Type: application/json

{
  "card_number": "4111111111111111",
  "months": 1
}
```

**months options:** `1` ($9.99) · `3` ($26.99) · `6` ($49.99) · `12` ($89.99)

**Response 200:**
```json
{
  "message": "Subscription upgraded successfully",
  "plan_months": 1,
  "amount_charged": 9.99,
  "currency": "USD",
  "transaction_ref": "uuid-here",
  "expires_at": "2026-04-12T...",
  "role": "premium"
}
```

---

#### Cancel Subscription
```
POST /api/subscriptions/cancel
Authorization: Bearer <token>
```

---

### 🛡️ Admin

#### List All Users
```
GET /api/admin/users
Authorization: Bearer <admin-token>
```

#### View Access Logs
```
GET /api/admin/logs?limit=50&offset=0
Authorization: Bearer <admin-token>
```

#### Export Logs as CSV
```
GET /api/admin/logs/export
Authorization: Bearer <admin-token>
```

#### Monthly Usage Report
```
GET /api/admin/report/monthly
GET /api/admin/report/monthly?format=csv
Authorization: Bearer <admin-token>
```

#### Change User Role
```
POST /api/admin/users/{id}/role
Authorization: Bearer <admin-token>
Content-Type: application/json

{ "role": "premium" }
```

---

## HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 401 | Missing / invalid / expired token |
| 403 | Forbidden (no subscription or not admin) |
| 404 | Resource not found |
| 409 | Conflict (duplicate username/email) |
| 422 | Validation error |
| 500 | Server error |

---

## Project Structure

```
subscription_api/
├── main.py              # Entry point
├── seed_admin.py        # Create admin user
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   ├── factory.py       # Flask app factory
│   ├── database.py      # SQLite init & connection
│   ├── auth.py          # Password hashing & JWT
│   ├── middleware.py    # Auth / premium / admin decorators
│   ├── logger.py        # Access log helper
│   └── routes.py        # All blueprints & route handlers
└── tests/
    └── test_api.py      # pytest test suite
```

---

## Database Schema

```
users         – id, username, email, password_hash, role, subscribed_at, expires_at
content       – id, title, body, tier (free|premium)
access_logs   – id, user_id, content_id, endpoint, method, status_code, ip, user_agent, accessed_at
payments      – id, user_id, amount, currency, status, transaction_ref
```
