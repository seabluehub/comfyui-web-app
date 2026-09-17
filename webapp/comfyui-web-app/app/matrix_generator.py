import random
from typing import List, Dict, Tuple
from app.database import get_db

# 10 Styles
STYLES = [
    ("ghibli", "吉卜力手绘", "studio ghibli style, hayao miyazaki aesthetic, hand-drawn watercolor cel, lush scenic atmosphere, nostalgic lighting, whimsical charm"),
    ("makoto_shinkai", "新海诚唯美", "makoto shinkai style, kimi no na wa aesthetic, hyper-detailed anime scenery, vibrant emotional lighting, dramatic sky with volumetric clouds, lens flare"),
    ("cyberpunk", "赛博朋克霓虹", "cyberpunk anime aesthetic, futuristic neon city backdrop, neon magenta and cyan rim light, holographic UI reflections, high tech gritty atmosphere"),
    ("watercolor", "水彩淡彩艺术", "soft watercolor painting style, delicate fluid strokes, pastel color palette, artistic paper texture, dreamy light bleed"),
    ("rococo", "洛可可华丽", "rococo anime style, ornate gold filigree, opulent pastel tones, intricate lace details, romantic classical ambiance, elegant baroque aesthetic"),
    ("gothic", "暗黑哥特", "dark gothic anime style, moonlit shadows, deep crimson and obsidian tones, Victorian stained glass, mysterious melancholic elegance"),
    ("retro_90s", "90年代赛璐璐", "1990s retro anime style, classic hand-painted cel animation look, warm grain, vintage color gamut, clean bold lineart"),
    ("cinematic", "胶片电影质感", "cinematic anime film still, 35mm film grain, shallow depth of field, anamorphic bokeh, dramatic directional lighting"),
    ("summer_breeze", "夏日清新日常", "sunny summer anime aesthetic, bright crisp daylight, blooming sunflowers, blue sky with white clouds, refreshing seaside breeze"),
    ("night_cityscape", "璀璨夜景光斑", "sparkling night city aesthetic, warm bokeh lights, shimmering reflections on rain-slicked asphalt, tranquil midnight beauty")
]

# 20 Outfits
OUTFITS = [
    ("school_uniform", "经典水手制服", "wearing a traditional pleated navy sailor school uniform with red scarf and high socks"),
    ("furisode_kimono", "华美振袖和服", "wearing an ornate floral silk furisode kimono with golden obi sash and kanzashi hair ornament"),
    ("tactical_gear", "机能战术特工服", "wearing high-tech tactical combat gear, modular straps, ballistic vest, and combat boots"),
    ("detective_trench", "英伦侦探风衣", "wearing a double-breasted beige detective trench coat with houndstooth scarf and gloves"),
    ("gothic_lolita", "哥特洛丽塔裙", "wearing an elaborate black and deep violet gothic lolita dress with tiered lace ruffles and ribbons"),
    ("casual_hoodie", "宽松连帽休闲卫衣", "wearing an oversized pastel hoodie, denim shorts, and chunky retro sneakers"),
    ("racing_leather", "赛车手紧身皮衣", "wearing a sleek aerodynamic leather racing suit with sponsor decals and carbon-fiber accents"),
    ("classic_maid", "古典女仆装", "wearing a crisp black and white maid dress with ruffled apron, frilled headband, and white stockings"),
    ("winter_coat", "冬日粗花呢大衣", "wearing a heavy wool winter coat with fluffy earmuffs, thick knitted scarf, and warm mittens"),
    ("sci_fi_plugsuit", "科幻紧身宇航服", "wearing a form-fitting sci-fi plugsuit with luminous energy channels and metallic armor plates"),
    ("magical_girl", "魔法少女战袍", "wearing a sparkling magical girl outfit with layered petal skirts, ribbons, and glowing gemstone brooch"),
    ("gym_sportswear", "学院运动体操服", "wearing athletic school gym clothes, sports jersey, track jacket, and runner shoes"),
    ("evening_gown", "高贵晚礼服", "wearing an elegant floor-length satin evening gown with open back and subtle diamond jewelry"),
    ("academy_blazer", "贵族学院西装", "wearing a tailored academy blazer uniform with crest patch, plaid skirt, and necktie"),
    ("sundress_straw_hat", "吊带夏裙配草帽", "wearing a breezy floral sundress and a wide-brimmed woven straw hat with ribbon"),
    ("modern_cheongsam", "改良锦缎旗袍", "wearing a modern sleeveless silk cheongsam qipao with gold dragon-phoenix embroidery and side slit"),
    ("cozy_pajamas", "居家舒适睡衣", "wearing soft oversized flannel sleepwear with cute plush slippers and sleepy mood"),
    ("safari_explorer", "荒野探险猎装", "wearing an adventurous safari explorer jacket, khaki shorts, utility belt, and binoculars"),
    ("hanfu_skirt", "古风汉服襦裙", "wearing flowing pastel Hanfu robes with wide embroidered sleeves and fluttering waist ribbons"),
    ("streetwear_tech", "街头潮牌工装", "wearing trendy urban streetwear with cargo pants, reflective jacket, and bucket hat")
]

# 5 Poses & Compositions
POSES = [
    ("dynamic_action", "疾驰跃动 / 战斗张力", "dynamic running pose, mid-motion leap, wind blowing hair, sharp determined gaze, energetic dynamic composition"),
    ("portrait_close", "微风吹拂 / 极近肖像", "close-up portrait, gentle smile, direct eye contact with viewer, soft breeze playing with stray bangs, detailed expressive eyes"),
    ("scenic_wide", "伫立远眺 / 广角风景", "wide angle environmental scenery, standing poised while gazing at the horizon, distant breathtaking backdrop, cinematic framing"),
    ("casual_sit", "闲坐憩息 / 咖啡时光", "relaxed sitting pose at a table, chin resting on hand, soft contemplative expression, cozy candid moment"),
    ("dramatic_low", "仰视英雄视角", "dramatic low angle perspective, looking up towards the sky, grand heroic stance, sweeping hair and garments")
]

NEGATIVE_PROMPT_DEFAULT = (
    "ugly, deformed, disfigured, poor anatomy, bad hands, extra fingers, missing fingers, "
    "blurry, low quality, pixelated, watermark, signature, username, text, out of frame"
)

def get_dimensions() -> Dict[str, List[Dict[str, str]]]:
    """Expose the full style/outfit/pose dimension lists (tag + Chinese label) for the UI."""
    def fmt(rows):
        return [{"tag": tag, "name": cn} for tag, cn, _ in rows]
    return {
        "styles": fmt(STYLES),
        "outfits": fmt(OUTFITS),
        "poses": fmt(POSES)
    }

def populate_matrix(character_id: int = 1, force_rebuild: bool = False) -> int:
    """
    Generate 1000 items (10 styles x 20 outfits x 5 poses) for the specified character
    and insert into prompt_matrix and generation_tasks.
    """
    with get_db() as conn:
        cur = conn.cursor()
        
        # Check existing count
        cur.execute("SELECT COUNT(*) FROM prompt_matrix WHERE character_id = ?", (character_id,))
        count = cur.fetchone()[0]
        
        if count >= 1000 and not force_rebuild:
            return count

        if force_rebuild:
            cur.execute("DELETE FROM generated_images WHERE character_id = ?", (character_id,))
            cur.execute("DELETE FROM generation_tasks WHERE character_id = ?", (character_id,))
            cur.execute("DELETE FROM prompt_matrix WHERE character_id = ?", (character_id,))
            conn.commit()

        # Get character info
        cur.execute("SELECT trigger_words FROM characters WHERE id = ?", (character_id,))
        row = cur.fetchone()
        trigger_words = row[0] if row else "1girl, anime masterpiece"

        matrix_records = []
        task_records = []
        
        base_seed = 100000

        for style_tag, style_cn, style_prompt in STYLES:
            for outfit_tag, outfit_cn, outfit_prompt in OUTFITS:
                for pose_tag, pose_cn, pose_prompt in POSES:
                    # Raw composite prompt
                    prompt_raw = f"{trigger_words}, {outfit_prompt}, {style_prompt}, {pose_prompt}"
                    # Expanded prompt with quality boosters
                    prompt_expanded = (
                        f"masterpiece, best quality, ultra-detailed anime artwork, "
                        f"{prompt_raw}, 8k resolution, crisp lineart, striking color harmony"
                    )
                    matrix_records.append((
                        character_id, style_tag, outfit_tag, pose_tag,
                        prompt_raw, prompt_expanded, NEGATIVE_PROMPT_DEFAULT
                    ))

        # Insert matrix
        cur.executemany("""
            INSERT INTO prompt_matrix (character_id, style_tag, outfit_tag, pose_tag, prompt_raw, prompt_expanded, negative_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, matrix_records)

        # Retrieve matrix IDs
        cur.execute("SELECT id FROM prompt_matrix WHERE character_id = ? ORDER BY id ASC", (character_id,))
        matrix_ids = [r[0] for r in cur.fetchall()]

        # Generate 1000 tasks
        random.seed(42)
        for idx, m_id in enumerate(matrix_ids):
            seed = base_seed + random.randint(1000, 99999999)
            task_records.append((
                m_id, character_id, 'PENDING', seed, 25, 7.0, 1024, 1024,
                'euler_ancestral', 'karras'
            ))

        cur.executemany("""
            INSERT INTO generation_tasks (matrix_id, character_id, status, seed, steps, cfg, width, height, sampler_name, scheduler)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, task_records)

        conn.commit()
        return len(matrix_records)
