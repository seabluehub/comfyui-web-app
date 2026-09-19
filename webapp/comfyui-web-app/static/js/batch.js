// ===== Batch Production Console =====
// Selection filters -> model config -> sequential execution -> live progress

const state = {
    filters: { styles: [], outfits: [], poses: [] },
    ws: null,
    currentTask: null,
    modelsCache: { checkpoints: [], unets: [], loras: [], source: "" },
    previewTimer: null,
    lastPreview: null
};

// DOM Elements
const msStyle = document.getElementById("msStyle");
const msOutfit = document.getElementById("msOutfit");
const msPose = document.getElementById("msPose");
const pvMatched = document.getElementById("pvMatched");
const pvPending = document.getElementById("pvPending");
const pvSuccess = document.getElementById("pvSuccess");
const pvFailed = document.getElementById("pvFailed");
const cfgTemplate = document.getElementById("cfgTemplate");
const cfgCheckpoint = document.getElementById("cfgCheckpoint");
const cfgLora = document.getElementById("cfgLora");
const cfgLoraStrength = document.getElementById("cfgLoraStrength");
const loraStrengthVal = document.getElementById("loraStrengthVal");
const cfgSteps = document.getElementById("cfgSteps");
const cfgCfg = document.getElementById("cfgCfg");
const cfgWidth = document.getElementById("cfgWidth");
const cfgHeight = document.getElementById("cfgHeight");
const cfgLimit = document.getElementById("cfgLimit");
const cfgIncludeDone = document.getElementById("cfgIncludeDone");
const btnExecute = document.getElementById("btnExecute");
const btnPause = document.getElementById("btnPause");
const btnResume = document.getElementById("btnResume");
const btnStop = document.getElementById("btnStop");
const btnRefreshStatus = document.getElementById("btnRefreshStatus");
const sessionStat = document.getElementById("sessionStat");
const sessionFill = document.getElementById("sessionFill");
const overallStat = document.getElementById("overallStat");
const overallFill = document.getElementById("overallFill");
const currentTaskBar = document.getElementById("currentTaskBar");
const statPending = document.getElementById("statPending");
const statSuccess = document.getElementById("statSuccess");
const statFailed = document.getElementById("statFailed");
const statAvg = document.getElementById("statAvg");
const statEngine = document.getElementById("statEngine");
const capsuleText = document.getElementById("capsuleText");
const logList = document.getElementById("logList");
const modelsSource = document.getElementById("modelsSource");
const toastNotice = document.getElementById("toastNotice");

// ===== Multi-Select Dropdown Component =====
class MultiSelect {
    constructor(rootEl, label, options, onChange) {
        this.root = rootEl;
        this.label = label;
        this.options = options; // [{tag, name}]
        this.onChange = onChange;
        this.selected = new Set();
        this.toggleBtn = rootEl.querySelector(".ms-toggle");
        this.menu = rootEl.querySelector(".ms-menu");
        this.optionsEl = rootEl.querySelector(".ms-options");
        this._render();
        this._bind();
    }

    _render() {
        this.optionsEl.innerHTML = "";
        this.options.forEach(opt => {
            const label = document.createElement("label");
            label.className = "ms-option";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.value = opt.tag;
            cb.onchange = () => {
                if (cb.checked) this.selected.add(opt.tag); else this.selected.delete(opt.tag);
                label.classList.toggle("checked", cb.checked);
                this._updateText();
                this.onChange();
            };
            const span = document.createElement("span");
            span.textContent = opt.name;
            label.appendChild(cb);
            label.appendChild(span);
            this.optionsEl.appendChild(label);
        });
        this._updateText();
    }

    _bind() {
        this.toggleBtn.onclick = (e) => {
            e.stopPropagation();
            document.querySelectorAll(".ms-dropdown.open").forEach(d => { if (d !== this.root) d.classList.remove("open"); });
            this.root.classList.toggle("open");
        };
        this.menu.onclick = (e) => e.stopPropagation();
        this.menu.querySelectorAll(".ms-actions button").forEach(btn => {
            btn.onclick = () => {
                if (btn.dataset.act === "all") {
                    this.options.forEach(o => this.selected.add(o.tag));
                } else {
                    this.selected.clear();
                }
                this.optionsEl.querySelectorAll(".ms-option").forEach(label => {
                    const cb = label.querySelector("input");
                    cb.checked = this.selected.has(cb.value);
                    label.classList.toggle("checked", cb.checked);
                });
                this._updateText();
                this.onChange();
            };
        });
    }

    _updateText() {
        const n = this.selected.size;
        this.root.classList.toggle("selected", n > 0);
        this.toggleBtn.textContent = n === 0 ? `${this.label}：全部`
            : n === this.options.length ? `${this.label}：全部 (${n})`
            : `${this.label}：已选 ${n} 项`;
    }

    get value() { return [...this.selected]; }
}

let msStyleCtl, msOutfitCtl, msPoseCtl;

// ===== Init =====
document.addEventListener("DOMContentLoaded", async () => {
    document.addEventListener("click", () => {
        document.querySelectorAll(".ms-dropdown.open").forEach(d => d.classList.remove("open"));
    });

    try {
        const res = await fetch("/api/batch/dimensions");
        const dims = await res.json();
        dims.styles.forEach(s => STYLE_NAMES[s.tag] = s.name);
        dims.outfits.forEach(o => OUTFIT_NAMES[o.tag] = o.name);
        dims.poses.forEach(p => POSE_NAMES[p.tag] = p.name);
        msStyleCtl = new MultiSelect(msStyle, "画风", dims.styles, onFilterChange);
        msOutfitCtl = new MultiSelect(msOutfit, "服装", dims.outfits, onFilterChange);
        msPoseCtl = new MultiSelect(msPose, "姿态", dims.poses, onFilterChange);
    } catch (e) {
        showToast("❌ 维度列表加载失败");
    }

    await loadModels();
    await loadPresets();
    await loadStatus();
    initWebSocket();
    initEvents();
    setInterval(loadStatus, 3000);
});

function showToast(msg, duration = 2800) {
    toastNotice.textContent = msg;
    toastNotice.classList.add("show");
    setTimeout(() => toastNotice.classList.remove("show"), duration);
}

// ===== Filters & Preview =====
function onFilterChange() {
    clearTimeout(state.previewTimer);
    state.previewTimer = setTimeout(refreshPreview, 250);
}

function currentFilters() {
    const charId = window.CharacterManager ? window.CharacterManager.getActiveCharacterId() : 1;
    return {
        character_id: charId,
        styles: msStyleCtl ? msStyleCtl.value : [],
        outfits: msOutfitCtl ? msOutfitCtl.value : [],
        poses: msPoseCtl ? msPoseCtl.value : []
    };
}

window.addEventListener("characterChanged", () => {
    refreshPreview();
    loadStatus();
});

async function refreshPreview() {
    try {
        const res = await fetch("/api/batch/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentFilters())
        });
        const data = await res.json();
        state.lastPreview = data;
        pvMatched.textContent = data.matched;
        pvPending.textContent = (data.pending === 0 && data.matched > 0) ? "0（已全部生成过，可勾选重跑）" : data.pending;
        pvSuccess.textContent = data.success;
        pvFailed.textContent = data.failed;
    } catch (e) {
        console.error("preview failed", e);
    }
}

// ===== Preset Recommendation Combos =====
const presetChips = document.getElementById("presetChips");
let presetList = [];

async function loadPresets() {
    try {
        const res = await fetch("/api/batch/presets");
        const data = await res.json();
        presetList = data.presets || [];
        renderPresetChips();
    } catch (e) {
        console.error("presets load failed", e);
    }
}

function renderPresetChips() {
    presetChips.innerHTML = "";
    presetList.forEach(p => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "preset-chip";
        chip.dataset.id = p.id;
        chip.title = p.desc;
        chip.innerHTML = `<span class="chip-name">${p.name}</span>` +
            (p.badge ? `<span class="chip-badge">${p.badge}</span>` : "") +
            `<span class="chip-desc">${p.desc}</span>`;
        chip.onclick = () => applyPreset(p.id);
        presetChips.appendChild(chip);
    });
}

function applyPreset(id) {
    const p = presetList.find(x => x.id === id);
    if (!p) return;
    // Template first (rebuilds checkpoint options), then fill every field
    cfgTemplate.value = p.template;
    rebuildCheckpointOptions();
    if ([...cfgCheckpoint.options].some(o => o.value === p.checkpoint)) {
        cfgCheckpoint.value = p.checkpoint;
    }
    // LoRA: ""=disable, filename=specific
    const loraOpt = [...cfgLora.options].find(o => o.value === p.lora);
    cfgLora.value = loraOpt ? p.lora : "__none__";
    if (p.lora_strength != null) {
        cfgLoraStrength.value = p.lora_strength;
        loraStrengthVal.textContent = p.lora_strength;
    }
    cfgSteps.value = p.steps;
    cfgCfg.value = p.cfg;
    cfgWidth.value = p.width;
    cfgHeight.value = p.height;
    // Active chip state
    document.querySelectorAll(".preset-chip").forEach(c =>
        c.classList.toggle("active", c.dataset.id === id));
    showToast(`🎯 已应用「${p.name}」：${p.desc}`, 3200);
    addLog("session", `已应用推荐方案「${p.name}」— 底模 ${p.checkpoint}，LoRA ${p.lora === "" ? "禁用" : p.lora}，${p.steps}步 ${p.width}×${p.height}`, "ok");
}

// ===== Model Lists =====
async function loadModels() {
    try {
        const res = await fetch("/api/batch/models");
        const data = await res.json();
        state.modelsCache = data;
        modelsSource.textContent = data.source === "comfyui" ? "✅ 模型列表来自 ComfyUI 实时接口" : "📁 模型列表来自本地模型库扫描 (ComfyUI 未连接)";
        rebuildCheckpointOptions();
        rebuildLoraOptions();
    } catch (e) {
        modelsSource.textContent = "⚠️ 模型列表加载失败";
    }
}

function rebuildCheckpointOptions() {
    const isFlux = cfgTemplate.value === "flux";
    const list = isFlux ? state.modelsCache.unets : state.modelsCache.checkpoints;
    const incompatible = new Set(state.modelsCache.incompatible || []);
    const prev = cfgCheckpoint.value;
    cfgCheckpoint.innerHTML = "";
    const defOpt = document.createElement("option");
    defOpt.value = "";
    defOpt.textContent = "自动选择（推荐）";
    cfgCheckpoint.appendChild(defOpt);
    (list || []).forEach(name => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = incompatible.has(name) ? `⚠ ${name}（纯UNet，不可用）` : name;
        if (incompatible.has(name)) opt.style.color = "#f87171";
        cfgCheckpoint.appendChild(opt);
    });
    if (prev && [...cfgCheckpoint.options].some(o => o.value === prev)) {
        cfgCheckpoint.value = prev;
    } else if ((list || []).length > 0) {
        // Smart preselect: prefer full anime SDXL checkpoints (never incompatible ones)
        const usable = list.filter(n => !incompatible.has(n));
        const prefer = usable.find(n => /GhostXL/i.test(n))
            || usable.find(n => /SDXL-Anime/i.test(n))
            || usable.find(n => /anime/i.test(n))
            || usable[0] || list[0];
        cfgCheckpoint.value = prefer;
    }
}

function rebuildLoraOptions() {
    const prev = cfgLora.value;
    cfgLora.innerHTML = "";
    const defOpt = document.createElement("option");
    defOpt.value = "__default__";
    defOpt.textContent = "自动（角色默认，缺失时自动禁用）";
    cfgLora.appendChild(defOpt);
    const noneOpt = document.createElement("option");
    noneOpt.value = "__none__";
    noneOpt.textContent = "不使用 LoRA";
    cfgLora.appendChild(noneOpt);
    (state.modelsCache.loras || []).forEach(name => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        cfgLora.appendChild(opt);
    });
    if (prev && [...cfgLora.options].some(o => o.value === prev)) cfgLora.value = prev;
}

// ===== Execute & Controls =====
function initEvents() {
    cfgTemplate.onchange = rebuildCheckpointOptions;
    cfgLoraStrength.oninput = () => loraStrengthVal.textContent = cfgLoraStrength.value;

    btnExecute.onclick = async () => {
        // Dangerous-action confirmation for rerun mode
        if (cfgIncludeDone.checked) {
            const pv = state.lastPreview || { matched: "?", success: 0 };
            const wipeCount = (pv.success || 0) + (pv.failed || 0);
            if (!confirm(
                `⚠️ 已勾选「重跑」：将重置当前筛选下 ${pv.matched} 个任务中的 ${wipeCount} 个已完成/失败记录，` +
                `并从画廊清除对应记录（图片文件保留）。确定继续吗？`
            )) return;
        }
        btnExecute.disabled = true;
        try {
            const loraVal = cfgLora.value === "__default__" ? null : (cfgLora.value === "__none__" ? "" : cfgLora.value);
            const charId = window.CharacterManager ? window.CharacterManager.getActiveCharacterId() : 1;
            const body = {
                character_id: charId,
                model: cfgTemplate.value,
                styles: msStyleCtl.value,
                outfits: msOutfitCtl.value,
                poses: msPoseCtl.value,
                include_done: cfgIncludeDone.checked,
                steps: cfgSteps.value ? parseInt(cfgSteps.value) : null,
                cfg: cfgCfg.value ? parseFloat(cfgCfg.value) : null,
                width: cfgWidth.value ? parseInt(cfgWidth.value) : null,
                height: cfgHeight.value ? parseInt(cfgHeight.value) : null,
                limit: cfgLimit.value ? parseInt(cfgLimit.value) : null,
                checkpoint: cfgCheckpoint.value || null,
                lora: loraVal,
                lora_strength: parseFloat(cfgLoraStrength.value)
            };
            const res = await fetch("/api/batch/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (!res.ok) {
                showToast(`❌ ${data.detail || "启动失败"}`);
                return;
            }
            if (!data.queued || data.queued <= 0) {
                showToast("⚠️ 队列为 0：所选组合的任务都已生成过。勾选「重跑该组合下已完成/失败的图片」可重新生成", 5000);
                addLog("warn", "批次未执行：所选组合均已生成过（0 张待生成）。如需重新生成请勾选「重跑已完成」选项。", "warn");
                currentTaskBar.innerHTML = `<span class="warn-text">⚠️ 所选组合均已生成过，无待生成任务。请更换组合，或勾选「重跑该组合下已完成/失败的图片」后重试。</span>`;
                await loadStatus();
                return;
            }
            (data.warnings || []).forEach(w => {
                addLog("warn", `⚠️ ${w}`, "warn");
                showToast(`⚠️ ${w}`, 4200);
            });
            showToast(`🚀 批次已启动！本次队列 ${data.queued} 张`);
            logList.innerHTML = "";
            addLog("session", `批次启动，队列共 ${data.queued} 张任务${data.limit ? `（上限 ${data.limit}）` : ""}`, "ok");
            await loadStatus();
        } catch (e) {
            showToast("❌ 网络错误，启动失败");
        } finally {
            btnExecute.disabled = false;
        }
    };

    btnPause.onclick = async () => { await postControl("/api/batch/pause", "⏸ 已暂停（当前单张完成后挂起）"); };
    btnResume.onclick = async () => { await postControl("/api/batch/resume", "▶ 已恢复队列"); };
    btnStop.onclick = async () => {
        if (confirm("确定停止当前批次吗？进度已保存，可随时重新执行。")) {
            await postControl("/api/batch/stop", "⏹ 批次已停止");
        }
    };
    btnRefreshStatus.onclick = async () => { await loadStatus(); await refreshPreview(); showToast("🔄 已刷新"); };
}

async function postControl(url, msg) {
    try {
        await fetch(url, { method: "POST" });
        showToast(msg);
        setTimeout(loadStatus, 400);
    } catch (e) {
        showToast("❌ 操作失败");
    }
}

// ===== Status & Progress =====
async function loadStatus() {
    try {
        const charId = window.CharacterManager ? window.CharacterManager.getActiveCharacterId() : 1;
        const res = await fetch(`/api/batch/status?character_id=${charId}`);
        const s = await res.json();
        renderStatus(s);
    } catch (e) { /* server restarting */ }
}

function renderStatus(s) {
    statPending.textContent = s.pending;
    statSuccess.textContent = s.success;
    statFailed.textContent = s.failed;
    statAvg.textContent = s.avg_sec_per_img ? `${s.avg_sec_per_img}s` : "0.0s";

    const overallPct = s.progress_percent || 0;
    overallStat.textContent = `${overallPct.toFixed(1)}% (${s.success} / ${s.total})`;
    overallFill.style.width = `${overallPct}%`;

    if (s.session_total > 0) {
        const pct = s.session_total ? (s.session_done / s.session_total * 100) : 0;
        sessionStat.textContent = `${s.session_done} / ${s.session_total}`;
        sessionFill.style.width = `${Math.min(pct, 100)}%`;
    } else {
        sessionStat.textContent = "0 / 0";
        sessionFill.style.width = "0%";
    }

    if (s.is_active) {
        capsuleText.textContent = `量产中 (#${s.current_task_id ?? "-"})`;
    } else if (s.is_paused) {
        capsuleText.textContent = "已暂停";
    } else {
        capsuleText.textContent = s.success >= s.total ? "全部完成 🎉" : "队列空闲";
    }

    if (!s.is_active && !s.is_paused && state.currentTask && s.current_task_id === null) {
        currentTaskBar.innerHTML = `<span class="idle-text">✅ 本批次执行结束。可前往 <a href="/">画廊</a> 查看成果，或继续选择下一批组合。</span>`;
    }
}

// ===== WebSocket Live Events =====
function initWebSocket() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    try {
        state.ws = new WebSocket(`${proto}://${location.host}/ws/progress`);
    } catch (e) { return; }

    state.ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch (e) { return; }
        handleEvent(msg.type, msg.data || {});
    };
    state.ws.onclose = () => setTimeout(initWebSocket, 4000);
}

const STYLE_NAMES = {}, OUTFIT_NAMES = {}, POSE_NAMES = {};
function tagName(kind, tag) {
    const map = kind === "style" ? STYLE_NAMES : kind === "outfit" ? OUTFIT_NAMES : POSE_NAMES;
    return map[tag] || tag;
}

function handleEvent(type, data) {
    switch (type) {
        case "init_status":
            renderStatus(data);
            break;
        case "session_started":
            addLog("session", `会话开始：共 ${data.session_total} 张`, "ok");
            break;
        case "task_start":
            state.currentTask = data;
            currentTaskBar.innerHTML = `🖌 正在生成任务 <strong>#${data.task_id}</strong> — ${tagName("style", data.style)} × ${tagName("outfit", data.outfit)} <span class="hint">采样中...</span>`;
            addLog("task", `#${data.task_id} 开始：${data.style} × ${data.outfit}`);
            break;
        case "step_progress": {
            const pct = data.max ? Math.round(data.step / data.max * 100) : 0;
            if (state.currentTask) {
                currentTaskBar.innerHTML = `🖌 正在生成任务 <strong>#${state.currentTask.task_id}</strong> — ${tagName("style", state.currentTask.style)} × ${tagName("outfit", state.currentTask.outfit)} <span class="step-chip">${data.step}/${data.max} (${pct}%)</span>`;
            }
            break;
        }
        case "task_success":
            addLog("ok", `#${data.task_id} ✅ ${data.file_name}（${data.exec_time}s）`, "ok");
            loadStatus(); refreshPreview();
            break;
        case "task_failed":
            addLog("err", `#${data.task_id} ❌ ${data.error}`, "err");
            break;
        case "cooldown":
            addLog("warn", `❄️ 温控休眠 ${data.seconds}s（${data.reason}）`, "warn");
            currentTaskBar.innerHTML = `<span class="warn-text">❄️ 温控休眠中... ${data.seconds}s 后继续</span>`;
            break;
        case "session_completed":
            addLog("session", `🏁 本批次结束：完成 ${data.session_done} / ${data.session_total}`, "ok");
            currentTaskBar.innerHTML = `<span class="ok-text">✅ 本批次执行完毕（${data.session_done} / ${data.session_total}）</span>`;
            loadStatus(); refreshPreview();
            break;
        case "filter_exhausted":
            addLog("session", `✅ 所选组合已全部生成，全库还剩 ${data.remaining_global} 张待生成（可继续选下一批组合）`, "ok");
            break;
        case "completed":
            addLog("session", "🎉 全部 1000 张量产任务已完成！", "ok");
            currentTaskBar.innerHTML = `<span class="ok-text">🎉 全部 1000 张量产任务已完成！</span>`;
            break;
    }
}

function addLog(kind, text, cls = "") {
    const entry = document.createElement("div");
    entry.className = `log-entry ${cls}`;
    const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    entry.textContent = `[${time}] ${text}`;
    const placeholder = logList.querySelector(".muted");
    if (placeholder) placeholder.remove();
    logList.prepend(entry);
    while (logList.children.length > 60) logList.lastChild.remove();
}
