import sqlite3
import os
from datetime import datetime
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

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
    """Create the tasks table if it does not already exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL,
                completed  INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL
            )
        """)
        conn.commit()


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict suitable for JSON serialisation."""
    return {
        "id":         row["id"],
        "title":      row["title"],
        "completed":  bool(row["completed"]),
        "created_at": row["created_at"],
    }


# ── Initialise DB on startup ─────────────────────────────────────────────────
init_db()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Task title cannot be empty"}), 400

    created_at = datetime.now().isoformat(timespec="seconds")
    try:
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO tasks (title, completed, created_at) VALUES (?, 0, ?)",
            (title, created_at),
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
def toggle_complete(task_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            conn.close()
            return jsonify({"error": "Task not found"}), 404

        new_state = 0 if row["completed"] else 1
        conn.execute(
            "UPDATE tasks SET completed = ? WHERE id = ?",
            (new_state, task_id),
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
def delete_task(task_id):
    try:
        conn = get_db()
        result = conn.execute(
            "DELETE FROM tasks WHERE id = ?", (task_id,)
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
