"""Cookie persistence, including domain/path and legacy-format support."""

import json
import logging
import time
from urllib.parse import urlparse

logger = logging.getLogger("snut.auth")


def save_session(session, session_file, eams_base):
    """把当前会话 Cookie 写入 .session/cookies.json。

    必须连 **domain 一起保存**。早期版本只存 name/value，
    恢复时 Cookie 因缺少归属域而无法正确发送。
    其中 CAS 的 ``CASTGC`` 尤其重要——它代表统一认证端的登录状态，
    只要它有效就能免密换到新的 EAMS 会话。
    """
    cookies = [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain or "",
            "path": c.path or "/",
        }
        for c in session.cookies
    ]
    data = {
        "saved_at": time.time(),
        "host": urlparse(eams_base).hostname,
        "cookies": cookies,
    }
    try:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        names = [c["name"] for c in cookies]
        logger.debug("会话已保存（%d 个 Cookie：%s）", len(cookies), names)
    except OSError as exc:
        logger.warning("保存会话失败：%s", exc)


def load_session(session, session_file):
    """从文件恢复会话，返回是否成功读到可用数据。"""
    if not session_file.exists():
        return False
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.debug("读取会话文件失败：%s", exc)
        return False

    raw = data.get("cookies")
    if not raw:
        return False

    count = 0
    if isinstance(raw, dict):
        # 兼容早期格式（只有 name/value，没有 domain）
        for name, value in raw.items():
            session.cookies.set(name, value)
            count += 1
    else:
        for item in raw:
            try:
                kwargs = {}
                if item.get("domain"):
                    kwargs["domain"] = item["domain"]
                if item.get("path"):
                    kwargs["path"] = item["path"]
                session.cookies.set(item["name"], item["value"], **kwargs)
                count += 1
            except (KeyError, TypeError):
                continue

    logger.debug("已从文件恢复 %d 个 Cookie", count)
    return count > 0

