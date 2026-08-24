# 在本项目根目录构建：
#   docker build -t radar-demo .
#   docker run --rm -p 8765:8765 \
#     -e RADAR_HOST=0.0.0.0 -e PORT=8765 \
#     -e LLM_BASE_URL=... -e LLM_API_KEY=... -e LLM_MODEL=... \
#     -e FEISHU_WEBHOOK_URL=... \
#     radar-demo
FROM python:3.12-slim
WORKDIR /app
COPY radar /app/radar
COPY web /app/web
COPY sources.json /app/sources.json
ENV PYTHONPATH=/app
ENV RADAR_HOST=0.0.0.0
ENV PORT=8765
EXPOSE 8765
CMD ["python", "-m", "radar", "serve"]
