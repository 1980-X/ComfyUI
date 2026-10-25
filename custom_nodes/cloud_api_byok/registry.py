from __future__ import annotations

from typing import Any, Callable

from .providers import dashscope, openai_images, tencent_hunyuan, tokenhub_hy_image

ProviderMod = Any

_PROVIDERS: dict[str, ProviderMod] = {
    dashscope.PROVIDER_ID: dashscope,
    tencent_hunyuan.PROVIDER_ID: tencent_hunyuan,
    openai_images.PROVIDER_ID: openai_images,
    tokenhub_hy_image.PROVIDER_ID: tokenhub_hy_image,
}


def list_providers() -> list[str]:
    return list(_PROVIDERS.keys())


def get_provider(provider_id: str) -> ProviderMod:
    if provider_id not in _PROVIDERS:
        raise RuntimeError(f"未知 provider: {provider_id}；可选: {', '.join(list_providers())}")
    return _PROVIDERS[provider_id]


def providers_for_capability(cap: str) -> list[str]:
    out = []
    for pid, mod in _PROVIDERS.items():
        caps = getattr(mod, "CAPABILITIES", {})
        if cap in caps and callable(caps.get(cap)):
            out.append(pid)
        elif cap.endswith("_models") and caps.get(cap):
            out.append(pid)
    return out


def image_provider_ids() -> list[str]:
    return [p for p in list_providers() if "text_to_image" in getattr(_PROVIDERS[p], "CAPABILITIES", {})]


def video_provider_ids() -> list[str]:
    return [p for p in list_providers() if "text_to_video" in getattr(_PROVIDERS[p], "CAPABILITIES", {})]


def image_models_for(provider_id: str) -> list[str]:
    mod = get_provider(provider_id)
    return list(mod.CAPABILITIES.get("image_models") or ["default"])


def video_models_for(provider_id: str) -> list[str]:
    mod = get_provider(provider_id)
    return list(mod.CAPABILITIES.get("video_models") or ["default"])


def call_image(provider_id: str, fn_name: str, **kwargs):
    mod = get_provider(provider_id)
    fn: Callable = mod.CAPABILITIES.get(fn_name)
    if not callable(fn):
        raise RuntimeError(f"provider {provider_id} 不支持 {fn_name}")
    return fn(**kwargs)


def call_video(provider_id: str, fn_name: str, **kwargs):
    return call_image(provider_id, fn_name, **kwargs)
