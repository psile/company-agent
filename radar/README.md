个性化推送（情报 + 为你，一条链路）

本机：
  cd D:\working\company_agent\radar
  python -m radar serve
  浏览器 http://127.0.0.1:8765/

模拟云（本机当一台 VM，0.0.0.0 监听）：
  python deploy/simulate_cloud.py
  默认端口 8766

真上云需要你们的机器。拷到 Linux 后：
  RADAR_HOST=0.0.0.0 PORT=8765 python -m radar serve

链路：采集 → LLM 结构化理解 → Memory（兴趣/项目/行为）→ 规则排序 + LLM 重排 → 中文总结/tag 推送 → 反馈写回。

LLM：LLM_BASE_URL / LLM_API_KEY / LLM_MODEL，或本机 RadarME 配置兜底。RADAR_LLM=0 关掉模型。
飞书：FEISHU_WEBHOOK_URL。未配只留文案。

详见 FEATURES.md
