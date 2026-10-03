"use strict";

const state = { status: null, evidence: [], index: null, context: null };
const byId = (id) => document.getElementById(id);

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function readJson(path, optional = false) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (optional && response.status === 404) return null;
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `${response.status} ${response.statusText}`);
  return payload;
}

async function refresh() {
  const button = byId("refresh");
  button.disabled = true;
  setConnection("reading", "Reading ledger");
  try {
    const [status, evidence, index, context] = await Promise.all([
      readJson("/api/status"),
      readJson("/api/evidence"),
      readJson("/api/index", true),
      readJson("/api/context"),
    ]);
    Object.assign(state, { status, evidence, index, context });
    render();
    const now = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
    byId("last-sync").textContent = `Last reading ${now}`;
    setConnection("online", "Loopback online");
  } catch (error) {
    setConnection("offline", "Ledger unavailable");
    byId("last-sync").textContent = error.message;
    renderError(error.message);
  } finally {
    button.disabled = false;
  }
}

function setConnection(mode, label) {
  byId("connection-signal").className = `signal ${mode}`;
  byId("connection-label").textContent = label;
}

function render() {
  const { status, evidence, index, context } = state;
  byId("project-objective").textContent = status.objective;
  byId("next-action").textContent = context.next_action;
  byId("metric-revision").textContent = String(status.revision).padStart(3, "0");
  byId("metric-tasks").textContent = String(status.tasks.length).padStart(2, "0");
  const counts = Object.groupBy ? Object.groupBy(status.tasks, (task) => task.status) : groupTasks(status.tasks);
  byId("metric-task-detail").textContent = `${(counts.planned || []).length} planned / ${(counts.active || []).length} active / ${(counts.completed || []).length} done`;
  byId("metric-evidence").textContent = String(evidence.length).padStart(2, "0");
  byId("metric-files").textContent = index ? String(index.files.length).padStart(2, "0") : "—";
  byId("metric-index-detail").textContent = index ? `${index.stale ? "stale" : "current"} · ${index.issues.length} issues` : "run vertex index";
  byId("source-mark").textContent = `source ${context.source_hash.slice(0, 10)}`;
  renderTasks(status.tasks);
  renderEvidence(evidence);
  renderIndex(index);
}

function groupTasks(tasks) {
  return tasks.reduce((groups, task) => {
    (groups[task.status] ||= []).push(task);
    return groups;
  }, {});
}

function renderTasks(tasks) {
  const target = byId("task-list");
  target.replaceChildren();
  if (!tasks.length) {
    target.append(element("p", "empty-state", "No tasks recorded. Add the first bounded task from the CLI."));
    return;
  }
  tasks.forEach((task) => {
    const row = element("article", "task-row");
    row.dataset.status = task.status;
    row.append(element("div", "task-id", task.id));

    const title = element("div", "task-title-wrap");
    title.append(element("h3", "task-title", task.title));
    title.append(element("p", "task-outcome", task.outcome));
    row.append(title);

    const contract = element("ul", "task-contract");
    task.acceptance_criteria.forEach((criterion) => {
      contract.append(element("li", "", `${criterion.id} — ${criterion.description}`));
    });
    if (task.blocker) contract.append(element("li", "", `Blocker — ${task.blocker}`));
    row.append(contract);

    const label = task.available ? `${task.status} / ready` : task.status;
    row.append(element("span", `status-stamp ${task.status}`, label));
    target.append(row);
  });
}

function renderEvidence(receipts) {
  const target = byId("evidence-list");
  target.replaceChildren();
  if (!receipts.length) {
    target.append(element("li", "empty-state", "No verification receipts yet."));
    return;
  }
  [...receipts].reverse().forEach((receipt) => {
    const item = element("li", `evidence-item ${receipt.outcome}`);
    const time = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(receipt.finished_at));
    item.append(element("time", "evidence-time", time));
    const main = element("div", "evidence-main");
    main.append(element("strong", "", `${receipt.task_id} / ${receipt.check_id}`));
    main.append(element("p", "evidence-command", receipt.command.join(" ")));
    item.append(main);
    item.append(element("span", `status-stamp ${receipt.outcome}`, receipt.outcome.replace("_", " ")));
    target.append(item);
  });
}

function renderIndex(index) {
  const target = byId("file-map");
  target.replaceChildren();
  if (!index) {
    target.append(element("p", "empty-state", "No generated index. Run `vertex index .` from the repository."));
    return;
  }
  byId("index-note").textContent = index.stale
    ? "The source changed after indexing. Rebuild before relying on these bearings."
    : `Indexed ${index.generated_at}. Static relationships remain advisory.`;
  index.files.forEach((file) => {
    const row = element("div", "file-row");
    row.append(element("span", "file-path", file.path));
    row.append(element("span", "file-counts", `${file.symbols} symbols · ${file.imports} imports`));
    target.append(row);
  });
}

function renderError(message) {
  const target = byId("task-list");
  target.replaceChildren(element("p", "empty-state error-state", message));
}

function activateTab(button) {
  document.querySelectorAll('[role="tab"]').forEach((tab) => {
    const selected = tab === button;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    byId(tab.getAttribute("aria-controls")).hidden = !selected;
  });
}

document.querySelectorAll('[role="tab"]').forEach((tab, index, tabs) => {
  tab.addEventListener("click", () => activateTab(tab));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    activateTab(tabs[next]);
    tabs[next].focus();
  });
});

byId("refresh").addEventListener("click", refresh);
refresh();
window.setInterval(refresh, 15_000);
