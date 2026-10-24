# -*- coding: utf-8 -*-
"""网站令牌、登录锁定与请求身份解析，不依赖 Web 框架。"""

import datetime
import hashlib
import hmac
import time

#: token 有效期（天）。同学手机上输一次口令，这段时间内不用再输。
TOKEN_TTL_DAYS = 30

#: 同一个 IP 连续输错多少次口令后暂时锁定
MAX_LOGIN_FAILURES = 8
LOCKOUT_SECONDS = 300

_failures = {}


def issue_token(secret, now=None):
    """签发无状态 token（日期 + HMAC），密钥为共享口令。

    形如 ``2026-09-25.3f2a...``，服务重启不影响已签发 token。
    """
    day = (now or datetime.date.today()).isoformat()
    sig = hmac.new(
        secret.encode("utf-8"), day.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return "%s.%s" % (day, sig)


def verify_token(secret, token, now=None):
    """校验 token 是否有效且未过期。"""
    if not token or "." not in token:
        return False
    day, _, sig = token.rpartition(".")
    today = now or datetime.date.today()
    for offset in range(TOKEN_TTL_DAYS):
        candidate = today - datetime.timedelta(days=offset)
        if candidate.isoformat() != day:
            continue
        expected = issue_token(secret, now=candidate).rpartition(".")[2]
        # 用 compare_digest 而不是 ==，避免通过响应时间逐字节猜签名
        return hmac.compare_digest(sig, expected)
    return False


def _bearer(request):
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _client_ip(request):
    """取真实客户端 IP。

    请求经过 Cloudflare 隧道而来，``request.client.host`` 永远是 127.0.0.1，
    所以读 Cloudflare 注入的 ``CF-Connecting-IP``。因为源站只监听回环、
    只有 cloudflared 能连进来，这个头是可信的。
    """
    return request.headers.get("cf-connecting-ip") or (
        request.client.host if request.client else "unknown"
    )


def _lockout_remaining(ip):
    entry = _failures.get(ip)
    if not entry:
        return 0
    count, first_at = entry
    if count < MAX_LOGIN_FAILURES:
        return 0
    remaining = LOCKOUT_SECONDS - (time.time() - first_at)
    if remaining <= 0:
        _failures.pop(ip, None)
        return 0
    return int(remaining) + 1


def _record_failure(ip):
    count, first_at = _failures.get(ip, (0, time.time()))
    if time.time() - first_at > LOCKOUT_SECONDS:
        count, first_at = 0, time.time()
    _failures[ip] = (count + 1, first_at)
