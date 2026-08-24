# 在 company_agent 目录构建：
#   docker build -f radar/Dockerfile -t radar-demo .
#   docker run --rm -p 8765:8765 \
#     -e RADAR_HOST=0.0.0.0 -e PORT=8765 \
#     -e LLM_BASE_URL=... -e LLM_API_KEY=... -e LLM_MODEL=... \
#     -e FEISHU_WEBHOOK_URL=... \
#     radar-demo
FROM python:3.12-slim
WORKDIR /app
COPY radar /app/radar
ENV PYTHONPATH=/app/radar
ENV RADAR_HOST=0.0.0.0
ENV PORT=8765
WORKDIR /app/radar
EXPOSE 8765
CMD ["python", "-m", "radar", "serve"]
