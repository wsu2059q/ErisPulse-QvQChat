FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装 ErisPulse 框架
RUN pip install --no-cache-dir erispulse

# 复制模块文件
COPY . /app/

# 安装 QvQChat 模块及其依赖
RUN pip install --no-cache-dir -e .

# 安装常用适配器（可选，根据需要取消注释）
# QQ 适配器（推荐用于 QQ 机器人）
RUN epsdk install OneBot11 || echo "OneBot11 适配器安装失败，请稍后手动安装"

# 云湖适配器
# RUN epsdk install Yunhu || echo "云湖适配器安装失败，请稍后手动安装"

# Telegram 适配器
# RUN epsdk install Telegram || echo "Telegram 适配器安装失败，请稍后手动安装"

# 创建配置文件目录
RUN mkdir -p /app/config

# 暴露端口（Server 模式适配器需要此端口）
EXPOSE 8000

# 启动命令
CMD ["ep", "run"]
