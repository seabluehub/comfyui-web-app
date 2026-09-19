// ===== Character Manager & Consistency Benchmark Module =====
// Shared across Gallery (index.html) and Batch Console (batch.html)

window.CharacterManager = {
    characters: [],
    presets: [],
    activeChar: null,

    async init() {
        this.bindEvents();
        await this.loadPresets();
        await this.loadCharacters();
    },

    getActiveCharacterId() {
        const stored = localStorage.getItem("active_character_id");
        return stored ? parseInt(stored, 10) : 1;
    },

    setActiveCharacterId(id) {
        localStorage.setItem("active_character_id", id);
        const hit = this.characters.find(c => c.id === id);
        if (hit) {
            this.activeChar = hit;
            this.updateNavUI();
            window.dispatchEvent(new CustomEvent("characterChanged", { detail: hit }));
        }
    },

    updateNavUI() {
        const char = this.activeChar;
        if (!char) return;

        const navAvatar = document.getElementById("navCharAvatar");
        if (navAvatar) navAvatar.textContent = char.avatar_icon || "👧";

        const charModel = document.getElementById("charModel");
        if (charModel) {
            const loraName = char.default_lora ? ` • ${char.default_lora.replace('.safetensors', '')}` : " • 无LoRA";
            charModel.textContent = `${(char.base_model || 'sdxl').toUpperCase()}${loraName}`;
        }

        const charSelect = document.getElementById("charSelect");
        if (charSelect) {
            charSelect.value = char.id;
        }
    },

    async loadPresets() {
        try {
            const res = await fetch("/api/characters/presets/examples");
            if (res.ok) {
                this.presets = await res.json();
                this.renderPresets();
            }
        } catch (e) {
            console.error("Failed to load character presets", e);
        }
    },

    async loadCharacters() {
        try {
            const res = await fetch("/api/characters");
            if (res.ok) {
                this.characters = await res.json();
                this.renderCharDropdown();
                this.renderCharCards();
                this.renderBenchmarkChars();

                // Restore active character
                const activeId = this.getActiveCharacterId();
                const current = this.characters.find(c => c.id === activeId) || this.characters[0];
                if (current) {
                    this.setActiveCharacterId(current.id);
                }
            }
        } catch (e) {
            console.error("Failed to load characters", e);
        }
    },

    renderCharDropdown() {
        const sel = document.getElementById("charSelect");
        if (!sel) return;

        sel.innerHTML = "";
        this.characters.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = `${c.avatar_icon || "👧"} ${c.name}`;
            sel.appendChild(opt);
        });

        sel.onchange = (e) => {
            const newId = parseInt(e.target.value, 10);
            this.setActiveCharacterId(newId);
        };
    },

    renderPresets() {
        const box = document.getElementById("presetButtons");
        if (!box) return;

        box.innerHTML = "";
        this.presets.forEach(p => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn-preset";
            btn.innerHTML = `<span class="icon">${p.avatar_icon}</span> ${p.name}`;
            btn.title = p.style_hint;
            btn.onclick = () => this.applyPreset(p);
            box.appendChild(btn);
        });
    },

    applyPreset(p) {
        document.getElementById("inpCharName").value = p.name;
        document.getElementById("inpCharCode").value = p.code;
        document.getElementById("inpCharAvatar").value = p.avatar_icon;
        document.getElementById("selCharBaseModel").value = p.base_model;
        document.getElementById("inpCharTrigger").value = p.trigger_words;
        document.getElementById("inpCharNegative").value = p.negative_prompt;
        document.getElementById("inpCharLora").value = p.default_lora;
        document.getElementById("inpCharLoraStrength").value = p.lora_strength || 0.85;
        document.getElementById("inpCharDesc").value = `${p.description}\n\n${p.style_hint}`;
        
        if (typeof showToast === "function") {
            showToast(`✨ 已套用「${p.name}」标准工业级设定示范！`);
        }
    },

    renderCharCards() {
        const list = document.getElementById("charCardsList");
        if (!list) return;

        list.innerHTML = "";
        const activeId = this.getActiveCharacterId();

        this.characters.forEach(c => {
            const card = document.createElement("div");
            card.className = `char-card-item ${c.id === activeId ? 'active' : ''}`;
            card.innerHTML = `
                <div class="char-card-top">
                    <div class="char-card-avatar">${c.avatar_icon || "👧"}</div>
                    <div class="char-card-meta">
                        <h4>${c.name}</h4>
                        <span>代号: ${c.code} • ${(c.base_model || 'sdxl').toUpperCase()}</span>
                    </div>
                </div>
                <div class="char-card-tags" title="${c.trigger_words}">
                    🎯 ${c.trigger_words}
                </div>
                <div class="char-card-footer">
                    <span>生产: <strong class="stat-badge">${c.generated_count || 0} / ${c.task_count || 0}</strong></span>
                    <div style="display:flex;gap:6px;">
                        <button class="btn btn-sm btn-ghost btn-edit-char" data-id="${c.id}" title="编辑属性">✏️</button>
                        ${c.id !== 1 ? `<button class="btn btn-sm btn-ghost btn-del-char" data-id="${c.id}" title="删除" style="color:var(--danger)">🗑️</button>` : ''}
                    </div>
                </div>
            `;

            card.onclick = (e) => {
                if (e.target.closest("button")) return;
                this.setActiveCharacterId(c.id);
                this.renderCharCards();
            };

            const btnEdit = card.querySelector(".btn-edit-char");
            if (btnEdit) {
                btnEdit.onclick = () => this.editCharacter(c);
            }

            const btnDel = card.querySelector(".btn-del-char");
            if (btnDel) {
                btnDel.onclick = () => this.deleteCharacter(c);
            }

            list.appendChild(card);
        });
    },

    editCharacter(c) {
        document.getElementById("charFormId").value = c.id;
        document.getElementById("charFormTitle").textContent = `编辑角色: ${c.name}`;
        document.getElementById("inpCharName").value = c.name;
        document.getElementById("inpCharCode").value = c.code;
        document.getElementById("inpCharCode").disabled = true; // code is primary key identifier
        document.getElementById("inpCharAvatar").value = c.avatar_icon || "👧";
        document.getElementById("selCharBaseModel").value = c.base_model || "sdxl";
        document.getElementById("inpCharTrigger").value = c.trigger_words || "";
        document.getElementById("inpCharNegative").value = c.negative_prompt || "";
        document.getElementById("inpCharLora").value = c.default_lora || "";
        document.getElementById("inpCharLoraStrength").value = c.lora_strength || 0.85;
        document.getElementById("inpCharDesc").value = c.description || "";
        
        const autoMat = document.getElementById("groupAutoMatrix");
        if (autoMat) autoMat.style.display = "none";
    },

    resetCharForm() {
        document.getElementById("charFormId").value = "";
        document.getElementById("charFormTitle").textContent = "新建角色定义";
        document.getElementById("charForm").reset();
        document.getElementById("inpCharCode").disabled = false;
        document.getElementById("inpCharAvatar").value = "👧";
        document.getElementById("inpCharLoraStrength").value = 0.85;
        
        const autoMat = document.getElementById("groupAutoMatrix");
        if (autoMat) autoMat.style.display = "block";
    },

    async saveCharacter() {
        const id = document.getElementById("charFormId").value;
        const name = document.getElementById("inpCharName").value.trim();
        const code = document.getElementById("inpCharCode").value.trim();
        const trigger = document.getElementById("inpCharTrigger").value.trim();

        if (!name || !trigger || (!id && !code)) {
            alert("请填写必填项（角色名称、标识代号、核心触发词）！");
            return;
        }

        const payload = {
            name: name,
            code: code,
            avatar_icon: document.getElementById("inpCharAvatar").value.trim() || "👧",
            base_model: document.getElementById("selCharBaseModel").value,
            trigger_words: trigger,
            negative_prompt: document.getElementById("inpCharNegative").value.trim(),
            default_lora: document.getElementById("inpCharLora").value.trim(),
            lora_strength: parseFloat(document.getElementById("inpCharLoraStrength").value) || 0.85,
            description: document.getElementById("inpCharDesc").value.trim(),
            auto_generate_matrix: document.getElementById("chkAutoMatrix")?.checked ?? true
        };

        try {
            let res;
            if (id) {
                // Update
                res = await fetch(`/api/characters/${id}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
            } else {
                // Create
                res = await fetch("/api/characters", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
            }

            if (!res.ok) {
                const err = await res.json();
                alert(err.detail || "保存失败");
                return;
            }

            const saved = await res.json();
            if (typeof showToast === "function") {
                showToast(`✅ 角色「${saved.name}」已成功保存！`);
            }

            await this.loadCharacters();
            this.setActiveCharacterId(saved.id);
            this.resetCharForm();
        } catch (e) {
            console.error("Save character error", e);
            alert("保存异常，请检查网络与服务状态");
        }
    },

    async deleteCharacter(c) {
        if (!confirm(`确定要删除角色「${c.name}」及其专属的变体任务与图片记录吗？此操作不可恢复！`)) {
            return;
        }

        try {
            const res = await fetch(`/api/characters/${c.id}`, { method: "DELETE" });
            if (res.ok) {
                if (typeof showToast === "function") {
                    showToast(`🗑️ 角色「${c.name}」已删除`);
                }
                await this.loadCharacters();
                this.setActiveCharacterId(1); // fallback to default
            } else {
                const err = await res.json();
                alert(err.detail || "删除失败");
            }
        } catch (e) {
            console.error("Delete character error", e);
        }
    },

    renderBenchmarkChars() {
        const sel = document.getElementById("benchSelChar");
        if (!sel) return;

        sel.innerHTML = "";
        this.characters.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = `${c.avatar_icon || "👧"} ${c.name}`;
            sel.appendChild(opt);
        });

        sel.value = this.getActiveCharacterId();
    },

    async runBenchmark() {
        const charId = parseInt(document.getElementById("benchSelChar").value, 10);
        const style = document.getElementById("benchSelStyle").value;
        const outfit = document.getElementById("benchSelOutfit").value;
        const seed = parseInt(document.getElementById("benchSeed").value, 10) || 424242;

        const grid = document.getElementById("benchmarkGrid");
        grid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align:center; padding: 40px; color: var(--text-muted);">
                <div class="pulse-dot" style="display:inline-block; margin-right:8px;"></div>
                正在并行测试分析 4 种阶梯一致性方案 (Phase 1 ~ Phase 4)...
            </div>
        `;

        try {
            const res = await fetch("/api/characters/benchmark/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    character_id: charId,
                    style_tag: style,
                    outfit_tag: outfit,
                    pose_tag: "portrait_close",
                    seed: seed
                })
            });

            if (!res.ok) {
                const err = await res.json();
                grid.innerHTML = `<div style="grid-column: 1 / -1; color: var(--danger); text-align:center;">错误: ${err.detail || '运行失败'}</div>`;
                return;
            }

            const data = await res.json();
            grid.innerHTML = "";

            data.phases.forEach(ph => {
                const card = document.createElement("div");
                card.className = "bench-card";
                card.innerHTML = `
                    <div class="bench-card-header">
                        <span class="bench-phase-tag">PHASE 0${ph.phase}</span>
                        <h4>${ph.phase_name}</h4>
                    </div>
                    <div class="bench-card-img">
                        <img src="${ph.image_url || ''}" alt="Phase ${ph.phase}">
                    </div>
                    <div class="bench-card-body">
                        <div class="bench-score-row">
                            <span class="label">一致性指数:</span>
                            <span class="score">${ph.phase === 1 ? '★☆☆☆ (易漂移)' : (ph.phase === 2 ? '★★☆☆ (色彩锁定)' : (ph.phase === 3 ? '★★★☆ (五官锁定)' : '★★★★ (终极稳定 >95%)'))}</span>
                        </div>
                        <p class="bench-desc">${ph.description}</p>
                        <div>
                            <strong style="color:var(--text-secondary);font-size:10px;">生效正面 Prompt:</strong>
                            <div class="bench-prompt-box">${ph.prompt}</div>
                        </div>
                        <div>
                            <strong style="color:var(--text-secondary);font-size:10px;">专属负向隔离词:</strong>
                            <div class="bench-prompt-box" style="max-height:50px;">${ph.negative_prompt}</div>
                        </div>
                    </div>
                `;
                grid.appendChild(card);
            });
        } catch (e) {
            console.error("Benchmark error", e);
            grid.innerHTML = `<div style="grid-column: 1 / -1; color: var(--danger); text-align:center;">请求异常，请稍后重试</div>`;
        }
    },

    bindEvents() {
        // Manage Chars button opens char modal
        const btnManage = document.getElementById("btnManageChars");
        const charModal = document.getElementById("charModal");
        const btnCloseCharModal = document.getElementById("btnCloseCharModal");
        const btnCancelChar = document.getElementById("btnCancelChar");
        const btnSaveChar = document.getElementById("btnSaveChar");
        const btnNewChar = document.getElementById("btnNewChar");

        if (btnManage && charModal) {
            btnManage.onclick = () => {
                this.resetCharForm();
                this.renderCharCards();
                charModal.style.display = "flex";
            };
        }

        if (btnCloseCharModal && charModal) {
            btnCloseCharModal.onclick = () => charModal.style.display = "none";
        }
        if (btnCancelChar && charModal) {
            btnCancelChar.onclick = () => charModal.style.display = "none";
        }
        if (btnSaveChar) {
            btnSaveChar.onclick = () => this.saveCharacter();
        }
        if (btnNewChar) {
            btnNewChar.onclick = () => this.resetCharForm();
        }

        // Benchmark button opens benchmark modal
        const btnBenchmark = document.getElementById("btnOpenBenchmark");
        const benchModal = document.getElementById("benchmarkModal");
        const btnCloseBenchmark = document.getElementById("btnCloseBenchmark");
        const btnRunBenchmark = document.getElementById("btnRunBenchmark");

        if (btnBenchmark && benchModal) {
            btnBenchmark.onclick = () => {
                this.renderBenchmarkChars();
                benchModal.style.display = "flex";
                this.runBenchmark(); // auto-run default preview
            };
        }

        if (btnCloseBenchmark && benchModal) {
            btnCloseBenchmark.onclick = () => benchModal.style.display = "none";
        }

        if (btnRunBenchmark) {
            btnRunBenchmark.onclick = () => this.runBenchmark();
        }
    }
};

document.addEventListener("DOMContentLoaded", () => {
    window.CharacterManager.init();
});
