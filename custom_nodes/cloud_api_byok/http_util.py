import base64
import io
from typing import Any

import numpy as np
import requests
import torch
from PIL import Image


DEFAULT_TIMEOUT = 120


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    data: Any = None,
    files: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any] | list[Any] | Any:
    resp = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        data=data,
        files=files,
        timeout=timeout,
    )
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text[:2000]}
    if resp.status_code >= 400:
        err = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(err, dict):
            code = err.get("code")
            zh = err.get("message_zh") or err.get("message") or ""
            if resp.status_code == 402 or str(code) in ("401009", "402"):
                raise RuntimeError(
                    f"TokenHub 配额耗尽 HTTP {resp.status_code} code={code}: {zh} "
                    f"（运维：控制台加配额或换 Key 后 recreate comfyui；Agent 勿改工作流/勿查 .env）"
                )
        raise RuntimeError(f"HTTP {resp.status_code} {url}: {payload}")
    return payload


def download_bytes(url: str, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    resp = requests.get(url, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"下载失败 HTTP {resp.status_code}: {url[:200]}")
    return resp.content


def tensor_to_pil(image: torch.Tensor) -> Image.Image:
    if image.ndim == 4:
        image = image[0]
    arr = (255.0 * image.clamp(0, 1).cpu().numpy()).astype(np.uint8)
    if arr.shape[-1] > 3:
        arr = arr[..., :3]
    return Image.fromarray(arr)


def pil_to_tensor(img: Image.Image) -> torch.Tensor:
    img = img.convert("RGB")
    arr = np.array(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None,]


def tensors_from_image_urls(urls: list[str]) -> torch.Tensor:
    if not urls:
        raise RuntimeError("厂商返回空图片列表")
    tensors = []
    for url in urls:
        data = download_bytes(url)
        img = Image.open(io.BytesIO(data))
        tensors.append(pil_to_tensor(img))
    return torch.cat(tensors, dim=0)


def tensors_from_b64_list(items: list[str]) -> torch.Tensor:
    if not items:
        raise RuntimeError("厂商返回空图片数据")
    tensors = []
    for item in items:
        raw = item
        if "," in raw and raw.strip().startswith("data:"):
            raw = raw.split(",", 1)[1]
        data = base64.b64decode(raw)
        img = Image.open(io.BytesIO(data))
        tensors.append(pil_to_tensor(img))
    return torch.cat(tensors, dim=0)


def image_to_data_uri(image: torch.Tensor, mime: str = "image/png") -> str:
    pil = tensor_to_pil(image)
    buf = io.BytesIO()
    fmt = "PNG" if mime.endswith("png") else "JPEG"
    pil.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def image_to_png_bytes(image: torch.Tensor) -> bytes:
    pil = tensor_to_pil(image)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def image_to_b64_png(image: torch.Tensor) -> str:
    return base64.b64encode(image_to_png_bytes(image)).decode("ascii")
