# -*- coding: utf-8 -*-
"""把 web/ 下的品牌矢量图导出成书签栏 / 分享卡片真正会用的位图。

    python scripts/make_brand_assets.py

产物（都在 web/ 下，**要和 svg 一起上传**）：

    favicon.ico           16/32/48 三尺寸，书签栏与标签页
    apple-touch-icon.png  180×180，iOS「添加到主屏幕」
    og-cover.png          1200×630，X / 微信 / QQ 分享卡片

服务器上没有图形工具链，所以 PNG 一律在本地生成后上传；上传脚本是
scripts/upload_frontend.py，它已经把这三个文件列进去了。

依赖 Pillow（不在 requirements.txt 里，只有画图时要用）：

    python -m pip install pillow

为什么不用 cairosvg / Inkscape 渲染 SVG：省一个重依赖；而且 16px 的图标
需要手工调线宽（见 _whale），渲染器不会替我们做这些像素级取舍。
"""

import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    raise SystemExit("缺少 Pillow：python -m pip install pillow")

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

# 与 web/logo.svg、style.css 里 .brand-mark 的渐变一致
BLUE_TOP = (0x20, 0x31, 0x70)      # #203170
BLUE_BOTTOM = (0x4A, 0x63, 0xC0)   # #4a63c0
OG_TOP = (0x1B, 0x2A, 0x63)
WHITE = (255, 255, 255)

FAVICON_SIZES = (16, 32, 48)
APPLE_SIZE = 180
OG_SIZE = (1200, 630)


def _gradient(w, h, start, end):
    """左上→右下渐变。渐变方向按画布宽高比归一化（和 SVG 的
    objectBoundingBox 单位一致），所以宽图和方图的斜角看起来一样。"""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = ((x / w) + (y / h)) / 2
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(start, end))
    return img


def _superellipse(cx, cy, w, h, n=2.5, steps=180):
    """超椭圆采样点。鲸鱼背宽腹收，圆和椭圆都不像；超椭圆一个指数就能调胖瘦，
    省掉为一张图标引入贝塞尔求值器。"""
    pts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        c, s = math.cos(a), math.sin(a)
        pts.append((
            cx + w / 2 * (abs(c) ** (2 / n)) * (1 if c >= 0 else -1),
            cy + h / 2 * (abs(s) ** (2 / n)) * (1 if s >= 0 else -1),
        ))
    return pts


def _whale(big, ss):
    """鲸鱼（背脊 + 水线）的白色掩膜，画在 big×big 画布上。

    坐标按 logo.svg 的 64×64 viewBox 等比换算：身体 x∈[14,50] y∈[17,46]，
    水线在 y≈41。16px 下线条会糊进身体，所以小尺寸时水线加粗、不透明度
    从 140/255（≈.55）提到 165/255。
    """
    k = big / 64.0
    img = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(img)
    d.polygon(_superellipse(32 * k, 31 * k, 36 * k, 27 * k), fill=242)
    lw = max(1.0, (3.4 if ss >= 32 else 4.2) * k)
    d.line([(20 * k, 41 * k), (44 * k, 41 * k)], fill=160, width=int(round(lw)))
    return img


def _icon(size, *, rounded=True, flat=False):
    """一张图标。flat=True：不圆角不要高光，且整块不透明（iOS 主屏用，
    iOS 会自己裁圆角，留透明反而会填成黑块）。"""
    ss = 8 if size <= 48 else 4
    big = size * ss

    canvas = _gradient(big, big, BLUE_TOP, BLUE_BOTTOM).convert("RGBA")
    if rounded and not flat:
        sheen = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(sheen).rectangle((0, 0, big, int(big * .55)),
                                        fill=(255, 255, 255, 56))
        canvas = Image.alpha_composite(canvas, sheen)

    if not rounded or flat:
        alpha = Image.new("L", (big, big), 255)
    else:
        alpha = Image.new("L", (big, big), 0)
        ImageDraw.Draw(alpha).rounded_rectangle(
            (0, 0, big - 1, big - 1), radius=round(big * 0.22), fill=255)

    canvas.putalpha(alpha)
    white = Image.new("RGBA", (big, big), WHITE + (0,))
    white.putalpha(ImageChops.multiply(_whale(big, ss), alpha))
    return Image.alpha_composite(canvas, white).resize((size, size), Image.LANCZOS)


# ---- 字体：按平台挑第一个装了的 ----
CJK_BOLD = ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]
MONO = ["C:/Windows/Fonts/consola.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]


def _font(paths, size):
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _bold(draw, xy, text, font, fill, stroke=1):
    """系统中文字体没有 Heavy 字重，同色外描边一圈就是「更粗一档」。
    比手工制字模稳，任何字体都适用。"""
    draw.text(xy, text, font=font, fill=fill, anchor="ls",
              stroke_width=stroke, stroke_fill=fill)


def build_favicon():
    out = WEB / "favicon.ico"
    _icon(FAVICON_SIZES[-1]).save(out, format="ICO", sizes=[(s, s) for s in FAVICON_SIZES])
    return out


def build_apple_touch():
    out = WEB / "apple-touch-icon.png"
    _icon(APPLE_SIZE, flat=True).save(out, format="PNG", optimize=True)
    return out


def build_og_cover():
    out = WEB / "og-cover.png"
    w, h = OG_SIZE
    img = _gradient(w, h, OG_TOP, BLUE_BOTTOM).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")

    # 课表网格：淡到只在深底上隐约可见，缩成缩略图就消失
    for y in (210, 330, 450):
        d.line([(84, y), (1116, y)], fill=(255, 255, 255, 18), width=1)
    for x in (180, 460, 740, 1020):
        d.line([(x, 84), (x, 546)], fill=(255, 255, 255, 18), width=1)
    # 时间轴折线：从网格里穿出来，末端在图标右侧收成圆点
    d.line([(84, 420), (420, 420), (560, 300)], fill=(255, 255, 255, 56), width=2)
    d.ellipse([(553, 293), (567, 307)], fill=(255, 255, 255, 140))

    # 左上：图标。底片用实色深蓝，免得和背景渐变撞成一片
    chip = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    ImageDraw.Draw(chip).rounded_rectangle((0, 0, 119, 119), radius=26, fill=OG_TOP + (255,))
    chip = Image.alpha_composite(chip, _icon(120).resize((120, 120), Image.LANCZOS))
    img.alpha_composite(chip, (84, 96))

    f_eyebrow = _font(CJK_BOLD, 28)
    f_title = _font(CJK_BOLD, 76)
    f_sub = _font(CJK_BOLD, 28)
    f_mono = _font(MONO, 24)
    f_slogan = _font(CJK_BOLD, 42)
    f_slogan2 = _font(CJK_BOLD, 25)

    d.text((238, 142), "SNUT · COURSE SHEET", font=f_eyebrow,
           fill=(255, 255, 255, 184), anchor="ls")
    _bold(d, (236, 222), "我的课表", f_title, WHITE)
    d.text((238, 274), "陕西理工大学 · 课表自动推送", font=f_sub,
           fill=(255, 255, 255, 200), anchor="ls")
    d.line([(238, 296), (760, 296)], fill=(255, 255, 255, 46), width=1)
    d.text((238, 332), "060131.xyz", font=f_mono, fill=(255, 255, 255, 153), anchor="ls")

    _bold(d, (84, 500), "每天 07:00 自动推送课表", f_slogan, WHITE)
    d.text((84, 552), "一次抓取，两个产物：手机上收邮件，网页上随时看今日与整周",
           font=f_slogan2, fill=(255, 255, 255, 184), anchor="ls")

    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out


def main():
    if not WEB.is_dir():
        raise SystemExit("找不到 web/：%s" % WEB)
    for fn in (build_favicon, build_apple_touch, build_og_cover):
        path = fn()
        print("%-28s %8d bytes" % (path.relative_to(ROOT), path.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
