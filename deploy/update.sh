#!/usr/bin/env bash
# 阿里云服务器一键更新脚本（在服务器上执行一次即可）：
#   curl -fsSL <raw-url>/deploy/update.sh | bash
# 或先安装到本机，以后每次更新只需运行：bash /opt/radar/update.sh
set -euo pipefail

# ── 配置（按需修改） ──
APP_DIR="${APP_DIR:-/opt/radar/app}"     # 代码目录
DATA_DIR="${DATA_DIR:-/opt/radar/data}"  # 数据目录（持久化，不随更新丢失）
ENV_FILE="${ENV_FILE:-/opt/radar/env}"  # 环境变量文件（LLM key、飞书等）
PORT="${PORT:-8765}"
IMAGE="radar-app:latest"
CONTAINER="radar"

echo "==> 1/6 准备目录"
mkdir -p "$APP_DIR" "$DATA_DIR"
[ -f "$ENV_FILE" ] || {
  echo "缺少 $ENV_FILE（LLM/飞书/DEV_SEED 配置），请先参照 env.example 创建。" >&2
  exit 1
}

echo "==> 2/6 拉取最新代码"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "${REPO_URL:?请在环境变量 REPO_URL 中指定 git 仓库地址}" "$APP_DIR"
fi

echo "==> 3/6 构建镜像"
docker build -t "$IMAGE" "$APP_DIR"

echo "==> 4/6 备份数据"
if [ -d "$DATA_DIR" ] && [ -n "$(ls -A "$DATA_DIR" 2>/dev/null)" ]; then
  tar -czf "${DATA_DIR}.bak.$(date +%Y%m%d%H%M).tgz" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
fi

echo "==> 5/6 重启容器"
docker rm -f "$CONTAINER" 2>/dev/null || true
docker run -d --name "$CONTAINER" --restart unless-stopped \
  -p "${PORT}:${PORT}" \
  -v "${DATA_DIR}:/app/data" \
  --env-file "$ENV_FILE" \
  -e PORT="$PORT" \
  -e RADAR_HOST=0.0.0.0 \
  "$IMAGE"

echo "==> 6/6 健康检查"
sleep 3
for i in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    echo "更新完成：http://<服务器IP>:${PORT}/"
    docker logs --tail 5 "$CONTAINER"
    exit 0
  fi
  sleep 3
done
echo "服务未在预期时间内就绪，查看日志：docker logs $CONTAINER" >&2
exit 1