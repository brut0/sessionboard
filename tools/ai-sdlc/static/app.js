"use strict";

const state = {
  activeRun: null,
  lastRenderedRunId: null,
  runs: [],
};

const el = {
  gitBadge: document.getElementById("git-badge"),
  llmBadge: document.getElementById("llm-badge"),
  statusBanner: document.getElementById("status-banner"),
  errorBanner: document.getElementById("error-banner"),
  runsList: document.getElementById("runs-list"),
  emptyState: document.getElementById("empty-state"),
  runWorkspace: document.getElementById("run-workspace"),
  activeTitle: document.getElementById("active-run-title"),
  activePrompt: document.getElementById("active-run-prompt"),
  pillSpec: document.getElementById("pill-spec"),
  pillIssue: document.getElementById("pill-issue"),
  pillBranch: document.getElementById("pill-branch"),
  patchesCount: document.getElementById("patches-count"),
  patchesContainer: document.getElementById("patches-container"),
  gatesOutput: document.getElementById("gates-output"),
  outIntake: document.getElementById("out-intake"),
  outSpec: document.getElementById("out-spec"),
  outArchitect: document.getElementById("out-architect"),
  outTdd: document.getElementById("out-tdd"),
  outCli: document.getElementById("out-cli"),
  outReview: document.getElementById("out-review"),
  outGit: document.getElementById("out-git"),
  settingsDialog: document.getElementById("settings-dialog"),
  cfgProvider: document.getElementById("cfg-provider"),
  cfgModel: document.getElementById("cfg-model"),
  cfgBaseUrl: document.getElementById("cfg-base-url"),
  cfgApiKey: document.getElementById("cfg-api-key"),
  cfgKeyHint: document.getElementById("cfg-key-hint"),
  toggleKeyBtn: document.getElementById("toggle-key-visibility"),
};

function setStatus(message) {
  el.statusBanner.textContent = message;
  el.errorBanner.hidden = true;
  el.errorBanner.textContent = "";
}

function setError(message) {
  el.errorBanner.textContent = message;
  el.errorBanner.hidden = false;
}

async function apiJson(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
  return data;
}

function renderCodeBlock(preEl, obj) {
  const code = preEl.querySelector("code") || preEl;
  code.textContent = obj ? JSON.stringify(obj, null, 2) : "(not executed yet)";
}

function renderConfig(cfg) {
  el.llmBadge.textContent = cfg.has_api_key
    ? `LLM: ${cfg.llm_provider} (${cfg.llm_model}) [KEY SET]`
    : `LLM: ${cfg.llm_provider} (${cfg.llm_model}) [NO KEY]`;
  el.llmBadge.className = `badge ${cfg.has_api_key ? "badge-ok" : "badge-warn"}`;

  el.cfgProvider.value = cfg.llm_provider;
  el.cfgModel.value = cfg.llm_model;
  el.cfgBaseUrl.value = cfg.openai_base_url;
  el.cfgKeyHint.textContent = cfg.has_api_key
    ? `Saved key: ${cfg.masked_key}`
    : "Saved key: none yet (paste Gemini or OpenAI key)";
}

function renderGitOverview(info) {
  const dirtyCount = Array.isArray(info.dirty_files) ? info.dirty_files.length : 0;
  el.gitBadge.textContent = `Branch: ${info.branch} (${dirtyCount} modified)`;
  el.outGit.querySelector("code").textContent = JSON.stringify(info, null, 2);
}

function renderRunsList() {
  el.runsList.textContent = "";
  if (state.runs.length === 0) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "No saved runs yet.";
    el.runsList.appendChild(empty);
    return;
  }

  for (const run of state.runs) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "run-item-btn";
    if (state.activeRun && state.activeRun.id === run.id) {
      btn.setAttribute("aria-current", "true");
    }

    const title = document.createElement("strong");
    title.textContent = run.title;
    const meta = document.createElement("span");
    meta.className = "hint";
    const issueTag = run.issue_number ? ` · #${run.issue_number}` : "";
    const specTag = run.spec_approved ? " [Spec Approved]" : "";
    meta.textContent = `Stage: ${run.current_stage}${specTag}${issueTag}`;

    btn.append(title, meta);
    btn.addEventListener("click", () => loadRun(run.id));
    li.appendChild(btn);
    el.runsList.appendChild(li);
  }
}

function renderPatches(patches) {
  el.patchesCount.textContent = String(patches.length);
  el.patchesContainer.textContent = "";
  if (!patches.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No pending file patches generated yet. Run Spec, Architect, TDD, or Implement first.";
    el.patchesContainer.appendChild(p);
    return;
  }

  for (const patch of patches) {
    const card = document.createElement("div");
    card.className = "patch-card";

    const header = document.createElement("div");
    header.className = "row-between wrap-gap";

    const label = document.createElement("label");
    label.className = "check-item";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "patch-select";
    cb.value = patch.path;
    cb.checked = !patch.applied;
    const pathStrong = document.createElement("strong");
    pathStrong.textContent = patch.path;
    label.append(cb, pathStrong);

    const badge = document.createElement("span");
    badge.className = `badge ${patch.applied ? "badge-ok" : "badge-warn"}`;
    badge.textContent = patch.applied ? "APPLIED" : "PENDING";
    header.append(label, badge);

    const rationale = document.createElement("p");
    rationale.className = "hint";
    rationale.textContent = patch.rationale || "Generated patch";

    const pre = document.createElement("pre");
    pre.className = "code-box";
    pre.setAttribute("role", "region");
    pre.setAttribute("tabindex", "0");
    pre.setAttribute("aria-label", `Diff preview for ${patch.path}`);
    const code = document.createElement("code");
    code.textContent = patch.diff_preview || patch.content;
    pre.appendChild(code);

    card.append(header, rationale, pre);
    el.patchesContainer.appendChild(card);
  }
}

function renderGates(gates) {
  el.gatesOutput.textContent = "";
  if (!gates.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No gate runs recorded yet.";
    el.gatesOutput.appendChild(p);
    return;
  }

  for (const item of [...gates].reverse()) {
    const card = document.createElement("div");
    card.className = "gate-card";

    const head = document.createElement("div");
    head.className = "row-between wrap-gap";
    const title = document.createElement("strong");
    title.textContent = `${item.gate} (${item.duration_ms} ms) — ${item.command}`;
    const badge = document.createElement("span");
    badge.className = `badge ${item.passed ? "badge-ok" : "badge-err"}`;
    badge.textContent = item.passed ? "PASS" : `FAIL (exit ${item.exit_code})`;
    head.append(title, badge);

    const pre = document.createElement("pre");
    pre.className = "code-box";
    pre.setAttribute("role", "region");
    pre.setAttribute("tabindex", "0");
    pre.setAttribute("aria-label", `Output for ${item.gate}`);
    const code = document.createElement("code");
    code.textContent = item.output;
    pre.appendChild(code);

    card.append(head, pre);
    el.gatesOutput.appendChild(card);
  }
}

function renderActiveRun(run) {
  state.activeRun = run;
  el.emptyState.hidden = true;
  el.runWorkspace.hidden = false;

  el.activeTitle.textContent = `${run.title} (${run.id})`;
  el.activePrompt.textContent = run.prompt;

  el.pillSpec.textContent = run.spec_approved ? "Spec: APPROVED" : "Spec: Pending";
  el.pillSpec.className = `badge ${run.spec_approved ? "badge-ok" : "badge-warn"}`;

  el.pillIssue.textContent = run.issue_number ? `Issue: #${run.issue_number}` : "Issue: None";
  el.pillIssue.className = `badge ${run.issue_number ? "badge-ok" : "badge-neutral"}`;

  el.pillBranch.textContent = run.branch_name ? `Branch: ${run.branch_name}` : "Branch: None";

  renderCodeBlock(el.outIntake, run.intake);
  renderCodeBlock(el.outSpec, run.spec);
  renderCodeBlock(el.outArchitect, run.architect);
  renderCodeBlock(el.outTdd, run.implement || run.tdd_tests);
  renderCodeBlock(el.outReview, run.review);
  el.outCli.querySelector("code").textContent = run.cli_log || "(not run yet)";

  // Prefill branch/PR hints cleanly when switching runs or after issue creation
  const switchedRun = state.lastRenderedRunId !== run.id;
  state.lastRenderedRunId = run.id;

  const branchInput = document.getElementById("branch-name");
  if ((switchedRun || !branchInput.value) && run.intake?.suggested_branch) {
    branchInput.value = run.intake.suggested_branch;
  } else if (switchedRun) {
    branchInput.value = "";
  }

  const prTitle = document.getElementById("pr-title");
  const expectedDefaultNoIssue = `feat: ${run.title}`;
  if (switchedRun || !prTitle.value || (run.issue_number && prTitle.value === expectedDefaultNoIssue)) {
    prTitle.value = run.issue_number ? `feat: ${run.title} (#${run.issue_number})` : expectedDefaultNoIssue;
  }

  renderPatches(run.pending_patches || []);
  renderGates(run.gate_results || []);
  renderRunsList();
}

async function refreshAll() {
  const [cfg, runs, gitInfo] = await Promise.all([
    apiJson("/api/config"),
    apiJson("/api/runs"),
    apiJson("/api/git-status"),
  ]);
  renderConfig(cfg);
  state.runs = runs;
  renderRunsList();
  renderGitOverview(gitInfo);
}

async function loadRun(runId) {
  try {
    const run = await apiJson(`/api/runs/${runId}`);
    renderActiveRun(run);
    setStatus(`Loaded run ${run.id}.`);
  } catch (err) {
    setError(`Failed to load run: ${err.message}`);
  }
}

function switchTab(selectedTab) {
  const tabs = document.querySelectorAll('[role="tab"]');
  for (const tab of tabs) {
    const isSelected = tab === selectedTab;
    tab.setAttribute("aria-selected", isSelected ? "true" : "false");
    const panel = document.getElementById(tab.dataset.panel);
    if (panel) {
      panel.hidden = !isSelected;
    }
  }
}

document.querySelectorAll('[role="tab"]').forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab));
});

document.getElementById("new-run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("create-run-btn");
  btn.disabled = true;
  try {
    const formData = new FormData(e.currentTarget);
    const run = await apiJson("/api/runs", {
      method: "POST",
      body: JSON.stringify({
        title: String(formData.get("title") || ""),
        prompt: String(formData.get("prompt") || ""),
      }),
    });
    e.currentTarget.reset();
    await refreshAll();
    renderActiveRun(run);
    setStatus(`Created AI SDLC run '${run.title}'. Run Stage 1 (Intake) to start.`);
  } catch (err) {
    setError(err.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("refresh-runs-btn").addEventListener("click", () => {
  refreshAll().catch((err) => setError(err.message));
});

document.querySelectorAll(".stage-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!state.activeRun) return;
    const stage = btn.dataset.stage;
    btn.disabled = true;
    setStatus(`Calling LLM for stage '${stage}'...`);
    try {
      const guidanceMap = {
        intake: document.getElementById("intake-guidance").value,
        spec: document.getElementById("spec-guidance").value,
        architect: document.getElementById("architect-guidance").value,
        tdd_tests: document.getElementById("tdd-guidance").value,
        implement: document.getElementById("tdd-guidance").value,
      };
      const updated = await apiJson(`/api/runs/${state.activeRun.id}/stages/${stage}`, {
        method: "POST",
        body: JSON.stringify({ guidance: guidanceMap[stage] || "" }),
      });
      renderActiveRun(updated);
      setStatus(`Completed stage '${stage}'. Review output and pending patches.`);
    } catch (err) {
      setError(`Stage '${stage}' error: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  });
});

document.getElementById("approve-spec-btn").addEventListener("click", async () => {
  if (!state.activeRun) return;
  try {
    const updated = await apiJson(`/api/runs/${state.activeRun.id}/approve-spec`, {
      method: "POST",
      body: "{}",
    });
    renderActiveRun(updated);
    setStatus("Spec approved. Architect and TDD stages are now unlocked.");
  } catch (err) {
    setError(err.message);
  }
});

document.getElementById("apply-all-patches-btn").addEventListener("click", async () => {
  if (!state.activeRun) return;
  const selected = Array.from(document.querySelectorAll(".patch-select:checked")).map((cb) => cb.value);
  if (!selected.length) {
    setError("Select at least one patch checkbox to apply.");
    return;
  }
  try {
    const res = await apiJson(`/api/runs/${state.activeRun.id}/apply`, {
      method: "POST",
      body: JSON.stringify({ paths: selected }),
    });
    renderActiveRun(res.run);
    await refreshAll();
    setStatus(`Applied ${res.applied_paths.length} file(s) safely after hygiene checks.`);
  } catch (err) {
    setError(`Apply rejected: ${err.message}`);
  }
});

document.getElementById("run-gates-btn").addEventListener("click", async () => {
  if (!state.activeRun) return;
  const selected = Array.from(document.querySelectorAll('input[name="gate"]:checked')).map((c) => c.value);
  if (!selected.length) {
    setError("Choose at least one verification gate.");
    return;
  }
  const btn = document.getElementById("run-gates-btn");
  btn.disabled = true;
  setStatus(`Running gates: ${selected.join(", ")}...`);
  try {
    const updated = await apiJson(`/api/runs/${state.activeRun.id}/gates`, {
      method: "POST",
      body: JSON.stringify({ gates: selected }),
    });
    renderActiveRun(updated);
    setStatus("Verification gate run finished.");
  } catch (err) {
    setError(err.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("ai-fix-btn").addEventListener("click", async () => {
  if (!state.activeRun) return;
  const failed = [...(state.activeRun.gate_results || [])].reverse().find((g) => !g.passed);
  if (!failed) {
    setError("No failing gate output recorded on this run.");
    return;
  }
  const btn = document.getElementById("ai-fix-btn");
  btn.disabled = true;
  setStatus(`Sending failing '${failed.gate}' log to AI Fixer...`);
  try {
    const updated = await apiJson(`/api/runs/${state.activeRun.id}/stages/fix_failure`, {
      method: "POST",
      body: JSON.stringify({ failing_output: `${failed.command}\n\n${failed.output}` }),
    });
    renderActiveRun(updated);
    switchTab(document.getElementById("tab-patches"));
    setStatus("AI Fixer generated patch candidates in Pending File Patches.");
  } catch (err) {
    setError(err.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("create-issue-btn").addEventListener("click", async () => {
  if (!state.activeRun) return;
  try {
    const updated = await apiJson(`/api/runs/${state.activeRun.id}/issue`, {
      method: "POST",
      body: "{}",
    });
    renderActiveRun(updated);
    setStatus(`Created GitHub Issue #${updated.issue_number}.`);
  } catch (err) {
    setError(`GitHub issue creation failed: ${err.message}`);
  }
});

document.getElementById("branch-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.activeRun) return;
  const branchName = new FormData(e.currentTarget).get("branch_name");
  try {
    const updated = await apiJson(`/api/runs/${state.activeRun.id}/branch`, {
      method: "POST",
      body: JSON.stringify({ branch_name: String(branchName || "") }),
    });
    renderActiveRun(updated);
    await refreshAll();
    setStatus(`Switched to branch '${updated.branch_name}'.`);
  } catch (err) {
    setError(err.message);
  }
});

document.getElementById("commit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.activeRun) return;
  const fd = new FormData(e.currentTarget);
  try {
    await apiJson(`/api/runs/${state.activeRun.id}/commit`, {
      method: "POST",
      body: JSON.stringify({
        message: String(fd.get("message") || ""),
        agent_role: String(fd.get("agent_role") || "devops-agent"),
      }),
    });
    await refreshAll();
    setStatus("Committed changes with Agent and Refs trailers.");
  } catch (err) {
    setError(err.message);
  }
});

document.getElementById("pr-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.activeRun) return;
  const fd = new FormData(e.currentTarget);
  try {
    const updated = await apiJson(`/api/runs/${state.activeRun.id}/pr`, {
      method: "POST",
      body: JSON.stringify({
        title: String(fd.get("title") || ""),
        close_issue: Boolean(fd.get("close_issue")),
      }),
    });
    renderActiveRun(updated);
    setStatus(`Pull request opened: ${updated.pr_url}`);
  } catch (err) {
    setError(err.message);
  }
});

document.getElementById("run-cli-btn").addEventListener("click", async () => {
  if (!state.activeRun) return;
  const instruction = document.getElementById("cli-instruction").value.trim();
  if (!instruction) {
    setError("Enter an instruction for the headless Gemini CLI runner.");
    return;
  }
  const btn = document.getElementById("run-cli-btn");
  btn.disabled = true;
  setStatus("Running local Gemini CLI in workspace...");
  try {
    const updated = await apiJson(`/api/runs/${state.activeRun.id}/agent-cli`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    });
    renderActiveRun(updated);
    await refreshAll();
    setStatus("Headless Gemini CLI execution finished.");
  } catch (err) {
    setError(err.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("open-settings-btn").addEventListener("click", () => {
  el.settingsDialog.showModal();
});

el.toggleKeyBtn.addEventListener("click", () => {
  const show = el.cfgApiKey.type === "password";
  el.cfgApiKey.type = show ? "text" : "password";
  el.toggleKeyBtn.setAttribute("aria-pressed", String(show));
  el.toggleKeyBtn.textContent = show ? "Hide" : "Show";
});

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  if (e.submitter?.getAttribute("formmethod") === "dialog") {
    return;
  }
  e.preventDefault();
  try {
    const cfg = await apiJson("/api/config", {
      method: "PUT",
      body: JSON.stringify({
        llm_provider: el.cfgProvider.value,
        llm_model: el.cfgModel.value,
        openai_base_url: el.cfgBaseUrl.value,
        api_key: el.cfgApiKey.value || null,
      }),
    });
    el.cfgApiKey.value = "";
    renderConfig(cfg);
    el.settingsDialog.close();
    setStatus(`Saved LLM configuration (${cfg.llm_provider} / ${cfg.llm_model}).`);
  } catch (err) {
    setError(`Failed to save API settings: ${err.message}`);
  }
});

refreshAll().catch((err) => setError(`Startup check failed: ${err.message}`));
