"""
Expense Tracker — Flask + SQLite backend
Session-based auth (register/login/logout) and a REST CRUD API for
expenses, plus server-rendered pages for the vanilla JS/HTML/CSS frontend.
"""
import os
import sqlite3
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "expenses.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

CATEGORIES = ["Food", "Transport", "Housing", "Utilities", "Health",
              "Entertainment", "Shopping", "Education", "Other"]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL DEFAULT 'Other',
                note TEXT DEFAULT '',
                expense_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.commit()


def row_to_expense(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "amount": row["amount"],
        "category": row["category"],
        "note": row["note"],
        "date": row["expense_date"],
    }


def row_to_user(row):
    return {"id": row["id"], "username": row["username"], "email": row["email"]}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return row


def login_required_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Authentication required"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Page routes (frontend)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard")) if current_user() else redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/register")
def register_page():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    return render_template("dashboard.html", username=user["username"], categories=CATEGORIES)


# ---------------------------------------------------------------------------
# Auth REST API
# ---------------------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "Username, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
    ).fetchone()
    if existing:
        return jsonify({"error": "Username or email already registered"}), 409

    password_hash = generate_password_hash(password)
    cur = db.execute(
        "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (username, email, password_hash, datetime.utcnow().isoformat()),
    )
    db.commit()

    session["user_id"] = cur.lastrowid
    return jsonify({"message": "Account created",
                     "user": {"id": cur.lastrowid, "username": username, "email": email}}), 201


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier.lower())
    ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"] = row["id"]
    return jsonify({"message": "Logged in", "user": row_to_user(row)}), 200


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200


@app.route("/api/me", methods=["GET"])
def api_me():
    user = current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({"user": row_to_user(user)}), 200


# ---------------------------------------------------------------------------
# Expense REST CRUD API
# ---------------------------------------------------------------------------
@app.route("/api/expenses", methods=["GET"])
@login_required_api
def get_expenses():
    user = current_user()
    db = get_db()
    category = request.args.get("category")

    if category and category != "All":
        rows = db.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND category = ? "
            "ORDER BY expense_date DESC, id DESC",
            (user["id"], category),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY expense_date DESC, id DESC",
            (user["id"],),
        ).fetchall()

    expenses = [row_to_expense(r) for r in rows]
    total = sum(e["amount"] for e in expenses)
    by_category = {}
    for e in expenses:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]

    return jsonify({
        "expenses": expenses,
        "total": round(total, 2),
        "count": len(expenses),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
    }), 200


@app.route("/api/expenses/<int:expense_id>", methods=["GET"])
@login_required_api
def get_expense(expense_id):
    user = current_user()
    row = get_db().execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user["id"])
    ).fetchone()
    if not row:
        return jsonify({"error": "Expense not found"}), 404
    return jsonify({"expense": row_to_expense(row)}), 200


@app.route("/api/expenses", methods=["POST"])
@login_required_api
def create_expense():
    user = current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    amount = data.get("amount")
    category = data.get("category") or "Other"
    note = (data.get("note") or "").strip()
    date_str = data.get("date")

    if not title:
        return jsonify({"error": "Title is required"}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Amount must be a positive number"}), 400

    try:
        expense_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        return jsonify({"error": "Date must be in YYYY-MM-DD format"}), 400

    if category not in CATEGORIES:
        category = "Other"

    db = get_db()
    cur = db.execute(
        "INSERT INTO expenses (user_id, title, amount, category, note, expense_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["id"], title, amount, category, note, expense_date.isoformat(),
         datetime.utcnow().isoformat()),
    )
    db.commit()

    row = db.execute("SELECT * FROM expenses WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"message": "Expense added", "expense": row_to_expense(row)}), 201


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
@login_required_api
def update_expense(expense_id):
    user = current_user()
    db = get_db()
    row = db.execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user["id"])
    ).fetchone()
    if not row:
        return jsonify({"error": "Expense not found"}), 404

    data = request.get_json(silent=True) or {}
    title = row["title"]
    amount = row["amount"]
    category = row["category"]
    note = row["note"]
    expense_date = row["expense_date"]

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "Title cannot be empty"}), 400

    if "amount" in data:
        try:
            amount = float(data.get("amount"))
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Amount must be a positive number"}), 400

    if "category" in data and data.get("category") in CATEGORIES:
        category = data.get("category")

    if "note" in data:
        note = (data.get("note") or "").strip()

    if "date" in data and data.get("date"):
        try:
            expense_date = datetime.strptime(data.get("date"), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return jsonify({"error": "Date must be in YYYY-MM-DD format"}), 400

    db.execute(
        "UPDATE expenses SET title = ?, amount = ?, category = ?, note = ?, expense_date = ? "
        "WHERE id = ? AND user_id = ?",
        (title, amount, category, note, expense_date, expense_id, user["id"]),
    )
    db.commit()

    updated = db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return jsonify({"message": "Expense updated", "expense": row_to_expense(updated)}), 200


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
@login_required_api
def delete_expense(expense_id):
    user = current_user()
    db = get_db()
    row = db.execute(
        "SELECT id FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user["id"])
    ).fetchone()
    if not row:
        return jsonify({"error": "Expense not found"}), 404

    db.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user["id"]))
    db.commit()
    return jsonify({"message": "Expense deleted"}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)