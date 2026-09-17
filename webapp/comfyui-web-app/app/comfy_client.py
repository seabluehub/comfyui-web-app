import json
import uuid
import asyncio
import struct
import time
import httpx
import websockets
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from PIL import Image, ImageDraw, ImageFont

from app.config import (
    COMFYUI_BASE_URL, COMFYUI_WS_URL, COMFYUI_CLIENT_ID,
    MOCK_MODE, OUTPUT_DIR, THUMB_DIR, WORKFLOWS_DIR, MODELS_EXTRA_PATH
)

MODEL_FILE_EXTS = (".safetensors", ".ckpt", ".pt", ".bin")

def find_model_file(name: str) -> Optional[Path]:
    """Locate a model file (possibly in a subfolder like 'SD1.5\\xxx.safetensors') in the local library."""
    if not MODELS_EXTRA_PATH:
        return None
    rel = name.replace("/", "\\")
    for sub in ("checkpoints", "unet", "diffusion_models"):
        p = MODELS_EXTRA_PATH / sub / rel
        if p.exists():
            return p
    return None

def inspect_checkpoint_file(name: str) -> Optional[Dict[str, bool]]:
    """
    Inspect a safetensors header to see whether the file is a FULL checkpoint
    (unet + text encoder + vae) or a diffusion-model-only weight.
    Returns None if the file cannot be located / parsed (validation skipped).
    """
    path = find_model_file(name)
    if not path or path.suffix.lower() != ".safetensors":
        return None
    try:
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            if n <= 0 or n > 20 * 1024 * 1024:
                return None
            header = json.loads(f.read(n).decode("utf-8", "ignore"))
        keys = [k for k in header.keys() if k != "__metadata__"]
        has_text = any(
            ("conditioner" in k) or k.startswith("cond_stage_model")
            or ("text_encoder" in k) or k.startswith("clip.") or k.startswith("clip_")
            for k in keys
        )
        has_vae = any(
            k.startswith("first_stage_model") or k.startswith("vae.") or k.startswith("vae_")
            for k in keys
        )
        has_unet = any(
            k.startswith("model.") or k.startswith("double_blocks")
            or k.startswith("single_blocks") or k.startswith("transformer.")
            for k in keys
        )
        return {"unet": has_unet, "text_encoder": has_text, "vae": has_vae}
    except Exception as e:
        logger.warning(f"inspect_checkpoint_file failed for {name}: {e}")
        return None

def detect_incompatible_checkpoints(ckpt_names: List[str]) -> List[str]:
    """Names in the checkpoint list that are diffusion-model-only (no CLIP/VAE)."""
    bad = []
    for name in ckpt_names:
        info = inspect_checkpoint_file(name)
        if info is not None and (not info["text_encoder"] or not info["vae"]):
            bad.append(name)
    return bad

class ComfyUIClient:
    def __init__(self, base_url: str = COMFYUI_BASE_URL, ws_url: str = COMFYUI_WS_URL, client_id: str = COMFYUI_CLIENT_ID):
        self.base_url = base_url
        self.ws_url = ws_url
        self.client_id = client_id

    async def check_health(self) -> bool:
        """Check if ComfyUI server is reachable."""
        if MOCK_MODE:
            return True
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/system_stats")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> Dict[str, Any]:
        """
        List available checkpoints / unets / loras.
        Prefers live ComfyUI /object_info; falls back to scanning the local
        models library directory (useful in MOCK_MODE).
        """
        if not MOCK_MODE:
            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    async def fetch(node: str, param: str) -> List[str]:
                        res = await client.get(f"{self.base_url}/object_info/{node}")
                        if res.status_code == 200:
                            return res.json()[node]["input"]["required"][param][0]
                        return []
                    ckpts = await fetch("CheckpointLoaderSimple", "ckpt_name")
                    unets = await fetch("UNETLoader", "unet_name")
                    loras = await fetch("LoraLoader", "lora_name")
                    if ckpts or unets or loras:
                        return {
                            "checkpoints": ckpts, "unets": unets, "loras": loras,
                            "source": "comfyui",
                            "incompatible": detect_incompatible_checkpoints(ckpts)
                        }
            except Exception as e:
                logger.warning(f"Failed to query ComfyUI object_info: {e}")

        def scan(subdirs: List[str]) -> List[str]:
            found: List[str] = []
            if MODELS_EXTRA_PATH and MODELS_EXTRA_PATH.exists():
                for sub in subdirs:
                    d = MODELS_EXTRA_PATH / sub
                    if d.is_dir():
                        found += [f.name for f in d.iterdir() if f.is_file() and f.suffix.lower() in MODEL_FILE_EXTS]
            return sorted(set(found))

        return {
            "checkpoints": scan(["checkpoints"]),
            "unets": scan(["diffusion_models", "unet"]),
            "loras": scan(["loras"]),
            "source": "local_scan",
            "incompatible": detect_incompatible_checkpoints(scan(["checkpoints"]))
        }

    def build_workflow(self, template_name: str, positive_prompt: str, negative_prompt: str,
                       seed: int, steps: int = 25, cfg: float = 7.0,
                       width: int = 1024, height: int = 1024,
                       lora_name: Optional[str] = None,
                       checkpoint_name: Optional[str] = None,
                       lora_strength: Optional[float] = None) -> Dict[str, Any]:
        """
        Load and parameterize workflow template JSON.

        - checkpoint_name: injected into CheckpointLoaderSimple (SDXL) or UNETLoader (Flux).
        - lora_name: None keeps template default; "" disables lora (node bypassed);
          a filename overrides the lora loader input.
        """
        template_file = WORKFLOWS_DIR / template_name
        if not template_file.exists():
            template_file = WORKFLOWS_DIR / "sdxl_anime_template.json"

        with open(template_file, "r", encoding="utf-8") as f:
            wf = json.load(f)

        lora_node_ids: List[str] = []
        remove_lora_nodes = (lora_name == "")

        # Inject into template structure
        for node_id, node in wf.items():
            class_type = node.get("class_type")
            inputs = node.get("inputs", {})
            if class_type == "KSampler":
                inputs["seed"] = seed
                inputs["steps"] = steps
                if "cfg" in inputs:
                    inputs["cfg"] = cfg
            elif class_type == "EmptyLatentImage":
                inputs["width"] = width
                inputs["height"] = height
            elif class_type == "CLIPTextEncode":
                # Differentiate positive and negative
                if node_id == "6" or "masterpiece" in str(inputs.get("text", "")):
                    inputs["text"] = positive_prompt
                elif node_id == "7" or "ugly" in str(inputs.get("text", "")):
                    inputs["text"] = negative_prompt
            elif class_type in ("LoraLoader", "LoraLoaderModelOnly"):
                if remove_lora_nodes:
                    lora_node_ids.append(node_id)
                else:
                    if lora_name:
                        inputs["lora_name"] = lora_name
                    if lora_strength is not None:
                        inputs["strength_model"] = lora_strength
                        if "strength_clip" in inputs:
                            inputs["strength_clip"] = lora_strength
            elif class_type == "CheckpointLoaderSimple" and checkpoint_name:
                inputs["ckpt_name"] = checkpoint_name
            elif class_type == "UNETLoader" and checkpoint_name:
                inputs["unet_name"] = checkpoint_name

        # Bypass lora loaders: rewire consumers to the lora node's own source, then drop the node
        if remove_lora_nodes and lora_node_ids:
            slot_key_map = {0: "model", 1: "clip"}
            for node_id, node in wf.items():
                inputs = node.get("inputs", {})
                for key, val in list(inputs.items()):
                    if isinstance(val, list) and len(val) == 2 and str(val[0]) in lora_node_ids:
                        # Route through the lora node's upstream source (model/clip)
                        upstream = wf[str(val[0])]["inputs"].get(slot_key_map.get(val[1], ""))
                        if upstream is not None:
                            inputs[key] = upstream
                        else:
                            inputs.pop(key)
            for node_id in lora_node_ids:
                wf.pop(node_id, None)

        return wf

    async def free_vram(self, unload_models: bool = False, free_memory: bool = True):
        """Invoke ComfyUI /free endpoint to release PyTorch VRAM fragments."""
        if MOCK_MODE:
            return True
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{self.base_url}/free", json={"unload_models": unload_models, "free_memory": free_memory})
                return True
        except Exception:
            return False

    async def execute_task(self, task_info: Dict[str, Any], progress_cb: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        """
        Executes a generation task. Dispatches to Mock Simulator or Live ComfyUI.
        """
        if MOCK_MODE:
            return await self._execute_mock(task_info, progress_cb)
        else:
            return await self._execute_live(task_info, progress_cb)

    async def _execute_mock(self, task_info: Dict[str, Any], progress_cb: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        """
        Simulates generation for dev environments without active GPU.
        Emits step progress and creates stylized sample PNGs with metadata.
        """
        steps = task_info.get("steps", 25)
        step_interval = 0.04  # ~1.0 sec total per mock image

        for step in range(1, steps + 1):
            await asyncio.sleep(step_interval)
            if progress_cb:
                await progress_cb(step, steps)

        task_id = task_info["id"]
        seed = task_info["seed"]
        style = task_info.get("style_tag", "anime")
        outfit = task_info.get("outfit_tag", "casual")
        pose = task_info.get("pose_tag", "action")
        prompt = task_info.get("prompt_final", "")
        
        file_name = f"lumina_{style}_{outfit}_{task_id:04d}.png"
        full_path = OUTPUT_DIR / file_name
        thumb_path = THUMB_DIR / file_name

        # Color palette by style
        palette_map = {
            "ghibli": (70, 140, 95),
            "makoto_shinkai": (45, 110, 190),
            "cyberpunk": (160, 30, 140),
            "watercolor": (180, 160, 210),
            "rococo": (210, 175, 120),
            "gothic": (40, 35, 55),
            "retro_90s": (195, 80, 60),
            "cinematic": (60, 75, 85),
            "summer_breeze": (90, 185, 230),
            "night_cityscape": (25, 30, 65)
        }
        bg_color = palette_map.get(style, (65, 90, 130))

        # Generate full image 1024x1024
        img = Image.new("RGB", (1024, 1024), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Draw decorative anime silhouette and framing
        draw.rectangle([(20, 20), (1004, 1004)], outline=(255, 255, 255, 180), width=4)
        draw.ellipse([(262, 180), (762, 680)], fill=(bg_color[0]+30, bg_color[1]+30, bg_color[2]+30))
        
        # Info header
        draw.text((60, 60), f"Lumina (露米娜) • #{task_id:04d}", fill=(255, 255, 255))
        draw.text((60, 100), f"Style: {style}  |  Outfit: {outfit}  |  Pose: {pose}", fill=(240, 240, 240))
        draw.text((60, 880), f"Seed: {seed}  |  Steps: {steps}  |  Sampler: euler_ancestral", fill=(200, 230, 255))
        
        # Wrap prompt snippet
        snippet = (prompt[:140] + "...") if len(prompt) > 140 else prompt
        draw.text((60, 930), f"Prompt: {snippet}", fill=(220, 220, 220))

        img.save(full_path, "PNG")

        # Create thumbnail 360x360
        thumb = img.resize((360, 360), Image.Resampling.LANCZOS)
        thumb.save(thumb_path, "JPEG", quality=85)

        return {
            "file_name": file_name,
            "full_path": str(full_path),
            "thumb_path": str(thumb_path),
            "file_size": full_path.stat().st_size,
            "width": 1024,
            "height": 1024
        }

    async def _execute_live(self, task_info: Dict[str, Any], progress_cb: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        """
        Submits prompt to active ComfyUI instance and streams WebSocket progress.
        Honors session-level overrides: template_name / checkpoint_name / lora_override.
        """
        template = task_info.get("template_name") or "sdxl_anime_template.json"
        # lora_override: None -> character default lora; "" -> disable lora; str -> specific file
        lora_override = task_info.get("lora_override", None)
        lora = task_info.get("default_lora") if lora_override is None else lora_override

        workflow = self.build_workflow(
            template_name=template,
            positive_prompt=task_info["prompt_final"],
            negative_prompt=task_info.get("negative_prompt", ""),
            seed=task_info["seed"],
            steps=task_info.get("steps", 25),
            cfg=task_info.get("cfg", 7.0),
            width=task_info.get("width", 1024),
            height=task_info.get("height", 1024),
            lora_name=lora,
            checkpoint_name=task_info.get("checkpoint_name"),
            lora_strength=task_info.get("lora_strength")
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": self.client_id}
            )
            if res.status_code != 200:
                # Extract ComfyUI node validation errors for an actionable message
                detail = []
                try:
                    err = res.json()
                    for nid, ne in (err.get("node_errors") or {}).items():
                        for e in ne.get("errors", []):
                            detail.append(f"{ne.get('class_type', '?')}#{nid}: {e.get('details') or e.get('message', '')}")
                except Exception:
                    pass
                msg = "; ".join(detail)[:400] or res.text[:200]
                raise RuntimeError(f"ComfyUI 拒绝工作流 (HTTP {res.status_code}): {msg}")
            prompt_res = res.json()
            prompt_id = prompt_res["prompt_id"]

        # Listen to WebSocket for completion
        images_output = []
        async with websockets.connect(self.ws_url) as ws:
            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    msg_data = data.get("data", {})

                    if msg_type == "progress" and msg_data.get("prompt_id") == prompt_id:
                        value = msg_data.get("value", 0)
                        max_val = msg_data.get("max", 1)
                        if progress_cb:
                            await progress_cb(value, max_val)

                    elif msg_type == "execution_error" and msg_data.get("prompt_id") == prompt_id:
                        # Node raised during execution (e.g. unloadable checkpoint)
                        raise RuntimeError(
                            f"ComfyUI 执行出错: {msg_data.get('exception_message', 'unknown')} "
                            f"(节点 {msg_data.get('node_type', '?')}#{msg_data.get('node_id', '?')})"
                        )

                    elif msg_type == "executed" and msg_data.get("prompt_id") == prompt_id:
                        node_output = msg_data.get("output", {})
                        if "images" in node_output:
                            images_output.extend(node_output["images"])
                        break

        # Download image from ComfyUI
        if not images_output:
            raise RuntimeError("ComfyUI finished execution but produced no images")

        img_info = images_output[0]
        file_name = img_info["filename"]
        subfolder = img_info.get("subfolder", "")
        img_type = img_info.get("type", "output")

        async with httpx.AsyncClient(timeout=60.0) as client:
            img_res = await client.get(
                f"{self.base_url}/view",
                params={"filename": file_name, "subfolder": subfolder, "type": img_type}
            )
            img_res.raise_for_status()

            full_path = OUTPUT_DIR / file_name
            with open(full_path, "wb") as f:
                f.write(img_res.content)

            # Generate thumbnail
            thumb_path = THUMB_DIR / file_name
            with Image.open(full_path) as im:
                thumb = im.resize((360, 360), Image.Resampling.LANCZOS)
                thumb.save(thumb_path, "JPEG", quality=85)

        return {
            "file_name": file_name,
            "full_path": str(full_path),
            "thumb_path": str(thumb_path),
            "file_size": full_path.stat().st_size,
            "width": task_info.get("width", 1024),
            "height": task_info.get("height", 1024)
        }
