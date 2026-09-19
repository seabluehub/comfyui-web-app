import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Set

from app.config import OUTPUT_DIR, THUMB_DIR, PORT, HOST
from app.database import init_db
from app.matrix_generator import populate_matrix
from app.comfy_client import ComfyUIClient
from app.batch_worker import BatchWorker
from app.routers import gallery, batch, system, characters

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        text = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(text)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    populate_matrix(character_id=1, force_rebuild=False)
    
    comfy_client = ComfyUIClient()
    worker = BatchWorker(comfy_client=comfy_client)
    
    # Wire batch worker events to WebSocket broadcaster
    async def on_worker_event(event: dict):
        await ws_manager.broadcast(event)

    worker.register_listener(on_worker_event)

    app.state.comfy_client = comfy_client
    app.state.worker = worker
    app.state.ws_manager = ws_manager

    yield
    # Shutdown
    worker.stop()

app = FastAPI(
    title="ComfyUI Anime Character Batch Production & Gallery",
    description="Local mass-production pipeline: 1000 character variants with character consistency and full prompt tracking.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(gallery.router)
app.include_router(batch.router)
app.include_router(system.router)
app.include_router(characters.router)

# WebSocket endpoint for real-time generation progress
@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial status
        status = app.state.worker.get_status()
        await websocket.send_text(json.dumps({"type": "init_status", "data": status}))
        while True:
            # Keep-alive receive ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# Mount media directories
app.mount("/output/full", StaticFiles(directory=str(OUTPUT_DIR)), name="output_full")
app.mount("/output/thumbs", StaticFiles(directory=str(THUMB_DIR)), name="output_thumbs")

# Mount frontend static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
