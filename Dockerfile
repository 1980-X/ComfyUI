# gpu001 说明：
# - Docker Hub 常超时：先 `docker pull registry.linkease.net:5443/library/python:3.11-slim`
#   再 `docker tag ... python:3.11-slim`，并用 `DOCKER_BUILDKIT=0 docker compose build`。
# - 已有旧镜像时，优先用依赖增量层（见 docs/plans 升级计划），避免重跑 apt。
FROM python:3.11-slim

# 可选系统依赖：libgl1（部分节点）、ffmpeg（av 包）、git（部分 pip 包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先安装 PyTorch CPU 版以减小镜像体积（requirements 已不含 torchaudio）
RUN pip install --no-cache-dir torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# 安装其余依赖（排除已预装的 torch/torchvision）
COPY requirements.txt .
RUN grep -v -E '^torch$|^torchvision$' requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

# 复制项目代码（运行时由 compose bind-mount 覆盖）
COPY . .

ENV CLI_ARGS=""

EXPOSE 8188

CMD ["sh", "-c", "python main.py --listen 0.0.0.0 --port 8188 --cpu ${CLI_ARGS}"]
