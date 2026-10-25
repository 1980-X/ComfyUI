"""OpenAI Images API and compatible gateways (BYOK)."""

from __future__ import annotations

import io
from typing import Any

import torch

from ..env import optional_env, require_env
from ..http_util import (
    http_json,
    image_to_png_bytes,
    tensors_from_b64_list,
    tensors_from_image_urls,
)

PROVIDER_ID = "openai_images"
DISPLAY_NAME = "OpenAI Images (compatible)"

IMAGE_MODELS = [
    "dall-e-3",
    "dall-e-2",
    "gpt-image-1",
]
VIDEO_MODELS: list[str] = []


def _base() -> str:
    return optional_env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {require_env('OPENAI_API_KEY')}",
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
    _ = negative_prompt, seed  # not in standard Images API
    size = f"{width}x{height}"
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": max(1, min(int(n), 4)),
        "size": size,
        "response_format": "b64_json",
    }
    # dall-e-3 only supports n=1 and fixed sizes
    if model.startswith("dall-e-3"):
        body["n"] = 1
        if size not in ("1024x1024", "1792x1024", "1024x1792"):
            body["size"] = "1024x1024"
    data = http_json(
        "POST",
        f"{_base()}/images/generations",
        headers=_headers(),
        json_body=body,
        timeout=180,
    )
    return _parse_image_data(data)


def image_edit(
    *,
    model: str,
    prompt: str,
    image: torch.Tensor,
    negative_prompt: str = "",
    seed: int = 42,
) -> torch.Tensor:
    _ = negative_prompt, seed
    import requests

    png = image_to_png_bytes(image)
    files = {
        "image": ("image.png", io.BytesIO(png), "image/png"),
    }
    form = {
        "model": model if model.startswith("dall-e-2") or model.startswith("gpt-image") else "dall-e-2",
        "prompt": prompt,
        "n": "1",
        "size": "1024x1024",
        "response_format": "b64_json",
    }
    headers = {"Authorization": f"Bearer {require_env('OPENAI_API_KEY')}"}
    resp = requests.post(
        f"{_base()}/images/edits",
        headers=headers,
        data=form,
        files=files,
        timeout=180,
    )
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"OpenAI edits 非 JSON HTTP {resp.status_code}: {resp.text[:500]}")
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAI edits HTTP {resp.status_code}: {data}")
    return _parse_image_data(data)


def _parse_image_data(data: dict[str, Any]) -> torch.Tensor:
    items = data.get("data") or []
    b64s = [i["b64_json"] for i in items if i.get("b64_json")]
    if b64s:
        return tensors_from_b64_list(b64s)
    urls = [i["url"] for i in items if i.get("url")]
    if urls:
        return tensors_from_image_urls(urls)
    raise RuntimeError(f"OpenAI Images 无结果: {data}")


CAPABILITIES = {
    "text_to_image": text_to_image,
    "image_edit": image_edit,
    "image_models": IMAGE_MODELS,
    "video_models": VIDEO_MODELS,
}
