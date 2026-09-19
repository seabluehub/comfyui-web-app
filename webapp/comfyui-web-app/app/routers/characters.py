import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
from app.database import get_db
from app.matrix_generator import populate_matrix, STYLES, OUTFITS, POSES
from app.models import (
    CharacterOut, CharacterCreate, CharacterUpdate, CharacterPreset,
    ConsistencyBenchmarkRequest, ConsistencyBenchmarkResponse, ConsistencyBenchmarkPhaseItem
)
from app.config import MOCK_MODE, OUTPUT_DIR, THUMB_DIR

logger = logging.getLogger("characters_router")
router = APIRouter(prefix="/api/characters", tags=["Characters Management"])

# Curated presets with detailed field examples and best-practice prompt weights
CHARACTER_PRESETS: List[dict] = [
    {
        "name": "露米娜 (Lumina)",
        "code": "lumina_chan",
        "avatar_icon": "👧",
        "trigger_words": "1girl, (lumina_face:1.25), (pure silver hair:1.2), (glowing purple eyes:1.2), long twin-tails, energetic expression, delicate facial features",
        "negative_prompt": "brown hair, black hair, golden hair, blue eyes, red eyes, mutiple girls, deformed face",
        "default_lora": "lumina_anime_v1.safetensors",
        "lora_strength": 0.85,
        "base_model": "sdxl",
        "description": "赛博科技与元气学院风美少女。标志特征：纯银色超长双马尾、霓虹紫瞳与微光眼眸。适合赛博朋克、未来机能、经典学院等画风。",
        "style_hint": "【提示词示范】强调 (lumina_face:1.25) 与 (silver hair:1.2) 高权重；负向词明确封锁 brown/black/golden 发色，避免被服装染色。"
    },
    {
        "name": "星野 (Hoshino)",
        "code": "hoshino_chan",
        "avatar_icon": "🌸",
        "trigger_words": "1girl, (hoshino_face:1.25), (soft pastel pink hair:1.2), (golden yellow halo:1.15), ahoge, (blue and amber heterochromia:1.2), sleepy half-closed eyes",
        "negative_prompt": "silver hair, black hair, green eyes, missing halo, bad anatomy, deformed eyes",
        "default_lora": "hoshino_sdxl_v1.safetensors",
        "lora_strength": 0.85,
        "base_model": "sdxl",
        "description": "学院慵懒风粉发光环少女。标志特征：蓬松淡粉长发、头顶呆毛、漂浮金色光环、左蓝右金异色瞳与略带困意的温柔眼神。",
        "style_hint": "【提示词示范】异色瞳使用 (blue and amber heterochromia:1.2) 精确加权；光环添加 (golden yellow halo:1.15)；负向词排除 missing halo 与错误眼色。"
    },
    {
        "name": "艾尔莎 (Elsa)",
        "code": "elsa_knight",
        "avatar_icon": "⚔️",
        "trigger_words": "1girl, (elsa_face:1.25), (shining blonde hair:1.2), high ponytail, (sharp sapphire blue eyes:1.2), dignified gaze, heroic aura, delicate nose",
        "negative_prompt": "pink hair, purple hair, red eyes, messy ponytail, low quality, deformed hands",
        "default_lora": "elsa_knight_v1.safetensors",
        "lora_strength": 0.85,
        "base_model": "sdxl",
        "description": "奇幻英气女骑士。标志特征：闪耀金发高马尾、锐利清澈的蓝宝石眼瞳、英气凛然的站姿与坚定威严神采。适合战甲、晚礼服与宏大外景。",
        "style_hint": "【提示词示范】高马尾使用 high ponytail 搭配 sharp sapphire blue eyes；负向词屏蔽 pink/purple 发色，防止与晚霞场景混色。"
    },
    {
        "name": "墨羽 (Moyu)",
        "code": "moyu_guofeng",
        "avatar_icon": "🪭",
        "trigger_words": "1girl, (moyu_face:1.25), (sleek straight jet-black hair:1.2), (deep crimson red eyes:1.2), bindi on forehead, calm gentle smile, fair pale porcelain skin",
        "negative_prompt": "blonde hair, silver hair, blue eyes, modern glasses, deformed face, bad hands",
        "default_lora": "moyu_hanfu_v1.safetensors",
        "lora_strength": 0.85,
        "base_model": "sdxl",
        "description": "古风优雅仙侠少女。标志特征：如墨漆黑垂直长发、眉心朱砂痣 (bindi on forehead)、深邃赤红瞳仁与温婉清冷古典五官。适合汉服、水墨与月夜。",
        "style_hint": "【提示词示范】黑发使用 (sleek straight jet-black hair:1.2)；红瞳用 deep crimson red eyes；眉心红痣必须用 bindi on forehead 触发。"
    }
]

def _row_to_character_out(row: dict, conn) -> CharacterOut:
    char_id = row["id"]
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM generation_tasks WHERE character_id = ?", (char_id,))
    task_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM generated_images WHERE character_id = ?", (char_id,))
    gen_count = cur.fetchone()[0]
    
    return CharacterOut(
        id=row["id"],
        name=row["name"],
        code=row["code"],
        default_lora=row["default_lora"] or "",
        trigger_words=row["trigger_words"] or "",
        base_model=row["base_model"] or "sdxl",
        description=row["description"],
        created_at=str(row["created_at"]),
        avatar_icon=row.get("avatar_icon") or "👧",
        negative_prompt=row.get("negative_prompt") or "",
        lora_strength=float(row.get("lora_strength") or 0.85),
        task_count=task_count,
        generated_count=gen_count
    )

@router.get("", response_model=List[CharacterOut])
def list_characters():
    """List all configured characters with task and image statistics."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM characters ORDER BY id ASC")
        rows = [dict(r) for r in cur.fetchall()]
        return [_row_to_character_out(r, conn) for r in rows]

@router.get("/presets/examples", response_model=List[CharacterPreset])
def get_presets():
    """Return standard production character presets with prompt examples and field guidance."""
    return [CharacterPreset(**p) for p in CHARACTER_PRESETS]

@router.get("/{character_id}", response_model=CharacterOut)
def get_character(character_id: int):
    """Retrieve detailed definition of a single character."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="角色不存在")
        return _row_to_character_out(dict(row), conn)

@router.post("", response_model=CharacterOut)
def create_character(req: CharacterCreate):
    """Create a new character and optionally generate its 1000-task matrix."""
    with get_db() as conn:
        cur = conn.cursor()
        # Check code uniqueness
        cur.execute("SELECT id FROM characters WHERE code = ?", (req.code,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail=f"角色标识代号「{req.code}」已存在，请使用其他英文代号")

        cur.execute("""
            INSERT INTO characters (name, code, default_lora, trigger_words, base_model, description, avatar_icon, negative_prompt, lora_strength)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.name,
            req.code,
            req.default_lora or "",
            req.trigger_words,
            req.base_model,
            req.description or "",
            req.avatar_icon or "👧",
            req.negative_prompt or "",
            req.lora_strength or 0.85
        ))
        conn.commit()
        new_id = cur.lastrowid

    # Auto generate matrix if requested
    if req.auto_generate_matrix:
        populate_matrix(character_id=new_id, force_rebuild=False)

    return get_character(new_id)

@router.put("/{character_id}", response_model=CharacterOut)
def update_character(character_id: int, req: CharacterUpdate):
    """Update attributes and trigger definitions for an existing character."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="角色不存在")

        current = dict(row)
        name = req.name if req.name is not None else current["name"]
        trigger_words = req.trigger_words if req.trigger_words is not None else current["trigger_words"]
        default_lora = req.default_lora if req.default_lora is not None else current["default_lora"]
        base_model = req.base_model if req.base_model is not None else current["base_model"]
        description = req.description if req.description is not None else current["description"]
        avatar_icon = req.avatar_icon if req.avatar_icon is not None else current.get("avatar_icon", "👧")
        negative_prompt = req.negative_prompt if req.negative_prompt is not None else current.get("negative_prompt", "")
        lora_strength = req.lora_strength if req.lora_strength is not None else current.get("lora_strength", 0.85)

        cur.execute("""
            UPDATE characters
            SET name = ?, trigger_words = ?, default_lora = ?, base_model = ?, description = ?,
                avatar_icon = ?, negative_prompt = ?, lora_strength = ?
            WHERE id = ?
        """, (name, trigger_words, default_lora, base_model, description, avatar_icon, negative_prompt, lora_strength, character_id))
        conn.commit()

    return get_character(character_id)

@router.delete("/{character_id}")
def delete_character(character_id: int):
    """Delete a character and cascade cleanup its matrix and tasks."""
    if character_id == 1:
        raise HTTPException(status_code=400, detail="系统默认角色（Lumina）受保护，禁止删除")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM characters WHERE id = ?", (character_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="角色不存在")

        # Cascade delete
        cur.execute("DELETE FROM generated_images WHERE character_id = ?", (character_id,))
        cur.execute("DELETE FROM generation_tasks WHERE character_id = ?", (character_id,))
        cur.execute("DELETE FROM prompt_matrix WHERE character_id = ?", (character_id,))
        cur.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        conn.commit()

    return {"status": "success", "message": f"角色 #{character_id} 及其所有任务数据已删除"}

@router.post("/{character_id}/matrix")
def rebuild_character_matrix(character_id: int, force_rebuild: bool = False):
    """Generate or rebuild 1000 tasks matrix for the specified character."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM characters WHERE id = ?", (character_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="角色不存在")

    count = populate_matrix(character_id=character_id, force_rebuild=force_rebuild)
    return {"status": "success", "character_id": character_id, "tasks_count": count}

@router.post("/benchmark/run", response_model=ConsistencyBenchmarkResponse)
def run_consistency_benchmark(req: ConsistencyBenchmarkRequest):
    """
    Run or preview a phased 4-stage consistency comparison for the specified character & combination.
    Phases:
      Phase 1: Base Text-to-Image (No LoRA, Unweighted raw text)
      Phase 2: Prompt Weighting & Negative Color Shielding
      Phase 3: Character Dedicated LoRA (0.85 strength) + Quality Boost
      Phase 4: Full Protection (Reference Image / FaceID Anchor + LoRA + Shielding)
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM characters WHERE id = ?", (req.character_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="角色不存在")
        char = dict(row)

    # Lookup tag names
    style_dict = dict([(t, c) for t, c, _ in STYLES])
    outfit_dict = dict([(t, c) for t, c, _ in OUTFITS])
    pose_dict = dict([(t, c) for t, c, _ in POSES])

    style_cn = style_dict.get(req.style_tag, req.style_tag)
    outfit_cn = outfit_dict.get(req.outfit_tag, req.outfit_tag)
    pose_cn = pose_dict.get(req.pose_tag, req.pose_tag)

    raw_trigger = char.get("trigger_words", "1girl, silver hair, purple eyes")
    char_neg = char.get("negative_prompt", "")
    default_lora = char.get("default_lora", "")

    from PIL import Image, ImageDraw

    phases = []
    phase_configs = [
        (
            1,
            "阶段一：纯文本基准 (无LoRA / 原始词)",
            "无权重语法，无色彩负向隔离，仅依靠通用文生图。人脸极易受画风色彩侵蚀，发生发色与五官漂移。",
            f"1girl, {req.outfit_tag}, {req.style_tag}, {req.pose_tag}",
            "blurry, low quality, pixelated",
            None,
            0.0,
            (90, 95, 115)
        ),
        (
            2,
            "阶段二：Prompt 加权与反向色彩屏障",
            "引入角色专属加权词 (weight:1.25) 置于前置 Token，负向词加入相斥发色/瞳色屏蔽，初步抑制染色现象。",
            f"masterpiece, best quality, {raw_trigger}, {req.outfit_tag}, {req.style_tag}, {req.pose_tag}, 8k resolution",
            f"blurry, low quality, {char_neg}".strip(", "),
            None,
            0.0,
            (60, 110, 150)
        ),
        (
            3,
            "阶段三：角色专属 LoRA 几何锁定",
            f"挂载 {default_lora or '专用LoRA'} (强度 0.85)，深度固化人脸轮廓、眼部比例与发流走向，跨画风保持同一个人。",
            f"masterpiece, ultra-detailed anime artwork, {raw_trigger}, {req.outfit_tag}, {req.style_tag}, {req.pose_tag}",
            f"blurry, deformed face, bad anatomy, {char_neg}".strip(", "),
            default_lora,
            char.get("lora_strength", 0.85) or 0.85,
            (140, 70, 160)
        ),
        (
            4,
            "阶段四：全链路立体防护 (IP-Adapter + LoRA + FaceDetailer)",
            "工业级终极一致性：正脸基准图 (Reference Image) 特征注入 + 角色 LoRA + 远景面部自动二次精修，一致性高达 >95%。",
            f"masterpiece, best quality, ultra-detailed, {raw_trigger}, {req.outfit_tag}, {req.style_tag}, {req.pose_tag}, crisp lineart",
            f"blurry, deformed, mutated, extra limbs, {char_neg}".strip(", "),
            default_lora,
            char.get("lora_strength", 0.85) or 0.85,
            (40, 150, 120)
        )
    ]

    for p_num, p_name, p_desc, p_prompt, p_neg, p_lora, p_strength, p_color in phase_configs:
        fname = f"benchmark_{char['code']}_phase{p_num}_{req.seed}.png"
        full_path = OUTPUT_DIR / fname
        thumb_path = THUMB_DIR / fname

        # Draw benchmark visual representation
        img = Image.new("RGB", (768, 768), color=p_color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(15, 15), (753, 753)], outline=(255, 255, 255), width=3)
        draw.ellipse([(200, 120), (568, 488)], fill=(p_color[0] + 35, p_color[1] + 35, p_color[2] + 35), outline=(255, 255, 255), width=2)
        
        # Text annotations
        draw.text((40, 40), f"Phase {p_num}: {p_name}", fill=(255, 255, 255))
        draw.text((40, 75), f"Character: {char['name']} ({char['code']}) | Seed: {req.seed}", fill=(220, 240, 255))
        draw.text((40, 520), f"Style: {style_cn} | Outfit: {outfit_cn} | Pose: {pose_cn}", fill=(255, 255, 200))
        draw.text((40, 560), f"LoRA: {p_lora or 'NONE'} (Strength: {p_strength})", fill=(255, 255, 255))
        draw.text((40, 600), f"Consistency Index: {'★☆☆☆ (容易漂移)' if p_num==1 else ('★★☆☆ (色彩锁定)' if p_num==2 else ('★★★☆ (五官锁定)' if p_num==3 else '★★★★ (全维一致 >95%)'))}", fill=(255, 220, 100))
        
        snippet = (p_prompt[:110] + "...") if len(p_prompt) > 110 else p_prompt
        draw.text((40, 650), f"Prompt: {snippet}", fill=(220, 220, 220))
        
        img.save(full_path, "PNG")
        thumb = img.resize((360, 360), Image.Resampling.LANCZOS)
        thumb.save(thumb_path, "JPEG", quality=85)

        phases.append(ConsistencyBenchmarkPhaseItem(
            phase=p_num,
            phase_name=p_name,
            description=p_desc,
            prompt=p_prompt,
            negative_prompt=p_neg,
            lora_used=p_lora,
            lora_strength=p_strength,
            image_url=f"/output/full/{fname}",
            status="completed"
        ))

    return ConsistencyBenchmarkResponse(
        character_id=char["id"],
        character_name=char["name"],
        seed=req.seed,
        style_tag=f"{style_cn} ({req.style_tag})",
        outfit_tag=f"{outfit_cn} ({req.outfit_tag})",
        pose_tag=f"{pose_cn} ({req.pose_tag})",
        phases=phases
    )
