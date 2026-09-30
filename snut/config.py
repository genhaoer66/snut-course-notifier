# -*- coding: utf-8 -*-
"""配置读取。

所有敏感信息（学号、密码、邮箱授权码）都从项目根目录的 .env 读取。
.env 已被 .gitignore 忽略，不会进入版本库。
"""

import datetime
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（snut/ 的上一级）
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)


class ConfigError(Exception):
    """配置项缺失或格式非法。"""


def _get(key, default=None, required=False):
    """读取字符串配置项，自动去除首尾空白。"""
    value = os.getenv(key)
    if value is not None:
        value = value.strip()
    if not value:
        value = default
    if required and not value:
        raise ConfigError(
            "缺少配置项 %s。请确认 %s 存在，且其中填写了该项。" % (key, ENV_FILE)
        )
    return value


def _get_int(key, default):
    raw = _get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError("%s 必须是整数，当前值：%r" % (key, raw))


def _get_float(key, default):
    raw = _get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError("%s 必须是数字，当前值：%r" % (key, raw))


def _get_bool(key, default=False):
    raw = _get(key)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


class Config(object):
    """运行时配置对象。"""

    def __init__(self):
        # ---------- 统一身份认证 ----------
        self.username = _get("SNUT_USERNAME", required=True)
        self.password = _get("SNUT_PASSWORD", required=True)

        # ---------- 学校系统地址 ----------
        self.auth_base = _get(
            "AUTH_BASE", "https://authserver.snut.edu.cn/authserver"
        )
        self.eams_base = _get("EAMS_BASE", "http://jwgl.snut.edu.cn/eams")

        # ---------- 邮件推送 ----------
        self.smtp_host = _get("SMTP_HOST", "smtp.qq.com")
        self.smtp_port = _get_int("SMTP_PORT", 465)
        self.smtp_user = _get("SMTP_USER")
        self.smtp_auth_code = _get("SMTP_AUTH_CODE")
        self.mail_to = _get("MAIL_TO")
        self.mail_from_name = _get("MAIL_FROM_NAME", "课表小助手")

        # ---------- 微信推送（可选） ----------
        self.serverchan_key = _get("SERVERCHAN_KEY")

        # ---------- 网站访问口令 ----------
        # 留空则网站完全公开。填了之后，/api/timetable 需要带 token 才能访问。
        # 注意：这是一道「挡陌生人」的共享口令，不是账号体系——
        # 全班同学用同一个口令，发给谁就等于允许谁看。
        self.web_password = _get("WEB_PASSWORD")

        # ---------- 其他 ----------
        self.http_timeout = _get_int("HTTP_TIMEOUT", 30)
        # 两次请求之间的最小间隔（秒）。学校 EAMS 有防刷机制，
        # 请求过密会返回"请不要过快点击"页面，务必留出间隔。
        self.request_interval = _get_float("REQUEST_INTERVAL", 2.0)
        self.debug_save_raw = _get_bool("DEBUG_SAVE_RAW", False)

        # 本学期第 1 周的周一日期（ISO 格式，如 2026-09-07）。
        # 用于推算"当前是第几周"。留空则不按周次过滤，
        # 当天所有课程都会列出（可能包含非本周的课）。
        start_raw = _get("SEMESTER_START")
        self.semester_start = None
        if start_raw:
            try:
                self.semester_start = datetime.date.fromisoformat(start_raw)
            except ValueError:
                raise ConfigError(
                    "SEMESTER_START 格式应为 YYYY-MM-DD（如 2026-09-07），"
                    "当前值：%r" % start_raw
                )

        self.log_dir = ROOT_DIR / "logs"
        self.session_dir = ROOT_DIR / ".session"
        # 课表快照（供网站读取）。含课程信息，不含任何个人信息。
        self.data_dir = ROOT_DIR / "data"
        # 网站前端静态文件目录
        self.web_dir = ROOT_DIR / "web"

    # ---------- 派生属性 ----------

    @property
    def mail_enabled(self):
        """邮件推送是否配置完整。"""
        return bool(self.smtp_user and self.smtp_auth_code and self.mail_to)

    @property
    def serverchan_enabled(self):
        """微信推送是否配置。"""
        return bool(self.serverchan_key)

    @property
    def sso_service_url(self):
        """CAS 登录成功后要跳回的地址（EAMS 的 SSO 入口）。"""
        return "%s/ssoLogin.action" % self.eams_base

    def ensure_dirs(self):
        """确保运行所需目录存在。"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


_instance = None


def get_config():
    """获取全局配置单例。"""
    global _instance
    if _instance is None:
        _instance = Config()
    return _instance
