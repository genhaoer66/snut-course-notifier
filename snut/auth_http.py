"""HTTP session configuration, throttling and SSL fallback."""

import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("snut.auth")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


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


class HTTPClient(object):
    """Shared authenticated-client transport."""

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

