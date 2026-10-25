"""Tencent Cloud Hunyuan image via TC3-HMAC-SHA256 (BYOK)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any

import requests
import torch

from ..async_job import poll_until
from ..env import optional_env, require_env
from ..http_util import image_to_b64_png, tensors_from_image_urls

PROVIDER_ID = "tencent_hunyuan"
DISPLAY_NAME = "Tencent Hunyuan Image"

IMAGE_MODELS = [
    "hunyuan-image",
]
VIDEO_MODELS: list[str] = []

HOST = "hunyuan.tencentcloudapi.com"
SERVICE = "hunyuan"
VERSION = "2023-09-01"


def _region() -> str:
    return optional_env("TENCENT_REGION", "ap-guangzhou")


def _sign(action: str, payload: dict[str, Any]) -> tuple[dict[str, str], str]:
    secret_id = require_env("TENCENT_SECRET_ID")
    secret_key = require_env("TENCENT_SECRET_KEY")
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    hashed_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()

    canonical_headers = (
        f"content-type:application/json; charset=utf-8\n"
        f"host:{HOST}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = (
        "POST\n/\n\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{hashed_payload}"
    )
    credential_scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = (
        "TC3-HMAC-SHA256\n"
        f"{timestamp}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac(secret_date, SERVICE)
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": HOST,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": VERSION,
        "X-TC-Region": _region(),
    }
    return headers, body


def _tc_request(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers, body = _sign(action, payload)
    resp = requests.post(
        f"https://{HOST}",
        headers=headers,
        data=body.encode("utf-8"),
        timeout=120,
    )
    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"腾讯云响应非 JSON HTTP {resp.status_code}: {resp.text[:500]}")
    if resp.status_code >= 400:
        raise RuntimeError(f"腾讯云 HTTP {resp.status_code}: {data}")
    response = data.get("Response") or {}
    if response.get("Error"):
        err = response["Error"]
        raise RuntimeError(f"腾讯云错误 {err.get('Code')}: {err.get('Message')}")
    return response


_ALLOWED_RES = [
    (1024, 1024),
    (768, 768),
    (768, 1024),
    (1024, 768),
    (720, 1280),
    (1280, 720),
    (768, 1280),
    (1280, 768),
]


def _nearest_resolution(width: int, height: int) -> str:
    best = min(_ALLOWED_RES, key=lambda wh: abs(wh[0] - width) + abs(wh[1] - height))
    return f"{best[0]}:{best[1]}"


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
    _ = model
    payload: dict[str, Any] = {
        "Prompt": prompt,
        "Resolution": _nearest_resolution(width, height),
        "Num": max(1, min(int(n), 4)),
        "LogoAdd": 0,
        "Revise": 1,
    }
    if negative_prompt.strip():
        payload["NegativePrompt"] = negative_prompt
    if seed >= 0:
        payload["Seed"] = int(seed)
    submitted = _tc_request("SubmitHunyuanImageJob", payload)
    job_id = submitted.get("JobId")
    if not job_id:
        raise RuntimeError(f"混元未返回 JobId: {submitted}")
    result = _wait_job(job_id)
    urls = result.get("ResultImage") or []
    return tensors_from_image_urls(list(urls))


def image_edit(
    *,
    model: str,
    prompt: str,
    image: torch.Tensor,
    negative_prompt: str = "",
    seed: int = 42,
) -> torch.Tensor:
    _ = model
    payload: dict[str, Any] = {
        "Prompt": prompt,
        "Num": 1,
        "LogoAdd": 0,
        "ContentImage": {"ImageBase64": image_to_b64_png(image)},
    }
    if negative_prompt.strip():
        payload["NegativePrompt"] = negative_prompt
    if seed >= 0:
        payload["Seed"] = int(seed)
    submitted = _tc_request("SubmitHunyuanImageJob", payload)
    job_id = submitted.get("JobId")
    if not job_id:
        raise RuntimeError(f"混元参考图任务未返回 JobId: {submitted}")
    result = _wait_job(job_id)
    urls = result.get("ResultImage") or []
    return tensors_from_image_urls(list(urls))


def _wait_job(job_id: str) -> dict[str, Any]:
    def fetch() -> tuple[str, Any]:
        data = _tc_request("QueryHunyuanImageJob", {"JobId": job_id})
        return str(data.get("JobStatusCode") or ""), data

    return poll_until(
        fetch,
        interval_sec=3.0,
        timeout_sec=600.0,
        success_states={"5"},
        failure_states={"4"},
    )


CAPABILITIES = {
    "text_to_image": text_to_image,
    "image_edit": image_edit,
    "image_models": IMAGE_MODELS,
    "video_models": VIDEO_MODELS,
}
