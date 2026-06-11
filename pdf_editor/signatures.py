from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)


@dataclass
class SignatureModel:
    name: str
    path: str
    opacity: int = 100


def render_signature(model: SignatureModel) -> bytes:
    with Image.open(model.path) as source:
        image = source.convert("RGBA")
        alpha = image.getchannel("A").point(lambda value: round(value * model.opacity / 100))
        image.putalpha(alpha)
        output = BytesIO()
        image.save(output, "PNG")
        return output.getvalue()


class SignatureDialog(QDialog):
    SETTINGS_KEY = "signature_models"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modèles de signature")
        self.setMinimumSize(570, 430)
        self.models = self._load_models()

        layout = QVBoxLayout(self)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMinimumWidth(190)
        body.addWidget(self.list)

        right = QVBoxLayout()
        self.preview = QLabel("Ajoutez un modèle de signature")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(320, 230)
        self.preview.setStyleSheet("background:#f3f5f8; border:1px solid #d5dae1; border-radius:8px;")
        right.addWidget(self.preview)
        self.opacity_label = QLabel("Transparence : 0 %")
        right.addWidget(self.opacity_label)
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 90)
        self.opacity.setValue(0)
        right.addWidget(self.opacity)
        body.addLayout(right)
        layout.addLayout(body)

        actions = QHBoxLayout()
        add = QPushButton("Ajouter un modèle")
        remove = QPushButton("Supprimer")
        add.clicked.connect(self._add_model)
        remove.clicked.connect(self._remove_model)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch()
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.list.currentRowChanged.connect(self._select_model)
        self.opacity.valueChanged.connect(self._opacity_changed)
        self._refresh_list()

    def selected_model(self) -> SignatureModel | None:
        row = self.list.currentRow()
        return self.models[row] if 0 <= row < len(self.models) else None

    def signature_data(self) -> bytes:
        model = self.selected_model()
        return render_signature(model) if model else b""

    def _load_models(self) -> list[SignatureModel]:
        raw = QSettings().value(self.SETTINGS_KEY, "[]")
        try:
            return [SignatureModel(**item) for item in json.loads(raw) if Path(item["path"]).exists()]
        except (TypeError, ValueError, KeyError):
            return []

    def _save_models(self) -> None:
        QSettings().setValue(self.SETTINGS_KEY, json.dumps([asdict(model) for model in self.models]))

    def _refresh_list(self) -> None:
        current = min(max(self.list.currentRow(), 0), max(0, len(self.models) - 1))
        self.list.clear()
        self.list.addItems([model.name for model in self.models])
        if self.models:
            self.list.setCurrentRow(current)
        else:
            self.preview.clear()

    def _add_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Ajouter une signature", "", "Images (*.png *.webp *.jpg *.jpeg *.bmp)")
        if path:
            name = Path(path).stem
            self.models.append(SignatureModel(name, path))
            self._refresh_list()
            self.list.setCurrentRow(len(self.models) - 1)

    def _remove_model(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self.models):
            self.models.pop(row)
            self._refresh_list()

    def _select_model(self, row: int) -> None:
        if not 0 <= row < len(self.models):
            return
        model = self.models[row]
        self.opacity.blockSignals(True)
        self.opacity.setValue(100 - model.opacity)
        self.opacity.blockSignals(False)
        self._update_preview()

    def _opacity_changed(self, value: int) -> None:
        model = self.selected_model()
        if model:
            model.opacity = 100 - value
            self._update_preview()

    def _update_preview(self) -> None:
        model = self.selected_model()
        if not model:
            return
        self.opacity_label.setText(f"Transparence : {100 - model.opacity} %")
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(render_signature(model))
            self.preview.setPixmap(pixmap.scaled(300, 205, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except OSError:
            self.preview.setText("Signature illisible")

    def _accept(self) -> None:
        if not self.selected_model():
            QMessageBox.information(self, "Signature", "Ajoutez ou sélectionnez un modèle de signature.")
            return
        self._save_models()
        self.accept()
