"""Pure CAS page parsing and result classification."""

from urllib.parse import urlparse

from bs4 import BeautifulSoup


def parse_login_page(html):
    soup = BeautifulSoup(html, "html.parser")

    def field(element_id):
        node = soup.find("input", {"id": element_id})
        if node is None:
            node = soup.find("input", {"name": element_id})
        return (node.get("value") or "").strip() if node else ""

    # 登录页里**同时存在多套表单**（生物识别 / 短信 / 账号密码 / 扫码），
    # 每套都有自己的 cllt 隐藏值，而它们的 id 是重复的。HTML 中第一个
    # id="cllt" 属于生物识别表单（value="fidoLogin"），用 soup.find 取第一个
    # 会拿到错误的值，服务端会按生物识别流程处理并返回"认证失败"。
    # 因此这里**不解析 cllt，直接锁定账号密码登录**，
    # 与学校 login.js 中 cllt=='userNameLogin' 的分支保持一致。
    cllt = "userNameLogin"
    dllt = "generalLogin"

    params = {
        "execution": field("execution"),
        "pwdEncryptSalt": field("pwdEncryptSalt"),
        "lt": field("lt"),
        "cllt": cllt,
        "dllt": dllt,
    }

    # 页面上始终存在验证码容器，但 <img id="captchaImg"> 初始**没有 src**，
    # 只有服务端真正要求验证码时才会由 JS 填入图片地址。
    # 所以判断依据是"有没有 src"，而不是"有没有这个标签"。
    captcha_img = soup.find("img", {"id": "captchaImg"})
    has_captcha = bool(captcha_img and (captcha_img.get("src") or "").strip())
    return params, has_captcha


def extract_error(html, final_url=""):
    """从登录页 HTML 中提取错误提示。"""
    soup = BeautifulSoup(html, "html.parser")

    selectors = (
        "#msg", "#errorMsg", ".alert-error", "#showErrorTip",
        ".login-error", "#formErrorTip", "#errorDiv", ".error-tip",
        "#showMsg", ".form-error", "#msgTips",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return "登录失败：%s" % text

    # 金智的提示常常直接写在页面文本里
    text = soup.get_text(" ", strip=True)
    for keyword in ("用户名或密码", "密码错误", "密码有误", "账号或密码",
                    "用户不存在", "账号被锁定", "账户被锁定", "验证码"):
        idx = text.find(keyword)
        if idx >= 0:
            snippet = text[max(0, idx - 30): idx + 50].strip()
            return "登录失败：…%s…" % snippet

    host = urlparse(final_url).hostname or final_url
    return (
        "登录失败：提交后仍停留在 %s，页面里没有找到明确的错误提示。"
        "请查看 logs/debug_login_failed.html 分析。" % host
    )


def is_eams_url(url, eams_base):
    final_host = (urlparse(url).hostname or "").lower()
    eams_host = (urlparse(eams_base).hostname or "").lower()
    return bool(eams_host and final_host == eams_host)
