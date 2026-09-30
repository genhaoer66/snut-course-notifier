# -*- coding: utf-8 -*-
"""消息推送。

已实现渠道
----------
* **邮件**（QQ 邮箱 / 163 等，走 SMTP SSL）—— 主力渠道。
  手机 QQ 与微信都会收到邮件到达提醒，且不依赖任何第三方服务，最稳定。

预留渠道
--------
* **微信**（Server酱）—— 配置了 ``SERVERCHAN_KEY`` 才会启用。

用法::

    from snut.notify import push
    push(config, "今日课表", text_body, html_body)
"""

import logging
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger(__name__)


class NotifyError(Exception):
    """推送失败。"""


# ----------------------------------------------------------------------
# 邮件
# ----------------------------------------------------------------------


def send_mail(config, subject, text_body, html_body=None):
    """通过 SMTP 发送邮件。

    注意事项（都是踩过的坑）：

    * ``SMTP_AUTH_CODE`` 填的是**授权码**，不是邮箱登录密码，
      填错会抛 ``535 Authentication failed``；
    * QQ 邮箱用 465 端口 + SSL；25 端口基本都被封；
    * 中文主题必须经 :class:`~email.header.Header` 编码，
      否则连接正常但发信会静默失败；
    * 同时附带纯文本与 HTML 两个版本，可显著降低被判垃圾邮件的概率。
    """
    if not config.mail_enabled:
        raise NotifyError(
            "邮件未配置完整：请在 .env 中填写 SMTP_USER、SMTP_AUTH_CODE、MAIL_TO"
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr(
        (str(Header(config.mail_from_name, "utf-8")), config.smtp_user)
    )
    msg["To"] = config.mail_to
    msg["Subject"] = Header(subject, "utf-8")
    msg["Reply-To"] = config.smtp_user

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(
            config.smtp_host,
            config.smtp_port,
            timeout=config.http_timeout,
            context=context,
        ) as server:
            server.login(config.smtp_user, config.smtp_auth_code)
            server.sendmail(
                config.smtp_user, [config.mail_to], msg.as_string()
            )
    except smtplib.SMTPAuthenticationError:
        raise NotifyError(
            "SMTP 认证失败：请确认 .env 中的 SMTP_AUTH_CODE 是**授权码**"
            "（在 QQ 邮箱 设置→账户→开启 IMAP/SMTP 服务 后获得），"
            "而不是邮箱登录密码。"
        )
    except smtplib.SMTPException as exc:
        raise NotifyError("发送邮件失败：%s" % exc)
    except OSError as exc:
        raise NotifyError(
            "连接邮件服务器失败：%s（请检查网络，或确认端口 %s 未被屏蔽）"
            % (exc, config.smtp_port)
        )

    logger.info("邮件已发送至 %s", config.mail_to)
    return True


# ----------------------------------------------------------------------
# 微信（Server酱，可选）
# ----------------------------------------------------------------------


def send_serverchan(config, title, text_body):
    """通过 Server酱推送到微信。未配置则跳过。"""
    if not config.serverchan_enabled:
        return False

    import requests

    url = "https://sctapi.ftqq.com/%s.send" % config.serverchan_key
    try:
        resp = requests.post(
            url,
            data={"title": title, "desp": text_body},
            timeout=config.http_timeout,
        )
        payload = resp.json()
    except Exception as exc:
        raise NotifyError("Server酱推送失败：%s" % exc)

    if payload.get("code") not in (0, "0"):
        raise NotifyError(
            "Server酱返回错误：%s" % payload.get("message", payload)
        )
    logger.info("微信（Server酱）已推送")
    return True


# ----------------------------------------------------------------------
# 统一入口
# ----------------------------------------------------------------------


def push(config, subject, text_body, html_body=None, raise_on_error=False):
    """按配置向所有已启用的渠道推送。

    默认**不会**因为某个渠道失败而中断其他渠道；失败会记录日志。
    设置 ``raise_on_error=True`` 时，只要有渠道失败就抛出异常。

    :return: 成功推送的渠道名列表
    """
    sent = []
    errors = []

    if config.mail_enabled:
        try:
            send_mail(config, subject, text_body, html_body)
            sent.append("mail")
        except NotifyError as exc:
            logger.error("邮件推送失败：%s", exc)
            errors.append(("mail", exc))

    if config.serverchan_enabled:
        try:
            send_serverchan(config, subject, text_body)
            sent.append("serverchan")
        except NotifyError as exc:
            logger.error("微信推送失败：%s", exc)
            errors.append(("serverchan", exc))

    if not sent and not errors:
        raise NotifyError(
            "没有任何可用的推送渠道。请在 .env 中配置邮件"
            "（SMTP_USER / SMTP_AUTH_CODE / MAIL_TO）后重试。"
        )

    if errors and raise_on_error:
        raise errors[0][1]

    return sent


def send_alert(config, message, detail=""):
    """发送告警消息。

    当自动登录失效、课表抓取失败等异常发生时调用，
    避免程序静默失败（那样用户可能几周都不知道课表已经没在推送了）。
    """
    subject = "【课表助手】出问题了，需要你处理"
    text = "%s\n\n%s\n\n—— 请检查程序运行日志（logs/ 目录）。" % (message, detail)
    try:
        return push(config, subject, text)
    except NotifyError as exc:
        logger.error("告警消息也发不出去：%s", exc)
        return []
