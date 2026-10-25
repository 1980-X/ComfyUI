from .nodes_image import CloudImageEdit, CloudTextToImage
from .nodes_video import CloudImageToVideo, CloudTextToVideo

NODE_CLASS_MAPPINGS = {
    "CloudTextToImage": CloudTextToImage,
    "CloudImageEdit": CloudImageEdit,
    "CloudTextToVideo": CloudTextToVideo,
    "CloudImageToVideo": CloudImageToVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CloudTextToImage": "Cloud Text to Image (BYOK)",
    "CloudImageEdit": "Cloud Image Edit (BYOK)",
    "CloudTextToVideo": "Cloud Text to Video (BYOK)",
    "CloudImageToVideo": "Cloud Image to Video (BYOK)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
