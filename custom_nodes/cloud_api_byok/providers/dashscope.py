"""Alibaba DashScope: Qwen-Image + Wan video (BYOK)."""

from __future__ import annotations

from typing import Any

import torch

from ..async_job import poll_until
from ..env import optional_env, require_env
from ..http_util import (
    download_bytes,
    http_json,
    image_to_data_uri,
    tensors_from_image_urls,
)

PROVIDER_ID = "dashscope"
DISPLAY_NAME = "DashScope (Qwen / Wan)"

IMAGE_MODELS = [
    "qwen-image-plus",
    "qwen-image",
    "wanx2.1-t2i-turbo",
    "wanx2.1-t2i-plus",
]
VIDEO_MODELS = [
    "wan2.2-t2v-plus",
    "wanx2.1-t2v-turbo",
    "wanx2.1-t2v-plus",
    "wanx2.1-i2v-turbo",
    "wanx2.1-i2v-plus",
]


def _base() -> str:
    return optional_env("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1").rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {require_env('DASHSCOPE_API_KEY')}",
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
    body: dict[str, Any] = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]
        },
        "parameters": {
            "size": f"{width}*{height}",
            "n": max(1, min(n, 4)),
            "seed": int(seed),
            "prompt_extend": True,
            "watermark": False,
        },
    }
    if negative_prompt.strip():
        body["parameters"]["negative_prompt"] = negative_prompt
    # wanx t2i uses a simpler input shape
    if model.startswith("wanx"):
        body = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {
                "size": f"{width}*{height}",
                "n": max(1, min(n, 4)),
                "seed": int(seed),
            },
        }
        if negative_prompt.strip():
            body["parameters"]["negative_prompt"] = negative_prompt
        url = f"{_base()}/services/aigc/text2image/image-synthesis"
        headers = {**_headers(), "X-DashScope-Async": "enable"}
        created = http_json("POST", url, headers=headers, json_body=body, timeout=60)
        task_id = (created.get("output") or {}).get("task_id") or created.get("task_id")
        if not task_id:
            raise RuntimeError(f"DashScope 未返回 task_id: {created}")
        result = _wait_task(task_id)
        urls = _extract_image_urls(result)
        return tensors_from_image_urls(urls)

    url = f"{_base()}/services/aigc/multimodal-generation/generation"
    data = http_json("POST", url, headers=_headers(), json_body=body, timeout=180)
    urls = _extract_image_urls(data)
    return tensors_from_image_urls(urls)


def image_edit(
    *,
    model: str,
    prompt: str,
    image: torch.Tensor,
    negative_prompt: str = "",
    seed: int = 42,
) -> torch.Tensor:
    data_uri = image_to_data_uri(image)
    body = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": data_uri},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {
            "n": 1,
            "seed": int(seed),
            "watermark": False,
        },
    }
    if negative_prompt.strip():
        body["parameters"]["negative_prompt"] = negative_prompt
    url = f"{_base()}/services/aigc/multimodal-generation/generation"
    data = http_json("POST", url, headers=_headers(), json_body=body, timeout=180)
    return tensors_from_image_urls(_extract_image_urls(data))


def text_to_video(
    *,
    model: str,
    prompt: str,
    negative_prompt: str = "",
    size: str = "1280*720",
    duration: int = 5,
    seed: int = 42,
) -> bytes:
    body: dict[str, Any] = {
        "model": model,
        "input": {"prompt": prompt},
        "parameters": {
            "size": size,
            "duration": int(duration),
            "seed": int(seed),
        },
    }
    if negative_prompt.strip():
        body["input"]["negative_prompt"] = negative_prompt
    url = f"{_base()}/services/aigc/video-generation/video-synthesis"
    headers = {**_headers(), "X-DashScope-Async": "enable"}
    created = http_json("POST", url, headers=headers, json_body=body, timeout=60)
    task_id = (created.get("output") or {}).get("task_id") or created.get("task_id")
    if not task_id:
        raise RuntimeError(f"DashScope 视频未返回 task_id: {created}")
    result = _wait_task(task_id, timeout_sec=900)
    video_url = _extract_video_url(result)
    return download_bytes(video_url, timeout=300)


def image_to_video(
    *,
    model: str,
    prompt: str,
    image: torch.Tensor,
    negative_prompt: str = "",
    duration: int = 5,
    seed: int = 42,
) -> bytes:
    data_uri = image_to_data_uri(image)
    body: dict[str, Any] = {
        "model": model,
        "input": {
            "prompt": prompt,
            "img_url": data_uri,
        },
        "parameters": {
            "duration": int(duration),
            "seed": int(seed),
        },
    }
    if negative_prompt.strip():
        body["input"]["negative_prompt"] = negative_prompt
    url = f"{_base()}/services/aigc/video-generation/video-synthesis"
    headers = {**_headers(), "X-DashScope-Async": "enable"}
    created = http_json("POST", url, headers=headers, json_body=body, timeout=60)
    task_id = (created.get("output") or {}).get("task_id") or created.get("task_id")
    if not task_id:
        raise RuntimeError(f"DashScope 图生视频未返回 task_id: {created}")
    result = _wait_task(task_id, timeout_sec=900)
    return download_bytes(_extract_video_url(result), timeout=300)


def _wait_task(task_id: str, timeout_sec: float = 600.0) -> dict[str, Any]:
    def fetch() -> tuple[str, Any]:
        data = http_json(
            "GET",
            f"{_base()}/tasks/{task_id}",
            headers=_headers(),
            timeout=60,
        )
        output = data.get("output") or data
        status = str(output.get("task_status") or output.get("status") or "")
        return status, data

    return poll_until(
        fetch,
        interval_sec=3.0,
        timeout_sec=timeout_sec,
        success_states={"SUCCEEDED", "SUCCESS"},
        failure_states={"FAILED", "CANCELED", "CANCELLED", "UNKNOWN"},
    )


def _extract_image_urls(data: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    output = data.get("output") or {}
    # multimodal-generation
    for choice in output.get("choices") or []:
        msg = choice.get("message") or {}
        for item in msg.get("content") or []:
            if isinstance(item, dict) and item.get("image"):
                urls.append(item["image"])
    # text2image results
    for item in output.get("results") or []:
        if isinstance(item, dict) and item.get("url"):
            urls.append(item["url"])
    if output.get("image_url"):
        urls.append(output["image_url"])
    if not urls and data.get("code"):
        raise RuntimeError(f"DashScope 图像失败: {data.get('code')} {data.get('message')}")
    return urls


def _extract_video_url(data: dict[str, Any]) -> str:
    output = data.get("output") or {}
    url = output.get("video_url") or output.get("url")
    if not url:
        raise RuntimeError(f"DashScope 视频结果无 URL: {data}")
    return url


CAPABILITIES = {
    "text_to_image": text_to_image,
    "image_edit": image_edit,
    "text_to_video": text_to_video,
    "image_to_video": image_to_video,
    "image_models": IMAGE_MODELS,
    "video_models": VIDEO_MODELS,
}
