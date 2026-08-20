# My Tasks — Flask To-Do App

A clean, minimal to-do application built with **Python Flask** (backend) and vanilla **HTML / CSS / JS** (frontend).

---

## Project Structure

```
Web Application/
├── app.py              # Flask backend & REST API
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Main page template
└── static/
    ├── style.css       # Dark glassmorphism styles
    └── script.js       # Frontend logic (fetch API)
```

---

## Prerequisites

- Python 3.8 or newer
- pip

---

## Setup & Run

### 1. (Recommended) Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the development server

```bash
python app.py
```

### 4. Open the app

Navigate to [http://127.0.0.1:5050](http://127.0.0.1:5050) in your browser.

---

## API Endpoints

| Method | Endpoint            | Description       |
|--------|---------------------|-------------------|
| GET    | `/api/tasks`        | List all tasks    |
| POST   | `/api/tasks`        | Add a new task    |
| DELETE | `/api/tasks/<id>`   | Delete a task     |

### POST body example

```json
{ "title": "Buy groceries" }
```

---

## Notes

- Tasks are stored **in-memory** — they reset when the server restarts.
- Press **Enter** in the input field to add a task quickly.
