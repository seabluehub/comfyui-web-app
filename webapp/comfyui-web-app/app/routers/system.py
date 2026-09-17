from fastapi import APIRouter, Request
from app.config import MOCK_MODE, COMFYUI_BASE_URL, PORT, HOST
from app.comfy_client import ComfyUIClient

router = APIRouter(prefix="/api/system", tags=["System"])

@router.get("/health")
async def health(request: Request):
    client: ComfyUIClient = request.app.state.comfy_client
    comfy_ok = await client.check_health()
    return {
        "status": "healthy",
        "mock_mode": MOCK_MODE,
        "comfyui_base_url": COMFYUI_BASE_URL,
        "comfyui_connected": comfy_ok,
        "server_port": PORT
    }
