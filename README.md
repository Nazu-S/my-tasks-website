# My Tasks — Flask To-Do App

A clean, minimal to-do application built with **Python Flask** (backend) and vanilla **HTML / CSS / JS** (frontend).

---

## Project Structure

```
Web Application/
├── app.py              # Flask backend & REST API
├── ai_provider.py      # Server-side Google Gemini integration and response validation
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

### 3. Configure the Gemini AI Assistant

The assistant uses Google's Gemini API. The API key stays on the server and is never sent to the browser.

#### Option A: Using a `.env` file (Recommended)

1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```

2. Get your Gemini API key from [Google AI Studio](https://ai.google.dev/)

3. Add your API key to `.env`:
   ```
   GEMINI_API_KEY=your-gemini-api-key-here
   ```

#### Option B: Set environment variable (PowerShell)

```powershell
$env:GEMINI_API_KEY = "your-gemini-api-key"
```

### 4. Start the development server

```bash
python app.py
```

### 5. Open the app

Navigate to [http://127.0.0.1:5050](http://127.0.0.1:5050) in your browser.

---

## API Endpoints

| Method | Endpoint            | Description       |
|--------|---------------------|-------------------|
| GET    | `/api/tasks`        | List all tasks    |
| POST   | `/api/tasks`        | Add a new task    |
| DELETE | `/api/tasks/<id>`   | Delete a task     |
| POST   | `/api/ai/tasks/suggest` | Generate suggestions without saving |
| POST   | `/api/ai/tasks/confirm` | Save selected suggestions |

### POST body example

```json
{ "title": "Buy groceries" }
```

AI suggestions are displayed for review and are not saved until the user selects
them and clicks **Add Selected Tasks**. Both AI endpoints require login.

## Testing

Run the focused AI tests with:

```powershell
python -m pytest -q test_ai_tasks.py
```

The authentication and two-account isolation tests use a fresh temporary
database automatically and do not require the development server:

```powershell
python -m pytest -q test_auth.py
```

---

## Notes
-Tasks and study plans are stored in a Supabase PostgreSQL database.
- Press **Enter** in the input field to add a task quickly.
