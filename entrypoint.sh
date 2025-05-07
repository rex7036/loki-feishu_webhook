#!/bin/sh

# 检查并应用时区设置
if [ -n "$TZ" ]; then
    ln -sf /usr/share/zoneinfo/$TZ /etc/localtime
    echo "$TZ" > /etc/timezone
fi

# 设置默认的 host 和 port
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

# 启动 FastAPI 应用
exec uvicorn main:app --host $HOST --port $PORT
