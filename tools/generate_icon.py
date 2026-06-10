from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "pdfeditor-icon.svg"
ICO = ROOT / "assets" / "pdfeditor.ico"
PNG = ROOT / "assets" / "pdfeditor-512.png"


def render(size: int) -> Image.Image:
    renderer = QSvgRenderer(str(SVG))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return Image.open(__import__("io").BytesIO(bytes(data))).convert("RGBA")


QGuiApplication.instance() or QGuiApplication([])
large = render(512)
large.save(PNG)
large.save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
