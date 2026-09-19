"""
ComfyUI 本地 API 客户端 —— 文生图（Flux 工作流）

用法:
    python comfy_api_client.py "一个动漫少女..." [选项]

示例:
    python comfy_api_client.py "吉卜力风格，蓝天下的草原小镇" --width 1024 --height 768
    python comfy_api_client.py "赛博朋克少女" --lora "F.1宫崎骏-吉卜力风格_v1.0.safetensors" --steps 20

依赖: 仅 Python 标准库（可用 ComfyUI 便携包自带的 python_embeded 运行）
"""

import argparse
import json
import pathlib
import random
import sys
import time
import urllib.parse
import urllib.request

SERVER = "http://127.0.0.1:8188"
ROOT = pathlib.Path(__file__).resolve().parent
TEMPLATE = ROOT / "workflows" / "flux_anime_template.json"
OUTPUT_DIR = ROOT / "output"

# 模板中各参数所在节点 ID（与 flux_anime_template.json 对应）
NODE_PROMPT = "6"      # CLIPTextEncode.text
NODE_LATENT = "5"      # EmptyLatentImage 宽高
NODE_SEED = "25"       # RandomNoise.noise_seed
NODE_STEPS = "17"      # BasicScheduler.steps
NODE_LORA = "27"       # LoraLoaderModelOnly.lora_name / strength_model
NODE_PREFIX = "9"      # SaveImage.filename_prefix


def http_get_json(url: str, timeout: int = 10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def queue_prompt(workflow: dict) -> str:
    """提交工作流到 /prompt，返回 prompt_id"""
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVER}/prompt?{urllib.parse.urlencode({'number': 1})}",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if "error" in result:
        raise RuntimeError(f"工作流校验失败: {result['error']}\n节点详情: {result.get('node_errors')}")
    return result["prompt_id"]


def wait_for_result(prompt_id: str, poll_interval: float = 1.5, timeout: int = 600):
    """轮询 /history/{id} 直到任务完成，返回 outputs"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            history = http_get_json(f"{SERVER}/history/{prompt_id}")
        except Exception:
            time.sleep(poll_interval)
            continue
        entry = history.get(prompt_id)
        if not entry:
            time.sleep(poll_interval)
            continue
        status = entry.get("status", {})
        if status.get("completed") or status.get("status_str") == "success":
            return entry["outputs"]
        if status.get("status_str") == "error":
            msgs = [m for m in status.get("messages", []) if m and m[0] == "execution_error"]
            raise RuntimeError(f"执行失败: {msgs or status}")
        time.sleep(poll_interval)
    raise TimeoutError(f"等待超时({timeout}s)")


def download_image(filename: str, subfolder: str = "", file_type: str = "output") -> pathlib.Path:
    """从 /view 下载生成的图片到本地 output/ 目录"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    query = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": file_type}
    )
    target = OUTPUT_DIR / filename
    urllib.request.urlretrieve(f"{SERVER}/view?{query}", target)
    return target


def build_workflow(args) -> dict:
    workflow = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    workflow[NODE_PROMPT]["inputs"]["text"] = args.prompt
    workflow[NODE_LATENT]["inputs"]["width"] = args.width
    workflow[NODE_LATENT]["inputs"]["height"] = args.height
    workflow[NODE_SEED]["inputs"]["noise_seed"] = (
        args.seed if args.seed is not None else random.randint(0, 2**32)
    )
    workflow[NODE_STEPS]["inputs"]["steps"] = args.steps
    workflow[NODE_LORA]["inputs"]["lora_name"] = args.lora
    workflow[NODE_LORA]["inputs"]["strength_model"] = args.lora_strength
    workflow[NODE_PREFIX]["inputs"]["filename_prefix"] = args.prefix
    return workflow


def main():
    parser = argparse.ArgumentParser(description="ComfyUI 文生图 API 客户端")
    parser.add_argument("prompt", help="正向提示词")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=None, help="随机种子，缺省随机")
    parser.add_argument(
        "--lora",
        default="F.1-H.超真人物萌妹_极致逼真人像写真_F.1-超真人物萌妹v1.0.safetensors",
        help="LoRA 文件名（见 D:\\MyAiModels\\LibLib\\Models\\loras）",
    )
    parser.add_argument("--lora-strength", type=float, default=1.0, dest="lora_strength")
    parser.add_argument("--prefix", default="api", help="输出文件名前缀")
    args = parser.parse_args()

    # 服务健康检查
    try:
        http_get_json(f"{SERVER}/system_stats", timeout=5)
    except Exception:
        sys.exit(f"[x] 无法连接 {SERVER}，请先启动 ComfyUI（run_nvidia_gpu.bat 或 --listen 参数）")

    workflow = build_workflow(args)
    prompt_id = queue_prompt(workflow)
    print(f"[>] 已提交任务 {prompt_id}")
    print(f"    提示词: {args.prompt[:60]}...")
    print(f"    模型: F.1-dev-fp8 + LoRA: {args.lora}")

    t0 = time.time()
    outputs = wait_for_result(prompt_id)
    elapsed = time.time() - t0

    saved = []
    for node_out in outputs.values():
        for img in node_out.get("images", []):
            path = download_image(img["filename"], img.get("subfolder", ""), img.get("type", "output"))
            saved.append(path)
            print(f"[✓] {elapsed:.1f}s 完成 → {path}")
    if not saved:
        sys.exit("[x] 任务完成但没有图片输出，请检查工作流")


if __name__ == "__main__":
    main()
