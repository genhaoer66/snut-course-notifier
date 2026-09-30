# -*- coding: utf-8 -*-
"""快速上传前端静态文件，不触发教务系统抓取。"""
import os
import paramiko

HOST = os.environ.get("SNUT_SSH_HOST")
REMOTE = os.environ.get("SNUT_REMOTE_DIR", "/opt/course-notifier")

password = os.environ.get("SNUT_SSH_PASS")
if not password:
    raise SystemExit("请设置 SNUT_SSH_PASS")
if not HOST:
    raise SystemExit("请设置 SNUT_SSH_HOST")

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username="root", password=password, timeout=45)
try:
    sftp = client.open_sftp()
    for rel in ("web/index.html", "web/style.css", "web/app.js"):
        sftp.put(os.path.join(root, rel), REMOTE + "/" + rel)
    sftp.close()
    print("已上传前端并启用版本化缓存")
finally:
    client.close()
