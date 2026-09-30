# -*- coding: utf-8 -*-
"""图形验证码识别。

学校统一认证在触发风控时会要求输入 4 位图形验证码。本模块用
`ddddocr <https://github.com/sml2h3/ddddocr>`_ 做自动识别——
它是目前中文验证码识别效果最好的开源方案。

若未安装 ddddocr，:meth:`CaptchaSolver.solve` 会返回 ``None``，
调用方应据此降级为人工输入（见 ``scripts/captcha_login.py``）。
"""

import logging

logger = logging.getLogger(__name__)


class CaptchaSolver(object):
    """验证码识别器（懒加载，首次识别时才载入模型）。"""

    def __init__(self):
        self._ocr = None
        self._unavailable_reason = None

    @property
    def available(self):
        """识别器是否可用（仅表示库是否装上，不代表识别一定成功）。"""
        self._ensure_loaded()
        return self._unavailable_reason is None

    @property
    def unavailable_reason(self):
        """不可用的原因，供日志与提示使用。"""
        self._ensure_loaded()
        return self._unavailable_reason

    def _ensure_loaded(self):
        if self._ocr is not None:
            return
        try:
            import ddddocr
        except ImportError:
            self._unavailable_reason = (
                "未安装 ddddocr，无法自动识别验证码。"
                "安装命令：python -m pip install ddddocr"
            )
            logger.warning(self._unavailable_reason)
            return

        # show_ad=False 关掉库自带的广告输出
        self._ocr = ddddocr.DdddOcr(show_ad=False)
        logger.debug("ddddocr 已就绪")

    def solve(self, image_bytes):
        """识别验证码。

        :param image_bytes: 验证码图片的原始字节
        :return: 识别出的字符串；不可用时返回 ``None``
        """
        self._ensure_loaded()
        if self._ocr is None:
            return None

        try:
            result = self._ocr.classification(image_bytes)
        except Exception as exc:
            logger.warning("验证码识别异常：%s", exc)
            return None

        if not result:
            return None

        result = result.strip()
        logger.info("验证码识别结果：%r", result)
        return result
