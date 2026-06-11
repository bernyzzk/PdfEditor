from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


PRESETS = {
    "Approuvé": "#16803c",
    "Confidentiel": "#c62828",
    "Brouillon": "#64748b",
    "Reçu": "#2563eb",
    "Validé": "#16803c",
}


@dataclass
class StampConfig:
    text: str = "Approuvé"
    include_date: bool = False
    image_path: str = ""
    color: str = "#16803c"


def render_stamp(config: StampConfig, size: tuple[int, int] = (1200, 360)) -> bytes:
    width, height = size
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    color = QColor(config.color)
    rgb = (color.red(), color.green(), color.blue(), 255)
    border = max(10, height // 24)
    radius = height // 8
    draw.rounded_rectangle((border, border, width - border, height - border), radius, outline=rgb, width=border)

    logo_width = 0
    if config.image_path and Path(config.image_path).exists():
        with Image.open(config.image_path) as source:
            logo = source.convert("RGBA")
            logo.thumbnail((height * 2, height - border * 5), Image.Resampling.LANCZOS)
            logo_width = logo.width + border * 3
            image.alpha_composite(logo, (border * 3, (height - logo.height) // 2))

    text = config.text.strip() or "Tampon"
    if config.include_date:
        text += f"\n{date.today():%d/%m/%Y}"
    font_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
    font_size = height // (4 if "\n" in text else 3)
    font = ImageFont.truetype(str(font_path), font_size) if font_path.exists() else ImageFont.load_default()
    text_box = draw.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center", stroke_width=1)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    area_left = logo_width + border * 2
    x = area_left + max(0, (width - area_left - text_width) // 2)
    y = max(border * 2, (height - text_height) // 2 - text_box[1])
    draw.multiline_text((x, y), text, font=font, fill=rgb, spacing=8, align="center", stroke_width=1, stroke_fill=rgb)

    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class StampDialog(QDialog):
    def __init__(self, parent=None, initial: StampConfig | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Créer un tampon")
        self.setMinimumWidth(500)
        self.config = initial or StampConfig()
        self._color = QColor(self.config.color)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItems([*PRESETS, "Personnalisé"])
        self.preset.setCurrentText(self.config.text if self.config.text in PRESETS else "Personnalisé")
        form.addRow("Modèle", self.preset)

        self.text = QLineEdit(self.config.text)
        self.text.setPlaceholderText("Texte du tampon")
        form.addRow("Texte", self.text)

        self.include_date = QCheckBox("Ajouter automatiquement la date du jour")
        self.include_date.setChecked(self.config.include_date)
        form.addRow("Date", self.include_date)

        image_row = QHBoxLayout()
        self.image_path = QLineEdit(self.config.image_path)
        self.image_path.setPlaceholderText("Logo ou image transparente facultative")
        browse = QPushButton("Parcourir")
        browse.clicked.connect(self._browse_image)
        image_row.addWidget(self.image_path)
        image_row.addWidget(browse)
        form.addRow("Image / logo", image_row)

        self.color_button = QPushButton("Choisir la couleur")
        self.color_button.clicked.connect(self._choose_color)
        form.addRow("Couleur", self.color_button)
        layout.addLayout(form)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(155)
        self.preview.setStyleSheet("background:#f3f5f8; border:1px solid #d5dae1; border-radius:8px;")
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.preset.currentTextChanged.connect(self._preset_changed)
        self.text.textChanged.connect(self._refresh_preview)
        self.include_date.toggled.connect(self._refresh_preview)
        self.image_path.textChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def stamp_data(self) -> bytes:
        self.config = StampConfig(
            self.text.text().strip() or "Tampon",
            self.include_date.isChecked(),
            self.image_path.text().strip(),
            self._color.name(),
        )
        return render_stamp(self.config)

    def _preset_changed(self, value: str) -> None:
        if value in PRESETS:
            self.text.setText(value)
            self._color = QColor(PRESETS[value])
        self._refresh_preview()

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choisir un logo", "", "Images (*.png *.webp *.jpg *.jpeg *.bmp)")
        if path:
            self.image_path.setText(path)
            self.preset.setCurrentText("Personnalisé")

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Couleur du tampon")
        if color.isValid():
            self._color = color
            self.preset.setCurrentText("Personnalisé")
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        self.color_button.setStyleSheet(f"color:{self._color.name()}; font-weight:600;")
        data = render_stamp(
            StampConfig(self.text.text(), self.include_date.isChecked(), self.image_path.text(), self._color.name()),
            (800, 240),
        )
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        self.preview.setPixmap(pixmap.scaled(440, 135, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
