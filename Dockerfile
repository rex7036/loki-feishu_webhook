# 第一阶段：构建阶段
FROM python:3.12.5 AS builder

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --user --no-cache-dir --upgrade pip
RUN pip install --user --no-cache-dir -r requirements.txt
#RUN pip install pymysql


# 复制应用代码
COPY . .

# 第二阶段：运行阶段
FROM python:3.12.5-slim

# 设置工作目录
WORKDIR /app

# 安装 tzdata
RUN apt-get update && apt-get install -y tzdata

# 复制从构建阶段的依赖
COPY --from=builder /root/.local /root/.local

# 复制应用代码
COPY . .

# 设置环境变量
ENV PATH=/root/.local/bin:$PATH

# 设置时区的默认值为 CST
ENV TZ=CST

# 添加一个脚本用于设置时区并启动应用
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# 暴露端口
EXPOSE 8000

# 使用 entrypoint.sh 启动应用
ENTRYPOINT ["entrypoint.sh"]

