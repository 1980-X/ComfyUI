import os


def require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}：请在仓库根目录 .env 填写后 recreate comfyui")
    return value


def optional_env(name: str, default: str = "") -> str:
    value = (os.environ.get(name) or "").strip()
    return value if value else default
