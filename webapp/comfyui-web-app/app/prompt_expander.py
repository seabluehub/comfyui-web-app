import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger("prompt_expander")

def expand_prompt_rule_based(trigger_words: str, style_desc: str, outfit_desc: str, pose_desc: str) -> str:
    """
    Deterministic rule-based anime prompt expander.
    """
    elements = [
        "masterpiece",
        "best quality",
        "ultra-detailed anime illustration",
        trigger_words.strip(),
        outfit_desc.strip(),
        style_desc.strip(),
        pose_desc.strip(),
        "striking visual composition",
        "detailed lighting and shadows",
        "crisp clean lineart",
        "8k wallpaper resolution"
    ]
    return ", ".join([e for e in elements if e])

async def expand_with_lm_studio(raw_prompt: str, base_url: str = "http://127.0.0.1:1234/v1", timeout_sec: float = 8.0) -> str:
    """
    Attempt to call local LM Studio (qwen3.5-35b or qwen2.5-7b) to expand the prompt.
    Falls back to rule-based if LM Studio is offline or times out.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": "qwen3.5-35b-a3b",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a prompt engineering specialist for anime Stable Diffusion / Flux models. Expand the input into a detailed English prompt tags list. Output ONLY the tags separated by commas, no preamble."
                        },
                        {
                            "role": "user",
                            "content": f"Expand this character concept into tags: {raw_prompt}"
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 128
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content:
                    return content
    except Exception as e:
        logger.debug(f"LM Studio not reachable or timed out: {e}")
    
    return raw_prompt

def unload_lm_studio_models():
    """
    Unload all models from LM Studio to free up VRAM before starting ComfyUI batching.
    """
    try:
        os.system("lms unload --all")
    except Exception:
        pass
