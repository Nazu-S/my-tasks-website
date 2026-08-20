import sqlite3
import os
from datetime import datetime
from functools import wraps
from flask import (
    Flask, jsonify, request, render_template,
    session, redirect, url_for, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ── Secret key (set SECRET_KEY env var on Render) ────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

# ── Database path ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "tasks.db")


# ── Database helpers ─────────────────────────────────────────────────────────

def get_db():
    """Open a database connection with row_factory for dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create / migrate the database schema on startup.
    - Creates 'users' table if it does not exist.
    - Creates 'tasks' table if it does not exist (with user_id).
    - Adds 'user_id' column to existing 'tasks' table if it is missing
      (non-destructive migration — existing rows keep user_id = NULL).
    """
    with get_db() as conn:
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                email      TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            )
        """)

        # Tasks table (created fresh with user_id for new databases)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL,
                completed  INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL,
                user_id    INTEGER REFERENCES users(id)
            )
        """)

        # Non-destructive migration: add user_id column to existing tasks table
        # if it was created before this version (safe to run every startup).
        existing_cols = [
            row[1]
            for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        ]
        if "user_id" not in existing_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER REFERENCES users(id)")

        conn.commit()


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict for JSON serialisation.
    Preserves the exact same shape the front-end already expects."""
    return {
        "id":         row["id"],
        "title":      row["title"],
        "completed":  bool(row["completed"]),
        "created_at": row["created_at"],
    }


# ── Auth helpers ─────────────────────────────────────────────────────────────

def get_current_user_id():
    """Return the logged-in user's ID from the session, or None."""
    return session.get("user_id")


def login_required(f):
    """Decorator: redirect to /login if the user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if get_current_user_id() is None:
            # API routes return JSON; page routes redirect
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Initialise DB on startup ─────────────────────────────────────────────────
init_db()


# ── Auth Routes ──────────────────────────────────────────────────────────────

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Sign-up page: creates a new user account."""
    # Already logged in → go to dashboard
    if get_current_user_id():
        return redirect(url_for("index"))

    if request.method == "POST":
        name     = request.form.get("name",     "").strip()
        email    = request.form.get("email",    "").strip().lower()
        password = request.form.get("password", "").strip()

        # Basic validation
        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("signup.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html")

        hashed_pw  = generate_password_hash(password)
        created_at = datetime.now().isoformat(timespec="seconds")

        try:
            with get_db() as conn:
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password, created_at) VALUES (?, ?, ?, ?)",
                    (name, email, hashed_pw, created_at),
                )
                conn.commit()
                user_id = cursor.lastrowid

            session["user_id"]   = user_id
            session["user_name"] = name
            return redirect(url_for("index"))

        except sqlite3.IntegrityError:
            # UNIQUE constraint on email failed
            flash("An account with that email already exists. Please log in.", "error")
            return render_template("signup.html")
        except Exception as e:
            flash(f"Something went wrong: {e}", "error")
            return render_template("signup.html")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page: authenticates an existing user."""
    # Already logged in → go to dashboard
    if get_current_user_id():
        return redirect(url_for("index"))

    if request.method == "POST":
        email    = request.form.get("email",    "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html")

        try:
            conn = get_db()
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
            conn.close()
        except Exception as e:
            flash(f"Database error: {e}", "error")
            return render_template("login.html")

        # Deliberately vague error message to avoid user enumeration
        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    """Clear the session and redirect to login."""
    session.clear()
    return redirect(url_for("login"))


# ── Main App Route ───────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    """Render the main task dashboard."""
    return render_template("index.html", user_name=session.get("user_name", ""))


# ── Task API Routes (all require login + ownership) ──────────────────────────

@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    """Return only the tasks belonging to the logged-in user."""
    user_id = get_current_user_id()
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        conn.close()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks", methods=["POST"])
@login_required
def add_task():
    """Create a new task owned by the logged-in user."""
    user_id = get_current_user_id()
    data  = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Task title cannot be empty"}), 400

    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        conn   = get_db()
        cursor = conn.execute(
            "INSERT INTO tasks (title, completed, created_at, user_id) VALUES (?, 0, ?, ?)",
            (title, created_at, user_id),
        )
        conn.commit()
        task_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        conn.close()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<int:task_id>/complete", methods=["PATCH"])
@login_required
def toggle_complete(task_id):
    """Toggle completion state — only if the task belongs to the logged-in user."""
    user_id = get_current_user_id()
    try:
        conn = get_db()
        row  = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        ).fetchone()
        if row is None:
            conn.close()
            return jsonify({"error": "Task not found"}), 404

        new_state = 0 if row["completed"] else 1
        conn.execute(
            "UPDATE tasks SET completed = ? WHERE id = ? AND user_id = ?",
            (new_state, task_id, user_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        conn.close()
        return jsonify(row_to_dict(updated)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    """Delete a task — only if it belongs to the logged-in user."""
    user_id = get_current_user_id()
    try:
        conn   = get_db()
        result = conn.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        conn.commit()
        conn.close()
        if result.rowcount == 0:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"message": "Task deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5050)
