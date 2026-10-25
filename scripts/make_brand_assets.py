# -*- coding: utf-8 -*-
"""生成课格位图资源；只依赖已安装的 Pillow，不读取配置或课表。"""
import io
import math
import struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
TEAL = '#0D7268'
FAVICON_SIZES = (16, 32, 48)
APPLE_SIZE = 180
OG_SIZE = (1200, 630)


def _rounded(draw, bounds, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = bounds
    points = []
    for cx, cy, start in ((x1-radius, y0+radius, -90),
                          (x1-radius, y1-radius, 0),
                          (x0+radius, y1-radius, 90),
                          (x0+radius, y0+radius, 180)):
        for angle in range(start, start+91, 5):
            rad = math.radians(angle)
            points.append((cx+radius*math.cos(rad), cy+radius*math.sin(rad)))
    draw.polygon(points, fill=fill)
    if outline:
        draw.line(points + [points[0]], fill=outline, width=width)


def _icon(size, flat=False):
    scale = 8 if size <= 48 else 4
    big = size * scale
    image = Image.new('RGBA', (big, big), TEAL if flat else (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _rounded(draw, (0, 0, big - 1, big - 1), 14 * big / 64, TEAL)
    # iOS 图形整体占画布 70%；16px 层仅保留右上实心格。
    k = big / 64 * (.70 if flat else 1)
    offset = (big - 64 * k) / 2
    for x, y in ((9, 9), (35, 9), (9, 35), (35, 35)):
        if size == 16 and (x, y) != (35, 9):
            continue
        bounds = (offset + x*k, offset + y*k, offset + (x+20)*k, offset + (y+20)*k)
        if (x, y) == (35, 9):
            _rounded(draw, bounds, 4*k, 'white')
        else:
            # 与 SVG 居中描边一致，轮廓向外扩半个线宽。
            half = 1.5*k
            bounds = (bounds[0]-half, bounds[1]-half, bounds[2]+half, bounds[3]+half)
            _rounded(draw, bounds, 5.5*k, '#92BFB9')
            inside = (bounds[0]+3*k, bounds[1]+3*k, bounds[2]-3*k, bounds[3]-3*k)
            _rounded(draw, inside, 2.5*k, TEAL)
    return image.resize((size, size), Image.LANCZOS)


def build_favicon():
    blobs = []
    for size in FAVICON_SIZES:
        buffer = io.BytesIO()
        _icon(size).save(buffer, format='PNG')
        blobs.append(buffer.getvalue())
    offset = 6 + 16 * len(blobs)
    entries = []
    for size, blob in zip(FAVICON_SIZES, blobs):
        entries.append(struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(blob), offset))
        offset += len(blob)
    out = WEB / 'favicon.ico'
    out.write_bytes(struct.pack('<HHH', 0, 1, len(blobs)) + b''.join(entries) + b''.join(blobs))
    return out


def build_apple_touch():
    out = WEB / 'apple-touch-icon.png'
    _icon(APPLE_SIZE, flat=True).convert('RGB').save(out)
    return out


def build_og_cover():
    out = WEB / 'og-cover.png'
    image = Image.new('RGB', OG_SIZE, '#F5F6F4')
    image.paste(_icon(160), (100, 235), _icon(160))
    draw = ImageDraw.Draw(image)
    font_path = next((str(p) for p in [Path('C:/Windows/Fonts/msyh.ttc'), Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')] if p.exists()), None)
    if font_path is None:
        raise SystemExit('缺少中文字体，不能生成分享图')
    for text, size, position, color in [
        ('课格', 72, (320, 190), '#161A1A'),
        ('陕西理工大学 · 班级课表', 32, (320, 300), '#475150'),
        ('每天 07:00 更新 · 今日课程与整周课表', 28, (320, 370), '#636D6B')]:
        draw.text(position, text, font=ImageFont.truetype(font_path, size), fill=color)
    image.save(out, optimize=True)
    return out


def main():
    for build in (build_favicon, build_apple_touch, build_og_cover):
        print(build().relative_to(ROOT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
