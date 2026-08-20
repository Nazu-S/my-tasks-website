const taskInput = document.getElementById("task-input");
const addBtn    = document.getElementById("add-btn");
const taskList  = document.getElementById("task-list");
const errorMsg  = document.getElementById("error-msg");
const taskCount = document.getElementById("task-count");
const emptyState = document.getElementById("empty-state");

/* ── helpers ──────────────────────────────────────────────── */

function showError(msg) {
  errorMsg.textContent = msg;
  setTimeout(() => { errorMsg.textContent = ""; }, 3000);
}

function updateStats(count) {
  taskCount.textContent = count === 1 ? "1 task" : `${count} tasks`;
  emptyState.style.display = count === 0 ? "flex" : "none";
}

function buildTaskEl(task) {
  const li = document.createElement("li");
  li.className = "task-item" + (task.completed ? " completed" : "");
  li.dataset.id = task.id;

  // Complete toggle button
  const completeBtn = document.createElement("button");
  completeBtn.className = "btn btn-complete";
  completeBtn.setAttribute("aria-label", task.completed
    ? `Unmark "${task.title}" as done`
    : `Mark "${task.title}" as done`);
  completeBtn.setAttribute("title", task.completed ? "Mark incomplete" : "Mark complete");
  completeBtn.innerHTML = task.completed ? "✓" : "";
  completeBtn.addEventListener("click", () => handleToggle(task.id, li));

  const title = document.createElement("span");
  title.className = "task-title";
  title.textContent = task.title;

  const delBtn = document.createElement("button");
  delBtn.className = "btn btn-delete";
  delBtn.setAttribute("aria-label", `Delete "${task.title}"`);
  delBtn.textContent = "🗑";
  delBtn.addEventListener("click", () => handleDelete(task.id, li));

  li.append(completeBtn, title, delBtn);
  return li;
}

/* ── API calls ────────────────────────────────────────────── */

async function loadTasks() {
  try {
    const res = await fetch("/api/tasks");
    if (!res.ok) { showError("Could not load tasks."); return; }
    const tasks = await res.json();
    taskList.innerHTML = "";
    tasks.forEach(t => taskList.appendChild(buildTaskEl(t)));
    updateStats(tasks.length);
  } catch {
    showError("Network error — could not load tasks.");
  }
}

async function handleAdd() {
  const title = taskInput.value.trim();
  if (!title) {
    showError("Please enter a task before adding.");
    taskInput.focus();
    return;
  }

  addBtn.disabled = true;

  try {
    const res = await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });

    if (!res.ok) {
      const data = await res.json();
      showError(data.error || "Could not add task.");
      return;
    }

    const task = await res.json();
    const el = buildTaskEl(task);
    taskList.prepend(el);              // newest at top
    taskInput.value = "";
    updateStats(taskList.children.length);
    taskInput.focus();
  } catch {
    showError("Network error — please try again.");
  } finally {
    addBtn.disabled = false;
  }
}

async function handleToggle(id, li) {
  try {
    const res = await fetch(`/api/tasks/${id}/complete`, { method: "PATCH" });
    if (!res.ok) { showError("Could not update task."); return; }
    const task = await res.json();

    // Update classes and button appearance in place (no full re-render)
    if (task.completed) {
      li.classList.add("completed");
    } else {
      li.classList.remove("completed");
    }
    const btn = li.querySelector(".btn-complete");
    btn.innerHTML = task.completed ? "✓" : "";
    btn.setAttribute("aria-label", task.completed
      ? `Unmark "${task.title}" as done`
      : `Mark "${task.title}" as done`);
    btn.setAttribute("title", task.completed ? "Mark incomplete" : "Mark complete");
  } catch {
    showError("Network error — please try again.");
  }
}

async function handleDelete(id, el) {
  el.classList.add("removing");
  await new Promise(r => setTimeout(r, 220));   // wait for CSS animation

  try {
    const res = await fetch(`/api/tasks/${id}`, { method: "DELETE" });
    if (!res.ok) { showError("Could not delete task."); return; }
    el.remove();
    updateStats(taskList.children.length);
  } catch {
    el.classList.remove("removing");
    showError("Network error — please try again.");
  }
}

/* ── event listeners ──────────────────────────────────────── */

addBtn.addEventListener("click", handleAdd);

taskInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleAdd();
});

/* ── init ─────────────────────────────────────────────────── */
loadTasks();
