# 基于 ErisPulse 官方镜像
FROM erispulse/erispulse:latest

# QvQChat 模块文件
COPY . /app/modules/ErisPulse-QvQChat/

# 安装 QvQChat 模块
RUN pip install --no-cache-dir /app/modules/ErisPulse-QvQChat/

# 安装常用模块
RUN epsdk install HelpModule || echo "HelpModule 已安装"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["ep", "run"]
