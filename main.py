from fastapi import FastAPI, Request, HTTPException
import os
import hashlib
import base64
import hmac
import time
import requests
import pymysql
import logging
import re
import urllib.parse
import json
from datetime import datetime, timedelta

app = FastAPI()

# 配置日志
logging.basicConfig(level=logging.INFO)

# 飞书 Webhook URL 和密钥
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")

# MySQL 数据库配置
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_DB = os.getenv("MYSQL_DB")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PSWD = os.getenv("MYSQL_PSWD")

# 微服务到人员的映射关系
SERVICE_TO_USER = {
    "service1": "user1",
    "service2": "user2",
    "service3": "user3",

}

class Database:
    def __init__(self, host, db, user, pswd):
        self.host = host
        self.db = db
        self.user = user
        self.pswd = pswd

    def __enter__(self):
        self.conn = pymysql.connect(host=self.host,
                                    user=self.user,
                                    password=self.pswd,
                                    database=self.db)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_tb is not None:
            logging.error(f"Error occurred: {exc_val}")
        self.conn.close()

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def proc_phone(phone):
    if len(phone) == 11:
        phone = f'+86{str(phone)}'
    return phone

def get_user_id(name=None, phone=None):
    with Database(host=MYSQL_HOST, db=MYSQL_DB, user=MYSQL_USER, pswd=MYSQL_PSWD) as conn:
        cursor = conn.cursor()
        sql = 'SELECT source_user_id FROM users WHERE'
        params = []

        if name:
            sql += ' username = %s'
            params.append(name)
        elif phone:
            phone = proc_phone(phone)
            sql += ' mobile = %s'
            params.append(phone)
        else:
            return None

        #logging.info(f"Executing SQL: {sql} with params: {params}")
        cursor.execute(sql, params)
        result = cursor.fetchone()
        if result:
            #logging.info(f"Found user_id: {result[0]}")
            return result[0].replace('feishu_', '')
        logging.warning("No user_id found")
        return None


def get_mention(service_name):
    user_name = SERVICE_TO_USER.get(service_name.strip())
    if user_name:
        return get_user_id(name=user_name)
    return None


def time_range(alert_time):
    # 计算时间范围
    alert_dt = datetime.strptime(alert_time, "%Y-%m-%dT%H:%M:%S")
    from_time = int((alert_dt - timedelta(minutes=5)).timestamp() * 1000)
    to_time = int((alert_dt + timedelta(minutes=5)).timestamp() * 1000)

    return from_time, to_time


def create_lokiurl(app_name, inf, from_time, to_time, uid):
    GRAFANA_URL = os.getenv("GRAFANA_URL")
    base_url = f"{GRAFANA_URL}/explore?orgId=1&left="

    # 参数字典
    query = {
            "datasource":"%s" % (uid),
            "queries":[
                {
                    "refId":"A",
                    "datasource":{
                        "type":"loki",
                        "uid":"%s" % (uid)
                    },
                    "editorMode":"builder",
                    "expr":(
                        r'{app=~"%s"} |= `` |= `"_typ"` | pattern `<_> [<_>] <_> -- [<_>][<_>] <_js>` | '
                        r'line_format `{{._js}}` | json | _typ = `resp` | _j_code != `200` | _inf = `%s` | __error__=``'
                    ) % (app_name, inf),
                    "queryType":"range"
                }
            ],
            "range":{
                "from": "%s" % (from_time),
                "to": "%s" % (to_time)
            }
        }
   


    # 将 query 字典转换为 JSON 字符串
    query_json = json.dumps(query)

    # 对 JSON 字符串进行 URL 编码
    query_encoded = urllib.parse.quote(query_json)

    # 拼接最终的 URL
    grafana_url = f"{base_url}{query_encoded}"
    return grafana_url

def create_errurl(app_name, namespace, keywords, from_time, to_time, uid):
    GRAFANA_URL = os.getenv("GRAFANA_URL")
    base_url = f"{GRAFANA_URL}/explore?orgId=1&left="

    # 参数字典
    query = {
            "datasource":"%s" % (uid),
            "queries":[
                {
                    "refId":"A",
                    "datasource":{
                        "type":"loki",
                        "uid":"%s" % (uid)
                    },
                    "editorMode":"builder",
                    "expr":(
                        r'{app=~"%s", namespace=~"%s"} |= `` != `"_typ"` != `<PicData>` |= `%s` | __error__=`` '
                    ) % (app_name, namespace, keywords),
                    "queryType":"range"
                }
            ],
            "range":{
                "from": "%s" % (from_time),
                "to": "%s" % (to_time)
            }
        }


    # 将 query 字典转换为 JSON 字符串
    query_json = json.dumps(query)

    # 对 JSON 字符串进行 URL 编码
    query_encoded = urllib.parse.quote(query_json)

    # 拼接最终的 URL
    grafana_url = f"{base_url}{query_encoded}"
    return grafana_url

@app.post("/alert")
async def receive_message(request: Request):
    try:
        data = await request.json()
        logging.info(f"Received data: {data}")
        message = data.get("message")
        status = data.get("status", None)
        at_name = data.get("at_name", None)
        at_phone = data.get("at_phone", None)

        if not message:
            logging.error("Message content is missing")
            raise HTTPException(status_code=400, detail="Message content is missing")

        if not status:
            logging.warning("Alert status is missing")
            status = "unknown"

        status_lower = status.lower()

        if status_lower == "firing":
            template_color = "red"
        elif status_lower == "medium":
            template_color = "yellow"
        elif status_lower == "resolved":
            template_color = "green"
        elif status_lower == "new":
            template_color = "blue"
        elif status_lower == "spcial":
            template_color = "purple"
        else:
            template_color = "grey"

        message_lines = message.split('\n')
        if message_lines[0].strip() == "":
            if len(message_lines) > 1:
                title = message_lines[1]
                content = '\n'.join(message_lines[2:]) if len(message_lines) > 2 else ""
            else:
                title = "无标题"
                content = ""
        else:
            title = message_lines[0]
            content = '\n'.join(message_lines[1:]) if len(message_lines) > 1 else ""

        alert_time = None
        for line in message_lines:
            if "告警时间" in line:
                alert_time = line.split(" ", 1)[1].strip()
                break

        if alert_time:
            from_time, to_time = time_range(alert_time)

        app_name = None
        for line in message_lines:
            if "服务名称" in line:
                app_name = line.split(" ", 1)
                if len(app_name) > 1:
                    app_name = app_name[1].strip()
                else:
                    logging.debug(f"Invalid 服务名称 line format: {line}")
                    app_name = None
                break

        inf = None
        for line in message_lines:
            if "接口名称" in line:
                inf = line.split(" ", 1)
                if len(inf) > 1:
                    inf = inf[1].strip()
                else:
                    logging.debug(f"Invalid 接口名称 line format: {line}")
                    inf = None
                break

        namespace = None
        uid = None
        for line in message_lines:
            if "命名空间" in line:
                namespace = line.split(" ", 1)
                if len(namespace) > 1:
                    namespace = namespace[1].strip()
                    if namespace == "zsetc":
                        uid = "3bQFX2XVz"
                    elif namespace == "jhetc":
                        uid = "3zvrzrQSz"
                else:
                    logging.debug(f"Invalid 命名空间 line format: {line}")
                    namespace = None
                break

        keywords = None
        for line in message_lines:
            if  "触发条件" in line:
                keywords = line.split(" ", 1)
                if len(keywords) > 1:
                    keywords = keywords[1].strip()
                    if "ERROR" in keywords:
                        keywords = "ERROR"
                    elif "Exception" in keywords:
                        keywords = "Exception"
                    elif "exception" in keywords:
                        keywords = "exception"
                    else:
                        keywords = None
                else:
                    logging.debug(f"Invalid 触发条件 line format: {line}")
                    keywords = None
                break

        if app_name and inf and alert_time:
            grafana_url = create_lokiurl(app_name, inf, from_time, to_time, uid)
            logging.debug(f"日志链接: {grafana_url}")
            content += f"\n\n[点击查看 Loki 日志]({grafana_url})"
            # content += f"\n查看 Loki 日志:\n{grafana_url}"

        elif app_name and namespace and keywords and alert_time:
            grafana_url = create_errurl(app_name, namespace, keywords, from_time, to_time, uid)
            logging.debug(f"日志链接: {grafana_url}")
            content += f"\n\n[点击查看 Loki 日志]({grafana_url})"
       

        at = ""
        if at_name == "all":
            at = '<at id="all">所有人</at>'
        elif at_name:
            names = at_name.split(',')
            at_users = []
            for name in names:
                user_id = get_user_id(name=name.strip())
                if user_id:
                    at_users.append(f'<at id="{user_id}">{name.strip()}</at>')
            at = ' '.join(at_users)
        elif at_phone:
            phones = at_phone.split(',')
            at_users = []
            for phone in phones:
                user_id = get_user_id(phone=phone.strip())
                if user_id:
                    at_users.append(f'<at id="{user_id}">{phone.strip()}</at>')
            at = ' '.join(at_users)
        else:
            for line in message_lines:
                if "服务名称" in line:
                    service_name = line.split(" ", 1)[1].strip()
                    user_id = get_mention(service_name)
                    if user_id:
                        at = f'<at id="{user_id}">{SERVICE_TO_USER[service_name]}</at> <at id="ou_xxxxxxxxxxxxxxxxxxxxxxxx">项目负责人姓名</at>'
                    break

        timestamp = str(int(time.time()))
        sign = gen_sign(timestamp, FEISHU_SECRET)

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "timestamp": timestamp,
            "sign": sign,
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "template": template_color
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"{content}"
                    },
                    {
                        "tag": "markdown",
                        "content": f"{at}"
                    }
                ]
            }
        }

        response = requests.post(FEISHU_WEBHOOK_URL, headers=headers, json=payload)
        response.raise_for_status()
        return {"code": 0, "message": "Success"}

    except Exception as e:
        logging.error(f"Error processing alert: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

