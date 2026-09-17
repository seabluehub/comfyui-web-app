import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Server Config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# ComfyUI Engine Config
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1")
COMFYUI_PORT = int(os.getenv("COMFYUI_PORT", "8188"))
COMFYUI_CLIENT_ID = os.getenv("COMFYUI_CLIENT_ID", "comfy_web_app_client")
COMFYUI_BASE_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"
COMFYUI_WS_URL = f"ws://{COMFYUI_HOST}:{COMFYUI_PORT}/ws?clientId={COMFYUI_CLIENT_ID}"

# Mode: true for local dev simulator without active GPU ComfyUI, false for live ComfyUI
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes")

# Storage Paths
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/tasks.sqlite")
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output/full")
THUMB_DIR = BASE_DIR / os.getenv("THUMB_DIR", "output/thumbs")
WORKFLOWS_DIR = BASE_DIR / "workflows"

# Local model library (used to list checkpoints/loras when ComfyUI is offline)
_models_extra = os.getenv("MODELS_EXTRA_PATH", "")
MODELS_EXTRA_PATH = Path(_models_extra) if _models_extra else None

# Ensure output directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Thermal & Batch Settings
COOLDOWN_BATCH_SIZE = int(os.getenv("COOLDOWN_BATCH_SIZE", "30"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "15"))
FREE_MEMORY_BATCH_SIZE = int(os.getenv("FREE_MEMORY_BATCH_SIZE", "50"))
