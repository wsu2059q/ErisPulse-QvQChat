# 基于 ErisPulse 官方镜像
FROM erispulse/erispulse:latest

LABEL org.opencontainers.image.title="ErisPulse-QvQChat" \
      org.opencontainers.image.description="ErisPulse QvQChat 智能对话模块 — 模型池+行为绑定+多智能体+知识库+MCP" \
      org.opencontainers.image.url="https://github.com/wsu2059q/ErisPulse-QvQChat" \
      org.opencontainers.image.source="https://github.com/wsu2059q/ErisPulse-QvQChat" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="wsu2059q"

# 安装 QvQChat 模块
COPY pyproject.toml README.md LICENSE ./
COPY QvQChat/ ./QvQChat/
RUN uv pip install --system -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["ep", "run"]
