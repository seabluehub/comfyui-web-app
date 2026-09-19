from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List, Dict, Any
import json
from app.config import WORKFLOWS_DIR, MOCK_MODE
from app.database import get_db
from app.matrix_generator import populate_matrix, get_dimensions
from app.batch_worker import build_task_filter
from app.comfy_client import ComfyUIClient, inspect_checkpoint_file
from app.models import BatchStatusResponse, StartBatchRequest

router = APIRouter(prefix="/api/batch", tags=["Batch Generation"])

# Preferred checkpoints for auto-fallback when template default is missing
_PREFERRED_CKPT_PATTERNS = ("GhostXL", "SDXL-Anime", "Anime")

# Curated one-click presets. Checkpoint/LoRA are resolved dynamically against
# the local model library; unavailable presets are filtered or marked.
_PRESET_DEFS = [
    {
        "id": "speed", "name": "⚡ 极速量产", "badge": "推荐 · 已验证",
        "desc": "GhostXL · 25步 · 1024² · 约8秒/张",
        "template": "sdxl", "match_ckpt": ["GhostXL"], "lora": "", "lora_strength": None,
        "steps": 25, "cfg": 7.0, "width": 1024, "height": 1024
    },
    {
        "id": "anime", "name": "🌸 动漫精修", "badge": "动漫最佳",
        "desc": "天空之境 v3.1 · 28步 · 1024² · 二次元质感更强",
        "template": "sdxl", "match_ckpt": ["天空之境", "SDXL-Anime"], "lora": "", "lora_strength": None,
        "steps": 28, "cfg": 7.0, "width": 1024, "height": 1024
    },
    {
        "id": "draft", "name": "🔍 草稿粗筛", "badge": "最快 ~4秒/张",
        "desc": "GhostXL · 12步 · 768² · 先快速筛构图再精修",
        "template": "sdxl", "match_ckpt": ["GhostXL"], "lora": "", "lora_strength": None,
        "steps": 12, "cfg": 7.0, "width": 768, "height": 768
    },
    {
        "id": "texture", "name": "🎨 质感增强", "badge": "实验",
        "desc": "GhostXL + 斑驳质感LoRA(0.35) · 25步 · 磨砂质感",
        "template": "sdxl", "match_ckpt": ["GhostXL"], "match_lora": ["斑驳w"],
        "lora": None, "lora_strength": 0.35,
        "steps": 25, "cfg": 7.0, "width": 1024, "height": 1024
    },
    {
        "id": "dramatic", "name": "🎭 2.5D戏剧", "badge": None,
        "desc": "ZHMix-Dramatic · 25步 · 1024² · 光影戏剧感",
        "template": "sdxl", "match_ckpt": ["ZHMix"], "lora": "", "lora_strength": None,
        "steps": 25, "cfg": 7.0, "width": 1024, "height": 1024
    },
    {
        "id": "dreamy", "name": "🖌️ 通用插画", "badge": None,
        "desc": "DreamShaper XL · 25步 · 1024² · 泛用质感",
        "template": "sdxl", "match_ckpt": ["dreamshaperXL", "dreamshaper xl"], "lora": "", "lora_strength": None,
        "steps": 25, "cfg": 7.0, "width": 1024, "height": 1024
    },
    {
        "id": "realistic", "name": "📷 写实人像", "badge": None,
        "desc": "写实系底模 · 30步 · 1024² · 真人质感",
        "template": "sdxl", "match_ckpt": ["XXMix_9realistic", "majicMIX"], "lora": "", "lora_strength": None,
        "steps": 30, "cfg": 6.0, "width": 1024, "height": 1024
    },
]

@router.get("/presets")
async def get_presets(request: Request):
    """One-click recommendation combos resolved against the actual local model library."""
    client: ComfyUIClient = request.app.state.comfy_client
    models = await client.list_models()
    incompatible = set(models.get("incompatible") or [])
    ckpt_pool = models["checkpoints"]
    lora_pool = models["loras"]

    def find(patterns, pool, skip_incompatible=True):
        for pat in patterns:
            for name in pool:
                if pat.lower() in name.lower():
                    if skip_incompatible and name in incompatible:
                        continue
                    return name
        return None

    presets = []
    for p in _PRESET_DEFS:
        ckpt = find(p["match_ckpt"], ckpt_pool)
        if not ckpt:
            continue  # required checkpoint not installed locally -> hide preset
        lora = p.get("lora", "")
        lora_strength = p.get("lora_strength")
        if p.get("match_lora"):
            hit = find(p["match_lora"], lora_pool, skip_incompatible=False)
            if not hit:
                continue
            lora = hit
        presets.append({
            "id": p["id"], "name": p["name"], "badge": p["badge"], "desc": p["desc"],
            "template": p["template"], "checkpoint": ckpt, "lora": lora,
            "lora_strength": lora_strength if lora else None,
            "steps": p["steps"], "cfg": p["cfg"], "width": p["width"], "height": p["height"]
        })
    return {"presets": presets, "source": models.get("source")}

def _template_default_model(template: str, model_kind: str) -> str | None:
    """Read the default checkpoint/unet filename from a workflow template."""
    tpl = WORKFLOWS_DIR / template
    if not tpl.exists():
        return None
    with open(tpl, "r", encoding="utf-8") as f:
        wf = json.load(f)
    want_class = "UNETLoader" if model_kind == "flux" else "CheckpointLoaderSimple"
    want_key = "unet_name" if model_kind == "flux" else "ckpt_name"
    for node in wf.values():
        if node.get("class_type") == want_class:
            return node.get("inputs", {}).get(want_key)
    return None

@router.post("/generate-matrix")
def generate_matrix(character_id: int = 1, force_rebuild: bool = False):
    """
    Populate the 1000 combinations matrix and tasks in database.
    """
    count = populate_matrix(character_id=character_id, force_rebuild=force_rebuild)
    return {"status": "ok", "total_matrix_tasks": count}

@router.get("/dimensions")
def dimensions():
    """Full style / outfit / pose dimension lists (tag + Chinese label)."""
    return get_dimensions()

@router.get("/models")
async def list_models(request: Request):
    """Available checkpoints / unets / loras (live ComfyUI or local model library scan)."""
    client: ComfyUIClient = request.app.state.comfy_client
    return await client.list_models()

@router.post("/preview")
def preview_selection(req: StartBatchRequest):
    """Count tasks matching the current tag selection and character, grouped by status."""
    filters = {"styles": req.styles, "outfits": req.outfits, "poses": req.poses}
    where, params = build_task_filter(filters, character_id=req.character_id)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT t.status, COUNT(*) FROM generation_tasks t
            JOIN prompt_matrix m ON t.matrix_id = m.id {where}
            GROUP BY t.status
        """, params)
        counts = dict(cur.fetchall())
    return {
        "matched": sum(counts.values()),
        "pending": counts.get("PENDING", 0),
        "success": counts.get("SUCCESS", 0),
        "failed": counts.get("FAILED", 0),
        "running": counts.get("RUNNING", 0)
    }

@router.get("/status", response_model=BatchStatusResponse)
def get_status(request: Request, character_id: Optional[int] = None):
    worker = request.app.state.worker
    return worker.get_status(character_id=character_id)

@router.post("/start")
async def start_batch(req: StartBatchRequest, request: Request):
    worker = request.app.state.worker
    # Ensure matrix exists
    populate_matrix(character_id=req.character_id, force_rebuild=False)

    if worker.is_running:
        raise HTTPException(status_code=409, detail="批量进程正在运行中，请先暂停或等待完成")

    filters = {"styles": req.styles, "outfits": req.outfits, "poses": req.poses}
    where_all, params_all = build_task_filter(filters, character_id=req.character_id)
    where_pending, params_pending = build_task_filter(filters, statuses=["PENDING"], character_id=req.character_id)

    with get_db() as conn:
        cur = conn.cursor()
        # Optional: re-run already completed / failed tasks of this selection
        if req.include_done:
            # Safety guard: refuse an overly broad rerun that would wipe the gallery
            cur.execute(f"""
                SELECT COUNT(*) FROM generation_tasks t
                JOIN prompt_matrix m ON t.matrix_id = m.id {where_all}
            """, params_all)
            matched_all = cur.fetchone()[0]
            if matched_all > 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"重跑范围过大（匹配 {matched_all} 个任务，将清空对应画廊记录）。"
                           f"请缩小画风/服装/姿态的选择范围，或取消勾选「重跑」"
                )
            cur.execute(f"""
                DELETE FROM generated_images WHERE task_id IN (
                    SELECT t.id FROM generation_tasks t
                    JOIN prompt_matrix m ON t.matrix_id = m.id {where_all}
                )
            """, params_all)
            cur.execute(f"""
                UPDATE generation_tasks SET status = 'PENDING', error_msg = NULL, retry_count = 0,
                       comfy_prompt_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT t.id FROM generation_tasks t
                    JOIN prompt_matrix m ON t.matrix_id = m.id {where_all}
                )
            """, params_all)

        # Apply sampling parameter overrides to the matched pending tasks
        sets, sparams = [], []
        if req.steps is not None:
            sets.append("steps = ?"); sparams.append(req.steps)
        if req.cfg is not None:
            sets.append("cfg = ?"); sparams.append(req.cfg)
        if req.width is not None:
            sets.append("width = ?"); sparams.append(req.width)
        if req.height is not None:
            sets.append("height = ?"); sparams.append(req.height)
        if sets:
            cur.execute(f"""
                UPDATE generation_tasks SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT t.id FROM generation_tasks t
                    JOIN prompt_matrix m ON t.matrix_id = m.id {where_pending}
                )
            """, sparams + params_pending)
        conn.commit()

    # Session-level generation engine config passed through to the worker / comfy client
    template = f"{req.model}_anime_template.json" if req.model in ("sdxl", "flux") else req.model
    warnings = []
    checkpoint_name = req.checkpoint
    lora_value = req.lora  # None = character default, "" = disable, str = explicit file

    # Live mode: validate model files BEFORE queuing anything (fail fast with clear reason)
    if not MOCK_MODE:
        client: ComfyUIClient = request.app.state.comfy_client
        if not await client.check_health():
            raise HTTPException(status_code=503, detail="ComfyUI 未连接，请确认 127.0.0.1:8188 服务已启动")

        models = await client.list_models()
        ckpt_pool = models["unets"] if req.model == "flux" else models["checkpoints"]
        ckpt_set = set(ckpt_pool)
        lora_set = set(models["loras"])

        # --- Resolve checkpoint ---
        if not checkpoint_name:
            checkpoint_name = _template_default_model(template, req.model)
            if checkpoint_name and checkpoint_name not in ckpt_set:
                warnings.append(f"模板默认底模「{checkpoint_name}」在本机不存在，已自动更换")
                checkpoint_name = None
        if not checkpoint_name:
            # Auto-fallback: pick a preferred FULL checkpoint (skip diffusion-only weights)
            def _is_full(name: str) -> bool:
                info = inspect_checkpoint_file(name)
                return info is None or (info["text_encoder"] and info["vae"])
            for pat in _PREFERRED_CKPT_PATTERNS:
                hit = next((n for n in ckpt_pool if pat.lower() in n.lower() and _is_full(n)), None)
                if hit:
                    checkpoint_name = hit
                    break
            if not checkpoint_name and ckpt_pool:
                full_pool = [n for n in ckpt_pool if _is_full(n)]
                checkpoint_name = (full_pool or ckpt_pool)[0]
            if checkpoint_name:
                warnings.append(f"已自动选择底模「{checkpoint_name}」")
        if not checkpoint_name:
            raise HTTPException(status_code=400, detail="本机未找到任何可用底模，请检查 ComfyUI 模型目录")
        elif req.checkpoint and req.checkpoint not in ckpt_set:
            raise HTTPException(status_code=400, detail=f"所选底模「{req.checkpoint}」不存在（可用 {len(ckpt_pool)} 个），请重新选择")

        # Reject diffusion-model-only weights (no CLIP/VAE) before wasting a batch
        if req.model != "flux":
            info = inspect_checkpoint_file(checkpoint_name)
            if info is not None and (not info["text_encoder"] or not info["vae"]):
                missing = []
                if not info["text_encoder"]:
                    missing.append("文本编码器(CLIP)")
                if not info["vae"]:
                    missing.append("VAE")
                raise HTTPException(
                    status_code=400,
                    detail=f"底模「{checkpoint_name}」缺少{'与'.join(missing)}，是纯扩散模型权重，"
                           f"无法用于 SDXL 一体化工作流。请改选完整底模（推荐 GhostXL_V1.0-Baked VAE）"
                )

        # --- Resolve lora ---
        if lora_value is None:
            with get_db() as conn:
                row = conn.cursor().execute(
                    "SELECT default_lora FROM characters WHERE id = ?", (req.character_id,)
                ).fetchone()
            default_lora = row[0] if row else None
            if default_lora and default_lora in lora_set:
                lora_value = default_lora
            else:
                lora_value = ""
                warnings.append(f"角色默认 LoRA「{default_lora}」不存在，本次已自动禁用 LoRA")
        elif lora_value and lora_value not in lora_set:
            raise HTTPException(status_code=400, detail=f"所选 LoRA「{lora_value}」不存在（可用 {len(models['loras'])} 个），请重新选择")

    config = {
        "template_name": template,
        "checkpoint_name": checkpoint_name,
        "lora_override": lora_value,
        "lora_strength": req.lora_strength
    }

    queued = await worker.start(limit=req.limit, filters=filters, config=config, character_id=req.character_id)
    return {"status": "started", "queued": queued, "limit": req.limit, "warnings": warnings}

@router.post("/pause")
def pause_batch(request: Request):
    worker = request.app.state.worker
    worker.pause()
    return {"status": "paused"}

@router.post("/resume")
def resume_batch(request: Request):
    worker = request.app.state.worker
    worker.resume()
    return {"status": "resumed"}

@router.post("/stop")
def stop_batch(request: Request):
    worker = request.app.state.worker
    worker.stop()
    return {"status": "stopped"}
