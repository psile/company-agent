# 在本项目根目录构建：
#   docker build -t radar-app .
#   docker run -d --name radar --restart unless-stopped \
#     -p 8765:8765 \
#     -v /opt/radar/data:/app/data \
#     --env-file /opt/radar/env \
#     radar-app
# 生产环境 /opt/radar/env 里务必包含：DEV_SEED=0 和 INITIAL_ADMIN_PASSWORD=<强密码>
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY radar /app/radar
COPY web /app/web
COPY sources.json /app/sources.json
ENV PYTHONPATH=/app
ENV RADAR_HOST=0.0.0.0
ENV PORT=8765
EXPOSE 8765
VOLUME /app/data
CMD ["python", "-m", "radar", "serve"]
