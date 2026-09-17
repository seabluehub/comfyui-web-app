import sys
import asyncio
import argparse
from app.database import init_db
from app.matrix_generator import populate_matrix
from app.comfy_client import ComfyUIClient
from app.batch_worker import BatchWorker

async def main():
    parser = argparse.ArgumentParser(description="Headless ComfyUI 1000-image Batch Runner")
    parser.add_argument("--character-id", type=int, default=1, help="Character ID")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of images to generate")
    parser.add_argument("--force-matrix", action="store_true", help="Rebuild the 1000-matrix from scratch")
    args = parser.parse_args()

    print("==================================================")
    print("  ComfyUI Anime Character Mass Production CLI   ")
    print("==================================================")
    
    init_db()
    print("1. Initializing database and prompt matrix...")
    count = populate_matrix(character_id=args.character_id, force_rebuild=args.force_matrix)
    print(f"   Matrix ready: {count} tasks available.")

    client = ComfyUIClient()
    worker = BatchWorker(comfy_client=client)

    def print_event(ev):
        t = ev["type"]
        d = ev["data"]
        if t == "task_start":
            print(f"\n[START] Task #{d['task_id']} ({d['style']} | {d['outfit']})")
        elif t == "step_progress":
            bar_len = 20
            ratio = d["step"] / d["max_steps"]
            filled = int(bar_len * ratio)
            bar = "=" * filled + "-" * (bar_len - filled)
            sys.stdout.write(f"\r  Sampling: [{bar}] {d['step']}/{d['max_steps']}")
            sys.stdout.flush()
        elif t == "task_success":
            print(f"\n[DONE] Saved: {d['file_name']} in {d['exec_time']}s (Total session: {d['total_session']})")
        elif t == "cooldown":
            print(f"\n[COOLDOWN] Thermal protection: sleeping {d['seconds']}s...")

    worker.register_listener(print_event)

    print(f"2. Starting production pipeline (Limit: {args.limit or 'Unlimited'})...\n")
    await worker.start(limit=args.limit)

    # Keep script running until worker finishes
    while worker.is_running:
        await asyncio.sleep(0.5)

    print("\nBatch production session completed!")

if __name__ == "__main__":
    asyncio.run(main())
