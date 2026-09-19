import sqlite3
from typing import Optional, Dict, Any, List
from app.config import DATABASE_PATH

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(64) NOT NULL,
            code VARCHAR(32) UNIQUE NOT NULL,
            default_lora VARCHAR(128) NOT NULL,
            trigger_words TEXT NOT NULL,
            base_model VARCHAR(32) DEFAULT 'sdxl',
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prompt_matrix (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            style_tag VARCHAR(64) NOT NULL,
            outfit_tag VARCHAR(64) NOT NULL,
            pose_tag VARCHAR(64) NOT NULL,
            prompt_raw TEXT NOT NULL,
            prompt_expanded TEXT NOT NULL,
            negative_prompt TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_id) REFERENCES characters(id)
        );

        CREATE TABLE IF NOT EXISTS generation_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matrix_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            status VARCHAR(16) DEFAULT 'PENDING',
            seed BIGINT NOT NULL,
            steps INTEGER DEFAULT 25,
            cfg FLOAT DEFAULT 7.0,
            width INTEGER DEFAULT 1024,
            height INTEGER DEFAULT 1024,
            sampler_name VARCHAR(32) DEFAULT 'euler_ancestral',
            scheduler VARCHAR(32) DEFAULT 'karras',
            comfy_prompt_id VARCHAR(64),
            error_msg TEXT,
            execution_time_sec FLOAT DEFAULT 0.0,
            retry_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (matrix_id) REFERENCES prompt_matrix(id),
            FOREIGN KEY (character_id) REFERENCES characters(id)
        );

        CREATE TABLE IF NOT EXISTS generated_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER UNIQUE NOT NULL,
            character_id INTEGER NOT NULL,
            file_name VARCHAR(128) NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            thumb_path VARCHAR(255) NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            style_tag VARCHAR(64),
            outfit_tag VARCHAR(64),
            pose_tag VARCHAR(64),
            prompt_final TEXT NOT NULL,
            seed BIGINT NOT NULL,
            rating INTEGER DEFAULT 0,
            is_favorite BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES generation_tasks(id),
            FOREIGN KEY (character_id) REFERENCES characters(id)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON generation_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_images_character ON generated_images(character_id);
        CREATE INDEX IF NOT EXISTS idx_images_tags ON generated_images(style_tag, outfit_tag, pose_tag);
        CREATE INDEX IF NOT EXISTS idx_images_rating ON generated_images(rating);
        """)

        # Lightweight migration: add gen_config column for generated_images
        cur = conn.cursor()
        cols_img = [r[1] for r in cur.execute("PRAGMA table_info(generated_images)").fetchall()]
        if "gen_config" not in cols_img:
            cur.execute("ALTER TABLE generated_images ADD COLUMN gen_config TEXT")

        # Lightweight migration: add avatar_icon, negative_prompt, lora_strength for characters
        cols_char = [r[1] for r in cur.execute("PRAGMA table_info(characters)").fetchall()]
        if "avatar_icon" not in cols_char:
            cur.execute("ALTER TABLE characters ADD COLUMN avatar_icon VARCHAR(32) DEFAULT '👧'")
        if "negative_prompt" not in cols_char:
            cur.execute("ALTER TABLE characters ADD COLUMN negative_prompt TEXT DEFAULT ''")
        if "lora_strength" not in cols_char:
            cur.execute("ALTER TABLE characters ADD COLUMN lora_strength FLOAT DEFAULT 0.85")

        # Insert default character if none exists
        cur.execute("SELECT id FROM characters WHERE code = 'lumina_chan'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO characters (name, code, default_lora, trigger_words, base_model, description, avatar_icon, negative_prompt, lora_strength)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "露米娜 (Lumina)",
                "lumina_chan",
                "lumina_anime_v1.safetensors",
                "1girl, (lumina_face:1.25), (pure silver hair:1.2), (glowing purple eyes:1.2), long twin-tails, energetic expression, delicate facial features",
                "sdxl",
                "固定二次元角色：银发紫瞳双马尾美少女，赛博科技与学院风，适配 1000 张多姿态、全风格与服装量产。",
                "👧",
                "brown hair, black hair, golden hair, blue eyes, red eyes, mutiple girls, deformed face",
                0.85
            ))
            conn.commit()
