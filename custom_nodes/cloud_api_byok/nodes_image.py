from . import registry


def _all_image_models() -> list[str]:
    models: list[str] = []
    for pid in registry.image_provider_ids():
        for m in registry.image_models_for(pid):
            if m not in models:
                models.append(m)
    return models or ["qwen-image-plus"]


class CloudTextToImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "provider": (registry.image_provider_ids(),),
                "model": (_all_image_models(),),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "width": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
                "height": ("INT", {"default": 1024, "min": 256, "max": 2048, "step": 64}),
                "n": ("INT", {"default": 1, "min": 1, "max": 4}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2147483647}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "model_override": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"
    CATEGORY = "cloud_api_byok/image"

    def generate(
        self,
        provider,
        model,
        prompt,
        width,
        height,
        n,
        seed,
        negative_prompt="",
        model_override="",
    ):
        use_model = (model_override or "").strip() or model
        images = registry.call_image(
            provider,
            "text_to_image",
            model=use_model,
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            width=int(width),
            height=int(height),
            n=int(n),
            seed=int(seed),
        )
        return (images,)


class CloudImageEdit:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "provider": (registry.image_provider_ids(),),
                "model": (_all_image_models(),),
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2147483647}),
            },
            "optional": {
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "model_override": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "edit"
    CATEGORY = "cloud_api_byok/image"

    def edit(
        self,
        provider,
        model,
        image,
        prompt,
        seed,
        negative_prompt="",
        model_override="",
    ):
        use_model = (model_override or "").strip() or model
        images = registry.call_image(
            provider,
            "image_edit",
            model=use_model,
            prompt=prompt,
            image=image,
            negative_prompt=negative_prompt or "",
            seed=int(seed),
        )
        return (images,)
