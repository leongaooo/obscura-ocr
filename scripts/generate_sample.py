"""Generate an obviously synthetic image for real local OCR acceptance."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
target = root / "examples" / "synthetic-invoice.png"
image = Image.new("RGB", (1600, 1000), "white")
draw = ImageDraw.Draw(image)
# Use a locally available font; no company files or downloaded assets are used.
font_path = Path("C:/Windows/Fonts/msyh.ttc")
font = (
    ImageFont.truetype(str(font_path), 42)
    if font_path.exists()
    else ImageFont.load_default(size=36)
)
lines = [
    "SYNTHETIC OCR TEST / NOT A VALID INVOICE",
    "电子发票（增值税普通发票）",
    "发票号码：00000000123456789012",
    "开票日期：2026年01月15日",
    "购买方名称：示例购买方有限公司",
    "销售方名称：示例销售方有限公司",
    "价税合计：￥123.45",
    "仅供软件测试使用 / SYNTHETIC DATA",
]
for index, text in enumerate(lines):
    draw.text((70, 60 + index * 105), text, fill="black", font=font)
image.save(target)
print(target)
