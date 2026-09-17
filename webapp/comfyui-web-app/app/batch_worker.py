import asyncio
import time
import json
import logging
from typing import Optional, Callable, Dict, Any, List
from app.database import get_db
from app.comfy_client import ComfyUIClient
from app.config import COOLDOWN_BATCH_SIZE, COOLDOWN_SECONDS, FREE_MEMORY_BATCH_SIZE, MOCK_MODE

logger = logging.getLogger("batch_worker")

def build_task_filter(filters: Optional[Dict[str, List[str]]], statuses: Optional[List[str]] = None):
    """
    Build a SQL WHERE clause for selecting generation tasks by matrix tag filters.
    Empty/None filter lists mean 'no restriction' (all values allowed).
    Returns (where_sql, params).
    """
    conds: List[str] = []
    params: List = []
    if statuses:
        conds.append(f"t.status IN ({','.join('?' * len(statuses))})")
        params.extend(statuses)
    for col, key in (("m.style_tag", "styles"), ("m.outfit_tag", "outfits"), ("m.pose_tag", "poses")):
        vals = [v for v in ((filters or {}).get(key) or []) if v]
        if vals:
            conds.append(f"{col} IN ({','.join('?' * len(vals))})")
            params.extend(vals)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    return where, params

class BatchWorker:
    def __init__(self, comfy_client: Optional[ComfyUIClient] = None):
        self.comfy = comfy_client or ComfyUIClient()
        self.is_running = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self.current_task_id: Optional[int] = None
        self.processed_in_session = 0
        self.start_time: Optional[float] = None
        self.listeners: List[Callable[[Dict[str, Any]], Any]] = []
        # Filtered batch session state
        self.active_filters: Optional[Dict[str, List[str]]] = None
        self.gen_config: Dict[str, Any] = {}
        self.session_total: int = 0

    def register_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        self.listeners.append(callback)

    def unregister_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        if callback in self.listeners:
            self.listeners.remove(callback)

    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        payload = {"type": event_type, "data": data, "timestamp": time.time()}
        for cb in list(self.listeners):
            try:
                res = cb(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Error in event listener: {e}")

    def recover_interrupted_tasks(self):
        """Reset orphaned RUNNING tasks back to PENDING."""
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE generation_tasks SET status = 'PENDING' WHERE status = 'RUNNING'")
            conn.commit()

    def get_status(self) -> Dict[str, Any]:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM generation_tasks")
            total = cur.fetchone()[0]

            cur.execute("SELECT status, COUNT(*) FROM generation_tasks GROUP BY status")
            status_counts = dict(cur.fetchall())

            pending = status_counts.get("PENDING", 0)
            running = status_counts.get("RUNNING", 0)
            success = status_counts.get("SUCCESS", 0)
            failed = status_counts.get("FAILED", 0)

            cur.execute("""
                SELECT file_name FROM generated_images
                ORDER BY id DESC LIMIT 1
            """)
            last_row = cur.fetchone()
            last_img = last_row[0] if last_row else None

        elapsed = (time.time() - self.start_time) if (self.is_running and self.start_time) else 0.0
        avg_sec = (elapsed / self.processed_in_session) if self.processed_in_session > 0 else 0.0
        percent = (success / total * 100.0) if total > 0 else 0.0

        return {
            "total": total,
            "pending": pending,
            "running": running,
            "success": success,
            "failed": failed,
            "is_active": self.is_running and self._pause_event.is_set(),
            "is_paused": self.is_running and not self._pause_event.is_set(),
            "current_task_id": self.current_task_id,
            "last_completed_image": last_img,
            "progress_percent": round(percent, 2),
            "elapsed_time_sec": round(elapsed, 1),
            "avg_sec_per_img": round(avg_sec, 2),
            "session_total": self.session_total,
            "session_done": self.processed_in_session
        }

    async def start(self, limit: Optional[int] = None, filters: Optional[Dict[str, List[str]]] = None,
                    config: Optional[Dict[str, Any]] = None) -> int:
        """Start the batch worker loop. Returns the number of queued tasks for this session."""
        if self.is_running:
            self._pause_event.set()
            return -1

        self.is_running = True
        self._pause_event.set()
        self.start_time = time.time()
        self.processed_in_session = 0
        self.recover_interrupted_tasks()
        self.active_filters = filters
        self.gen_config = config or {}

        # Count how many tasks this filtered session will process
        where, params = build_task_filter(filters, statuses=["PENDING"])
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT COUNT(*) FROM generation_tasks t
                JOIN prompt_matrix m ON t.matrix_id = m.id {where}
            """, params)
            pending_count = cur.fetchone()[0]

        self.session_total = min(pending_count, limit) if limit else pending_count
        await self._emit_event("session_started", {
            "session_total": self.session_total,
            "limit": limit,
            "filters": filters or {}
        })
        asyncio.create_task(self._worker_loop(limit))
        return self.session_total

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def stop(self):
        self.is_running = False
        self._pause_event.set()

    async def _worker_loop(self, limit: Optional[int] = None):
        tasks_done = 0

        while self.is_running:
            await self._pause_event.wait()

            if limit is not None and tasks_done >= limit:
                break

            # Fetch next pending task (restricted to the active tag filters, if any)
            where, fparams = build_task_filter(self.active_filters, statuses=["PENDING"])
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    SELECT t.id, t.matrix_id, t.character_id, t.seed, t.steps, t.cfg,
                           t.width, t.height, m.style_tag, m.outfit_tag, m.pose_tag,
                           m.prompt_expanded as prompt_final, m.negative_prompt,
                           c.default_lora, c.trigger_words
                    FROM generation_tasks t
                    JOIN prompt_matrix m ON t.matrix_id = m.id
                    JOIN characters c ON t.character_id = c.id
                    {where}
                    ORDER BY t.id ASC LIMIT 1
                """, fparams)
                row = cur.fetchone()

            if not row:
                # No more pending tasks matching the active filter.
                # Distinguish "selected combos finished" from "all 1000 done".
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM generation_tasks WHERE status = 'PENDING'")
                    remaining_global = cur.fetchone()[0]
                if remaining_global == 0:
                    logger.info("Batch production queue completed!")
                    await self._emit_event("completed", {"message": "All batch tasks completed"})
                else:
                    logger.info("Selected filter combos finished; %d tasks remain globally.", remaining_global)
                    await self._emit_event("filter_exhausted", {
                        "message": "Selected combos finished",
                        "remaining_global": remaining_global
                    })
                break

            task_info = dict(row)
            # Apply session-level generation config overrides (template / checkpoint / lora)
            task_info.update(self.gen_config)
            task_id = task_info["id"]
            self.current_task_id = task_id

            # Mark RUNNING
            with get_db() as conn:
                conn.execute(
                    "UPDATE generation_tasks SET status = 'RUNNING', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (task_id,)
                )
                conn.commit()

            await self._emit_event("task_start", {"task_id": task_id, "style": task_info["style_tag"], "outfit": task_info["outfit_tag"]})

            async def step_cb(step: int, max_steps: int):
                await self._emit_event("step_progress", {"task_id": task_id, "step": step, "max_steps": max_steps})

            start_t = time.time()
            try:
                result = await self.comfy.execute_task(task_info, progress_cb=step_cb)
                exec_sec = time.time() - start_t

                # Save generated image record
                with get_db() as conn:
                    # Persist the full generation config used for this image (traceability)
                    lora_used = task_info.get("lora_override")
                    if lora_used is None:
                        lora_used = task_info.get("default_lora")
                    gen_config = {
                        "mode": "mock" if MOCK_MODE else "live",
                        "template": task_info.get("template_name") or "sdxl_anime_template.json",
                        "checkpoint": task_info.get("checkpoint_name"),
                        "lora": lora_used,
                        "lora_strength": task_info.get("lora_strength"),
                        "steps": task_info.get("steps"),
                        "cfg": task_info.get("cfg"),
                        "sampler": "euler_ancestral",
                        "scheduler": "karras"
                    }
                    conn.execute("""
                        INSERT INTO generated_images (
                            task_id, character_id, file_name, file_path, thumb_path,
                            file_size_bytes, width, height, style_tag, outfit_tag,
                            pose_tag, prompt_final, seed, gen_config
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        task_id, task_info["character_id"], result["file_name"],
                        result["full_path"], result["thumb_path"], result["file_size"],
                        result["width"], result["height"], task_info["style_tag"],
                        task_info["outfit_tag"], task_info["pose_tag"],
                        task_info["prompt_final"], task_info["seed"],
                        json.dumps(gen_config, ensure_ascii=False)
                    ))

                    conn.execute("""
                        UPDATE generation_tasks
                        SET status = 'SUCCESS', execution_time_sec = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (round(exec_sec, 2), task_id))
                    conn.commit()

                self.processed_in_session += 1
                tasks_done += 1

                await self._emit_event("task_success", {
                    "task_id": task_id,
                    "file_name": result["file_name"],
                    "style": task_info["style_tag"],
                    "outfit": task_info["outfit_tag"],
                    "pose": task_info["pose_tag"],
                    "exec_time": round(exec_sec, 2),
                    "total_session": self.processed_in_session
                })

                # Laptop Thermal Protection: Sleep interval every COOLDOWN_BATCH_SIZE images
                if self.processed_in_session > 0 and self.processed_in_session % COOLDOWN_BATCH_SIZE == 0:
                    logger.info(f"Thermal protection: cooling down for {COOLDOWN_SECONDS}s after {self.processed_in_session} images...")
                    await self._emit_event("cooldown", {
                        "seconds": COOLDOWN_SECONDS,
                        "reason": f"Completed batch of {COOLDOWN_BATCH_SIZE} images"
                    })
                    await asyncio.sleep(COOLDOWN_SECONDS)

                # PyTorch VRAM Garbage Collection Hook
                if self.processed_in_session > 0 and self.processed_in_session % FREE_MEMORY_BATCH_SIZE == 0:
                    logger.info("Freeing PyTorch VRAM cache on ComfyUI...")
                    await self.comfy.free_vram(unload_models=False, free_memory=True)

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                with get_db() as conn:
                    conn.execute("""
                        UPDATE generation_tasks
                        SET status = 'FAILED', error_msg = ?, retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (str(e), task_id))
                    conn.commit()

                await self._emit_event("task_failed", {"task_id": task_id, "error": str(e)})
                await asyncio.sleep(3.0)

        self.is_running = False
        self.current_task_id = None
        await self._emit_event("session_completed", {
            "session_total": self.session_total,
            "session_done": self.processed_in_session
        })
