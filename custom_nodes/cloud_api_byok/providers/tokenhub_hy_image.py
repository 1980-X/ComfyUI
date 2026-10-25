"""Tencent TokenHub Hy-Image (hy-image-v3) via wand sync API (BYOK)."""

from __future__ import annotations

from typing import Any

import torch

from ..env import optional_env, require_env
from ..http_util import http_json, image_to_data_uri, tensors_from_image_urls

PROVIDER_ID = "tokenhub_hy_image"
DISPLAY_NAME = "TokenHub Hy-Image"

IMAGE_MODELS = [
    "hy-image-v3",
    "hy-image-v3.5-preview",
]
VIDEO_MODELS: list[str] = []

# gpu001 current Key is domestic. Intl keys must set TOKENHUB_BASE_URL explicitly.
DEFAULT_BASE = "https://tokenhub.tencentmaas.com/v1"
GEN_PATH = "/wand/hunyuan-image/v3-generation"


def _base() -> str:
    # Prefer dedicated TokenHub base; fall back to OPENAI_BASE_URL if it looks like TokenHub.
    dedicated = optional_env("TOKENHUB_BASE_URL", "")
    if dedicated:
        return dedicated.rstrip("/")
    openai_base = optional_env("OPENAI_BASE_URL", "")
    if "tokenhub" in openai_base.lower():
        return openai_base.rstrip("/")
    return DEFAULT_BASE


def _api_key() -> str:
    # Prefer TOKENHUB_API_KEY; reuse OPENAI_API_KEY when pointing at TokenHub.
    key = optional_env("TOKENHUB_API_KEY", "")
    if key:
        return key
    return require_env("OPENAI_API_KEY")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def text_to_image(
    *,
    model: str,
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    n: int = 1,
    seed: int = 42,
) -> torch.Tensor:
    _ = negative_prompt, n
    use_model = (model or "hy-image-v3").strip() or "hy-image-v3"
    # hy-image-v3 area cap is 1024*1024 per docs
    area = int(width) * int(height)
    if area > 1024 * 1024:
        width, height = 1024, 1024
    body: dict[str, Any] = {
        "model": use_model,
        "prompt": prompt,
        "size": f"{int(width)}x{int(height)}",
        "revise": True,
        "footnote": "",
    }
    if int(seed) > 0:
        body["seed"] = int(seed)
    data = http_json(
        "POST",
        f"{_base()}{GEN_PATH}",
        headers=_headers(),
        json_body=body,
        timeout=180,
    )
    return tensors_from_image_urls(_extract_urls(data))


def image_edit(
    *,
    model: str,
    prompt: str,
    image: torch.Tensor,
    negative_prompt: str = "",
    seed: int = 42,
) -> torch.Tensor:
    _ = negative_prompt
    use_model = (model or "hy-image-v3").strip() or "hy-image-v3"
    body: dict[str, Any] = {
        "model": use_model,
        "prompt": prompt,
        "images": [image_to_data_uri(image)],
        "revise": True,
        "footnote": "",
    }
    if int(seed) > 0:
        body["seed"] = int(seed)
    data = http_json(
        "POST",
        f"{_base()}{GEN_PATH}",
        headers=_headers(),
        json_body=body,
        timeout=180,
    )
    return tensors_from_image_urls(_extract_urls(data))


def _extract_urls(data: dict[str, Any]) -> list[str]:
    if data.get("error"):
        err = data["error"]
        raise RuntimeError(
            f"TokenHub 生图失败 {err.get('code')}: {err.get('message_zh') or err.get('message')}"
        )
    urls = []
    for item in data.get("data") or []:
        if isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
    if not urls:
        raise RuntimeError(f"TokenHub 生图无 URL: {data}")
    return urls


CAPABILITIES = {
    "text_to_image": text_to_image,
    "image_edit": image_edit,
    "image_models": IMAGE_MODELS,
    "video_models": VIDEO_MODELS,
}
