"use strict";

const $ = id => document.getElementById(id);
let tasks = [];
let aiSuggestionData = [];
let calendarDate = new Date();
let studyPlans = [];
let activeModal = null;

function showError(message, target = $("error-msg"), timeout = 3500) {
    if (!target) return;
    target.textContent = message;
    window.setTimeout(() => { target.textContent = ""; }, timeout);
}

function escapeHTML(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function dueLabel(value) {
    if (!value) return "No due date";
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function taskElement(task) {
    const row = document.createElement("div");
    row.className = `task-row${task.completed ? " completed" : ""}`;
    row.dataset.id = task.id;
    const check = document.createElement("button");
    check.type = "button";
    check.className = "complete-button";
    check.textContent = task.completed ? "✓" : "";
    check.setAttribute("aria-label", `${task.completed ? "Unmark" : "Mark"} ${task.title}`);
    check.addEventListener("click", () => toggleTask(task.id));
    const content = document.createElement("div");
    content.className = "task-content";
    const title = document.createElement("strong");
    title.textContent = task.title;
    const meta = document.createElement("span");
    const priority = task.priority || "General";
    meta.innerHTML = `<em class="tag tag-${escapeHTML(priority)}">${escapeHTML(priority)}</em><span>${escapeHTML(dueLabel(task.due_date))}</span>`;
    content.append(title, meta);
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "edit-button";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => editTask(task));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Delete ${task.title}`);
    remove.addEventListener("click", () => deleteTask(task.id));
    row.append(check, content, edit, remove);
    return row;
}

function render() {
    const query = $("search-input")?.value.trim().toLowerCase() || "";
    const matching = tasks.filter(task => String(task.title || "").toLowerCase().includes(query));
    const today = new Date().toISOString().slice(0, 10);
    const list = $("task-list");
    if (list) { list.innerHTML = ""; matching.forEach(task => list.appendChild(taskElement(task))); }
    const empty = $("empty-state");
    if (empty) { empty.hidden = tasks.length !== 0 && matching.length !== 0; empty.querySelector("p").textContent = tasks.length ? "No tasks to display." : "No tasks yet. Add your first one above."; }
    if ($("filter-empty")) $("filter-empty").hidden = true;
    const completed = tasks.filter(task => task.completed).length;
    const pending = tasks.length - completed;
    const percent = tasks.length ? Math.round(completed / tasks.length * 100) : 0;
    if ($("total-tasks")) $("total-tasks").textContent = tasks.length;
    if ($("completed-tasks")) $("completed-tasks").textContent = completed;
    if ($("pending-tasks")) $("pending-tasks").textContent = pending;
    if ($("focus-tasks")) $("focus-tasks").textContent = tasks.filter(task => !task.completed && (!task.due_date || task.due_date === today)).length;
    if ($("completed-caption")) $("completed-caption").textContent = percent === 100 ? "All done today" : `${percent}% of total tasks`;
    if ($("progress-percent")) $("progress-percent").textContent = `${percent}%`;
    if ($("overview-completed")) $("overview-completed").textContent = completed;
    if ($("overview-pending")) $("overview-pending").textContent = pending;
    if ($("progress-ring")) $("progress-ring").style.setProperty("--progress", `${percent * 3.6}deg`);
    renderRecentTasks();
    renderCalendar();
}

function renderRecentTasks() {
    const recent = $("recent-list");
    if (!recent) return;
    recent.innerHTML = "";
    tasks.slice(0, 4).forEach(task => {
        const item = document.createElement("div");
        item.className = `recent-item${task.completed ? " completed" : ""}`;
        item.innerHTML = `<span class="recent-check">${task.completed ? "✓" : ""}</span><span>${escapeHTML(task.title)}</span><small>${task.completed ? "Completed" : escapeHTML(dueLabel(task.due_date))}</small>`;
        recent.appendChild(item);
    });
}

function renderCalendar() {
    const calendar = $("calendar-panel");
    if (!calendar) return;
    const title = calendar.querySelector(".calendar-title");
    const grid = calendar.querySelector(".calendar-grid");
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();
    if (title) title.textContent = calendarDate.toLocaleDateString(undefined, { month: "long", year: "numeric" });
    if (!grid) return;
    grid.innerHTML = "";
    ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].forEach(day => { const el = document.createElement("span"); el.className = "calendar-weekday"; el.textContent = day; grid.appendChild(el); });
    for (let index = 0; index < new Date(year, month, 1).getDay(); index += 1) { const blank = document.createElement("span"); blank.className = "calendar-day blank"; grid.appendChild(blank); }
    for (let day = 1; day <= new Date(year, month + 1, 0).getDate(); day += 1) {
        const date = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
        const items = tasks.filter(task => task.due_date === date);
        const cell = document.createElement("button");
        cell.type = "button";
        cell.className = `calendar-day${items.length ? " has-tasks" : ""}`;
        cell.innerHTML = `<b>${day}</b>${items.slice(0, 2).map(task => `<small>${escapeHTML(task.title)}</small>`).join("")}`;
        if (items.length) { cell.title = items.map(task => task.title).join(", "); cell.addEventListener("click", () => showCalendarTasks(date)); }
        grid.appendChild(cell);
    }
}

function showCalendarTasks(date) {
    const items = tasks.filter(task => task.due_date === date);
    if (items.length) window.alert(`${dueLabel(date)}\n\n${items.map(task => `${task.completed ? "✓" : "○"} ${task.title}`).join("\n")}`);
}

async function loadTasks() {
    try { const response = await fetch("/api/tasks"); if (!response.ok) throw new Error(); const data = await response.json(); tasks = Array.isArray(data) ? data : data.tasks || []; render(); }
    catch (error) { console.error("loadTasks:", error); showError("Could not load your tasks."); }
}

async function addTask() {
    const input = $("task-input");
    const title = input?.value.trim();
    if (!title) { showError("Please enter a task."); input?.focus(); return; }
    const body = { title, priority: $("task-priority")?.value || null, due_date: $("task-due-date")?.value || null };
    try { const response = await fetch("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); if (!response.ok) throw new Error(); input.value = ""; loadTasks(); }
    catch { showError("Could not add the task."); }
}

async function toggleTask(id) {
    try { const response = await fetch(`/api/tasks/${id}/complete`, { method: "PATCH" }); if (!response.ok) throw new Error(); loadTasks(); }
    catch { showError("Could not update the task."); }
}

async function deleteTask(id) {
    const task = tasks.find(item => String(item.id) === String(id));
    if (!task || !window.confirm(`Delete "${task.title}"?`)) return;
    try { const response = await fetch(`/api/tasks/${id}`, { method: "DELETE" }); if (!response.ok) throw new Error(); loadTasks(); }
    catch { showError("Could not delete the task."); }
}

async function editTask(task) {
    const title = window.prompt("Task title", task.title);
    if (title === null || !title.trim()) { if (title !== null) showError("Task title cannot be empty."); return; }
    const dueDate = window.prompt("Due date (YYYY-MM-DD), or leave blank", task.due_date || "");
    const priority = window.prompt("Priority: low, medium, or high", task.priority || "medium");
    if (dueDate === null || priority === null) return;
    try { const response = await fetch(`/api/tasks/${task.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim(), due_date: dueDate.trim(), priority: priority.trim() }) }); const data = await response.json(); if (!response.ok) throw new Error(data.error); tasks = tasks.map(item => item.id === task.id ? data : item); render(); }
    catch { showError("Could not edit the task."); }
}

function modalMarkup(type) {
    if (type === "profile") return `<div class="modal-backdrop" data-modal-close></div><section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="profile-title"><button class="modal-close" type="button" aria-label="Close" data-modal-close>×</button><p class="eyebrow">YOUR PROFILE</p><h2 id="profile-title">Profile</h2><div class="profile-details" id="profile-details">Loading profile...</div></section>`;
    return `<div class="modal-backdrop" data-modal-close></div><section class="modal-card study-plan-card" role="dialog" aria-modal="true" aria-labelledby="study-plan-title"><button class="modal-close" type="button" aria-label="Close" data-modal-close>×</button><p class="eyebrow">YOUR ROUTINE</p><h2 id="study-plan-title">Study Plan</h2><form id="study-plan-form" class="modal-form"><label for="plan-goal">Goal <span class="required-mark">*</span></label><input id="plan-goal" required placeholder="Prepare for DBMS exam"><label for="plan-subjects">Subjects <span class="optional-mark">(optional)</span></label><input id="plan-subjects" placeholder="DBMS, Java, Python"><label for="plan-time">Daily study time <span class="required-mark">*</span></label><input id="plan-time" required placeholder="40 minutes"><label for="plan-exam">Exam date <span class="optional-mark">(optional)</span></label><input id="plan-exam" type="date"><label for="plan-difficulty">Difficulty <span class="required-mark">*</span></label><select id="plan-difficulty" required><option value="" selected disabled>Select difficulty</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select><button class="primary-button" type="submit">Save Study Plan</button><p id="plan-message" class="success-message" role="status"></p></form></section>`;
}

function createModal(type) { const modal = document.createElement("div"); modal.id = `${type}-modal`; modal.className = "feature-modal"; modal.hidden = true; modal.dataset.modalType = type; modal.innerHTML = modalMarkup(type); document.body.appendChild(modal); modal.querySelectorAll("[data-modal-close]").forEach(button => button.addEventListener("click", () => closeModal(modal))); if (type === "study-plan") modal.querySelector("#study-plan-form").addEventListener("submit", event => saveStudyPlan(event, modal)); return modal; }
function closeModal(modal) { if (!modal) return; modal.hidden = true; if (activeModal === modal) activeModal = null; document.body.classList.remove("modal-open"); }
function openModal(modal) { if (activeModal && activeModal !== modal) closeModal(activeModal); activeModal = modal; modal.hidden = false; document.body.classList.add("modal-open"); }

async function openProfile() { const modal = $("profile-modal") || createModal("profile"); openModal(modal); const details = modal.querySelector("#profile-details"); try { const response = await fetch("/api/profile"); const data = await response.json(); if (!response.ok) throw new Error(); details.innerHTML = `<strong>${escapeHTML(data.name)}</strong><span>${escapeHTML(data.email)}</span><small>Member since ${escapeHTML(dueLabel(data.created_at.slice(0, 10)))}</small>`; } catch { details.textContent = "Could not load profile."; } }
function openStudyPlan() { const modal = $("study-plan-modal") || createModal("study-plan"); modal.querySelector("#study-plan-form").reset(); modal.querySelector("#plan-difficulty").value = ""; openModal(modal); }
async function saveStudyPlan(event, modal) { event.preventDefault(); const goal = modal.querySelector("#plan-goal").value.trim(); const time = modal.querySelector("#plan-time").value.trim(); const difficulty = modal.querySelector("#plan-difficulty").value; const message = modal.querySelector("#plan-message"); if (!goal) { message.textContent = "Please enter your goal."; return; } if (!time) { message.textContent = "Please enter your daily study time."; return; } if (!difficulty) { message.textContent = "Please select a difficulty level."; return; } const plan = { goal, subjects: modal.querySelector("#plan-subjects").value.trim(), daily_study_time: time, exam_date: modal.querySelector("#plan-exam").value || null, difficulty: difficulty.toLowerCase() }; try { const response = await fetch("/api/study-plans", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(plan) }); const data = await response.json(); if (!response.ok) throw new Error(data.error); message.textContent = "Study plan saved."; await loadStudyPlans(); window.setTimeout(() => closeModal(modal), 700); } catch (error) { message.textContent = error.message || "Could not save study plan."; } }

async function loadStudyPlans() { const list = $("plans-list"); const empty = $("plans-empty"); try { const response = await fetch("/api/study-plans"); if (!response.ok) throw new Error(); studyPlans = await response.json(); if (!list || !empty) return; list.innerHTML = ""; const hasPlans = studyPlans.length > 0; empty.hidden = hasPlans; empty.style.display = hasPlans ? "none" : "grid"; if (!hasPlans) return; studyPlans.forEach(plan => { const card = document.createElement("article"); card.className = "study-plan-card"; card.innerHTML = `<div class="plan-card-heading"><h3>${escapeHTML(plan.goal)}</h3><button type="button" class="delete-plan" data-plan-id="${plan.id}" aria-label="Delete study plan">×</button></div><p><strong>Subjects:</strong> ${escapeHTML(plan.subjects)}</p><p><strong>Daily time:</strong> ${escapeHTML(plan.daily_study_time)}</p><p><strong>Exam date:</strong> ${escapeHTML(plan.exam_date ? dueLabel(plan.exam_date) : "Not set")}</p><p><strong>Difficulty:</strong> ${escapeHTML(plan.difficulty)}</p><small>Created ${escapeHTML(dueLabel(plan.created_at.slice(0, 10)))}</small>`; list.appendChild(card); }); list.querySelectorAll(".delete-plan").forEach(button => button.addEventListener("click", () => deleteStudyPlan(button.dataset.planId))); } catch { studyPlans = []; if (list) list.innerHTML = '<p class="error-message">Could not load study plans.</p>'; if (empty) { empty.hidden = true; empty.style.display = "none"; } } }
async function deleteStudyPlan(id) { try { const response = await fetch(`/api/study-plans/${id}`, { method: "DELETE" }); if (!response.ok) throw new Error(); await loadStudyPlans(); } catch { showError("Could not delete study plan."); } }

function ensureDynamicSections() {
    const controls = document.querySelector(".add-controls");
    if (controls && !$("task-priority")) controls.insertAdjacentHTML("afterbegin", '<select id="task-priority" aria-label="Task priority"><option value="">Priority</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select><input id="task-due-date" type="date" aria-label="Task due date">');
    const recent = $("recent");
    if (recent && !$("calendar-panel")) recent.insertAdjacentHTML("beforebegin", '<section class="panel calendar-panel" id="calendar-panel"><div class="panel-heading"><div><p class="eyebrow">PLAN AHEAD</p><h2 class="calendar-title"></h2></div><div class="calendar-controls"><button type="button" data-calendar-prev aria-label="Previous month">‹</button><button type="button" data-calendar-next aria-label="Next month">›</button></div></div><div class="calendar-grid"></div></section>');
}

function setup() {
    ensureDynamicSections();
    setupProfileMenu();
    $("add-btn")?.addEventListener("click", addTask);
    $("task-input")?.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); addTask(); } });
    $("search-input")?.addEventListener("input", render);
    $("new-plan-button")?.addEventListener("click", openStudyPlan);
    $("ai-generate-btn")?.addEventListener("click", generateSuggestions);
    $("ai-add-btn")?.addEventListener("click", confirmSuggestions);
    document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => { $("ai-goal").value = buildAiPrompt(button.dataset.prompt); generateSuggestions(); }));
    document.querySelectorAll("[data-scroll]").forEach(button => button.addEventListener("click", () => document.querySelector(button.dataset.scroll)?.scrollIntoView({ behavior: "smooth" })));
    document.querySelectorAll("[data-calendar-prev]").forEach(button => button.addEventListener("click", () => { calendarDate.setMonth(calendarDate.getMonth() - 1); renderCalendar(); }));
    document.querySelectorAll("[data-calendar-next]").forEach(button => button.addEventListener("click", () => { calendarDate.setMonth(calendarDate.getMonth() + 1); renderCalendar(); }));
    document.querySelectorAll(".nav-link").forEach(link => link.addEventListener("click", event => { const text = link.textContent.toLowerCase(); if (text.includes("profile")) { event.preventDefault(); openProfile(); } else if (text.includes("study plan")) { event.preventDefault(); openStudyPlan(); } else if (text.includes("calendar")) { event.preventDefault(); $("calendar-panel")?.scrollIntoView({ behavior: "smooth" }); } else if (text.includes("ai assistant")) { event.preventDefault(); $("assistant")?.scrollIntoView({ behavior: "smooth" }); } else if (text.includes("my tasks")) { event.preventDefault(); $("today")?.scrollIntoView({ behavior: "smooth" }); } else if (text.includes("add task")) { event.preventDefault(); $("add-task")?.scrollIntoView({ behavior: "smooth" }); } }));
    document.addEventListener("keydown", event => { if (event.key === "Escape" && activeModal) closeModal(activeModal); });
    document.addEventListener("click", event => { if (event.target.classList.contains("modal-backdrop")) closeModal(event.target.closest(".feature-modal")); });
    loadTasks();
    loadStudyPlans();
}

function buildAiPrompt(action) {
    const taskContext = tasks.length
        ? `Existing tasks: ${tasks.slice(0, 12).map(task => task.title).join("; ")}.`
        : "There are no existing tasks yet.";
    const planContext = studyPlans.length
        ? `Saved study plans: ${studyPlans.map(plan => `${plan.goal} (${plan.subjects || "no subjects"})`).join("; ")}.`
        : "There are no saved study plans yet.";
    if (action === "Motivate me") return "Give me three small, encouraging actions to help me stay motivated today. Make each action an actionable task.";
    if (action === "Create a study plan") return `Create practical study tasks based on my saved study plans. ${planContext}`;
    if (action === "Suggest tasks for me") return `Suggest practical next tasks based on my current work. ${taskContext} ${planContext}`;
    return `Tell me what I should focus on today and turn it into practical tasks. ${taskContext} ${planContext}`;
}

function setupProfileMenu() {
    const chip = document.querySelector(".profile-chip");
    if (!chip || $("profile-menu")) return;

    chip.setAttribute("aria-haspopup", "menu");
    chip.setAttribute("aria-expanded", "false");
    chip.insertAdjacentHTML("afterend", '<div id="profile-menu" class="profile-menu" role="menu" hidden><button type="button" role="menuitem" id="profile-menu-open">Profile</button><form method="POST" action="/logout"><button type="submit" role="menuitem">Logout</button></form></div>');
    const menu = $("profile-menu");

    chip.addEventListener("click", event => {
        event.stopPropagation();
        const isOpen = !menu.hidden;
        menu.hidden = isOpen;
        chip.setAttribute("aria-expanded", String(!isOpen));
    });
    $("profile-menu-open").addEventListener("click", () => {
        menu.hidden = true;
        chip.setAttribute("aria-expanded", "false");
        openProfile();
    });
    document.addEventListener("click", event => {
        if (!menu.hidden && !menu.contains(event.target) && !chip.contains(event.target)) {
            menu.hidden = true;
            chip.setAttribute("aria-expanded", "false");
        }
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !menu.hidden) {
            menu.hidden = true;
            chip.setAttribute("aria-expanded", "false");
        }
    });
}

async function generateSuggestions() {
    const aiGoal = $("ai-goal");
    const aiGenerateBtn = $("ai-generate-btn");
    const aiResults = $("ai-results");
    const aiSuggestions = $("ai-suggestions");
    const aiErrorMsg = $("ai-error-msg");
    const aiSuggestionCount = $("ai-suggestion-count");

    const goal = aiGoal?.value.trim();
    const count = Number(aiSuggestionCount?.value || 3);

    // Check that the user entered a goal
    if (!goal) {
        showError("Please enter a goal first.", aiErrorMsg);
        return;
    }

    // Prevent multiple requests
    if (!aiGenerateBtn || aiGenerateBtn.disabled) {
        return;
    }

    aiGenerateBtn.disabled = true;

    // Save the original button text
    if (!aiGenerateBtn.dataset.originalLabel) {
        aiGenerateBtn.dataset.originalLabel =
            aiGenerateBtn.textContent.trim();
    }

    aiGenerateBtn.textContent = "Generating...";

    // Hide old results while generating
    if (aiResults) {
        aiResults.hidden = true;
    }

    try {
        const response = await fetch("/api/ai/tasks/suggest", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                goal: goal,
                 count: Number(document.getElementById("ai-suggestion-count")?.value || 3)
            })
        });

        let data = {};

        try {
            data = await response.json();
        } catch {
            data = {};
        }

        // Handle server/API errors
        if (!response.ok) {
            const error = new Error(
                data.error || "Failed to generate suggestions."
            );

            error.status = response.status;
            throw error;
        }

        // Make sure suggestions are actually returned
        aiSuggestionData = Array.isArray(data.suggestions)
            ? data.suggestions
            : [];

        if (!aiSuggestionData.length) {
            throw new Error("No suggestions were generated.");
        }

        // Clear previous suggestions
        if (aiSuggestions) {
            aiSuggestions.innerHTML = "";

            aiSuggestionData.forEach((suggestion, index) => {
                const label = document.createElement("label");
                label.className = "ai-suggestion";

                const title =
                    suggestion.title || "Suggested task";

                const priority =
                    suggestion.priority || "medium";

                const dueDate =
                    suggestion.due_date
                        ? ` · due ${suggestion.due_date}`
                        : "";

                label.innerHTML = `
    <span>
        <strong>${escapeHTML(title)}</strong>
        <small>
            ${escapeHTML(priority)}${escapeHTML(dueDate)}
        </small>
    </span>
`;

                aiSuggestions.appendChild(label);
            });
        }

        // Show generated suggestions
        if (aiResults) {
            aiResults.hidden = false;
        }

        // Clear previous error
        if (aiErrorMsg) {
            aiErrorMsg.textContent = "";
            aiErrorMsg.hidden = true;
        }

    } catch (error) {
        console.error("AI suggestion error:", error);

        let message;

        if (error.status === 503) {
            message =
                "AI service is not configured. Please check the API settings.";
        } else if (error.status === 401 || error.status === 403) {
            message =
                "Gemini API key is invalid or unauthorized.";
        } else if (error.status === 429) {
            message =
                "Gemini API quota has been reached. Please try again later.";
        } else if (error.message === "No suggestions were generated.") {
            message =
                "The AI did not return any suggestions. Please try again.";
        } else {
            message =
                "Sorry, I couldn't generate suggestions right now. Please try again.";
        }

        showError(message, aiErrorMsg, 5000);

    } finally {
        // Always restore the button
        if (aiGenerateBtn) {
            aiGenerateBtn.disabled = false;

            aiGenerateBtn.textContent =
                aiGenerateBtn.dataset.originalLabel ||
                "Generate tasks ✦";
        }
    }
}
async function confirmSuggestions() { const aiSuggestions = $("ai-suggestions"); const aiErrorMsg = $("ai-error-msg"); const aiResults = $("ai-results"); const aiGoal = $("ai-goal"); const selected = [...aiSuggestions.querySelectorAll("input:checked")].map(input => aiSuggestionData[Number(input.value)]); if (!selected.length) { showError("Select at least one suggestion.", aiErrorMsg); return; } try { const response = await fetch("/api/ai/tasks/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ suggestions: selected }) }); if (!response.ok) throw new Error(); aiResults.hidden = true; aiGoal.value = ""; loadTasks(); } catch { showError("Could not add suggested tasks.", aiErrorMsg); } }

document.addEventListener("DOMContentLoaded", setup);