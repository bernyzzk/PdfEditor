from __future__ import annotations

import fitz
from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFontComboBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .canvas import PdfCanvas, Tool
from .model import PdfDocument, PdfObject
from .stamps import StampConfig, StampDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.model = PdfDocument()
        self.canvas = PdfCanvas(self.model)
        self.thumbnails = QListWidget()
        self.signature_path = ""
        self.stamp_config = StampConfig()
        self.stamp_data = b""
        self.text_color = QColor("#111827")
        self._loading_thumbnails = False
        self._build_ui()
        self._connect()
        self._update_title()

    def _build_ui(self) -> None:
        self.resize(1480, 940)
        self.setMinimumSize(1050, 720)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setStyleSheet("QScrollArea { background: #e7ebf0; border: none; }")
        self.setCentralWidget(self.scroll)

        self.thumbnails.setIconSize(QSize(132, 180))
        self.thumbnails.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.thumbnails.setDefaultDropAction(Qt.DropAction.MoveAction)
        pages = QDockWidget("Pages", self)
        pages.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        pages.setWidget(self.thumbnails)
        pages.setMinimumWidth(185)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, pages)

        top = QToolBar("Outils principaux")
        top.setMovable(False)
        top.setIconSize(QSize(24, 24))
        top.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(top)

        top.addAction(self._action("Ouvrir", "Ctrl+O", self.open_pdf, QStyle.StandardPixmap.SP_DialogOpenButton))
        top.addAction(self._action("Exporter", "Ctrl+S", self.save_pdf, QStyle.StandardPixmap.SP_DialogSaveButton))
        top.addSeparator()
        top.addAction(self._action("Annuler", "Ctrl+Z", self.model.undo, QStyle.StandardPixmap.SP_ArrowBack))
        top.addAction(self._action("Rétablir", "Ctrl+Y", self.model.redo, QStyle.StandardPixmap.SP_ArrowForward))
        top.addSeparator()

        self.tool_actions: dict[Tool, QAction] = {}
        tool_specs = [
            (Tool.PAN, "Lecture", "Esc", "hand"),
            (Tool.SELECT, "Sélectionner un texte ou une image", "V", "select"),
            (Tool.TEXT, "Ajouter du texte directement", "T", "text"),
            (Tool.IMAGE, "Ajouter une image", "I", "image"),
            (Tool.LINK, "Ajouter un lien", "L", "link"),
            (Tool.DRAW, "Crayon", "D", "draw"),
            (Tool.HIGHLIGHT, "Surligner", "H", "highlight"),
            (Tool.ERASER, "Gomme d'objet", "E", "eraser"),
            (Tool.SIGNATURE, "Signature", "G", "signature"),
            (Tool.STAMP, "Tampon", "M", "stamp"),
        ]
        for tool, tooltip, shortcut, icon_name in tool_specs:
            action = self._action(tooltip, shortcut, lambda checked=False, t=tool: self.set_tool(t), icon=self._draw_icon(icon_name))
            action.setCheckable(True)
            top.addAction(action)
            self.tool_actions[tool] = action
        self.tool_actions[Tool.PAN].setChecked(True)
        top.addSeparator()
        top.addAction(self._action("Copier l'objet sélectionné", "Ctrl+C", self.canvas.copy_selected, icon=self._draw_icon("copy")))
        top.addAction(self._action("Coller l'objet", "Ctrl+V", self.canvas.paste_copied, icon=self._draw_icon("paste")))
        top.addAction(self._action("Valider le texte (Ctrl+Entrée)", "Ctrl+Return", self.canvas.commit_editor, icon=self._draw_icon("check")))
        self.replace_image_action = self._action("Remplacer l'image sélectionnée", "", self.replace_selected_image, icon=self._draw_icon("replace"))
        self.replace_image_action.setEnabled(False)
        top.addAction(self.replace_image_action)
        top.addAction(self._action("Effacer l'objet sélectionné", "Delete", self.erase_selected, icon=self._draw_icon("trash")))
        top.addSeparator()
        top.addAction(self._action("Rotation de la page", "Ctrl+R", self.rotate_page, icon=self._draw_icon("rotate")))
        top.addAction(self._action("Supprimer la page", "Ctrl+Delete", self.delete_page, QStyle.StandardPixmap.SP_TrashIcon))
        top.addAction(self._action("Fusionner des PDF", "", self.merge_pdfs, icon=self._draw_icon("merge")))
        top.addAction(self._action("Extraire la page actuelle", "", self.extract_page, icon=self._draw_icon("split")))
        top.addAction(self._action("Rechercher du texte", "Ctrl+F", self.search_text, QStyle.StandardPixmap.SP_FileDialogContentsView))
        top.addAction(self._action("Masquer définitivement un terme", "", self.redact_text, icon=self._draw_icon("redact")))
        top.addAction(self._action("OCR local du document", "", self.run_ocr, icon=self._draw_icon("ocr")))
        top.addAction(self._action("Convertir vers Word", "", self.export_word, icon=self._draw_icon("word")))
        top.addAction(self._action("Convertir vers Excel", "", self.export_excel, icon=self._draw_icon("excel")))
        top.addAction(self._action("Convertir vers PowerPoint", "", self.export_powerpoint, icon=self._draw_icon("powerpoint")))
        top.addSeparator()
        top.addAction(self._action("Zoom arrière", "Ctrl+-", lambda: self.change_zoom(-0.15), QStyle.StandardPixmap.SP_ArrowDown))
        top.addAction(self._action("Zoom avant", "Ctrl++", lambda: self.change_zoom(0.15), QStyle.StandardPixmap.SP_ArrowUp))
        self.zoom_label = QLabel(" 100% ")
        top.addWidget(self.zoom_label)

        formatting = QToolBar("Texte")
        formatting.setMovable(False)
        self.addToolBarBreak()
        self.addToolBar(formatting)
        formatting.addWidget(QLabel(" Police  "))
        self.font_combo = QFontComboBox()
        self.font_combo.setMinimumWidth(220)
        formatting.addWidget(self.font_combo)
        formatting.addWidget(QLabel("  Taille  "))
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(5, 144)
        self.font_size.setValue(12)
        self.font_size.setSuffix(" pt")
        formatting.addWidget(self.font_size)
        self.color_button = QPushButton()
        self.color_button.setToolTip("Couleur du texte")
        self.color_button.setFixedSize(34, 26)
        formatting.addWidget(self.color_button)
        self.selection_label = QLabel("  Aucun objet sélectionné")
        formatting.addSeparator()
        formatting.addWidget(self.selection_label)
        self._update_color_button()

        inspector = QDockWidget("Mise en page", self)
        inspector_body = QWidget()
        inspector_layout = QVBoxLayout(inspector_body)
        inspector_hint = QLabel("Sélectionnez un texte, une image ou un graphique pour le déplacer et le redimensionner.")
        inspector_hint.setWordWrap(True)
        inspector_layout.addWidget(inspector_hint)
        form = QFormLayout()
        self.geometry_fields: dict[str, QDoubleSpinBox] = {}
        for key, label in (("x", "Position X"), ("y", "Position Y"), ("w", "Largeur"), ("h", "Hauteur")):
            field = QDoubleSpinBox()
            field.setRange(-10000, 10000)
            field.setDecimals(1)
            field.setSuffix(" pt")
            field.setEnabled(False)
            form.addRow(label, field)
            self.geometry_fields[key] = field
        inspector_layout.addLayout(form)
        self.apply_geometry_button = QPushButton("Appliquer la mise en page")
        self.apply_geometry_button.setEnabled(False)
        self.apply_geometry_button.clicked.connect(self.apply_geometry)
        inspector_layout.addWidget(self.apply_geometry_button)
        inspector_layout.addStretch()
        inspector.setWidget(inspector_body)
        inspector.setMinimumWidth(225)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, inspector)

        nav = QToolBar("Navigation")
        nav.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, nav)
        nav.addAction(self._action("Page précédente", "PageUp", self.previous_page, QStyle.StandardPixmap.SP_ArrowLeft))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        nav.addWidget(self.page_spin)
        self.page_count_label = QLabel(" / 0 ")
        nav.addWidget(self.page_count_label)
        nav.addAction(self._action("Page suivante", "PageDown", self.next_page, QStyle.StandardPixmap.SP_ArrowRight))
        nav.addSeparator()
        self.status_label = QLabel("Prêt")
        nav.addWidget(self.status_label)

        self.setStyleSheet(
            """
            QMainWindow { background: #f5f7fb; }
            QToolBar { background: #ffffff; border: none; border-bottom: 1px solid #dce1e7; spacing: 4px; padding: 7px; }
            QToolButton { padding: 7px; border-radius: 7px; }
            QToolButton:hover { background: #edf3ff; }
            QToolButton:checked { background: #dce9ff; border: 1px solid #9dbcf8; }
            QDockWidget { font-weight: 600; color: #253047; }
            QDockWidget::title { background: #ffffff; padding: 9px; border-bottom: 1px solid #dce1e7; }
            QListWidget { background: #f7f8fa; border: none; padding: 8px; outline: none; }
            QListWidget::item { padding: 7px; margin: 3px; border-radius: 6px; }
            QListWidget::item:selected { background: #dce9ff; color: #185abc; }
            QFontComboBox, QDoubleSpinBox, QSpinBox { min-height: 27px; border: 1px solid #d5dae1; border-radius: 6px; background: white; padding: 1px 5px; }
            QPushButton { min-height: 28px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; padding: 3px 8px; }
            QPushButton:hover { background: #edf3ff; border-color: #8fb2f4; }
            """
        )

    def _connect(self) -> None:
        self.model.changed.connect(self.refresh_current)
        self.model.structure_changed.connect(self.refresh_all)
        self.model.page_changed.connect(self._on_page_changed)
        self.model.dirty_changed.connect(self._update_title)
        self.thumbnails.currentRowChanged.connect(self.model.set_page)
        self.thumbnails.model().rowsMoved.connect(self._thumbnail_moved)
        self.page_spin.valueChanged.connect(lambda value: self.model.set_page(value - 1))
        self.canvas.signature_requested.connect(self.add_signature)
        self.canvas.image_requested.connect(self.add_image)
        self.canvas.link_requested.connect(self.add_link)
        self.canvas.stamp_requested.connect(self.add_stamp)
        self.canvas.object_selected.connect(self._object_selected)
        self.canvas.status.connect(self.status_label.setText)
        self.canvas.pan_requested.connect(self._pan_canvas)
        self.font_combo.currentFontChanged.connect(lambda font: self._apply_text_style())
        self.font_size.valueChanged.connect(lambda value: self._apply_text_style())
        self.color_button.clicked.connect(self.choose_text_color)

    def _action(self, tooltip: str, shortcut: str, callback, standard=None, icon: QIcon | None = None) -> QAction:
        action = QAction(icon or self.style().standardIcon(standard), "", self)
        action.setToolTip(f"{tooltip}{f' ({shortcut})' if shortcut else ''}")
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        return action

    def open_pdf(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un PDF", "", "Documents PDF (*.pdf)")
        if not path:
            return
        if not self.model.open(path):
            password, ok = QInputDialog.getText(self, "PDF protégé", "Mot de passe :", QLineEdit.EchoMode.Password)
            if not ok or not self.model.open(path, password):
                QMessageBox.critical(self, "Ouverture impossible", "Mot de passe incorrect ou PDF illisible.")

    def save_pdf(self) -> None:
        if not self.model.is_open:
            return
        self.canvas.commit_editor()
        suggested = str(self.model.path.with_stem(f"{self.model.path.stem}_modifie")) if self.model.path else ""
        path, _ = QFileDialog.getSaveFileName(self, "Exporter le PDF", suggested, "Documents PDF (*.pdf)")
        if path:
            try:
                self.model.save(path if path.lower().endswith(".pdf") else path + ".pdf")
            except Exception as exc:
                QMessageBox.critical(self, "Export impossible", str(exc))

    def refresh_all(self) -> None:
        self.canvas.refresh()
        self._load_thumbnails()
        self._update_navigation()
        self._update_title()

    def refresh_current(self) -> None:
        self.canvas.refresh()
        index = self.model.page_index
        if self.model.is_open and 0 <= index < self.thumbnails.count():
            self.thumbnails.item(index).setIcon(QIcon(QPixmap.fromImage(self.model.render_thumbnail(index))))
        self._update_navigation()
        self._update_title()

    def _load_thumbnails(self) -> None:
        self._loading_thumbnails = True
        self.thumbnails.clear()
        if self.model.is_open:
            for index in range(self.model.page_count):
                item = QListWidgetItem(QIcon(QPixmap.fromImage(self.model.render_thumbnail(index))), f"Page {index + 1}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
                self.thumbnails.addItem(item)
            self.thumbnails.setCurrentRow(self.model.page_index)
        self._loading_thumbnails = False

    def _thumbnail_moved(self, parent, start, end, destination, row) -> None:
        if not self._loading_thumbnails:
            target = row - 1 if row > start else row
            QTimer.singleShot(0, lambda: self.model.move_page(start, target))

    def _on_page_changed(self, index: int) -> None:
        if self.thumbnails.currentRow() != index:
            self.thumbnails.setCurrentRow(index)
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(index + 1)
        self.page_spin.blockSignals(False)
        self.canvas.selected = None
        self.canvas.refresh()
        self._update_navigation()

    def _update_navigation(self) -> None:
        count = self.model.page_count
        self.page_spin.setMaximum(max(1, count))
        self.page_count_label.setText(f" / {count} ")

    def set_tool(self, tool: Tool) -> None:
        if tool == Tool.STAMP:
            dialog = StampDialog(self, self.stamp_config)
            if not dialog.exec():
                tool = self.canvas.tool
            else:
                self.stamp_data = dialog.stamp_data()
                self.stamp_config = dialog.config
        for current, action in self.tool_actions.items():
            action.setChecked(current == tool)
        self.canvas.set_tool(tool)

    def _object_selected(self, obj: PdfObject | None) -> None:
        self.replace_image_action.setEnabled(bool(obj and obj.kind == "image"))
        if not obj:
            self.selection_label.setText("  Aucun objet sélectionné")
            for field in self.geometry_fields.values():
                field.setEnabled(False)
            self.apply_geometry_button.setEnabled(False)
            return
        labels = {"text": "Texte", "image": "Image", "graphic": "Graphique"}
        self.selection_label.setText(f"  {labels.get(obj.kind, obj.kind.capitalize())} sélectionné")
        values = {"x": obj.rect.x0, "y": obj.rect.y0, "w": obj.rect.width, "h": obj.rect.height}
        for key, field in self.geometry_fields.items():
            field.setEnabled(True)
            field.setValue(values[key])
        self.apply_geometry_button.setEnabled(True)
        if obj.kind == "text":
            self.font_combo.setCurrentFont(obj.font)
            self.font_size.setValue(obj.size)
            self.text_color = QColor.fromRgbF(*obj.color)
            self._update_color_button()
            self._apply_text_style()

    def apply_geometry(self) -> None:
        obj = self.canvas.selected
        if not obj:
            return
        x = self.geometry_fields["x"].value()
        y = self.geometry_fields["y"].value()
        width = max(10, self.geometry_fields["w"].value())
        height = max(10, self.geometry_fields["h"].value())
        target = fitz.Rect(x, y, x + width, y + height)
        self.model.transform_object(self.model.page_index, obj, target)
        self.canvas.selected = self.model.object_at(self.model.page_index, fitz.Point(x + width / 2, y + height / 2))
        self._object_selected(self.canvas.selected)

    def _pan_canvas(self, dx: int, dy: int) -> None:
        horizontal = self.scroll.horizontalScrollBar()
        vertical = self.scroll.verticalScrollBar()
        horizontal.setValue(horizontal.value() - dx)
        vertical.setValue(vertical.value() - dy)

    def _apply_text_style(self) -> None:
        self.canvas.set_text_style(self.font_combo.currentFont().family(), self.font_size.value(), self._qcolor_tuple(self.text_color))

    def choose_text_color(self) -> None:
        color = QColorDialog.getColor(self.text_color, self, "Couleur du texte")
        if color.isValid():
            self.text_color = color
            self._update_color_button()
            self._apply_text_style()

    def _update_color_button(self) -> None:
        self.color_button.setStyleSheet(f"background:{self.text_color.name()}; border: 2px solid #d5dae1; border-radius:5px;")

    def add_image(self, rect: fitz.Rect) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Ajouter une image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.model.add_image(self.model.page_index, rect, path)

    def add_signature(self, rect: fitz.Rect) -> None:
        path = self.signature_path
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Choisir une signature", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.signature_path = path
            self.model.add_signature(self.model.page_index, rect, path)

    def add_stamp(self, rect: fitz.Rect) -> None:
        if not self.stamp_data:
            dialog = StampDialog(self, self.stamp_config)
            if not dialog.exec():
                return
            self.stamp_data = dialog.stamp_data()
            self.stamp_config = dialog.config
        self.model.add_stamp(self.model.page_index, rect, self.stamp_data)
        self.status_label.setText(f"Tampon « {self.stamp_config.text} » ajouté")

    def add_link(self, rect: fitz.Rect) -> None:
        uri, ok = QInputDialog.getText(self, "Ajouter un lien", "Adresse web :")
        if ok and uri:
            if "://" not in uri:
                uri = "https://" + uri
            self.model.add_link(self.model.page_index, rect, uri)

    def replace_selected_image(self) -> None:
        obj = self.canvas.selected
        if not obj or obj.kind != "image":
            return
        path, _ = QFileDialog.getOpenFileName(self, "Remplacer l'image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.model.replace_image(self.model.page_index, obj, path)

    def erase_selected(self) -> None:
        if self.canvas.selected:
            self.model.erase_object(self.model.page_index, self.canvas.selected)

    def rotate_page(self) -> None:
        self.model.rotate_page(self.model.page_index)

    def delete_page(self) -> None:
        if self.model.page_count <= 1:
            QMessageBox.information(self, "Suppression impossible", "Un PDF doit conserver au moins une page.")
        else:
            self.model.delete_page(self.model.page_index)

    def merge_pdfs(self) -> None:
        if not self.model.is_open:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Fusionner des PDF", "", "Documents PDF (*.pdf)")
        if paths:
            self.model.merge_files(paths)

    def extract_page(self) -> None:
        if not self.model.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Extraire la page", f"page-{self.model.page_index + 1}.pdf", "Documents PDF (*.pdf)")
        if path:
            self.model.extract_page(self.model.page_index, path if path.lower().endswith(".pdf") else path + ".pdf")

    def search_text(self) -> None:
        if not self.model.is_open:
            return
        query, ok = QInputDialog.getText(self, "Rechercher", "Texte à rechercher :")
        if not ok or not query:
            return
        for offset in range(self.model.page_count):
            index = (self.model.page_index + offset) % self.model.page_count
            hits = self.model.doc.load_page(index).search_for(query)
            if hits:
                self.model.set_page(index)
                self.canvas.selected = PdfObject("résultat", hits[0], query)
                self.canvas.update()
                self.selection_label.setText(f"  Résultat page {index + 1}")
                return
        QMessageBox.information(self, "Recherche", "Aucun résultat.")

    def redact_text(self) -> None:
        if not self.model.is_open:
            return
        query, ok = QInputDialog.getText(self, "Redaction", "Terme à masquer définitivement :")
        if not ok or not query:
            return
        answer = QMessageBox.question(self, "Confirmer la redaction", f"Masquer définitivement toutes les occurrences de « {query} » ?")
        if answer == QMessageBox.StandardButton.Yes:
            count = self.model.redact_text(query)
            QMessageBox.information(self, "Redaction", f"{count} occurrence(s) masquée(s).")

    def run_ocr(self) -> None:
        if not self.model.is_open:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            count = self.model.run_ocr()
            QMessageBox.information(self, "OCR local", f"OCR terminé sur {count} page(s).")
        except Exception as exc:
            QMessageBox.critical(self, "OCR impossible", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def export_word(self) -> None:
        self._export_office("Word (*.docx)", ".docx", self.model.export_word)

    def export_excel(self) -> None:
        self._export_office("Excel (*.xlsx)", ".xlsx", self.model.export_excel)

    def export_powerpoint(self) -> None:
        self._export_office("PowerPoint (*.pptx)", ".pptx", self.model.export_powerpoint)

    def _export_office(self, file_filter: str, suffix: str, exporter) -> None:
        if not self.model.is_open:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Convertir le document", "", file_filter)
        if not path:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            exporter(path if path.lower().endswith(suffix) else path + suffix)
        except Exception as exc:
            QMessageBox.critical(self, "Conversion impossible", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def change_zoom(self, delta: float) -> None:
        self.canvas.set_zoom(self.canvas.zoom + delta)
        self.zoom_label.setText(f" {self.canvas.zoom:.0%} ")

    def previous_page(self) -> None:
        self.model.set_page(self.model.page_index - 1)

    def next_page(self) -> None:
        self.model.set_page(self.model.page_index + 1)

    def _update_title(self, *args) -> None:
        name = self.model.path.name if self.model.path else "Sans document"
        self.setWindowTitle(f"{name}{' • modifié' if self.model.dirty else ''} — PdfEditor")

    def _confirm_discard(self) -> bool:
        if not self.model.dirty:
            return True
        answer = QMessageBox.question(self, "Modifications non exportées", "Abandonner les modifications non exportées ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            self.model.close()
            event.accept()
        else:
            event.ignore()

    @staticmethod
    def _qcolor_tuple(color: QColor) -> tuple[float, float, float]:
        return color.redF(), color.greenF(), color.blueF()

    @staticmethod
    def _draw_icon(name: str) -> QIcon:
        pix = QPixmap(28, 28)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#26344d"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        polygon = lambda points: QPolygon([QPoint(x, y) for x, y in points])
        if name == "select":
            painter.drawPolygon(polygon([(5, 4), (11, 22), (14, 15), (22, 12)]))
        elif name == "text":
            painter.drawLine(6, 6, 22, 6); painter.drawLine(14, 6, 14, 22)
        elif name == "image":
            painter.drawRect(4, 5, 20, 17); painter.drawEllipse(16, 8, 3, 3); painter.drawPolyline(polygon([(6, 20), (11, 14), (15, 18), (19, 13), (23, 20)]))
        elif name == "link":
            painter.drawArc(4, 8, 13, 12, 40 * 16, 280 * 16); painter.drawArc(11, 8, 13, 12, 220 * 16, 280 * 16)
        elif name == "draw":
            painter.drawLine(5, 22, 20, 7); painter.drawLine(18, 5, 22, 9); painter.drawLine(5, 22, 10, 21)
        elif name == "highlight":
            painter.drawLine(7, 20, 21, 20); painter.drawRect(9, 5, 10, 11)
        elif name == "eraser":
            painter.drawPolygon(polygon([(5, 18), (15, 6), (23, 14), (14, 23)]))
        elif name == "signature":
            painter.drawPolyline(polygon([(4, 20), (9, 10), (11, 20), (16, 13), (17, 20), (24, 17)]))
        elif name == "stamp":
            painter.drawRoundedRect(4, 7, 20, 14, 3, 3)
            painter.drawLine(8, 11, 20, 11)
            painter.drawLine(8, 16, 20, 16)
        elif name == "check":
            painter.drawPolyline(polygon([(5, 14), (11, 20), (23, 7)]))
        elif name == "hand":
            painter.drawPolyline(polygon([(8, 22), (6, 14), (9, 13), (11, 17), (11, 6), (14, 5), (15, 15), (17, 8), (20, 9), (21, 17), (18, 23)]))
        elif name == "copy":
            painter.drawRect(8, 8, 14, 15); painter.drawRect(5, 5, 14, 15)
        elif name == "paste":
            painter.drawRect(6, 8, 16, 16); painter.drawRect(10, 4, 8, 6)
        elif name == "trash":
            painter.drawRect(8, 9, 13, 15); painter.drawLine(6, 7, 23, 7); painter.drawLine(11, 4, 18, 4)
        elif name == "rotate":
            painter.drawArc(5, 5, 18, 18, 30 * 16, 280 * 16); painter.drawPolyline(polygon([(18, 4), (23, 5), (22, 10)]))
        elif name == "replace":
            painter.drawLine(5, 10, 22, 10); painter.drawPolyline(polygon([(18, 6), (22, 10), (18, 14)])); painter.drawLine(22, 19, 5, 19)
        elif name == "merge":
            painter.drawRect(4, 5, 9, 16); painter.drawRect(15, 7, 9, 16); painter.drawLine(10, 14, 19, 14)
        elif name == "split":
            painter.drawRect(5, 4, 18, 20); painter.drawLine(4, 14, 24, 14); painter.drawLine(11, 10, 17, 18)
        elif name == "redact":
            painter.drawRect(4, 7, 20, 14); painter.fillRect(7, 11, 14, 6, QColor("#26344d"))
        elif name == "ocr":
            painter.drawEllipse(5, 5, 18, 18); painter.drawLine(14, 7, 14, 21); painter.drawLine(8, 14, 20, 14)
        elif name == "word":
            painter.drawRect(5, 4, 18, 20); painter.drawText(8, 20, "W")
        elif name == "excel":
            painter.drawRect(5, 4, 18, 20); painter.drawText(8, 20, "X")
        elif name == "powerpoint":
            painter.drawRect(5, 4, 18, 20); painter.drawText(8, 20, "P")
        else:
            painter.drawEllipse(6, 6, 16, 16)
        painter.end()
        return QIcon(pix)
