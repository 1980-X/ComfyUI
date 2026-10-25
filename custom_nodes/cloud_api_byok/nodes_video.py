import os
import time

import folder_paths

from . import registry


def _all_video_models() -> list[str]:
    models: list[str] = []
    for pid in registry.video_provider_ids():
        for m in registry.video_models_for(pid):
            if m not in models:
                models.append(m)
    return models or ["wan2.2-t2v-plus"]


def _save_video_bytes(data: bytes, prefix: str = "cloud_byok") -> str:
    out_dir = folder_paths.get_output_directory()
    os.makedirs(out_dir, exist_ok=True)
    name = f"{prefix}_{int(time.time())}.mp4"
    path = os.path.join(out_dir, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


class CloudTextToVideo:
    @classmethod
    def INPUT_TYPES(cls):
        providers = registry.video_provider_ids() or ["dashscope"]
        return {
            "required": {
                "provider": (providers,),
                "model": (_all_video_models(),),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "size": ("STRING", {"default": "1280*720"}),
                "duration": ("INT", {"default": 5, "min": 1, "max": 15}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2147483647}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "model_override": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "generate"
    CATEGORY = "cloud_api_byok/video"
    OUTPUT_NODE = True

    def generate(
        self,
        provider,
        model,
        prompt,
        size,
        duration,
        seed,
        negative_prompt="",
        model_override="",
    ):
        use_model = (model_override or "").strip() or model
        data = registry.call_video(
            provider,
            "text_to_video",
            model=use_model,
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            size=size,
            duration=int(duration),
            seed=int(seed),
        )
        path = _save_video_bytes(data)
        return (path,)


class CloudImageToVideo:
    @classmethod
    def INPUT_TYPES(cls):
        providers = registry.video_provider_ids() or ["dashscope"]
        return {
            "required": {
                "provider": (providers,),
                "model": (_all_video_models(),),
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "duration": ("INT", {"default": 5, "min": 1, "max": 15}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2147483647}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "model_override": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "generate"
    CATEGORY = "cloud_api_byok/video"
    OUTPUT_NODE = True

    def generate(
        self,
        provider,
        model,
        image,
        prompt,
        duration,
        seed,
        negative_prompt="",
        model_override="",
    ):
        use_model = (model_override or "").strip() or model
        data = registry.call_video(
            provider,
            "image_to_video",
            model=use_model,
            prompt=prompt,
            image=image,
            negative_prompt=negative_prompt or "",
            duration=int(duration),
            seed=int(seed),
        )
        path = _save_video_bytes(data, prefix="cloud_byok_i2v")
        return (path,)
