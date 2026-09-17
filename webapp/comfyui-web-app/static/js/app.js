// State Management
const state = {
    characterId: 1,
    currentStyle: "",
    currentOutfit: "",
    currentPose: "",
    sortBy: "newest",
    search: "",
    currentPage: 1,
    pageSize: 24,
    totalImages: 0,
    ws: null,
    activeBatch: false
};

const STYLES_META = [
    { tag: "ghibli", name: "吉卜力" },
    { tag: "makoto_shinkai", name: "新海诚" },
    { tag: "cyberpunk", name: "赛博朋克" },
    { tag: "watercolor", name: "水彩" },
    { tag: "rococo", name: "洛可可" },
    { tag: "gothic", name: "暗黑哥特" },
    { tag: "retro_90s", name: "90s复古" },
    { tag: "cinematic", name: "胶片电影" },
    { tag: "summer_breeze", name: "夏日清凉" },
    { tag: "night_cityscape", name: "夜景璀璨" }
];

// DOM Elements
const galleryGrid = document.getElementById("galleryGrid");
const emptyState = document.getElementById("emptyState");
const styleTags = document.getElementById("styleTags");
const selectOutfit = document.getElementById("selectOutfit");
const selectPose = document.getElementById("selectPose");
const selectSort = document.getElementById("selectSort");
const inputSearch = document.getElementById("inputSearch");
const btnSearch = document.getElementById("btnSearch");
const btnStartBatch = document.getElementById("btnStartBatch");
const btnPauseBatch = document.getElementById("btnPauseBatch");
const btnRefresh = document.getElementById("btnRefresh");
const progressStat = document.getElementById("progressStat");
const progressFill = document.getElementById("progressFill");
const liveStepText = document.getElementById("liveStepText");
const statPending = document.getElementById("statPending");
const statSuccess = document.getElementById("statSuccess");
const statAvgTime = document.getElementById("statAvgTime");
const statEngine = document.getElementById("statEngine");
const capsuleText = document.getElementById("capsuleText");
const paginationBar = document.getElementById("paginationBar");
const pageInfo = document.getElementById("pageInfo");
const btnPrevPage = document.getElementById("btnPrevPage");
const btnNextPage = document.getElementById("btnNextPage");

// Modal Elements
const imageModal = document.getElementById("imageModal");
const btnModalClose = document.getElementById("btnModalClose");
const modalImg = document.getElementById("modalImg");
const modalTitle = document.getElementById("modalTitle");
const modalTags = document.getElementById("modalTags");
const modalPrompt = document.getElementById("modalPrompt");
const modalSeed = document.getElementById("modalSeed");
const modalResolution = document.getElementById("modalResolution");
const modalTime = document.getElementById("modalTime");
const modalSize = document.getElementById("modalSize");
const btnCopyPrompt = document.getElementById("btnCopyPrompt");
const btnDownloadOriginal = document.getElementById("btnDownloadOriginal");
const toastNotice = document.getElementById("toastNotice");

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
    initStyleTags();
    initFilters();
    initWebSocket();
    await loadSystemHealth();
    await loadCharacter();
    await loadTags();
    await loadBatchStatus();
    await loadGallery();
    initEvents();
});

function showToast(msg) {
    toastNotice.textContent = msg;
    toastNotice.classList.add("show");
    setTimeout(() => toastNotice.classList.remove("show"), 2800);
}

function initStyleTags() {
    STYLES_META.forEach(s => {
        const btn = document.createElement("button");
        btn.className = "tag-btn";
        btn.dataset.style = s.tag;
        btn.textContent = s.name;
        btn.onclick = () => {
            document.querySelectorAll("#styleTags .tag-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.currentStyle = s.tag;
            state.currentPage = 1;
            loadGallery();
        };
        styleTags.appendChild(btn);
    });

    const allBtn = styleTags.querySelector('[data-style=""]');
    allBtn.onclick = () => {
        document.querySelectorAll("#styleTags .tag-btn").forEach(b => b.classList.remove("active"));
        allBtn.classList.add("active");
        state.currentStyle = "";
        state.currentPage = 1;
        loadGallery();
    };
}

function initFilters() {
    selectOutfit.onchange = (e) => {
        state.currentOutfit = e.target.value;
        state.currentPage = 1;
        loadGallery();
    };
    selectPose.onchange = (e) => {
        state.currentPose = e.target.value;
        state.currentPage = 1;
        loadGallery();
    };
    selectSort.onchange = (e) => {
        state.sortBy = e.target.value;
        state.currentPage = 1;
        loadGallery();
    };
    btnSearch.onclick = () => {
        state.search = inputSearch.value.trim();
        state.currentPage = 1;
        loadGallery();
    };
    inputSearch.onkeyup = (e) => {
        if (e.key === "Enter") btnSearch.click();
    };
}

async function loadSystemHealth() {
    try {
        const res = await fetch("/api/system/health");
        const data = await res.json();
        if (data.mock_mode) {
            statEngine.textContent = "仿真模拟";
            statEngine.className = "stat-num info";
        } else {
            statEngine.textContent = data.comfyui_connected ? "ComfyUI在线" : "未连接";
            statEngine.className = data.comfyui_connected ? "stat-num success" : "stat-num danger";
        }
    } catch (e) {
        console.error("Health check error:", e);
    }
}

async function loadCharacter() {
    try {
        const res = await fetch(`/api/gallery/character?character_id=${state.characterId}`);
        const data = await res.json();
        document.getElementById("charName").textContent = data.name;
        document.getElementById("charModel").textContent = `${data.base_model.toUpperCase()} • ${data.default_lora}`;
    } catch (e) {
        console.error("Character load error:", e);
    }
}

async function loadTags() {
    try {
        const res = await fetch(`/api/gallery/tags?character_id=${state.characterId}`);
        const data = await res.json();

        // Populate Outfits
        selectOutfit.innerHTML = '<option value="">全部服装 (20套)</option>';
        data.outfits.forEach(o => {
            const opt = document.createElement("option");
            opt.value = o.tag;
            opt.textContent = `${o.tag} (${o.count})`;
            selectOutfit.appendChild(opt);
        });

        // Populate Poses
        selectPose.innerHTML = '<option value="">全部姿态 (5种)</option>';
        data.poses.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p.tag;
            opt.textContent = `${p.tag} (${p.count})`;
            selectPose.appendChild(opt);
        });
    } catch (e) {
        console.error("Tags load error:", e);
    }
}

async function loadBatchStatus() {
    try {
        const res = await fetch("/api/batch/status");
        const data = await res.json();
        updateBatchDashboard(data);
    } catch (e) {
        console.error("Batch status error:", e);
    }
}

function updateBatchDashboard(status) {
    const total = status.total || 1000;
    const success = status.success || 0;
    const pending = status.pending || 0;
    const percent = status.progress_percent || 0;

    progressStat.textContent = `${percent}% (${success} / ${total})`;
    progressFill.style.width = `${percent}%`;
    statPending.textContent = pending;
    statSuccess.textContent = success;
    statAvgTime.textContent = status.avg_sec_per_img ? `${status.avg_sec_per_img}s` : "0.0s";

    if (status.is_active) {
        state.activeBatch = true;
        btnStartBatch.style.display = "none";
        btnPauseBatch.style.display = "inline-flex";
        capsuleText.textContent = `量产中... (#${status.current_task_id || "-"})`;
    } else {
        state.activeBatch = false;
        btnStartBatch.style.display = "inline-flex";
        btnPauseBatch.style.display = "none";
        capsuleText.textContent = success >= total ? "量产全部达成 🎉" : `就绪 (${success} / ${total})`;
    }
}

async function loadGallery() {
    galleryGrid.innerHTML = '<div class="loading-spin" style="padding:40px;color:#94a3b8;">加载中...</div>';
    try {
        const params = new URLSearchParams({
            character_id: state.characterId,
            page: state.currentPage,
            page_size: state.pageSize,
            sort_by: state.sortBy
        });
        if (state.currentStyle) params.append("style", state.currentStyle);
        if (state.currentOutfit) params.append("outfit", state.currentOutfit);
        if (state.currentPose) params.append("pose", state.currentPose);
        if (state.search) params.append("search", state.search);

        const res = await fetch(`/api/gallery/images?${params.toString()}`);
        const data = await res.json();

        renderGallery(data);
    } catch (e) {
        console.error("Gallery load error:", e);
        galleryGrid.innerHTML = '<div style="color:#ef4444;padding:20px;">加载画廊失败，请检查网络或后端服务。</div>';
    }
}

function renderGallery(data) {
    galleryGrid.innerHTML = "";
    state.totalImages = data.total;

    if (!data.images || data.images.length === 0) {
        emptyState.style.display = "block";
        paginationBar.style.display = "none";
        return;
    }

    emptyState.style.display = "none";
    paginationBar.style.display = "flex";

    const totalPages = Math.ceil(data.total / state.pageSize) || 1;
    pageInfo.textContent = `第 ${data.page} 页 / 共 ${totalPages} 页 (共 ${data.total} 张)`;
    btnPrevPage.disabled = data.page <= 1;
    btnNextPage.disabled = data.page >= totalPages;

    data.images.forEach(img => {
        const card = document.createElement("div");
        card.className = "image-card";
        card.innerHTML = `
            <div class="card-media">
                <div class="card-badge-top">
                    <span class="badge">${img.style_tag || 'anime'}</span>
                    <span class="badge">${img.outfit_tag || 'casual'}</span>
                </div>
                <img src="${img.thumb_url}" alt="${img.file_name}" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22300%22><rect width=%22300%22 height=%22300%22 fill=%22%23222%22/><text x=%2250%%22 y=%2250%%22 fill=%22%23888%22 text-anchor=%22middle%22>Preview</text></svg>'">
            </div>
            <div class="card-body">
                <div class="card-prompt" title="${img.prompt_final}">${img.prompt_final}</div>
                <div class="card-footer">
                    <span class="seed">Seed: ${img.seed}</span>
                    <div class="card-actions">
                        <button class="card-btn btn-copy-card" title="复制提示词">📋 复制</button>
                    </div>
                </div>
            </div>
        `;

        card.onclick = (e) => {
            if (e.target.classList.contains("btn-copy-card")) {
                e.stopPropagation();
                copyText(img.prompt_final);
                showToast("✅ 已复制正面提示词！");
                return;
            }
            openModal(img);
        };

        galleryGrid.appendChild(card);
    });
}

function openModal(img) {
    modalImg.src = img.image_url;
    modalTitle.textContent = `${img.file_name}`;
    modalTags.innerHTML = `
        <span class="badge">${img.style_tag}</span>
        <span class="badge">${img.outfit_tag}</span>
        <span class="badge">${img.pose_tag}</span>
    `;
    modalPrompt.textContent = img.prompt_final;
    modalSeed.textContent = img.seed;
    modalResolution.textContent = `${img.width} × ${img.height}`;
    modalTime.textContent = img.created_at;
    modalSize.textContent = `${(img.file_size_bytes / 1024).toFixed(1)} KB`;

    // Generation config (template / checkpoint / lora / sampler) with graceful fallbacks
    const g = img.gen_config || {};
    const tplMap = {
        "sdxl_anime_template.json": "SDXL 极速量产",
        "flux_anime_template.json": "Flux 高清精修"
    };
    document.getElementById("modalTemplate").textContent =
        g.template ? (tplMap[g.template] || g.template) : "未知";
    document.getElementById("modalCheckpoint").textContent =
        g.checkpoint || "未指定（模板默认）";
    const loraEl = document.getElementById("modalLora");
    if (g.lora === "" || g.lora === null || g.lora === undefined) {
        loraEl.textContent = "已禁用";
    } else {
        loraEl.textContent = `${g.lora}${g.lora_strength != null ? ` (${g.lora_strength})` : ""}`;
    }
    document.getElementById("modalSteps").textContent =
        g.steps != null ? `${g.steps} 步` : "-";
    document.getElementById("modalSampler").textContent =
        g.sampler ? `${g.sampler}${g.scheduler ? ` / ${g.scheduler}` : ""}` : "-";
    document.getElementById("modalCfg").textContent =
        g.cfg != null ? g.cfg : "-";
    document.getElementById("modalEngine").textContent =
        g.mode === "live" ? "ComfyUI 实际生成" : (g.mode === "mock" ? "仿真模式（占位图）" : "-");
    btnDownloadOriginal.href = img.image_url;

    btnCopyPrompt.onclick = () => {
        copyText(img.prompt_final);
        showToast("✅ 已复制完整 Prompt 到剪贴板！");
    };

    imageModal.style.display = "flex";
}

function closeModal() {
    imageModal.style.display = "none";
}

function copyText(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
    } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
    }
}

function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/progress`;
    
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log("WebSocket connected to progress channel");
    };

    state.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleWsMessage(msg);
        } catch (e) {
            console.error("WS Parse error:", e);
        }
    };

    state.ws.onclose = () => {
        setTimeout(initWebSocket, 3000);
    };
}

function handleWsMessage(msg) {
    const type = msg.type;
    const data = msg.data;

    if (type === "step_progress") {
        liveStepText.innerHTML = `<span class="live-badge">⚡ 渲染中:</span> 任务 #${data.task_id} 正在采样 — 步数: ${data.step} / ${data.max_steps}`;
    } else if (type === "task_start") {
        liveStepText.innerHTML = `<span class="live-badge">🚀 启动:</span> 任务 #${data.task_id} [${data.style} • ${data.outfit}]`;
    } else if (type === "task_success") {
        liveStepText.innerHTML = `<span class="live-badge" style="color:#10b981;">✅ 达成:</span> 任务 #${data.task_id} 产出成功 (${data.exec_time}s)`;
        loadBatchStatus();
        // Prepend new image if on first page
        if (state.currentPage === 1 && !state.currentStyle && !state.currentOutfit) {
            loadGallery();
        }
    } else if (type === "cooldown") {
        liveStepText.innerHTML = `<span class="live-badge" style="color:#f59e0b;">❄️ 降温休眠:</span> 笔记本保护中，等待 ${data.seconds} 秒后继续...`;
    } else if (type === "completed") {
        liveStepText.innerHTML = `<span class="live-badge" style="color:#10b981;">🎉 任务完成:</span> 1000 张矩阵全部产出完毕！`;
        loadBatchStatus();
        loadGallery();
    }
}

function initEvents() {
    btnStartBatch.onclick = async () => {
        try {
            const res = await fetch("/api/batch/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ character_id: state.characterId })
            });
            if (res.ok) {
                showToast("🚀 已启动批量量产流水线！");
                loadBatchStatus();
            }
        } catch (e) {
            showToast("启动失败: " + e);
        }
    };

    btnPauseBatch.onclick = async () => {
        await fetch("/api/batch/pause", { method: "POST" });
        showToast("⏸ 量产队列已暂停");
        loadBatchStatus();
    };

    btnRefresh.onclick = () => {
        loadBatchStatus();
        loadGallery();
        loadTags();
        showToast("🔄 画廊已刷新");
    };

    btnPrevPage.onclick = () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            loadGallery();
        }
    };

    btnNextPage.onclick = () => {
        state.currentPage++;
        loadGallery();
    };

    btnModalClose.onclick = closeModal;
    imageModal.onclick = (e) => {
        if (e.target === imageModal) closeModal();
    };
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeModal();
    });
}
