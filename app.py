import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from functools import wraps
from flask import (
    Flask, jsonify, request, render_template,
    session, redirect, url_for, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from ai_provider import generate_task_suggestions, AIProviderError

# Load environment variables from .env file on startup
load_dotenv()

app = Flask(__name__)

# ── Secret key (set SECRET_KEY env var on Render) ────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():
    """Open a PostgreSQL database connection with dict-like rows."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    """Create the database tables if they do not already exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id),
                priority TEXT,
                due_date TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS study_plans (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                goal TEXT NOT NULL,
                subjects TEXT NOT NULL,
                daily_study_time TEXT NOT NULL,
                exam_date TEXT,
                difficulty TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict for JSON serialisation.
    Preserves the exact same shape the front-end already expects."""
    return {
        "id":         row["id"],
        "title":      row["title"],
        "completed":  bool(row["completed"]),
        "created_at": row["created_at"],
        "priority":   row["priority"] if "priority" in row.keys() else None,
        "due_date":   row["due_date"] if "due_date" in row.keys() else None,
    }


def validate_task_details(data):
    """Validate optional task metadata shared by create and edit requests."""
    priority = data.get("priority")
    due_date = data.get("due_date")
    if priority is not None and priority not in {"low", "medium", "high"}:
        return None
    if due_date == "":
        due_date = None
    if due_date is not None:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except (TypeError, ValueError):
            return None
    return priority, due_date


def user_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


def plan_to_dict(row):
    return {
        "id": row["id"],
        "goal": row["goal"],
        "subjects": row["subjects"],
        "daily_study_time": row["daily_study_time"],
        "exam_date": row["exam_date"],
        "difficulty": row["difficulty"],
        "created_at": row["created_at"],
    }


def validate_study_plan(data):
    goal = data.get("goal", "").strip()
    subjects = data.get("subjects", "") or ""
    subjects = subjects.strip()
    daily_study_time = data.get("daily_study_time", "").strip()
    exam_date = data.get("exam_date") or None
    difficulty = data.get("difficulty", "").strip().lower()
    if not goal or not daily_study_time:
        return None
    if difficulty not in {"easy", "medium", "hard"}:
        return None
    if exam_date:
        try:
            datetime.strptime(exam_date, "%Y-%m-%d")
        except (TypeError, ValueError):
            return None
    return goal, subjects, daily_study_time, exam_date, difficulty


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
                    "INSERT INTO users (name, email, password, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                    (name, email, hashed_pw, created_at),
                )
                conn.commit()
                user_id = cursor.fetchone()["id"]
            session["user_id"]   = user_id
            session["user_name"] = name
            return redirect(url_for("index"))

        except psycopg.errors.UniqueViolation:
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
                "SELECT * FROM users WHERE email = %s", (email,)
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


@app.route("/api/profile", methods=["GET"])
@login_required
def get_profile():
    user_id = get_current_user_id()
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
    if user is None:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(user_to_dict(user))


@app.route("/api/study-plan", methods=["GET"])
@login_required
def get_study_plan():
    user_id = get_current_user_id()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = %s AND completed = 0 "
            "ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, created_at",
            (user_id,),
        ).fetchall()
    tasks = [row_to_dict(row) for row in rows]
    return jsonify({
        "tasks": tasks,
        "total": len(tasks),
        "scheduled": sum(task["due_date"] is not None for task in tasks),
    })


@app.route("/api/study-plans", methods=["GET"])
@login_required
def get_study_plans():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM study_plans WHERE user_id = %s ORDER BY created_at DESC",
            (get_current_user_id(),),
        ).fetchall()
    return jsonify([plan_to_dict(row) for row in rows])


@app.route("/api/study-plans", methods=["POST"])
@login_required
def create_study_plan():
    data = request.get_json(silent=True) or {}
    plan = validate_study_plan(data)
    if plan is None:
        return jsonify({"error": "Please complete all study plan fields."}), 400
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_db() as conn:
        cursor = conn.execute(
             """INSERT INTO study_plans
                (user_id, goal, subjects, daily_study_time, exam_date, difficulty, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id""",
             (get_current_user_id(), *plan, created_at),
        )
        plan_id = cursor.fetchone()["id"]

        row = conn.execute(
            "SELECT * FROM study_plans WHERE id = %s AND user_id = %s",
            (plan_id, get_current_user_id()),
        ).fetchone()
    return jsonify(plan_to_dict(row)), 201


@app.route("/api/study-plans/<int:plan_id>", methods=["DELETE"])
@login_required
def delete_study_plan(plan_id):
    with get_db() as conn:
        result = conn.execute(
            "DELETE FROM study_plans WHERE id = %s AND user_id = %s",
            (plan_id, get_current_user_id()),
        )
    if result.rowcount == 0:
        return jsonify({"error": "Study plan not found"}), 404
    return jsonify({"message": "Study plan deleted"}), 200


# ── Task API Routes (all require login + ownership) ──────────────────────────

@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    """Return only the tasks belonging to the logged-in user."""
    user_id = get_current_user_id()
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC",
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
    details = validate_task_details(data)
    if details is None:
        return jsonify({"error": "Invalid priority or due date"}), 400
    priority, due_date = details

    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        conn   = get_db()
        cursor = conn.execute(
            "INSERT INTO tasks (title, completed, created_at, user_id, priority, due_date) "
            "VALUES (%s, 0, %s, %s, %s, %s) RETURNING id",
            (title, created_at, user_id, priority, due_date),
        )
        task_id = cursor.fetchone()["id"]
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = %s", (task_id,)
        ).fetchone()
        conn.close()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
@login_required
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Task title cannot be empty"}), 400
    details = validate_task_details(data)
    if details is None:
        return jsonify({"error": "Invalid priority or due date"}), 400
    priority, due_date = details
    try:
        with get_db() as conn:
            result = conn.execute(
                "UPDATE tasks SET title = %s, priority = %s, due_date = %s "
                "WHERE id = %s AND user_id = %s",
                (title, priority, due_date, task_id, get_current_user_id()),
            )
            if result.rowcount == 0:
                return jsonify({"error": "Task not found"}), 404
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
                (task_id, get_current_user_id()),
            ).fetchone()
        return jsonify(row_to_dict(row)), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500


def validate_suggestions(suggestions):
    """Validate the small, user-confirmed payload sent by the dashboard."""
    if not isinstance(suggestions, list) or not suggestions or len(suggestions) > 20:
        return None

    validated = []
    for suggestion in suggestions:
        if not isinstance(suggestion, dict):
            return None
        title = suggestion.get("title", "")
        priority = suggestion.get("priority", "medium")
        due_date = suggestion.get("due_date")
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
            return None
        if priority not in {"low", "medium", "high"}:
            return None
        if due_date is not None:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except (TypeError, ValueError):
                return None
        validated.append({"title": title.strip(), "priority": priority, "due_date": due_date})
    return validated


@app.route("/api/ai/tasks/suggest", methods=["POST"])
@login_required
def suggest_ai_tasks():
    """Generate suggestions without writing anything to the database."""
    data = request.get_json(silent=True) or {}

    goal = data.get("goal", "")
    count = data.get("count", 3)

    if not isinstance(goal, str) or not goal.strip():
        return jsonify({"error": "Please enter a goal first."}), 400

    if len(goal.strip()) > 2000:
        return jsonify({"error": "Please keep your goal under 2,000 characters."}), 400

    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 3

    count = max(1, min(count, 10))

    try:
        suggestions = generate_task_suggestions(goal.strip(), count)
    except AIProviderError as error:
        return jsonify({"error": str(error)}), error.status_code

    return jsonify({"suggestions": suggestions}), 200

@app.route("/api/ai/tasks/confirm", methods=["POST"])
@login_required
def confirm_ai_tasks():
    """Save only suggestions explicitly selected by the logged-in user."""
    data = request.get_json(silent=True) or {}
    suggestions = validate_suggestions(data.get("suggestions"))
    if suggestions is None:
        return jsonify({"error": "Please select valid task suggestions."}), 400

    user_id = get_current_user_id()
    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        with get_db() as conn:
            created = []
            for suggestion in suggestions:
                cursor = conn.execute(
                    """INSERT INTO tasks
                       (title, completed, created_at, user_id, priority, due_date)
                       VALUES (%s, 0, %s, %s, %s, %s)""",
                    (suggestion["title"], created_at, user_id,
                     suggestion["priority"], suggestion["due_date"]),
                )
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
                    (cursor.lastrowid, user_id),
                ).fetchone()
                created.append(row_to_dict(row))
            conn.commit()
        return jsonify({"tasks": created}), 201
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.route("/api/tasks/<int:task_id>/complete", methods=["PATCH"])
@login_required
def toggle_complete(task_id):
    """Toggle completion state — only if the task belongs to the logged-in user."""
    user_id = get_current_user_id()
    try:
        conn = get_db()
        row  = conn.execute(
            "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
            (task_id, user_id)
        ).fetchone()
        if row is None:
            conn.close()
            return jsonify({"error": "Task not found"}), 404

        new_state = 0 if row["completed"] else 1
        conn.execute(
            "UPDATE tasks SET completed = %s WHERE id = %s AND user_id = %s",
            (new_state, task_id, user_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = %s", (task_id,)
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
            "DELETE FROM tasks WHERE id = %s AND user_id = %s",
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
