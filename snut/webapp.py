# -*- coding: utf-8 -*-
"""课表网站后端（FastAPI）。

职责极其单一：把 :mod:`snut.snapshot` 落地的 JSON 喂给前端。

**它刻意不 import 任何与学校系统打交道的模块**（``auth`` / ``course`` /
``captcha``）。这个隔离带来三个好处：

* 同学怎么刷新都不会给学校增加哪怕一次请求；
* 学校风控、改版、限流都波及不到网站；
* 这个进程的内存里**没有学号、没有密码、没有会话 Cookie**——
  即使 web 层被攻破，也拿不到能登录教务系统的东西。

启动::

    uvicorn snut.webapp:app --host 127.0.0.1 --port 8000

**必须绑 127.0.0.1**。公网入口交给 cloudflared 隧道，这样源站不开放任何
入站端口，别人扫到 8000 也进不来。
"""

import datetime
import hashlib
import hmac
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
)
from fastapi.staticfiles import StaticFiles

from .config import ROOT_DIR, ConfigError, get_config
from .formatter import current_week_from_start
from .snapshot import load_snapshot

logger = logging.getLogger(__name__)

#: token 有效期（天）。同学手机上输一次口令，这段时间内不用再输。
TOKEN_TTL_DAYS = 30

#: 同一个 IP 连续输错多少次口令后暂时锁定
MAX_LOGIN_FAILURES = 8
LOCKOUT_SECONDS = 300

app = FastAPI(
    title="课表",
    # 关掉自动生成的文档页：它会把接口结构暴露给所有人，没有理由开着
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# ----------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------


def _config():
    """懒加载配置。

    刻意不在模块级调用 ``get_config()``——那样一旦 .env 有问题，
    web 进程会在 import 阶段就崩掉，systemd 只看到「启动失败」，
    排查起来毫无头绪。放在请求里 catch 就能给出明确提示。
    """
    return get_config()


def _config_or_error():
    try:
        return get_config(), None
    except ConfigError as exc:
        logger.error("配置有问题：%s", exc)
        return None, JSONResponse(
            {"error": "服务端配置缺失", "code": "config"}, status_code=500
        )


# ----------------------------------------------------------------------
# 口令与 token
# ----------------------------------------------------------------------
#
# 无状态设计：token 就是「签发日期 + HMAC 签名」，服务端不存 session。
# 好处是重启服务、甚至换机器，同学手上的 token 都还有效。
# 密钥用口令本身，不知道口令就伪造不出签名。


def issue_token(secret, now=None):
    """签发 token，形如 ``2026-09-25.3f2a...``。"""
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
        expected = hmac.new(
            secret.encode("utf-8"), day.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        # 用 compare_digest 而不是 ==，避免通过响应时间逐字节猜签名
        return hmac.compare_digest(sig, expected)
    return False


def _bearer(request):
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


# ----------------------------------------------------------------------
# 登录失败限速（内存态，单进程够用）
# ----------------------------------------------------------------------

_failures = {}


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


# ----------------------------------------------------------------------
# 中间件：反搜索引擎收录
# ----------------------------------------------------------------------

#: 所有响应都带这个头。详见 robots.txt 路由里的说明。
NOINDEX_HEADER = "noindex, nofollow, noarchive, nosnippet"


@app.middleware("http")
async def add_noindex_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = NOINDEX_HEADER
    # 静态资源带版本查询参数时仍可长期复用；HTML/API 保持短缓存，
    # 这样换版不会让同学长期看到旧页面，课表数据也不会跨天滞留。
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    elif request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache"
    return response


# ----------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------


@app.api_route("/", methods=["GET", "HEAD"])
async def index():
    config, error = _config_or_error()
    if error:
        return error
    return FileResponse(
        str(config.web_dir / "index.html"),
        media_type="text/html; charset=utf-8",
    )


@app.api_route("/api/timetable", methods=["GET", "HEAD"])
async def timetable(request: Request):
    """课表数据。**网站唯一的数据接口。**

    前端一次拿全量，之后按周过滤、切周次全在本地算——所以切周次是瞬时的，
    不会每切一次就打一次服务器。
    """
    config, error = _config_or_error()
    if error:
        return error

    if config.web_password and not verify_token(
        config.web_password, _bearer(request)
    ):
        return JSONResponse(
            {"error": "需要访问口令", "code": "auth_required"}, status_code=401
        )

    snapshot = load_snapshot(config)
    if snapshot is None:
        return JSONResponse(
            {
                "error": "课表数据还没生成",
                "code": "no_data",
                "hint": "服务器上的抓取任务可能尚未运行过",
            },
            status_code=503,
        )

    payload = dict(snapshot)
    # 当前周次实时算，不用快照里的——快照可能是昨天生成的，
    # 跨周那天就会显示错周次。
    payload["current_week"] = (
        current_week_from_start(config.semester_start)
        if config.semester_start
        else None
    )
    payload["server_today"] = datetime.date.today().isoformat()

    # 有口令时绝不能用 public——那会让 Cloudflare 把带数据的响应缓存下来
    # 发给没口令的人。private 只允许浏览器自己缓存。
    cache = "private, max-age=300" if config.web_password else "public, max-age=600"
    return JSONResponse(payload, headers={"Cache-Control": cache})


@app.post("/api/login")
async def login(request: Request):
    config, error = _config_or_error()
    if error:
        return error

    if not config.web_password:
        # 没设口令 = 完全公开，前端直接进入
        return JSONResponse({"ok": True, "token": None})

    ip = _client_ip(request)
    remaining = _lockout_remaining(ip)
    if remaining:
        return JSONResponse(
            {
                "error": "口令错误次数过多，请 %d 秒后再试" % remaining,
                "code": "locked",
            },
            status_code=429,
        )

    try:
        body = await request.json()
    except Exception:
        body = {}
    password = (body or {}).get("password") or ""

    if not hmac.compare_digest(str(password), config.web_password):
        _record_failure(ip)
        logger.warning("口令校验失败，来源 %s", ip)
        return JSONResponse(
            {"error": "口令不对", "code": "bad_password"}, status_code=401
        )

    _failures.pop(ip, None)
    return JSONResponse({"ok": True, "token": issue_token(config.web_password)})


@app.api_route("/healthz", methods=["GET", "HEAD"])
async def healthz():
    """健康检查：确认进程活着，以及快照是否可读。"""
    config, error = _config_or_error()
    if error:
        return error
    snapshot = load_snapshot(config)
    return JSONResponse(
        {
            "ok": True,
            "has_snapshot": snapshot is not None,
            "updated_at": (snapshot or {}).get("updated_at"),
            "courses": len((snapshot or {}).get("courses") or []),
            "auth": bool(config.web_password),
        }
    )


#: 拿数据去训练 / 做 AI 检索的爬虫。**不要**往里加 Googlebot、bingbot、
#: Baiduspider 这类搜索引擎爬虫——它们要能进来读 noindex。
AI_CRAWLERS = (
    "GPTBot",
    "ChatGPT-User",
    "OAI-SearchBot",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "Google-Extended",
    "Applebot-Extended",
    "Bytespider",
    "CCBot",
    "PerplexityBot",
    "meta-externalagent",
    "Amazonbot",
    "cohere-ai",
    "Diffbot",
    "Omgilibot",
    "FacebookBot",
)


@app.api_route("/robots.txt", methods=["GET", "HEAD"])
async def robots():
    """robots.txt —— 只挡 AI 训练爬虫，**故意不写 ``Disallow: /``**。

    这一点很反直觉，但很关键：

    ``Disallow`` 只挡**抓取**，不挡**收录**。一个被 disallow 的网址，
    照样可能出现在搜索结果里（只显示一个空壳 URL）。真正能拒绝收录的是
    ``noindex`` 指令，而它**必须让爬虫抓得到页面才能读到**。

    所以如果这里写 ``Disallow: /``，爬虫进不来 → 读不到我们响应头里的
    ``X-Robots-Tag: noindex`` → 网址反而可能被收录。两个指令会互相打架。

    正确做法：让正经搜索引擎进来（读 ``noindex`` 然后不收录），
    只点名挡掉那些拿数据去训练的 AI 爬虫。
    """
    lines = [
        "# 本站不希望被收录，请遵守响应头中的 X-Robots-Tag: noindex",
        "",
    ]
    for agent in AI_CRAWLERS:
        lines.append("User-agent: %s" % agent)
        lines.append("Disallow: /")
        lines.append("")
    lines += [
        "# 搜索引擎请正常抓取：响应头里的 noindex 会告诉你不要收录",
        "User-agent: *",
        "Disallow:",
        "",
    ]
    return PlainTextResponse("\n".join(lines))


# ----------------------------------------------------------------------
# 静态资源
# ----------------------------------------------------------------------
# 挂在模块末尾：StaticFiles 会把 web/ 整个目录暴露在 /static/ 下，
# 里面只有前端文件，没有任何数据或配置。
#
# 这里直接用 ROOT_DIR 拼路径而**不**经由 get_config()——get_config() 会
# 要求 .env 里有学号密码，而 web 进程根本不需要那些。不能在 import 阶段
# 因为一个用不到的原因让服务起不来。

WEB_DIR = ROOT_DIR / "web"

if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
else:  # pragma: no cover - 仅在目录缺失时触发
    logger.error("前端目录不存在：%s（页面会 404）", WEB_DIR)
