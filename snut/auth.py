# -*- coding: utf-8 -*-
"""陕西理工大学统一身份认证（金智 authserver / CAS）登录。

登录流程
--------
1. GET  ``authserver/login?service=<EAMS的ssoLogin>``
   从 HTML 中提取 ``execution``、``pwdEncryptSalt``、``lt``。
2. 用 ``pwdEncryptSalt`` 对密码做 AES-CBC/PKCS7 加密。
3. POST 同一地址，提交 ``username`` / ``password``(密文) / ``execution`` 等字段。
4. 跟随 302 拿到 ``ticket``，再用它换取 EAMS 的会话 Cookie。


密码加密算法（逆向自学校 encrypt.js）
-------------------------------------
学校的 ``/authserver/snut/static/common/encrypt.js`` 末尾：

.. code-block:: javascript

    function getAesString(n, f, c) {          // n=明文, f=key, c=iv
        f = f.replace(/(^\\s+)|(\\s+$)/g, "");
        f = CryptoJS.enc.Utf8.parse(f);
        c = CryptoJS.enc.Utf8.parse(c);
        return CryptoJS.AES.encrypt(n, f,
            {iv: c, mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7}
        ).toString();
    }
    function encryptAES(n, f) {               // n=密码, f=salt
        return f ? getAesString(randomString(64) + n, f, randomString(16)) : n;
    }

即：**明文 = 64位随机串 + 密码**，key = salt，iv = 随机16位，
AES-CBC-PKCS7 加密后 Base64 编码。随机串的字符集见 ``AES_CHARS``。
"""

import base64
import json
import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from urllib3.exceptions import InsecureRequestWarning

logger = logging.getLogger(__name__)

# 学校 encrypt.js 里的 $aes_chars：刻意去掉了 I/L/O/U/V 等易混字符
AES_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class AuthError(Exception):
    """登录失败。"""


class CaptchaRequired(AuthError):
    """需要图形验证码，无法静默登录。

    出现这个异常意味着账号可能已被风控，或学校策略要求每次登录都输验证码。
    """


def _random_string(length):
    """生成随机串（对应 encrypt.js 的 randomString）。"""
    return "".join(random.choice(AES_CHARS) for _ in range(length))


def encrypt_password(password, salt):
    """按学校算法加密密码。

    :param password: 明文密码
    :param salt: 登录页隐藏字段 ``pwdEncryptSalt`` 的值
    :return: Base64 编码的密文；若 salt 为空则原样返回密码
    """
    if not salt:
        return password

    # 明文 = 64位随机串 + 密码
    plaintext = _random_string(64) + password
    key = salt.strip().encode("utf-8")
    iv = _random_string(16).encode("utf-8")

    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return base64.b64encode(ciphertext).decode("ascii")


class ThrottledAdapter(HTTPAdapter):
    """请求适配器：限速 + 协议纠正。

    **限速**：学校 EAMS 有防刷机制，短时间内的密集请求会返回
    "请不要过快点击" 的提示页而不是真实数据。挂在 Session 上后，
    **所有**经该 Session 发出的请求都会自动保持最小间隔，
    不会因为某处漏加延时而触发风控。

    **协议纠正**：学校 EAMS 返回的 302 会把统一认证地址写成
    ``http://authserver.snut.edu.cn/...``（80 端口），但该端口不可达，
    只有 https(443) 可用。若照此重定向，requests 会一直卡到超时
    （报 WinError 10060）。因此这里把指向 authserver 的 http 请求
    统一提升为 https。
    """

    #: 需要强制走 https 的主机前缀
    FORCE_HTTPS_PREFIX = "http://authserver.snut.edu.cn"

    def __init__(self, min_interval, max_retries=3):
        self.min_interval = max(0.0, float(min_interval or 0))
        self._last_at = 0.0
        # 学校服务器响应慢且偶尔抽风，配上退避重试
        retry_kwargs = dict(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            backoff_factor=1.5,          # 重试前分别等 1.5s / 3s / 6s
            status_forcelist=[500, 502, 503, 504],
        )
        methods = frozenset(["GET", "POST"])
        try:
            # urllib3 >= 1.26 的写法
            retry = Retry(allowed_methods=methods, **retry_kwargs)
        except TypeError:
            # urllib3 <= 1.25 里这个参数叫 method_whitelist（默认不含 POST，
            # 而取课表用的正是 POST，必须显式加上，否则失败不会重试）
            retry = Retry(method_whitelist=methods, **retry_kwargs)
        super(ThrottledAdapter, self).__init__(max_retries=retry)

    def send(self, request, **kwargs):
        if request.url.startswith(self.FORCE_HTTPS_PREFIX):
            request.url = "https://" + request.url[len("http://"):]

        if self.min_interval > 0:
            waited = time.time() - self._last_at
            if waited < self.min_interval:
                time.sleep(self.min_interval - waited)
        try:
            return super(ThrottledAdapter, self).send(request, **kwargs)
        finally:
            self._last_at = time.time()


class LoginClient(object):
    """封装 CAS 登录与 EAMS 会话。"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        # 全局限速：所有请求都自动保持间隔
        self.session.mount(
            "http://", ThrottledAdapter(getattr(config, "request_interval", 0))
        )
        self.session.mount(
            "https://", ThrottledAdapter(getattr(config, "request_interval", 0))
        )
        # 学校服务器的 SSL 证书若不被信任，下面的 _request 会自动降级
        self._ssl_verify = True

    # ------------------------------------------------------------------
    # 底层请求
    # ------------------------------------------------------------------

    def _request(self, method, url, **kwargs):
        """统一请求入口。

        限速由挂在 Session 上的 ThrottledAdapter 自动完成。
        学校服务器的证书链可能不完整，首次遇到 SSL 错误时自动降级为
        不校验证书并重试一次，同时打印提示。
        """
        kwargs.setdefault("timeout", self.config.http_timeout)
        kwargs.setdefault("verify", self._ssl_verify)

        try:
            return self.session.request(method, url, **kwargs)
        except requests.exceptions.SSLError:
            if not self._ssl_verify:
                raise
            logger.warning(
                "SSL 证书校验失败，已降级为不校验证书重试（仅影响本机到学校的连接）"
            )
            self._ssl_verify = False
            kwargs["verify"] = False
            return self.session.request(method, url, **kwargs)

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------

    def _fetch_login_page(self, service):
        """GET 登录页并解析出必要字段。"""
        url = "%s/login" % self.config.auth_base
        resp = self._request("GET", url, params={"service": service})
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"

        # 被防刷机制拦截时给出明确提示，而不是含糊的"结构异常"
        if "过快点击" in resp.text:
            raise AuthError(
                "登录页返回了『请不要过快点击』——请求过于频繁被限流。"
                "请等待几分钟后重试，或调大 .env 中的 REQUEST_INTERVAL。"
            )

        soup = BeautifulSoup(resp.text, "html.parser")

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

        if not params["execution"]:
            # 保存现场，便于事后分析到底是改版还是被限流
            try:
                self.config.ensure_dirs()
                dump = self.config.log_dir / "debug_login_page_broken.html"
                dump.write_text(resp.text, encoding="utf-8")
                saved = "已保存到 %s" % dump
            except OSError:
                saved = "保存现场失败"

            raise AuthError(
                "登录页结构异常：未找到 execution 字段（%s）。"
                "常见原因：请求过于频繁被限流，或认证系统已改版。"
                % saved
            )

        # 页面上始终存在验证码容器，但 <img id="captchaImg"> 初始**没有 src**，
        # 只有服务端真正要求验证码时才会由 JS 填入图片地址。
        # 所以判断依据是"有没有 src"，而不是"有没有这个标签"。
        captcha_img = soup.find("img", {"id": "captchaImg"})
        has_captcha = bool(captcha_img and (captcha_img.get("src") or "").strip())
        return params, resp.text, has_captcha

    # ------------------------------------------------------------------
    # 分步登录（需要图形验证码时必须分两步：salt 每次都会变）
    # ------------------------------------------------------------------

    def prepare(self):
        """第一步：抓登录页，解析出本次登录所需的一次性参数。

        每次登录都要重新调用——``pwdEncryptSalt`` 每次都不同。
        解析结果保存在实例上，供 :meth:`submit` 使用。
        """
        service = self.config.sso_service_url
        params, page_html, has_captcha = self._fetch_login_page(service)
        logger.debug(
            "登录页字段：execution=%s lt=%r salt=%r",
            params["execution"], params["lt"], params["pwdEncryptSalt"],
        )
        self._login_params = params
        self._has_captcha = has_captcha
        return params

    def fetch_captcha(self, save_path=None):
        """下载图形验证码图片。

        :param save_path: 给定则把图片写入该路径（便于人工识别）
        :return: 图片字节内容
        """
        url = "%s/getCaptcha.htl" % self.config.auth_base
        resp = self._request("GET", url, params={"_t": int(time.time() * 1000)})
        resp.raise_for_status()
        if save_path is not None:
            Path(save_path).write_bytes(resp.content)
        return resp.content

    def submit(self, captcha=""):
        """第二步：提交登录表单。

        :param captcha: 图形验证码答案；不需要验证码时留空
        :raises CaptchaRequired: 服务端要求验证码，或验证码错误
        :raises AuthError: 其他登录失败
        """
        if not getattr(self, "_login_params", None):
            raise RuntimeError("请先调用 prepare() 获取登录页参数")

        params = self._login_params
        service = self.config.sso_service_url

        encrypted = encrypt_password(self.config.password, params["pwdEncryptSalt"])

        form = {
            "username": self.config.username,
            "password": encrypted,
            "_eventId": "submit",
            "cllt": params["cllt"],
            "dllt": params["dllt"],
            "lt": params["lt"],
            "execution": params["execution"],
            "_encoded": "false",
        }
        if captcha:
            form["captcha"] = captcha

        url = "%s/login" % self.config.auth_base
        resp = self._request(
            "POST",
            url,
            params={"service": service},
            data=form,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": resp_referer(url, service),
                "Origin": self.config.auth_base.rsplit("/authserver", 1)[0],
            },
        )
        resp.encoding = resp.apparent_encoding or "utf-8"

        if not self._login_failed(resp):
            logger.info("登录成功，最终地址：%s", resp.url)
            return self.session

        if self.config.debug_save_raw:
            dump_path = self.config.log_dir / "debug_login_failed.html"
            try:
                dump_path.write_text(resp.text, encoding="utf-8")
                logger.info("登录失败的响应已保存到 %s", dump_path)
            except OSError:
                pass

        message = self._extract_error(resp.text, resp.url)
        if "验证码" in message or "动态码" in message:
            raise CaptchaRequired(message)
        raise AuthError(message)

    def login(self):
        """一步完成登录（适用于不需要图形验证码的情况）。

        :raises CaptchaRequired: 服务端要求图形验证码
        :raises AuthError: 登录失败
        """
        self.prepare()
        return self.submit()

    def login_with_captcha(self, solver, max_attempts=3):
        """自动处理图形验证码的登录。

        策略：

        1. 先尝试**不带验证码**直接登录（多数情况其实不需要验证码）；
        2. 若服务端要求验证码，则下载验证码图片交 OCR 识别后重试；
        3. 识别错误时最多重试 ``max_attempts`` 次。
           每次重试都会重新抓登录页——``pwdEncryptSalt`` 与验证码都是
           一次性的，重用旧参数必定失败。

        :param solver: :class:`snut.captcha.CaptchaSolver` 实例
        :raises CaptchaRequired: 需要验证码但 OCR 不可用或连续识别失败
        :raises AuthError: 其他登录失败
        """
        # 第一轮：直接登录，看服务端是否放行
        self.prepare()
        try:
            self.submit()
            self.save_session()
            return self.session
        except CaptchaRequired:
            logger.info("服务端要求图形验证码，转入自动识别流程")

        if not solver.available:
            raise CaptchaRequired(
                "服务端要求图形验证码，但自动识别不可用（%s）。"
                "请先运行 scripts/captcha_login.py 人工登录一次。"
                % solver.unavailable_reason
            )

        last_error = "未知"
        for attempt in range(1, max_attempts + 1):
            self.prepare()
            image = self.fetch_captcha()
            code = solver.solve(image)
            if not code:
                last_error = "识别结果为空"
                logger.warning("第 %d 次：验证码识别为空", attempt)
                continue

            try:
                self.submit(captcha=code)
            except CaptchaRequired as exc:
                last_error = str(exc)
                logger.warning(
                    "第 %d 次：验证码 %r 未通过，重新获取后再试", attempt, code
                )
                continue

            self.save_session()
            logger.info("验证码登录成功（第 %d 次尝试，识别结果 %r）", attempt, code)
            return self.session

        raise CaptchaRequired(
            "验证码自动识别连续失败 %d 次（最后一次：%s）。"
            "可运行 scripts/captcha_login.py 人工登录。"
            % (max_attempts, last_error)
        )

    # ------------------------------------------------------------------
    # 会话持久化
    # ------------------------------------------------------------------

    @property
    def _session_file(self):
        return self.config.session_dir / "cookies.json"

    def save_session(self):
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
            for c in self.session.cookies
        ]
        data = {
            "saved_at": time.time(),
            "host": urlparse(self.config.eams_base).hostname,
            "cookies": cookies,
        }
        try:
            self._session_file.parent.mkdir(parents=True, exist_ok=True)
            self._session_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            names = [c["name"] for c in cookies]
            logger.debug("会话已保存（%d 个 Cookie：%s）", len(cookies), names)
        except OSError as exc:
            logger.warning("保存会话失败：%s", exc)

    def load_session(self):
        """从文件恢复会话，返回是否成功读到可用数据。"""
        if not self._session_file.exists():
            return False
        try:
            data = json.loads(self._session_file.read_text(encoding="utf-8"))
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
                self.session.cookies.set(name, value)
                count += 1
        else:
            for item in raw:
                try:
                    kwargs = {}
                    if item.get("domain"):
                        kwargs["domain"] = item["domain"]
                    if item.get("path"):
                        kwargs["path"] = item["path"]
                    self.session.cookies.set(item["name"], item["value"], **kwargs)
                    count += 1
                except (KeyError, TypeError):
                    continue

        logger.debug("已从文件恢复 %d 个 Cookie", count)
        return count > 0

    def silent_sso_login(self):
        """尝试用已有的 CAS 票据静默登录（不需要密码，也不需要验证码）。

        原理：CAS 的 ``CASTGC`` Cookie 代表统一认证服务端的登录状态。
        只要它仍在有效期内，访问 ``authserver/login?service=...`` 会被
        **直接 302 并签发新的 ticket**，全程无需重新认证。

        这正是"EAMS 会话过期但不必重新输密码"的关键路径，
        实测中它能让程序在大多数情况下完全绕开图形验证码。

        :return: 是否成功换到 EAMS 会话
        """
        service = self.config.sso_service_url
        url = "%s/login" % self.config.auth_base
        try:
            resp = self._request(
                "GET", url, params={"service": service}, allow_redirects=True
            )
        except requests.RequestException as exc:
            logger.debug("静默登录请求异常：%s", exc)
            return False

        final_host = (urlparse(resp.url).hostname or "").lower()
        eams_host = (urlparse(self.config.eams_base).hostname or "").lower()
        if eams_host and final_host == eams_host:
            logger.info("静默登录成功：CAS 票据仍有效，已换到新的 EAMS 会话")
            return True

        logger.debug("静默登录未成功，最终停留在：%s", resp.url)
        return False

    def ensure_login(self, force=False, solver=None):
        """确保处于已登录状态。

        依次尝试三条路径，代价由低到高：

        1. **直接复用**已保存的 EAMS 会话（零成本）；
        2. **静默 SSO**——EAMS 会话过期但 CAS 票据（CASTGC）仍有效时，
           免密换一个新会话。这条路能绕开图形验证码，应尽量走；
        3. **完整的账号密码登录**（可能触发图形验证码）。

        :param force: 为 True 时跳过前两条，强制重新登录
        :param solver: 传入 :class:`snut.captcha.CaptchaSolver` 时，
                       遇到验证码会自动识别；为 None 则遇到验证码直接报错
        :raises CaptchaRequired: 需要图形验证码且无法自动解决
        :raises AuthError: 登录失败
        """
        if not force:
            if self.load_session():
                if self.is_logged_in():
                    logger.info("复用已保存的会话，无需重新登录")
                    return self.session

                logger.debug("EAMS 会话已过期，尝试用 CAS 票据静默登录")
                if self.silent_sso_login() and self.is_logged_in():
                    self.save_session()
                    return self.session
                logger.debug("静默登录未能恢复会话")

        logger.info("需要完整的账号密码登录")
        if solver is not None:
            self.login_with_captcha(solver)
        else:
            self.login()
            self.save_session()
        return self.session

    # ------------------------------------------------------------------
    # 结果判定
    # ------------------------------------------------------------------

    def _login_failed(self, resp):
        """判断登录是否失败。

        成功时会被重定向到 EAMS 域名下；失败时停在 authserver 的登录页。

        注意：必须比对 **主机名**，不能只看 URL 字符串。失败时的地址形如
        ``authserver.../login?service=...%2Feams%2F...``，其中 service 参数
        里也含有 "eams" 字样，用 ``"eams" in url`` 判断会永远误判为成功。
        """
        final_host = (urlparse(resp.url).hostname or "").lower()
        eams_host = (urlparse(self.config.eams_base).hostname or "").lower()
        if eams_host and final_host == eams_host:
            return False
        return True

    @staticmethod
    def _extract_error(html, final_url=""):
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

    # ------------------------------------------------------------------
    # 会话校验
    # ------------------------------------------------------------------

    def is_logged_in(self):
        """检查当前会话是否仍有效（能否访问需要登录的页面）。"""
        url = "%s/courseTableForStd.action" % self.config.eams_base
        try:
            resp = self._request("GET", url, allow_redirects=False)
        except requests.RequestException as exc:
            logger.debug("会话校验请求异常：%s", exc)
            return False
        # 未登录时会被 302 回 CAS
        return resp.status_code == 200


def resp_referer(url, service):
    """构造 Referer（金智认证有时会校验）。"""
    return "%s?service=%s" % (url, requests.utils.quote(service, safe=""))
