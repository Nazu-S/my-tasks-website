"""
Two-Account Isolation Test for My Tasks
Run with: python test_auth.py
Server must be running on http://127.0.0.1:5050
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import http.cookiejar

BASE = "http://127.0.0.1:5050"

PASS = "\033[92m  ✅ PASS\033[0m"
FAIL = "\033[91m  ❌ FAIL\033[0m"


def make_opener():
    """Create a fresh cookie-enabled URL opener (simulates a new browser session)."""
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def post_form(opener, url, data):
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        resp = opener.open(req)
        return resp.geturl(), resp.status
    except urllib.error.HTTPError as e:
        return e.url, e.code


def get_json(opener, url):
    req = urllib.request.Request(BASE + url)
    try:
        resp = opener.open(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def post_json(opener, url, payload):
    encoded = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        resp = opener.open(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def delete(opener, url):
    req = urllib.request.Request(BASE + url, method="DELETE")
    try:
        resp = opener.open(req)
        return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def check(label, condition):
    print(f"{PASS if condition else FAIL}  {label}")
    return condition


all_passed = True


# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  MY TASKS — Two-Account Isolation Test")
print("=" * 60)

# ── TEST 1: Unauthenticated redirect ──────────────────────────
print("\n[ 1 ] Unauthenticated access to / → must redirect to login")
anon = make_opener()
final_url, _, = post_form(anon, "/logout", {})   # ensure no stale session
status, _ = get_json(anon, "/api/tasks")
all_passed &= check("GET /api/tasks without login returns 401", status == 401)

# ── TEST 2: Sign up User A ────────────────────────────────────
print("\n[ 2 ] Sign up as User A")
session_a = make_opener()
url, _ = post_form(session_a, "/signup",
                   {"name": "User A", "email": "usera@test.com", "password": "passwordA"})
all_passed &= check("After signup, redirected to dashboard (/)", url.endswith("/") or url == BASE + "/")

# ── TEST 3: User A creates a task ─────────────────────────────
print("\n[ 3 ] User A creates a task")
status, task_a = post_json(session_a, "/api/tasks", {"title": "Task from User A"})
all_passed &= check("POST /api/tasks returns 201", status == 201)
all_passed &= check("Task title is correct", task_a.get("title") == "Task from User A")
task_a_id = task_a.get("id")
print(f"       Task A ID: {task_a_id}")

# ── TEST 4: User A sees their task ───────────────────────────
print("\n[ 4 ] User A's task list")
status, tasks_a = get_json(session_a, "/api/tasks")
titles_a = [t["title"] for t in tasks_a]
all_passed &= check("User A can see 'Task from User A'", "Task from User A" in titles_a)

# ── TEST 5: Log out User A ────────────────────────────────────
print("\n[ 5 ] User A logs out")
url, _ = post_form(session_a, "/logout", {})
all_passed &= check("After logout, redirected to login page", "login" in url)

# ── TEST 6: Sign up User B ────────────────────────────────────
print("\n[ 6 ] Sign up as User B")
session_b = make_opener()
url, _ = post_form(session_b, "/signup",
                   {"name": "User B", "email": "userb@test.com", "password": "passwordB"})
all_passed &= check("User B signed up and landed on dashboard", url.endswith("/") or url == BASE + "/")

# ── TEST 7: User B creates a task ─────────────────────────────
print("\n[ 7 ] User B creates a task")
status, task_b = post_json(session_b, "/api/tasks", {"title": "Task from User B"})
all_passed &= check("POST /api/tasks returns 201", status == 201)
task_b_id = task_b.get("id")
print(f"       Task B ID: {task_b_id}")

# ── TEST 8: User B cannot see User A's task ───────────────────
print("\n[ 8 ] User B's task list (ISOLATION CHECK)")
status, tasks_b = get_json(session_b, "/api/tasks")
titles_b = [t["title"] for t in tasks_b]
all_passed &= check("User B can see 'Task from User B'", "Task from User B" in titles_b)
all_passed &= check("User B CANNOT see 'Task from User A'", "Task from User A" not in titles_b)

# ── TEST 9: User B cannot delete User A's task (IDOR check) ───
print("\n[ 9 ] IDOR: User B tries to DELETE User A's task by ID")
if task_a_id:
    status = delete(session_b, f"/api/tasks/{task_a_id}")
    all_passed &= check(f"DELETE task {task_a_id} (User A's) by User B returns 404", status == 404)

# ── TEST 10: User B tries to toggle User A's task ─────────────
print("\n[ 10 ] IDOR: User B tries to PATCH (toggle) User A's task")
if task_a_id:
    req = urllib.request.Request(
        BASE + f"/api/tasks/{task_a_id}/complete", method="PATCH"
    )
    req.add_header("Content-Length", "0")
    try:
        resp = session_b.open(req)
        status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    all_passed &= check(f"PATCH task {task_a_id} (User A's) by User B returns 404", status == 404)

# ── TEST 11: Log out B, log in as User A ──────────────────────
print("\n[ 11 ] User B logs out, User A logs in")
post_form(session_b, "/logout", {})
# Re-use session_a opener (cookies were cleared when server session cleared)
session_a2 = make_opener()
url, _ = post_form(session_a2, "/login",
                   {"email": "usera@test.com", "password": "passwordA"})
all_passed &= check("User A logged in, redirected to dashboard", url.endswith("/") or url == BASE + "/")

# ── TEST 12: User A cannot see User B's task ──────────────────
print("\n[ 12 ] User A's task list after re-login (ISOLATION CHECK)")
status, tasks_a2 = get_json(session_a2, "/api/tasks")
titles_a2 = [t["title"] for t in tasks_a2]
all_passed &= check("User A can see 'Task from User A'", "Task from User A" in titles_a2)
all_passed &= check("User A CANNOT see 'Task from User B'", "Task from User B" not in titles_a2)

# ── TEST 13: Wrong password is rejected ───────────────────────
print("\n[ 13 ] Wrong password is rejected")
session_bad = make_opener()
url, _ = post_form(session_bad, "/login",
                   {"email": "usera@test.com", "password": "WRONGPASSWORD"})
all_passed &= check("Wrong password stays on login page (not redirected)", "login" in url)

# ── TEST 14: Duplicate email is rejected ──────────────────────
print("\n[ 14 ] Duplicate email signup is rejected")
session_dup = make_opener()
url, _ = post_form(session_dup, "/signup",
                   {"name": "Duplicate", "email": "usera@test.com", "password": "anything"})
all_passed &= check("Duplicate email stays on signup page", "signup" in url)

# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
if all_passed:
    print("\033[92m  🎉 ALL TESTS PASSED — User isolation is working correctly!\033[0m")
else:
    print("\033[91m  ⚠️  SOME TESTS FAILED — see above for details.\033[0m")
print("=" * 60 + "\n")
