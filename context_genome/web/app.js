const $ = (selector) => document.querySelector(selector);

const ui = {
  grid: $("#grid"),
  presetSelect: $("#presetSelect"),
  seedInput: $("#seedInput"),
  agentModeSelect: $("#agentModeSelect"),
  resetBtn: $("#resetBtn"),
  stepBtn: $("#stepBtn"),
  playBtn: $("#playBtn"),
  exportBtn: $("#exportBtn"),
  speedInput: $("#speedInput"),
  speedValue: $("#speedValue"),
  widthInput: $("#widthInput"),
  heightInput: $("#heightInput"),
  initialCellEnergyInput: $("#initialCellEnergyInput"),
  initialCellMineralInput: $("#initialCellMineralInput"),
  radiationInput: $("#radiationInput"),
  initialOrgsInput: $("#initialOrgsInput"),
  initialOrgEnergyInput: $("#initialOrgEnergyInput"),
  maxActivePerCellInput: $("#maxActivePerCellInput"),
  conflictToggle: $("#conflictToggle"),
  deleteToggle: $("#deleteToggle"),
  mutationToggle: $("#mutationToggle"),
  disasterToggle: $("#disasterToggle"),
  regenInput: $("#regenInput"),
  maintenanceInput: $("#maintenanceInput"),
  stopExtinctToggle: $("#stopExtinctToggle"),
  stopMaxTickInput: $("#stopMaxTickInput"),
  stopRuntimeInput: $("#stopRuntimeInput"),
  stopStableInput: $("#stopStableInput"),
  stopDominanceInput: $("#stopDominanceInput"),
  llmModelInput: $("#llmModelInput"),
  llmBaseUrlInput: $("#llmBaseUrlInput"),
  llmApiKeyInput: $("#llmApiKeyInput"),
  saveRuntimeBtn: $("#saveRuntimeBtn"),
  clearRuntimeKeyBtn: $("#clearRuntimeKeyBtn"),
  llmCapInput: $("#llmCapInput"),
  llmTokenBudgetInput: $("#llmTokenBudgetInput"),
  llmTempInput: $("#llmTempInput"),
  seedTemplate: $("#seedTemplate"),
  seedText: $("#seedText"),
  spawnLabel: $("#spawnLabel"),
  spawnBtn: $("#spawnBtn"),
  skillEditor: $("#skillEditor"),
  saveSkillBtn: $("#saveSkillBtn"),
  removeOrgBtn: $("#removeOrgBtn"),
  inspectorStatus: $("#inspectorStatus"),
  inspectorSummary: $("#inspectorSummary"),
  refreshInspectorBtn: $("#refreshInspectorBtn"),
  inspectorPrompt: $("#inspectorPrompt"),
  inspectorResponse: $("#inspectorResponse"),
  inspectorAction: $("#inspectorAction"),
  reportBtn: $("#reportBtn"),
  reportStatus: $("#reportStatus"),
  reportOutput: $("#reportOutput"),
  runSelect: $("#runSelect"),
  loadRunBtn: $("#loadRunBtn"),
  resultStatus: $("#resultStatus"),
  resultCurrent: $("#resultCurrent"),
  resultCompareStatus: $("#resultCompareStatus"),
  resultRunASelect: $("#resultRunASelect"),
  resultRunBSelect: $("#resultRunBSelect"),
  refreshResultsBtn: $("#refreshResultsBtn"),
  experimentTemplateStatus: $("#experimentTemplateStatus"),
  experimentTemplateHint: $("#experimentTemplateHint"),
  experimentButtons: [...document.querySelectorAll("[data-experiment]")],
  tabButtons: [...document.querySelectorAll("[data-tab]")],
  tabPanels: [...document.querySelectorAll("[data-tab-panel]")],
};

const EXPERIMENT_TEMPLATES = {
  quick: {
    label: "Quick Smoke",
    preset: "sandbox",
    agent: "rule",
    values: {
      speed: 5,
      width: 12,
      height: 12,
      initialOrgs: 8,
      initialCellEnergy: 100,
      initialCellMineral: 45,
      radiation: 0.002,
      initialOrgEnergy: 55,
      maxActivePerCell: 4,
      conflict: 0,
      delete: 0,
      mutation: 0,
      disaster: 0,
      regen: 6,
      maintenance: 0.8,
      llmCap: 0,
      llmBudget: 1000000,
      temperature: 0.2,
    },
    hint: "Rule-agent smoke test. Reset, then Step or Play to validate ecology without model cost.",
  },
  lowcost: {
    label: "Low-Cost LLM",
    preset: "sandbox",
    agent: "llm_json",
    values: {
      speed: 1,
      width: 12,
      height: 12,
      initialOrgs: 4,
      initialCellEnergy: 110,
      initialCellMineral: 45,
      radiation: 0.002,
      initialOrgEnergy: 55,
      maxActivePerCell: 3,
      conflict: 0,
      delete: 0,
      mutation: 0,
      disaster: 0,
      regen: 4.5,
      maintenance: 0.9,
      llmCap: 4,
      llmBudget: 1000000,
      temperature: 0.15,
    },
    hint: "Small LLM run for behavior checks. Keep Play short and watch the token budget card.",
  },
  pressure: {
    label: "Selection Pressure",
    preset: "wild",
    agent: "llm_json",
    values: {
      speed: 2,
      width: 16,
      height: 16,
      initialOrgs: 18,
      initialCellEnergy: 85,
      initialCellMineral: 55,
      radiation: 0.015,
      initialOrgEnergy: 50,
      maxActivePerCell: 3,
      conflict: 1,
      delete: 1,
      mutation: 1.2,
      disaster: 3,
      regen: 3.5,
      maintenance: 1.05,
      llmCap: 8,
      llmBudget: 10000000,
      temperature: 0.25,
    },
    hint: "Evolution pressure preset. Reset to seed a competitive world with mutation and disasters.",
  },
  cache: {
    label: "Cache Study",
    preset: "tournament",
    agent: "llm_json",
    values: {
      speed: 1,
      width: 14,
      height: 14,
      initialOrgs: 8,
      initialCellEnergy: 100,
      initialCellMineral: 50,
      radiation: 0.002,
      initialOrgEnergy: 58,
      maxActivePerCell: 3,
      conflict: 0,
      delete: 0,
      mutation: 0,
      disaster: 0,
      regen: 4,
      maintenance: 0.9,
      llmCap: 6,
      llmBudget: 5000000,
      temperature: 0.05,
    },
    hint: "Stable prompt-cache study. Compare cache hit after short, repeated Step runs.",
  },
};

let state = null;
let presets = null;
let selectedCell = { x: 0, y: 0 };
let selectedOrgId = null;
let playing = false;
let playTimer = null;
let playStartedAt = 0;
let busy = false;
let runs = [];
let activeTab = "tune";

async function api(path, body = null) {
  const options = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    : {};
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

async function init() {
  presets = await api("/api/presets");
  fillPresetControls();
  state = await api("/api/state");
  await refreshRuns();
  syncSwitchesFromState();
  renderState();
  await refreshCell();
  bindEvents();
}

function fillPresetControls() {
  ui.presetSelect.innerHTML = "";
  Object.entries(presets.presets).forEach(([name, config]) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = `${name} - ${config.ecology_label}`;
    ui.presetSelect.append(option);
  });
  ui.agentModeSelect.innerHTML = "";
  Object.entries(presets.agent_modes).forEach(([mode, info]) => {
    const option = document.createElement("option");
    option.value = mode;
    option.textContent = info.label;
    option.title = info.description;
    ui.agentModeSelect.append(option);
  });
  ui.llmModelInput.value = presets.llm_runtime?.model || "";
  ui.llmBaseUrlInput.value = presets.llm_runtime?.base_url || "";
  ui.llmApiKeyInput.value = "";
  renderLlmStatus();
  fillSeedTemplates("sandbox");
}

function fillSeedTemplates(presetName) {
  const seeds = presets.seed_skills[presetName] || presets.seed_skills.sandbox;
  ui.seedTemplate.innerHTML = "";
  seeds.forEach(([label, text], index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = label;
    ui.seedTemplate.append(option);
  });
  ui.seedText.value = seeds[0]?.[1] || presets.default_skill;
}

function bindEvents() {
  ui.tabButtons.forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });
  ui.experimentButtons.forEach((button) => {
    button.addEventListener("click", () => applyExperimentTemplate(button.dataset.experiment));
  });

  ui.presetSelect.addEventListener("change", () => {
    const name = ui.presetSelect.value;
    const config = presets.presets[name];
    applyConfigToControls(config);
    fillSeedTemplates(name);
  });

  ui.seedTemplate.addEventListener("change", () => {
    const seeds = presets.seed_skills[ui.presetSelect.value] || presets.seed_skills.sandbox;
    ui.seedText.value = seeds[Number(ui.seedTemplate.value)]?.[1] || presets.default_skill;
  });

  ui.llmModelInput.addEventListener("input", renderLlmStatus);
  ui.llmModelInput.addEventListener("change", applyLiveConfig);
  ui.llmBaseUrlInput.addEventListener("input", renderLlmStatus);
  ui.llmApiKeyInput.addEventListener("input", renderLlmStatus);
  ui.saveRuntimeBtn.addEventListener("click", () => saveLlmRuntime(false));
  ui.clearRuntimeKeyBtn.addEventListener("click", () => saveLlmRuntime(true));

  ui.resetBtn.addEventListener("click", async () => {
    stopPlaying();
    const payload = {
      preset: ui.presetSelect.value,
      seed: ui.seedInput.value,
      overrides: resetOverrides(),
    };
    state = await api("/api/reset", payload);
    selectedCell = { x: 0, y: 0 };
    selectedOrgId = null;
    renderState();
    await refreshCell();
    clearOrgEditor();
  });

  ui.stepBtn.addEventListener("click", async () => {
    await tick(Number(ui.speedInput.value));
  });

  ui.agentModeSelect.addEventListener("change", applyLiveConfig);
  [
    ui.speedInput,
    ui.widthInput,
    ui.heightInput,
    ui.initialCellEnergyInput,
    ui.initialCellMineralInput,
    ui.radiationInput,
    ui.initialOrgsInput,
    ui.initialOrgEnergyInput,
    ui.maxActivePerCellInput,
  ].forEach((input) => {
    input.addEventListener("input", renderControlValues);
  });

  [
    ui.conflictToggle,
    ui.deleteToggle,
    ui.mutationToggle,
    ui.disasterToggle,
    ui.regenInput,
    ui.maintenanceInput,
    ui.stopExtinctToggle,
    ui.stopMaxTickInput,
    ui.stopRuntimeInput,
    ui.stopStableInput,
    ui.stopDominanceInput,
    ui.llmCapInput,
    ui.llmTokenBudgetInput,
    ui.llmTempInput,
  ].filter(Boolean).forEach((input) => {
    input.addEventListener("input", renderControlValues);
    input.addEventListener("change", applyLiveConfig);
  });

  ui.playBtn.addEventListener("click", () => {
    if (playing) {
      stopPlaying();
    } else {
      startPlaying();
    }
  });

  ui.exportBtn.addEventListener("click", async () => {
    stopPlaying();
    const result = await api("/api/export", {});
    runs = result.runs || [];
    renderRuns();
    $("#exportStatus").textContent = result.summary?.run_id || "exported";
  });

  ui.loadRunBtn.addEventListener("click", async () => {
    const runId = ui.runSelect.value;
    if (!runId) return;
    stopPlaying();
    const result = await api("/api/load_run", { run_id: runId });
    state = result.state;
    selectedCell = { x: 0, y: 0 };
    selectedOrgId = null;
    syncSwitchesFromState();
    renderState();
    await refreshCell();
    clearOrgEditor();
    $("#exportStatus").textContent = `loaded ${runId}`;
  });

  ui.spawnBtn.addEventListener("click", async () => {
    const payload = {
      x: selectedCell.x,
      y: selectedCell.y,
      label: ui.spawnLabel.value || "Researcher Context",
      skill_text: ui.seedText.value,
    };
    const result = await api("/api/spawn", payload);
    state = result.state;
    renderState();
    await refreshCell();
  });

  ui.saveSkillBtn.addEventListener("click", async () => {
    if (!selectedOrgId) return;
    const result = await api("/api/edit_skill", {
      org_id: selectedOrgId,
      skill_text: ui.skillEditor.value,
    });
    state = result.state;
    renderState();
    await refreshCell();
    await loadOrg(selectedOrgId);
  });

  ui.removeOrgBtn.addEventListener("click", async () => {
    if (!selectedOrgId) return;
    const result = await api("/api/delete_org", { org_id: selectedOrgId });
    state = result.state;
    selectedOrgId = null;
    renderState();
    await refreshCell();
    clearOrgEditor();
  });

  ui.reportBtn.addEventListener("click", generateReport);
  ui.refreshInspectorBtn?.addEventListener("click", () => {
    if (selectedOrgId) refreshInspector(selectedOrgId);
  });
  ui.refreshResultsBtn?.addEventListener("click", refreshRuns);
  ui.resultRunASelect?.addEventListener("change", renderResults);
  ui.resultRunBSelect?.addEventListener("change", renderResults);
}

function activateTab(tabName, reveal = false) {
  if (!tabName) return;
  activeTab = tabName;
  ui.tabButtons.forEach((button) => {
    const isActive = button.dataset.tab === tabName;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  ui.tabPanels.forEach((panel) => {
    const isActive = panel.dataset.tabPanel === tabName;
    panel.classList.toggle("is-active", isActive);
    panel.hidden = !isActive;
  });
  if (reveal && window.matchMedia("(max-width: 980px)").matches) {
    document.querySelector(".side-pane")?.scrollIntoView({ block: "start", behavior: "smooth" });
  }
}

function liveOverrides() {
  const mutationRate = Number(ui.mutationToggle.value || 0) / 100;
  const disasterChance = Number(ui.disasterToggle.value || 0) / 100;
  return {
    allow_conflict: Number(ui.conflictToggle.value || 0) >= 1,
    allow_delete: Number(ui.deleteToggle.value || 0) >= 1,
    enable_mutation: mutationRate > 0,
    enable_disasters: disasterChance > 0,
    base_mutation_rate: mutationRate,
    event_chance_per_tick: disasterChance,
    energy_regen_per_tick: Number(ui.regenInput.value || 0),
    base_maintenance: Number(ui.maintenanceInput.value || 1),
    agent_mode: ui.agentModeSelect.value,
    llm_model: ui.llmModelInput.value.trim(),
    llm_temperature: Number(ui.llmTempInput.value || 0.2),
    max_llm_calls_per_tick: Number(ui.llmCapInput.value || 8),
    llm_token_budget: Number(ui.llmTokenBudgetInput.value || 0),
  };
}

function resetOverrides() {
  return {
    ...liveOverrides(),
    world_width: Number(ui.widthInput.value || 16),
    world_height: Number(ui.heightInput.value || 16),
    initial_cell_energy: Number(ui.initialCellEnergyInput.value || 80),
    initial_cell_mineral: Number(ui.initialCellMineralInput.value || 40),
    radiation_default: Number(ui.radiationInput.value || 0),
    initial_orgs: Number(ui.initialOrgsInput.value || 0),
    initial_org_energy: Number(ui.initialOrgEnergyInput.value || 42),
    max_active_per_cell: Number(ui.maxActivePerCellInput.value || 4),
  };
}

function syncSwitchesFromState() {
  ui.presetSelect.value = state.config.name;
  applyConfigToControls(state.config);
  ui.agentModeSelect.value = state.config.agent_mode || "llm_json";
  ui.llmModelInput.value = state.config.llm_model || presets.llm_runtime?.model || "";
  ui.llmTempInput.value = state.config.llm_temperature ?? 0.2;
  ui.llmCapInput.value = state.config.max_llm_calls_per_tick ?? 8;
  ui.llmTokenBudgetInput.value = state.config.llm_token_budget ?? 10000000;
  renderLlmStatus();
  renderControlValues();
  fillSeedTemplates(state.config.name);
}

function applyConfigToControls(config) {
  ui.conflictToggle.value = config.allow_conflict ? "1" : "0";
  ui.deleteToggle.value = config.allow_delete ? "1" : "0";
  ui.mutationToggle.value = config.enable_mutation ? percentValue(config.base_mutation_rate, 0.5) : "0";
  ui.disasterToggle.value = config.enable_disasters ? percentValue(config.event_chance_per_tick, 0) : "0";
  ui.regenInput.value = config.energy_regen_per_tick ?? 5;
  ui.maintenanceInput.value = config.base_maintenance ?? 1;
  ui.widthInput.value = config.world_width ?? config.width ?? 16;
  ui.heightInput.value = config.world_height ?? config.height ?? 16;
  ui.initialCellEnergyInput.value = config.initial_cell_energy ?? 80;
  ui.initialCellMineralInput.value = config.initial_cell_mineral ?? 40;
  ui.radiationInput.value = config.radiation_default ?? 0;
  ui.initialOrgsInput.value = config.initial_orgs ?? 6;
  ui.initialOrgEnergyInput.value = config.initial_org_energy ?? 42;
  ui.maxActivePerCellInput.value = config.max_active_per_cell ?? 4;
  ui.llmTokenBudgetInput.value = config.llm_token_budget ?? 10000000;
  renderControlValues();
}

async function applyExperimentTemplate(key) {
  const template = EXPERIMENT_TEMPLATES[key];
  if (!template || !presets) return;
  stopPlaying();
  if (template.preset && presets.presets[template.preset]) {
    ui.presetSelect.value = template.preset;
    applyConfigToControls(presets.presets[template.preset]);
    fillSeedTemplates(template.preset);
  }
  if (template.agent) ui.agentModeSelect.value = template.agent;
  const values = template.values || {};
  setControlValue(ui.speedInput, values.speed);
  setControlValue(ui.widthInput, values.width);
  setControlValue(ui.heightInput, values.height);
  setControlValue(ui.initialOrgsInput, values.initialOrgs);
  setControlValue(ui.initialCellEnergyInput, values.initialCellEnergy);
  setControlValue(ui.initialCellMineralInput, values.initialCellMineral);
  setControlValue(ui.radiationInput, values.radiation);
  setControlValue(ui.initialOrgEnergyInput, values.initialOrgEnergy);
  setControlValue(ui.maxActivePerCellInput, values.maxActivePerCell);
  setControlValue(ui.conflictToggle, values.conflict);
  setControlValue(ui.deleteToggle, values.delete);
  setControlValue(ui.mutationToggle, values.mutation);
  setControlValue(ui.disasterToggle, values.disaster);
  setControlValue(ui.regenInput, values.regen);
  setControlValue(ui.maintenanceInput, values.maintenance);
  setControlValue(ui.llmCapInput, values.llmCap);
  setControlValue(ui.llmTokenBudgetInput, values.llmBudget);
  setControlValue(ui.llmTempInput, values.temperature);
  renderControlValues();
  renderLlmStatus();
  ui.experimentTemplateStatus.textContent = template.label;
  ui.experimentTemplateHint.textContent = template.hint;
  await applyLiveConfig();
}

function setControlValue(input, value) {
  if (value !== undefined && value !== null) {
    input.value = String(value);
  }
}

function percentValue(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? String(number * 100) : String(fallback);
}

function renderControlValues() {
  $("#speedValue").textContent = ui.speedInput.value;
  $("#widthValue").textContent = ui.widthInput.value;
  $("#heightValue").textContent = ui.heightInput.value;
  $("#initialCellEnergyValue").textContent = ui.initialCellEnergyInput.value;
  $("#initialCellMineralValue").textContent = ui.initialCellMineralInput.value;
  $("#radiationValue").textContent = Number(ui.radiationInput.value || 0).toFixed(3);
  $("#initialOrgsValue").textContent = ui.initialOrgsInput.value;
  $("#initialOrgEnergyValue").textContent = ui.initialOrgEnergyInput.value;
  $("#maxActivePerCellValue").textContent = ui.maxActivePerCellInput.value;
  $("#conflictValue").textContent = Number(ui.conflictToggle.value || 0) >= 1 ? "on" : "off";
  $("#deleteValue").textContent = Number(ui.deleteToggle.value || 0) >= 1 ? "on" : "off";
  $("#mutationValue").textContent = `${Number(ui.mutationToggle.value || 0).toFixed(1)}%`;
  $("#disasterValue").textContent = `${Number(ui.disasterToggle.value || 0).toFixed(1)}%`;
  $("#regenValue").textContent = Number(ui.regenInput.value || 0).toFixed(2);
  $("#maintenanceValue").textContent = Number(ui.maintenanceInput.value || 0).toFixed(2);
  setText("#stopExtinctValue", Number(controlValue(ui.stopExtinctToggle, 0)) >= 1 ? "on" : "off");
  setText("#stopMaxTickValue", stopLabel(controlValue(ui.stopMaxTickInput, 0), "t"));
  setText("#stopRuntimeValue", stopLabel(controlValue(ui.stopRuntimeInput, 0), "min"));
  setText("#stopStableValue", stopLabel(controlValue(ui.stopStableInput, 0), "t"));
  setText("#stopDominanceValue", stopLabel(controlValue(ui.stopDominanceInput, 0), "%"));
  $("#llmCapValue").textContent = ui.llmCapInput.value;
  $("#llmTokenBudgetValue").textContent = formatBudgetLabel(Number(ui.llmTokenBudgetInput.value || 0));
  $("#llmTempValue").textContent = Number(ui.llmTempInput.value || 0).toFixed(2);
}

function renderLlmStatus() {
  const runtime = presets?.llm_runtime || {};
  const hasKey = Boolean(runtime.has_api_key);
  const hasModel = Boolean(ui.llmModelInput.value.trim() || runtime.model);
  const hasUnsavedKey = Boolean(ui.llmApiKeyInput.value.trim());
  const status = $("#llmRuntimeStatus");
  $("#llmRuntimePanel")?.classList.toggle("needs-key", !hasKey);
  if (hasKey && hasModel) {
    status.textContent = "configured";
  } else if (hasUnsavedKey && hasModel) {
    status.textContent = "save key";
  } else if (!hasKey && !hasModel) {
    status.textContent = "missing key + model";
  } else if (!hasKey) {
    status.textContent = "missing key";
  } else {
    status.textContent = "missing model";
  }
  ui.llmApiKeyInput.placeholder = hasKey ? "stored; paste new key to replace" : "paste key to save in memory";
  $("#runtimeSecretStatus").textContent = hasKey ? "key available / hidden" : "key not saved";
}

async function tick(steps = 1) {
  if (busy) return;
  busy = true;
  try {
    state = await api("/api/tick", { steps, overrides: liveOverrides() });
    renderState();
    await refreshCell();
    if (selectedOrgId) {
      await loadOrg(selectedOrgId, false);
    }
  } finally {
    busy = false;
  }
}

async function applyLiveConfig() {
  if (busy || !state) return;
  state = await api("/api/config", { overrides: liveOverrides() });
  renderState();
}

async function saveLlmRuntime(clearKey = false) {
  if (busy || !state) return;
  busy = true;
  ui.saveRuntimeBtn.disabled = true;
  ui.clearRuntimeKeyBtn.disabled = true;
  $("#runtimeSecretStatus").textContent = clearKey ? "clearing" : "saving";
  try {
    const result = await api("/api/llm_runtime", {
      base_url: ui.llmBaseUrlInput.value.trim(),
      api_key: clearKey ? "" : ui.llmApiKeyInput.value.trim(),
      clear_api_key: clearKey,
      overrides: liveOverrides(),
    });
    if (result.llm_runtime) {
      presets.llm_runtime = result.llm_runtime;
      ui.llmBaseUrlInput.value = result.llm_runtime.base_url || ui.llmBaseUrlInput.value.trim();
    }
    if (result.state) {
      state = result.state;
    }
    ui.llmApiKeyInput.value = "";
    renderLlmStatus();
    renderState();
  } catch (error) {
    $("#llmRuntimeStatus").textContent = "save failed";
    $("#runtimeSecretStatus").textContent = error.message;
  } finally {
    ui.saveRuntimeBtn.disabled = false;
    ui.clearRuntimeKeyBtn.disabled = false;
    busy = false;
  }
}

async function generateReport() {
  if (busy || !state) return;
  stopPlaying();
  busy = true;
  ui.reportBtn.disabled = true;
  ui.reportStatus.textContent = "summarizing";
  ui.reportOutput.textContent = "Generating bilingual ecology report...";
  try {
    const result = await api("/api/report", { overrides: liveOverrides() });
    if (result.state) {
      state = result.state;
      renderState();
    }
    ui.reportStatus.textContent = result.usage
      ? `${formatCompactNumber(result.usage.total_tokens || 0)} tokens`
      : "generated";
    ui.reportOutput.textContent = result.report || "The model returned an empty report.";
  } catch (error) {
    ui.reportStatus.textContent = "failed";
    ui.reportOutput.textContent = `Report failed: ${error.message}`;
  } finally {
    ui.reportBtn.disabled = false;
    busy = false;
  }
}

function startPlaying() {
  const stopReason = automaticStopReason(isTokenBudgetExhausted());
  if (stopReason) {
    renderState();
    return;
  }
  playing = true;
  playStartedAt = Date.now();
  ui.playBtn.textContent = "Pause";
  ui.playBtn.classList.add("is-playing");
  playTimer = setInterval(() => tick(Number(ui.speedInput.value)), 520);
}

function stopPlaying() {
  playing = false;
  playStartedAt = 0;
  ui.playBtn.textContent = "Play";
  ui.playBtn.classList.remove("is-playing");
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
}

function renderState() {
  if (!state) return;
  $("#ecologyLabel").textContent = state.config.ecology_label;
  const cellCount = Math.max(1, state.config.width * state.config.height);
  const occupiedCells = state.cells.filter((cell) => cell.org_count > 0).length;
  const corpseCells = state.cells.filter((cell) => cell.corpse_count > 0).length;
  const recentPop = state.history?.at(-8)?.population ?? state.stats.population;
  const populationDelta = state.stats.population - recentPop;
  const avgCellEnergy = state.stats.total_cell_energy / cellCount;
  $("#tickStat").textContent = state.tick;
  $("#popStat").textContent = state.stats.population;
  $("#lineageStat").textContent = state.stats.lineages;
  $("#diversityStat").textContent = state.stats.diversity.toFixed(2);
  $("#integrityStat").textContent = `${Math.round(state.stats.avg_integrity * 100)}%`;
  $("#energyStat").textContent = Math.round(state.stats.total_cell_energy);
  const tokenBudgetExhausted = isTokenBudgetExhausted();
  const stopReason = automaticStopReason(tokenBudgetExhausted);
  if (stopReason && playing) {
    stopPlaying();
  }
  $("#tickSub").textContent = stopReason
    ? stopReason
    : state.stats.llm_pending
      ? `${state.stats.llm_pending} pending`
      : playing
        ? "playing"
        : "ready";
  $("#popSub").textContent = `${formatSigned(populationDelta)} in window / ${state.stats.corpses} corpses`;
  $("#lineageSub").textContent = `${state.stats.births} births / ${state.stats.deaths} deaths`;
  $("#diversitySub").textContent = `${occupiedCells} occupied cells`;
  $("#integritySub").textContent = corpseCells ? `${corpseCells} corpse cells` : "no corpse cells";
  $("#energySub").textContent = `avg ${avgCellEnergy.toFixed(1)} / cell`;
  const cacheHitTokens = state.stats.llm_prompt_cache_hit_tokens || 0;
  const cacheMissTokens = state.stats.llm_prompt_cache_miss_tokens || 0;
  const cacheTotalTokens = cacheHitTokens + cacheMissTokens;
  const cacheHitRate = cacheTotalTokens > 0 ? cacheHitTokens / cacheTotalTokens : 0;
  const recentUsage = state.events
    .map((event) => event.data?.usage)
    .filter(Boolean);
  const recentCacheHitTokens = recentUsage.reduce((sum, usage) => sum + (usage.prompt_cache_hit_tokens || 0), 0);
  const recentCacheMissTokens = recentUsage.reduce((sum, usage) => sum + (usage.prompt_cache_miss_tokens || 0), 0);
  const recentCacheTotalTokens = recentCacheHitTokens + recentCacheMissTokens;
  const recentCacheHitRate = recentCacheTotalTokens > 0 ? recentCacheHitTokens / recentCacheTotalTokens : cacheHitRate;
  const tokenBudget = state.stats.llm_token_budget || state.config.llm_token_budget || 0;
  const totalTokens = state.stats.llm_total_tokens || 0;
  const budgetPercent = tokenBudget > 0 ? Math.min(100, Math.round((totalTokens / tokenBudget) * 100)) : 0;
  $("#tokenStat").textContent = formatCompactNumber(totalTokens);
  $("#tokenStat").title = `${state.stats.llm_pending || 0} pending / ${formatCompactNumber(cacheHitTokens)} cache hit / ${formatCompactNumber(cacheMissTokens)} cache miss / budget ${tokenBudget ? formatCompactNumber(tokenBudget) : "off"}`;
  $("#tokenSub").textContent = tokenBudgetExhausted
    ? `budget ${formatCompactNumber(tokenBudget)} reached`
    : tokenBudget > 0
      ? `${budgetPercent}% of ${formatCompactNumber(tokenBudget)}${state.stats.llm_pending ? ` / ${state.stats.llm_pending} pending` : ""}`
      : `${state.stats.llm_pending || 0} pending`;
  if (ui.reportBtn) {
    ui.reportBtn.disabled = tokenBudgetExhausted;
    ui.reportBtn.title = tokenBudgetExhausted ? "Raise the token budget to generate another LLM report." : "";
  }
  $("#cacheHitStat").textContent = recentCacheTotalTokens > 0 ? `${Math.round(recentCacheHitRate * 100)}%` : "0%";
  $("#cacheHitStat").title = `recent ${formatCompactNumber(recentCacheHitTokens)} hit / ${formatCompactNumber(recentCacheMissTokens)} miss; lifetime ${Math.round(cacheHitRate * 100)}%`;
  $("#cacheSub").textContent = `life ${Math.round(cacheHitRate * 100)}%`;
  renderStopStatus(stopReason);
  const gridSummary = $("#gridSummary");
  const gridSummaryText = `${occupiedCells} occupied / ${corpseCells} corpse cells / max energy ${Math.max(...state.cells.map((cell) => cell.energy), 0).toFixed(1)}`;
  gridSummary.textContent = gridSummaryText;
  gridSummary.dataset.default = gridSummaryText;
  $("#birthDeathStat").textContent = `${state.stats.births} births / ${state.stats.deaths} deaths`;
  $("#scheduledStat").textContent = `${state.stats.scheduled_last_tick} scheduled`;
  renderGrid();
  renderSummary({ occupiedCells, corpseCells, avgCellEnergy, populationDelta, recentCacheHitRate });
  renderLineages();
  renderResults();
  renderEvents();
  drawHistory();
}

function renderSummary(metrics) {
  const topLineage = state.lineages[0];
  const recentEvents = state.events.slice(0, 36);
  const actionCounts = countBy(recentEvents.filter((event) => isActionLikeEvent(event)).map((event) => event.kind));
  const dominantAction = Object.entries(actionCounts).sort((a, b) => b[1] - a[1])[0];
  const warnings = recentEvents.filter((event) => event.severity === "warn").length;
  const pending = state.stats.llm_pending || 0;
  const bound = state.stats.llm_bound || 0;
  const activeLastTick = state.stats.llm_active_last_tick || 0;
  const leaderText = topLineage
    ? `${topLineage.lineage_id} leads with ${topLineage.population} active organisms and a ${topLineage.dominant_strategy} bias`
    : "no active lineage is currently leading";
  const phase = worldPhase(metrics.populationDelta, pending, warnings);
  $("#summaryMode").textContent = phase.label;
  $("#summaryLead").textContent = `${phase.sentence}. ${leaderText}.`;

  const bullets = [
    {
      title: "Population",
      text: `${state.stats.population} active, ${state.stats.corpses} corpses, ${formatSigned(metrics.populationDelta)} over the recent window.`,
    },
    {
      title: "Resources",
      text: `${metrics.occupiedCells} cells occupied; average cell energy is ${metrics.avgCellEnergy.toFixed(1)} with ${metrics.corpseCells} corpse-bearing cells.`,
    },
    {
      title: "LLM Loop",
      text: pending
        ? `${pending} decisions are waiting; ${activeLastTick}/${bound} bound organisms were called this tick; recent cache hit is about ${Math.round(metrics.recentCacheHitRate * 100)}%.`
        : `No pending decisions; ${activeLastTick}/${bound} bound organisms were called this tick; recent cache hit is about ${Math.round(metrics.recentCacheHitRate * 100)}%.`,
    },
    {
      title: "Behavior",
      text: dominantAction ? `Recent dominant event is ${dominantAction[0]} (${dominantAction[1]} events).` : "No recent ecological action yet.",
    },
  ];
  $("#summaryBullets").innerHTML = bullets
    .map((item) => `<div class="summary-item"><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.text)}</small></div>`)
    .join("");

  const signals = buildSignals({ ...metrics, topLineage, warnings, dominantAction, pending });
  $("#signalCount").textContent = String(signals.length);
  $("#signalList").innerHTML = signals
    .map(
      (item) => `
        <div class="signal-item" style="--signal-color:${item.color}">
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.text)}</small>
        </div>
      `,
    )
    .join("");

  const actionRows = Object.entries(actionCounts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  $("#actionSummaryCount").textContent = `${recentEvents.length} events`;
  $("#actionSummary").innerHTML = actionRows.length
    ? actionRows
        .map(
          ([kind, count]) => `
            <div class="action-chip">
              <strong>${escapeHtml(kind)}</strong>
              <em>${count}</em>
              <small>${escapeHtml(actionMeaning(kind))}</small>
            </div>
          `,
        )
        .join("")
    : `<div class="action-chip"><strong>quiet</strong><em>0</em><small>No recent actions to summarize.</small></div>`;
}

function worldPhase(populationDelta, pending, warnings) {
  if (pending > 0) {
    return { label: "deciding", sentence: "The ecology is waiting on a batch of organism decisions" };
  }
  if (populationDelta > 2) {
    return { label: "expanding", sentence: "The ecology is expanding and new copies are gaining ground" };
  }
  if (populationDelta < -2 || warnings > 8) {
    return { label: "stressed", sentence: "The ecology is under pressure from failed actions or losses" };
  }
  return { label: "steady", sentence: "The ecology is in a steady observation phase" };
}

function buildSignals({ occupiedCells, corpseCells, avgCellEnergy, topLineage, warnings, dominantAction, pending }) {
  const signals = [];
  signals.push({
    title: pending ? "LLM batch in flight" : "Decision loop clear",
    text: pending ? `${pending} organism requests are still returning.` : "Actions can resolve without waiting on a current batch.",
    color: pending ? "#5967c7" : "#168b88",
  });
  if (topLineage) {
    signals.push({
      title: "Leading lineage",
      text: `${topLineage.lineage_id} has score ${topLineage.score.toFixed(1)} and strategy ${topLineage.dominant_strategy}.`,
      color: lineageColor(topLineage.lineage_id),
    });
  }
  signals.push({
    title: "Resource field",
    text: `Average energy is ${avgCellEnergy.toFixed(1)}; ${occupiedCells} cells are currently occupied.`,
    color: avgCellEnergy > 120 ? "#3a965b" : avgCellEnergy > 70 ? "#c98b22" : "#c94f6d",
  });
  if (corpseCells > 0 || warnings > 0) {
    signals.push({
      title: "Risk markers",
      text: `${corpseCells} corpse cells and ${warnings} recent warnings.`,
      color: "#c94f6d",
    });
  }
  if (dominantAction) {
    signals.push({
      title: "Dominant action",
      text: `${dominantAction[0]} appears most often in the recent event window.`,
      color: "#60707a",
    });
  }
  return signals.slice(0, 5);
}

async function refreshRuns() {
  const payload = await api("/api/runs");
  runs = payload.runs || [];
  renderRuns();
}

function renderRuns() {
  renderRunSelect(ui.runSelect, runs, "No saved runs yet", false);
  renderRunSelect(ui.resultRunASelect, runs, "Select primary run", true);
  renderRunSelect(ui.resultRunBSelect, runs, "Select comparison run", true);
  renderResults();
}

function renderRunSelect(select, rows, emptyLabel, allowBlank) {
  if (!select) return;
  const previous = select.value;
  select.innerHTML = "";
  if (allowBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = emptyLabel;
    select.append(blank);
  }
  if (!rows.length) {
    if (!allowBlank) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = emptyLabel;
      select.append(option);
    }
    return;
  }
  rows.forEach((run) => {
    const option = document.createElement("option");
    option.value = run.run_id;
    const pop = run.stats?.population ?? 0;
    const tokens = run.stats?.llm_total_tokens ?? 0;
    option.textContent = `${run.run_id} / pop ${pop} / ${formatCompactNumber(tokens)} tokens`;
    select.append(option);
  });
  if ([...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  } else if (!allowBlank && rows[0]) {
    select.value = rows[0].run_id;
  }
}

function renderResults() {
  if (!ui.resultCurrent || !ui.resultStatus || !ui.resultComparison || !ui.resultCompareStatus || !state) return;
  ui.resultStatus.textContent = `${runs.length} saved`;
  ui.resultCurrent.innerHTML = resultCardHtml(liveResultSummary(), "Live world");
  const primary = runs.find((run) => run.run_id === ui.resultRunASelect?.value);
  const compare = runs.find((run) => run.run_id === ui.resultRunBSelect?.value);
  if (!primary) {
    ui.resultCompareStatus.textContent = "choose runs";
    ui.resultComparison.innerHTML = `<div class="empty-note">Export at least one run, then select it here to compare outcomes.</div>`;
    return;
  }
  ui.resultCompareStatus.textContent = compare ? "diff" : "single run";
  ui.resultComparison.innerHTML = `
    ${resultCardHtml(primary, "Primary")}
    ${compare ? resultCardHtml(compare, "Compare") : `<div class="empty-note">Select a second run to see metric deltas.</div>`}
    ${compare ? resultDeltaHtml(primary, compare) : ""}
  `;
}

function liveResultSummary() {
  return {
    run_id: "live",
    preset: state.config.name,
    seed: ui.seedInput.value || "current",
    tick: state.tick,
    stats: state.stats || {},
    lineages: state.lineages || [],
  };
}

function resultCardHtml(run, title) {
  const stats = run.stats || {};
  const lineages = run.lineages || [];
  const top = lineages[0];
  const cacheRate = cacheHitRateFromStats(stats);
  return `
    <article class="result-card">
      <strong>${escapeHtml(title)}</strong>
      <small>${escapeHtml(run.run_id || "run")} / ${escapeHtml(run.preset || "preset")} / seed ${escapeHtml(run.seed ?? "none")}</small>
      <div class="result-metrics">
        ${metricHtml("tick", run.tick ?? 0)}
        ${metricHtml("active", stats.population ?? 0)}
        ${metricHtml("lineages", stats.lineages ?? lineages.length ?? 0)}
        ${metricHtml("births", stats.births ?? 0)}
        ${metricHtml("deaths", stats.deaths ?? 0)}
        ${metricHtml("tokens", formatCompactNumber(stats.llm_total_tokens || 0))}
        ${metricHtml("cache", `${Math.round(cacheRate * 100)}%`)}
        ${metricHtml("integrity", `${Math.round((stats.avg_integrity || 0) * 100)}%`)}
      </div>
      <p>${top ? escapeHtml(`${top.lineage_id} leads: ${top.population} active / ${top.dominant_strategy} / score ${Number(top.score || 0).toFixed(1)}`) : "No leading lineage yet."}</p>
    </article>
  `;
}

function metricHtml(label, value) {
  return `<span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(label)}</small></span>`;
}

function resultDeltaHtml(primary, compare) {
  const a = primary.stats || {};
  const b = compare.stats || {};
  const rows = [
    ["active", a.population, b.population],
    ["lineages", a.lineages, b.lineages],
    ["births", a.births, b.births],
    ["deaths", a.deaths, b.deaths],
    ["tokens", a.llm_total_tokens, b.llm_total_tokens],
    ["cache hit", cacheHitRateFromStats(a) * 100, cacheHitRateFromStats(b) * 100],
  ];
  return `
    <article class="result-card result-delta">
      <strong>Delta</strong>
      <small>primary minus comparison</small>
      ${rows
        .map(([label, left, right]) => {
          const diff = Number(left || 0) - Number(right || 0);
          const value = label === "cache hit" ? `${formatSigned(diff.toFixed(0))}%` : formatSigned(Math.round(diff));
          return `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`;
        })
        .join("")}
    </article>
  `;
}

function cacheHitRateFromStats(stats) {
  const hit = Number(stats?.llm_prompt_cache_hit_tokens || 0);
  const miss = Number(stats?.llm_prompt_cache_miss_tokens || 0);
  return hit + miss > 0 ? hit / (hit + miss) : 0;
}

function renderGrid() {
  ui.grid.style.setProperty("--cols", state.config.width);
  const maxEnergy = Math.max(...state.cells.map((cell) => cell.energy), 1);
  const maxDirectorySize = Math.max(...state.cells.map((cell) => cell.directory_size), 1);
  const eventFlashes = buildEventFlashes();
  const fragment = document.createDocumentFragment();
  state.cells.forEach((cell) => {
    const button = document.createElement("button");
    button.className = "cell";
    if (cell.org_count > 0) button.classList.add("has-orgs");
    else button.classList.add("is-empty");
    if (cell.corpse_count > 0) button.classList.add("has-corpses");
    if (cell.entropy > 0.22) button.classList.add("is-unstable");
    if (cell.x === selectedCell.x && cell.y === selectedCell.y) {
      button.classList.add("is-selected");
    }
    const energyRatio = clamp(cell.energy / maxEnergy, 0, 1);
    const sizeRatio = clamp(cell.directory_size / maxDirectorySize, 0, 1);
    const traitColorValue = traitColor(cell.skill_trait);
    button.style.setProperty("--energy-level", `${Math.round(energyRatio * 100)}%`);
    button.style.setProperty("--energy-alpha", String(0.16 + energyRatio * 0.58));
    button.style.setProperty("--lineage-color", cell.dominant_lineage ? lineageColor(cell.dominant_lineage) : "rgba(255,255,255,0.2)");
    button.style.setProperty("--trait-color", traitColorValue);
    button.style.setProperty("--size-alpha", String(sizeRatio * 0.28));
    button.setAttribute("aria-label", cellSummaryText(cell));
    button.addEventListener("mouseenter", () => {
      $("#gridSummary").textContent = cellSummaryText(cell);
    });
    button.addEventListener("mouseleave", () => {
      const summary = $("#gridSummary");
      summary.textContent = summary.dataset.default || "";
    });
    button.addEventListener("click", async () => {
      selectedCell = { x: cell.x, y: cell.y };
      renderGrid();
      activateTab("cell", true);
      await refreshCell();
    });
    button.append(cellLayer("cell-energy"));
    button.append(cellLayer("cell-size"));
    button.append(cellLayer("cell-lineage"));
    if (cell.org_count > 0 || cell.corpse_count > 0 || (cell.x === selectedCell.x && cell.y === selectedCell.y)) {
      const trait = document.createElement("span");
      trait.className = "cell-trait";
      trait.textContent = traitInitial(cell.skill_trait);
      button.append(trait);
    }
    if (cell.org_count > 0) {
      const dots = document.createElement("span");
      dots.className = "cell-dots";
      const dotCount = Math.min(cell.org_count, 4);
      for (let i = 0; i < dotCount; i += 1) {
        dots.append(cellLayer("cell-dot"));
      }
      if (cell.org_count > 4) {
        const count = document.createElement("b");
        count.textContent = cell.org_count;
        dots.append(count);
      }
      button.append(dots);
    }
    if (cell.corpse_count > 0) {
      const corpse = document.createElement("span");
      corpse.className = "cell-corpse";
      corpse.textContent = cell.corpse_count > 1 ? String(cell.corpse_count) : "";
      button.append(corpse);
    }
    const flash = eventFlashes.get(coordKey(cell.x, cell.y));
    if (flash) {
      const marker = document.createElement("span");
      marker.className = `cell-event-flash event-${flash.kind}`;
      marker.textContent = flash.icon;
      marker.title = flash.label;
      button.append(marker);
    }
    fragment.append(button);
  });
  ui.grid.replaceChildren(fragment);
}

function cellLayer(className) {
  const element = document.createElement("span");
  element.className = className;
  return element;
}

function cellSummaryText(cell) {
  return [
    `cell ${pad(cell.x)}_${pad(cell.y)}`,
    `${cell.skill_trait || "local"}`,
    `E ${cell.energy.toFixed(1)}`,
    `${cell.org_count} orgs`,
    `${cell.corpse_count} corpses`,
    formatBytes(cell.directory_size),
    `entropy ${cell.entropy.toFixed(3)}`,
    cell.dominant_lineage || "",
  ]
    .filter(Boolean)
    .join(" / ");
}

function buildEventFlashes() {
  const flashes = new Map();
  const minTick = Math.max(0, Number(state.tick || 0) - 2);
  state.events
    .filter((event) => event.tick >= minTick)
    .slice(0, 60)
    .reverse()
    .forEach((event) => {
      const visual = eventVisual(event.kind);
      if (!visual) return;
      const coord = eventCoord(event);
      if (!coord) return;
      flashes.set(coordKey(coord.x, coord.y), {
        ...visual,
        label: `${event.kind} tick ${event.tick}`,
      });
    });
  return flashes;
}

function eventCoord(event) {
  const fields = [
    event.target,
    event.data?.target,
    event.data?.source,
    event.data?.child_id,
    event.data?.source_id,
    event.actor_id,
    event.message,
  ];
  for (const value of fields) {
    const coord = parseCoordFromText(value);
    if (coord) return coord;
  }
  return null;
}

function parseCoordFromText(value) {
  const text = String(value || "");
  let match = text.match(/\/cells\/(\d{2})_(\d{2})\//);
  if (!match) match = text.match(/\bcell\s+(\d{2})_(\d{2})\b/i);
  if (!match) match = text.match(/\b(\d{2})_(\d{2})\b/);
  if (!match) return null;
  return { x: Number(match[1]), y: Number(match[2]) };
}

function coordKey(x, y) {
  return `${x},${y}`;
}

function eventVisual(kind) {
  const visuals = {
    birth: { icon: "+", kind: "birth" },
    death: { icon: "x", kind: "death" },
    decay: { icon: "-", kind: "decay" },
    copy: { icon: "C", kind: "copy" },
    move: { icon: "M", kind: "move" },
    steal: { icon: "S", kind: "steal" },
    disaster: { icon: "!", kind: "disaster" },
    delete: { icon: "!", kind: "delete" },
    repair: { icon: "R", kind: "repair" },
    protect: { icon: "P", kind: "protect" },
    reflect: { icon: "*", kind: "reflect" },
  };
  return visuals[kind] || null;
}

function renderLineages() {
  const list = $("#lineageList");
  if (!state.lineages.length) {
    list.innerHTML = `<div class="lineage-row"><div></div><div class="row-main"><strong>No active lineages</strong><small>All runnable directories are gone.</small></div></div>`;
    return;
  }
  list.innerHTML = "";
  const maxScore = Math.max(...state.lineages.map((lineage) => lineage.score), 1);
  state.lineages.forEach((lineage) => {
    const row = document.createElement("div");
    row.className = "lineage-row";
    const scoreRatio = clamp(lineage.score / maxScore, 0, 1);
    row.innerHTML = `
      <span class="swatch" style="background:${lineageColor(lineage.lineage_id)}"></span>
      <span class="row-main">
        <strong>${lineage.lineage_id}</strong>
        <small>${lineage.dominant_strategy} / ${lineage.population} orgs / ${lineage.occupied_cells} cells / I ${Math.round(lineage.avg_integrity * 100)}%</small>
        <span class="lineage-bar"><i style="width:${Math.round(scoreRatio * 100)}%;background:${lineageColor(lineage.lineage_id)}"></i></span>
      </span>
      <span class="score-pill">${lineage.score.toFixed(1)}</span>
    `;
    list.append(row);
  });
}

function renderEvents() {
  const log = $("#eventLog");
  $("#eventCount").textContent = `${state.events.length} recent`;
  log.innerHTML = "";
  state.events.slice(0, 80).forEach((event) => {
    const row = document.createElement("div");
    row.className = `event-row ${event.severity === "warn" ? "warn" : ""}`;
    const raw = event.data?.raw || event.data?.fragment || event.data?.error || "";
    const usage = event.data?.usage;
    const cacheText = usage
      ? ` / cache ${formatCompactNumber(usage.prompt_cache_hit_tokens || 0)} hit ${formatCompactNumber(usage.prompt_cache_miss_tokens || 0)} miss`
      : "";
    const usageLine = usage
      ? `<small>tokens ${formatCompactNumber(usage.total_tokens || 0)} = ${formatCompactNumber(usage.prompt_tokens || 0)} prompt + ${formatCompactNumber(usage.completion_tokens || 0)} completion${cacheText}${usage.estimated ? " / estimated" : ""}</small>`
      : "";
    const rawBlock = raw
      ? `<pre class="event-raw">${escapeHtml(raw)}</pre>`
      : "";
    row.innerHTML = `
      <strong>${event.kind} <small>tick ${event.tick}</small></strong>
      <small>${escapeHtml(event.message)}</small>
      ${usageLine}
      ${rawBlock}
    `;
    log.append(row);
  });
}

async function refreshCell() {
  const payload = await api(`/api/cell?x=${selectedCell.x}&y=${selectedCell.y}`);
  const cell = payload.cell;
  $("#cellTitle").textContent = `Cell ${pad(cell.x)}_${pad(cell.y)}`;
  $("#cellMeta").textContent = `${cell.skill_trait || "trait"} / ${payload.organisms.length} visible`;
  renderCellMetrics(cell);
  renderLocalCellSkill(cell.skill_fragment || "");
  const list = $("#cellOrganisms");
  list.innerHTML = "";
  if (!payload.organisms.length) {
    list.innerHTML = `<div class="org-row"><strong>Empty</strong><small>Spawn a seed here or wait for copies to arrive.</small></div>`;
    return;
  }
  payload.organisms.forEach((org) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `org-row ${org.org_id === selectedOrgId ? "is-selected" : ""}`;
    row.style.setProperty("--org-lineage-color", lineageColor(org.lineage_id));
    row.innerHTML = `
      <strong>${org.org_id}</strong>
      <small>${org.strategy} / ${org.alive ? "active" : "corpse"} / E ${org.energy.toFixed(1)} / I ${Math.round(org.integrity * 100)}% / ${formatBytes(org.size)}</small>
      ${tagListHtml(org.tags || [], "mini")}
      <small>${escapeHtml(formatLlmBinding(org))}</small>
      <small>${escapeHtml(formatAbilitySummary(org.abilities || {}))}</small>
      <pre class="skill-preview">${escapeHtml(org.skill_preview || "")}</pre>
    `;
    row.addEventListener("click", async () => {
      selectedOrgId = org.org_id;
      await loadOrg(org.org_id);
      activateTab("edit", true);
      await refreshCell();
    });
    list.append(row);
  });
}

function renderCellMetrics(cell) {
  let target = $("#cellMetrics");
  if (!target) {
    target = document.createElement("div");
    target.id = "cellMetrics";
    target.className = "cell-metrics";
    $("#cellOrganisms").insertAdjacentElement("beforebegin", target);
  }
  target.innerHTML = `
    <span><strong>${cell.energy.toFixed(1)}</strong><small>energy</small></span>
    <span><strong>${cell.mineral.toFixed(1)}</strong><small>mineral</small></span>
    <span><strong>${cell.org_count}</strong><small>active</small></span>
    <span><strong>${cell.corpse_count}</strong><small>corpses</small></span>
    <span><strong>${cell.radiation.toFixed(3)}</strong><small>radiation</small></span>
    <span><strong>${cell.entropy.toFixed(2)}</strong><small>entropy</small></span>
    <span><strong>${formatBytes(cell.directory_size)}</strong><small>files</small></span>
  `;
}

function renderLocalCellSkill(skillText) {
  let target = $("#localCellSkill");
  if (!target) {
    target = document.createElement("pre");
    target.id = "localCellSkill";
    target.className = "local-skill";
    $("#cellOrganisms").insertAdjacentElement("beforebegin", target);
  }
  target.textContent = skillText || "";
  target.style.display = skillText ? "block" : "none";
}

async function loadOrg(orgId, replaceEditor = true) {
  try {
    const org = await api(`/api/org?id=${encodeURIComponent(orgId)}`);
    $("#orgTitle").textContent = org.org_id;
    $("#orgMeta").textContent = `${org.strategy} / gen ${org.generation} / ${formatBytes(org.size)} / ${formatLlmBinding(org)}`;
    renderOrgTags(org.tags || []);
    renderOrgAbilities(org.abilities || {});
    renderOrgFiles(org.files || {});
    if (replaceEditor) {
      ui.skillEditor.value = org.skill_text || "";
    }
    renderReadonlySkill(org.skill_text || "");
    await refreshInspector(orgId);
  } catch {
    clearOrgEditor();
  }
}

function clearOrgEditor() {
  $("#orgTitle").textContent = "Organism";
  $("#orgMeta").textContent = "none selected";
  ui.skillEditor.value = "";
  renderOrgTags([]);
  renderOrgAbilities({});
  renderOrgFiles({});
  renderReadonlySkill("");
  renderInspector(null);
}

async function refreshInspector(orgId) {
  if (!orgId) {
    renderInspector(null);
    return;
  }
  try {
    const payload = await api(`/api/llm_inspector?id=${encodeURIComponent(orgId)}`);
    renderInspector(payload);
  } catch {
    renderInspector(null);
  }
}

function renderInspector(payload) {
  if (!ui.inspectorStatus) return;
  if (!payload) {
    ui.inspectorStatus.textContent = "select organism";
    ui.inspectorSummary.innerHTML = `<span><strong>0</strong><small>turns</small></span><span><strong>-</strong><small>model</small></span>`;
    ui.inspectorPrompt.textContent = "No prompt yet.";
    ui.inspectorResponse.textContent = "No response yet.";
    ui.inspectorAction.textContent = "No action yet.";
    return;
  }
  const usage = payload.usage || {};
  ui.inspectorStatus.textContent = payload.raw_response ? `tick ${payload.last_llm_tick}` : "not called";
  ui.inspectorSummary.innerHTML = `
    ${metricHtml("turns", payload.llm_turns || 0)}
    ${metricHtml("last tick", payload.last_llm_tick >= 0 ? payload.last_llm_tick : "-")}
    ${metricHtml("tokens", formatCompactNumber(usage.total_tokens || 0))}
    ${metricHtml("cache hit", formatCompactNumber(usage.prompt_cache_hit_tokens || 0))}
    ${metricHtml("cache miss", formatCompactNumber(usage.prompt_cache_miss_tokens || 0))}
    ${metricHtml("model", payload.llm_model || "-")}
  `;
  ui.inspectorPrompt.textContent = payload.prompt || "No prompt captured yet. Use LLM JSON mode or Prompt preview.";
  ui.inspectorResponse.textContent = payload.raw_response || "No LLM response captured yet.";
  ui.inspectorAction.textContent = payload.parsed_action
    ? JSON.stringify(payload.parsed_action, null, 2)
    : payload.parse_error
      ? `Parse error: ${payload.parse_error}`
      : "No parsed action yet.";
}

function renderOrgTags(tags) {
  let target = $("#orgTags");
  if (!target) {
    target = document.createElement("div");
    target.id = "orgTags";
    target.className = "tag-list";
    ui.skillEditor.insertAdjacentElement("beforebegin", target);
  }
  target.innerHTML = tagListInnerHtml(tags);
}

function renderOrgAbilities(abilities) {
  let target = $("#orgAbilities");
  if (!target) {
    target = document.createElement("div");
    target.id = "orgAbilities";
    target.className = "ability-list";
    ui.skillEditor.insertAdjacentElement("beforebegin", target);
  }
  const entries = abilityEntries(abilities);
  if (!entries.length) {
    target.innerHTML = "";
    return;
  }
  target.innerHTML = entries
    .map(([key, value]) => `<span><strong>${escapeHtml(key)}</strong><small>${Number(value).toFixed(2)}x</small></span>`)
    .join("");
}

function tagListHtml(tags, size = "") {
  const className = size ? `tag-list ${size}` : "tag-list";
  return `<div class="${className}">${tagListInnerHtml(tags)}</div>`;
}

function tagListInnerHtml(tags) {
  return (tags || [])
    .slice(0, 12)
    .map((tag) => `<span>${escapeHtml(tag)}</span>`)
    .join("");
}

function renderReadonlySkill(skillText) {
  let target = $("#readonlySkill");
  if (!target) {
    target = document.createElement("pre");
    target.id = "readonlySkill";
    target.className = "readonly-skill";
    ui.skillEditor.insertAdjacentElement("beforebegin", target);
  }
  target.textContent = skillText || "";
  target.style.display = skillText ? "block" : "none";
}

function renderOrgFiles(files) {
  const names = Object.keys(files);
  let target = $("#orgFiles");
  if (!target) {
    target = document.createElement("div");
    target.id = "orgFiles";
    target.className = "file-list";
    ui.skillEditor.insertAdjacentElement("beforebegin", target);
  }
  if (!names.length) {
    target.innerHTML = "";
    return;
  }
  target.innerHTML = names
    .sort()
    .map((name) => {
      const file = files[name];
      const preview = file.preview ? `<small>${escapeHtml(file.preview)}</small>` : "";
      return `<div class="file-row"><strong>${escapeHtml(name)}</strong><span>${formatBytes(file.size)} / ${escapeHtml(file.status)}</span>${preview}</div>`;
    })
    .join("");
}

function drawHistory() {
  const canvas = $("#historyChart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#d8e0e5";
  ctx.lineWidth = 1;
  for (let i = 1; i < 4; i += 1) {
    const y = (h / 4) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  const rows = state.history || [];
  if (rows.length < 2) return;
  const maxPop = Math.max(...rows.map((row) => row.population), 1);
  const maxEnergy = Math.max(...rows.map((row) => row.total_cell_energy), 1);
  drawSeries(ctx, rows, "population", maxPop, "#168b88", w, h);
  drawSeries(ctx, rows, "diversity", 1, "#5967c7", w, h);
  drawSeries(ctx, rows, "total_cell_energy", maxEnergy, "#c98b22", w, h);
}

function drawSeries(ctx, rows, key, maxValue, color, w, h) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  rows.forEach((row, index) => {
    const x = rows.length === 1 ? 0 : (index / (rows.length - 1)) * (w - 10) + 5;
    const value = clamp(row[key] / maxValue, 0, 1);
    const y = h - 10 - value * (h - 20);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function lineageColor(id) {
  if (!id) return "#8b99a3";
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  const palette = ["#168b88", "#c98b22", "#c94f6d", "#5967c7", "#3a965b", "#8f5fbf", "#d46f3d", "#2d7db3"];
  return palette[hash % palette.length];
}

function traitColor(trait) {
  const palette = {
    forage: "#168b88",
    spread: "#5967c7",
    guard: "#3a965b",
    repair: "#c98b22",
    migrate: "#2d7db3",
    minimal: "#60707a",
    scavenge: "#8f5fbf",
    steal: "#c94f6d",
  };
  return palette[String(trait || "").toLowerCase()] || "#60707a";
}

function traitInitial(trait) {
  const labels = {
    forage: "F",
    spread: "S",
    guard: "G",
    repair: "R",
    migrate: "M",
    minimal: "N",
    scavenge: "V",
    steal: "T",
  };
  return labels[String(trait || "").toLowerCase()] || "";
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function formatCompactNumber(value) {
  const number = Number(value || 0);
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`;
  if (number >= 10_000) return `${Math.round(number / 1000)}K`;
  if (number >= 1000) return `${(number / 1000).toFixed(1)}K`;
  return String(Math.round(number));
}

function formatBudgetLabel(value) {
  const number = Number(value || 0);
  return number > 0 ? formatCompactNumber(number) : "off";
}

function stopLabel(value, suffix) {
  const number = Number(value || 0);
  return number > 0 ? `${number}${suffix}` : "off";
}

function controlValue(input, fallback = 0) {
  return input ? input.value : fallback;
}

function setText(selector, value) {
  const element = $(selector);
  if (element) element.textContent = value;
}

function isTokenBudgetExhausted() {
  return Boolean(
    state?.config?.agent_mode === "llm_json" &&
      state?.stats?.llm_token_budget_exhausted,
  );
}

function automaticStopReason(tokenBudgetExhausted = false) {
  if (!state) return "";
  if (tokenBudgetExhausted) return "token budget reached";
  if (Number(controlValue(ui.stopExtinctToggle, 0)) >= 1 && state.tick > 0 && Number(state.stats.population || 0) <= 0) {
    return "extinction";
  }
  const maxTick = Number(controlValue(ui.stopMaxTickInput, 0));
  if (maxTick > 0 && Number(state.tick || 0) >= maxTick) {
    return `tick ${maxTick} reached`;
  }
  const runtimeMinutes = Number(controlValue(ui.stopRuntimeInput, 0));
  if (runtimeMinutes > 0 && playStartedAt > 0 && Date.now() - playStartedAt >= runtimeMinutes * 60_000) {
    return `${runtimeMinutes} min reached`;
  }
  const dominance = Number(controlValue(ui.stopDominanceInput, 0));
  const topLineage = state.lineages?.[0];
  if (dominance > 0 && topLineage && Number(state.stats.population || 0) > 0) {
    const share = (Number(topLineage.population || 0) / Number(state.stats.population || 1)) * 100;
    if (share >= dominance) {
      return `${dominance}% dominance`;
    }
  }
  const stableTicks = Number(controlValue(ui.stopStableInput, 0));
  if (stableTicks > 0 && hasStablePopulation(stableTicks)) {
    return `${stableTicks}t no-change`;
  }
  return "";
}

function hasStablePopulation(stableTicks) {
  const rows = state?.history || [];
  if (!rows.length) return false;
  const currentPop = Number(state.stats.population || 0);
  const windowRows = rows.filter((row) => Number(state.tick || 0) - Number(row.tick || 0) <= stableTicks);
  if (windowRows.length < 3) return false;
  return windowRows.every((row) => Number(row.population || 0) === currentPop);
}

function renderStopStatus(reason) {
  const status = $("#stopStatus");
  const hint = $("#stopHint");
  if (!status || !hint) return;
  if (reason) {
    status.textContent = "paused";
    hint.textContent = `Auto-paused: ${reason}. Step still works for diagnosis.`;
  } else if (playing) {
    status.textContent = "armed";
    hint.textContent = "Stop conditions are watching the active Play loop.";
  } else {
    status.textContent = "optional";
    hint.textContent = "These conditions pause Play only. Step still works for diagnosis.";
  }
}

function formatSigned(value) {
  const number = Number(value || 0);
  if (number > 0) return `+${number}`;
  return String(number);
}

function abilityEntries(abilities) {
  const order = ["harvest", "copy", "move", "steal", "attack", "defense", "repair", "reflect"];
  return order
    .filter((key) => abilities[key] !== undefined)
    .map((key) => [key, Number(abilities[key] || 1)]);
}

function formatAbilitySummary(abilities) {
  const labels = {
    harvest: "H",
    copy: "C",
    move: "M",
    steal: "S",
    attack: "A",
    defense: "D",
    repair: "R",
    reflect: "F",
  };
  return abilityEntries(abilities)
    .map(([key, value]) => `${labels[key] || key[0].toUpperCase()} ${value.toFixed(1)}x`)
    .join(" / ");
}

function formatLlmBinding(org) {
  const turns = Number(org.llm_turns || 0);
  const lastTick = Number(org.last_llm_tick ?? -1);
  const model = org.llm_model ? ` / ${org.llm_model}` : "";
  const last = lastTick >= 0 ? `last ${lastTick}` : "not called";
  return `LLM ${turns} turns / ${last}${model}`;
}

function isActionLikeEvent(event) {
  return [
    "harvest",
    "copy",
    "move",
    "steal",
    "reflect",
    "repair",
    "protect",
    "write",
    "delete",
    "scan",
    "read",
    "llm",
    "birth",
    "death",
  ].includes(event.kind);
}

function countBy(values) {
  return values.reduce((counts, value) => {
    counts[value] = (counts[value] || 0) + 1;
    return counts;
  }, {});
}

function actionMeaning(kind) {
  const meanings = {
    harvest: "organisms are gathering local energy",
    copy: "organisms are reproducing into nearby cells",
    move: "organisms are relocating across the grid",
    steal: "organisms are grafting context fragments from neighbors",
    reflect: "organisms are appending learned rules to their context genome",
    repair: "organisms are restoring integrity",
    protect: "organisms are adding shields around files",
    write: "organisms are editing virtual files",
    delete: "organisms are attacking runnable files",
    scan: "organisms are sampling nearby cells",
    read: "organisms are inspecting virtual paths",
    llm: "model requests are being submitted or returned",
    birth: "new runnable organisms appeared",
    death: "organisms became nonviable",
  };
  return meanings[kind] || "recent ecological event";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

init().catch((error) => {
  document.body.innerHTML = `<pre>${escapeHtml(error.stack || error.message)}</pre>`;
});
