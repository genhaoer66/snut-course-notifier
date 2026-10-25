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


def _collect_files():
    return [
        "web/" + name
        for name in sorted(os.listdir(os.path.join(root, "web")))
        if os.path.isfile(os.path.join(root, "web", name))
    ]


client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username="root", password=password, timeout=45)
try:
    sftp = client.open_sftp()
    for rel in _collect_files():
        sftp.put(os.path.join(root, rel), REMOTE + "/" + rel)
    sftp.close()
    print("已上传全部前端静态文件")
finally:
    client.close()
