# Loki-Feishu 告警通知服务

基于 FastAPI 实现的告警通知服务，用于接收告警信息并通过飞书群聊机器人发送富文本通知，支持自动@相关责任人、生成 Grafana 日志链接等功能。

## 功能特性

- 📨 接收 JSON 格式告警信息，转发至飞书群聊
- 🎨 支持不同告警状态的颜色标记（红色-紧急/黄色-中等/绿色-已解决等）
- @ 指定人员或服务负责人
- 🔗 自动生成 Grafana Loki 日志查询链接
- 🔒 支持飞书机器人签名验证
- 📊 基于 MySQL 数据库的用户信息查询

## 快速开始

### 环境要求

- Python 3.8+
- MySQL 5.7+
- FastAPI 依赖库

### 安装依赖

```bash
pip install fastapi uvicorn pymysql requests python-dotenv
```



### 配置说明
数据库需要自行创建，并至少录入以下几个字段：
```text
username          用户名
nickname          中文名
mobile            手机号
source_user_id    飞书用户id
```
<img width="713" alt="image" src="https://github.com/user-attachments/assets/fea9a549-ae75-45a3-823d-4346cfcf5492" />


### 环境变量
```ini
# 飞书配置
FEISHU_WEBHOOK_URL=你的飞书机器人Webhook地址
FEISHU_SECRET=你的飞书机器人签名密钥

# MySQL 配置
MYSQL_HOST=数据库地址
MYSQL_DB=数据库名称
MYSQL_USER=数据库用户
MYSQL_PSWD=数据库密码

# Grafana 配置
GRAFANA_URL=你的Grafana地址
```

### 运行服务
#### 1. 裸机
复制 `.env.example` 创建 `.env` 文件并配置

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
#### 2. docker-compose
1.按实际情况编辑main.py内容，主要在这这两个位置：
<img width="343" alt="image" src="https://github.com/user-attachments/assets/8bbddde5-f6eb-43f8-a755-5c9dc07a5ee4" />

<img width="1025" alt="image" src="https://github.com/user-attachments/assets/d16e924c-4ff4-415c-9061-b91cc45c9a73" />
2.构建容器镜像,并推送到镜像仓库：

```bash
docker build -t loki-feishu_webhook -f Dockerfile
docker tag  loki-feishu_webhook:latest your_repo/loki-feishu_webhook:latest
docker push your_repo/loki-feishu_webhook:latest
```
3.按实际情况修改compose.yaml配置后运行：

```bash
docker compose up -d
```
#### 3. kubernetes

```bash
kubectl create ns ns.yaml
kubectl apply -f .
```

## API 接口

### 发送告警通知

**Endpoint**: `POST /alert`

```json
{
    "message": "服务名称 order-service\n接口名称 /api/v1/pay\n告警时间 2023-08-01T14:30:00\n错误率超过阈值 5%",
    "status": "firing",
    "at_name": "user1"
}
```

**参数说明**:

| 参数     | 类型   | 必填 | 说明                            |
| :------- | :----- | :--- | :------------------------------ |
| message  | string | 是   | 告警内容（多行文本）            |
| status   | string | 否   | 告警状态（firing/resolved等）   |
| at_name  | string | 否   | 需要@的用户名（多个用逗号分隔） |
| at_phone | string | 否   | 需要@的手机号（多个用逗号分隔） |

## 消息格式要求

告警消息 `message` 建议包含以下关键信息（除了服务名称，其他顺序可调）：

```text
服务名称: [服务名]
接口名称: [接口路径]
命名空间: [namespace]
触发条件: [错误关键词]
告警时间: [ISO 格式时间]
[其他描述信息...]
```

## 功能扩展

### 配置服务负责人

修改 `SERVICE_TO_USER` 映射关系：

```python
SERVICE_TO_USER = {
    "order-service": "zhangsan",
    "payment-service": "lisi",
    # 添加更多服务映射...
}
```

### 自定义 Grafana 链接

1. 修改 `create_lokiurl()` 和 `create_errurl()` 中的查询语句
2. 调整命名空间与 UID 的对应关系

## 注意事项

1. 飞书机器人需开启「加签」功能并配置签名密钥
2. 确保 MySQL 用户表包含以下字段：
   - `source_user_id`（飞书用户ID）
   - `username`/`mobile`
3. 生产环境建议配合 Nginx 部署并配置 HTTPS
4. 需要开启飞书群聊机器人的「IP白名单」功能

## 示例消息
<img width="529" alt="image" src="https://github.com/user-attachments/assets/c36637e6-e66b-4e95-a360-6e3f700da81c" />

