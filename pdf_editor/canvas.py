from __future__ import annotations

from enum import Enum, auto

import fitz
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QWidget

from .model import PdfDocument, PdfObject


class Tool(Enum):
    PAN = auto()
    SELECT = auto()
    TEXT = auto()
    IMAGE = auto()
    LINK = auto()
    DRAW = auto()
    HIGHLIGHT = auto()
    ERASER = auto()
    SIGNATURE = auto()
    STAMP = auto()


class InlineTextEditor(QPlainTextEdit):
    commit_requested = Signal()
    cancel_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.commit_requested.emit()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
            return
        super().keyPressEvent(event)


class PdfCanvas(QWidget):
    status = Signal(str)
    object_selected = Signal(object)
    signature_requested = Signal(object)
    image_requested = Signal(object)
    link_requested = Signal(object)
    stamp_requested = Signal(object)
    pan_requested = Signal(int, int)

    def __init__(self, model: PdfDocument) -> None:
        super().__init__()
        self.model = model
        self.zoom = 1.0
        self.tool = Tool.PAN
        self.pixmap = QPixmap()
        self.drag_start: QPoint | None = None
        self.drag_end: QPoint | None = None
        self.ink_points: list[QPoint] = []
        self.selected: PdfObject | None = None
        self.editor: InlineTextEditor | None = None
        self.editor_object: PdfObject | None = None
        self.transform_start: QPoint | None = None
        self.transform_original: fitz.Rect | None = None
        self.transform_preview: fitz.Rect | None = None
        self.resize_handle: str | None = None
        self.hovered: PdfObject | None = None
        self.copied_payload: dict | None = None
        self.pan_start: QPoint | None = None
        self.font_family = "Helvetica"
        self.font_size = 12.0
        self.text_color = (0.07, 0.09, 0.13)
        self.setMouseTracking(True)

    def set_tool(self, tool: Tool) -> None:
        self.cancel_editor()
        self.tool = tool
        self.selected = None
        self.object_selected.emit(None)
        cursor = Qt.CursorShape.ArrowCursor
        if tool in (Tool.PAN, Tool.SELECT):
            cursor = Qt.CursorShape.OpenHandCursor
        if tool in (Tool.TEXT, Tool.IMAGE, Tool.LINK, Tool.HIGHLIGHT, Tool.SIGNATURE, Tool.STAMP):
            cursor = Qt.CursorShape.CrossCursor
        elif tool == Tool.DRAW:
            cursor = Qt.CursorShape.PointingHandCursor
        elif tool == Tool.ERASER:
            cursor = Qt.CursorShape.ForbiddenCursor
        self.setCursor(cursor)
        self.update()

    def set_text_style(self, family: str, size: float, color: tuple[float, float, float]) -> None:
        self.font_family, self.font_size, self.text_color = family, size, color
        if self.editor:
            font = self.editor.font()
            font.setFamily(family)
            font.setPointSizeF(size)
            self.editor.setFont(font)
            self.editor.setStyleSheet(self._editor_style())

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.25, min(zoom, 4.0))
        self.refresh()

    def refresh(self) -> None:
        self.cancel_editor()
        if not self.model.is_open:
            self.pixmap = QPixmap()
            self.resize(700, 900)
        else:
            render_scale = min(max(self.zoom * 2.0, 1.5), 5.0)
            self.pixmap = QPixmap.fromImage(self.model.render_page(self.model.page_index, render_scale))
            self.pixmap.setDevicePixelRatio(render_scale / self.zoom)
            page = self.model.doc.load_page(self.model.page_index)
            self.resize(round(page.rect.width * self.zoom), round(page.rect.height * self.zoom))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        if not self.pixmap.isNull():
            painter.drawPixmap(0, 0, self.pixmap)
        if self.tool == Tool.SELECT and self.model.is_open:
            colors = {"text": QColor("#2f6fed"), "image": QColor("#8b5cf6"), "graphic": QColor("#e58a16")}
            for obj in self.model.page_objects(self.model.page_index):
                color = colors.get(obj.kind, QColor("#667085"))
                color.setAlpha(85 if obj is not self.hovered else 190)
                painter.setPen(QPen(color, 1, Qt.PenStyle.DashLine))
                painter.drawRect(self._screen_rect(obj.rect))
        if self.selected:
            painter.setPen(QPen(QColor("#246bfd"), 2, Qt.PenStyle.DashLine))
            selection_rect = self.transform_preview or self.selected.rect
            screen_rect = self._screen_rect(selection_rect)
            painter.drawRect(screen_rect)
            for handle in self._handle_rects(screen_rect).values():
                painter.fillRect(handle, QColor("#ffffff"))
                painter.setPen(QPen(QColor("#246bfd"), 1))
                painter.drawRect(handle)
        if self.tool == Tool.DRAW and len(self.ink_points) > 1:
            painter.setPen(QPen(QColor("#e5484d"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPolyline(self.ink_points)
        if self.drag_start and self.drag_end:
            rect = QRect(self.drag_start, self.drag_end).normalized()
            if self.tool == Tool.HIGHLIGHT:
                painter.fillRect(rect, QColor(255, 205, 48, 90))
            painter.setPen(QPen(QColor("#246bfd"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.model.is_open:
            return
        point = event.position().toPoint()
        pdf_point = self._pdf_point(point)
        if self.tool == Tool.PAN:
            self.pan_start = point
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if self.tool == Tool.TEXT:
            self.start_editor(fitz.Rect(pdf_point.x, pdf_point.y, pdf_point.x + 300 / self.zoom, pdf_point.y + 90 / self.zoom))
            return
        if self.tool == Tool.SELECT:
            if self.selected:
                handle = self._handle_at(point, self._screen_rect(self.selected.rect))
                if handle:
                    self.resize_handle = handle
                    self.transform_start = point
                    self.transform_original = fitz.Rect(self.selected.rect)
                    self.setCursor(self._cursor_for_handle(handle))
                    return
            current = self.model.object_at(self.model.page_index, pdf_point)
            if current:
                self.selected = current
                self.object_selected.emit(current)
                self.transform_start = point
                self.transform_original = fitz.Rect(current.rect)
                self.resize_handle = None
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                self.select_at(pdf_point)
            return
        if self.tool == Tool.ERASER:
            obj = self.model.object_at(self.model.page_index, pdf_point)
            if obj:
                self.model.erase_object(self.model.page_index, obj)
            return
        if self.tool == Tool.DRAW:
            self.ink_points = [point]
        elif self.tool in (Tool.IMAGE, Tool.LINK, Tool.HIGHLIGHT, Tool.SIGNATURE, Tool.STAMP):
            self.drag_start = point
            self.drag_end = point
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.tool != Tool.SELECT or not self.model.is_open:
            return
        obj = self.model.object_at(self.model.page_index, self._pdf_point(event.position().toPoint()))
        if obj and obj.kind == "text":
            self.selected = obj
            self.object_selected.emit(obj)
            self.start_editor(obj.rect, obj.text, obj)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = event.position().toPoint()
        self.status.emit(f"x {point.x() / self.zoom:.0f}  y {point.y() / self.zoom:.0f}")
        if not event.buttons() & Qt.MouseButton.LeftButton:
            if self.tool == Tool.SELECT and self.model.is_open:
                self.hovered = self.model.object_at(self.model.page_index, self._pdf_point(point))
                handle = self._handle_at(point, self._screen_rect(self.selected.rect)) if self.selected else None
                self.setCursor(self._cursor_for_handle(handle) if handle else Qt.CursorShape.OpenHandCursor)
                self.update()
            return
        if self.tool == Tool.PAN and self.pan_start:
            delta = point - self.pan_start
            self.pan_requested.emit(delta.x(), delta.y())
            self.pan_start = point
        elif self.tool == Tool.DRAW and self.ink_points:
            self.ink_points.append(point)
        elif self.tool == Tool.SELECT and self.transform_start and self.transform_original:
            dx = (point.x() - self.transform_start.x()) / self.zoom
            dy = (point.y() - self.transform_start.y()) / self.zoom
            if self.resize_handle:
                self.transform_preview = self._resized_rect(self.transform_original, self.resize_handle, dx, dy)
            else:
                self.transform_preview = self.transform_original + (dx, dy, dx, dy)
        elif self.drag_start:
            self.drag_end = point
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.model.is_open:
            return
        if self.tool == Tool.PAN:
            self.pan_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        if self.tool == Tool.DRAW and len(self.ink_points) > 1:
            self.model.add_ink(self.model.page_index, [self._pdf_point(p) for p in self.ink_points], (0.9, 0.12, 0.16), 2.0)
        elif self.tool == Tool.SELECT and self.selected and self.transform_preview:
            target = fitz.Rect(self.transform_preview)
            self.model.transform_object(self.model.page_index, self.selected, target)
            self.selected = self.model.object_at(
                self.model.page_index, fitz.Point((target.x0 + target.x1) / 2, (target.y0 + target.y1) / 2)
            )
            self.object_selected.emit(self.selected)
        elif self.drag_start and self.drag_end:
            rect = self._pdf_rect(QRect(self.drag_start, self.drag_end).normalized())
            if self.tool == Tool.HIGHLIGHT:
                self.model.add_highlight(self.model.page_index, rect)
            elif self.tool == Tool.IMAGE:
                self.image_requested.emit(rect)
            elif self.tool == Tool.LINK:
                self.link_requested.emit(rect)
            elif self.tool == Tool.SIGNATURE:
                self.signature_requested.emit(rect)
            elif self.tool == Tool.STAMP:
                self.stamp_requested.emit(rect)
        self.ink_points, self.drag_start, self.drag_end = [], None, None
        self.transform_start, self.transform_original, self.transform_preview = None, None, None
        self.resize_handle = None
        if self.tool == Tool.SELECT:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def select_at(self, point: fitz.Point) -> None:
        self.selected = self.model.object_at(self.model.page_index, point)
        self.object_selected.emit(self.selected)
        self.update()

    def copy_selected(self) -> None:
        if not self.selected:
            return
        self.copied_payload = self.model.copy_object_payload(self.model.page_index, self.selected)
        if self.selected.kind == "text":
            QApplication.clipboard().setText(self.selected.text)
        self.status.emit("Objet copié")

    def paste_copied(self) -> None:
        if not self.model.is_open:
            return
        payload = self.copied_payload
        if not payload and QApplication.clipboard().text():
            payload = {
                "kind": "text",
                "rect": (60, 60, 300, 95),
                "text": QApplication.clipboard().text(),
                "font": self.font_family,
                "size": self.font_size,
                "color": self.text_color,
            }
        if payload:
            self.selected = self.model.paste_object(self.model.page_index, payload)
            self.object_selected.emit(self.selected)
            self.status.emit("Objet collé")

    def start_editor(self, rect: fitz.Rect, text: str = "", obj: PdfObject | None = None) -> None:
        self.cancel_editor()
        self.editor_object = obj
        self.editor = InlineTextEditor(self)
        self.editor.setPlainText(text)
        self.editor.setGeometry(self._screen_rect(rect).adjusted(-2, -2, 60, 28))
        family, size, color = self.font_family, self.font_size, self.text_color
        if obj:
            family, size, color = obj.font, obj.size, obj.color
        self.font_family, self.font_size, self.text_color = family, size, color
        font = self.editor.font()
        font.setFamily(family)
        font.setPointSizeF(size)
        self.editor.setFont(font)
        self.editor.setStyleSheet(self._editor_style())
        self.editor.commit_requested.connect(self.commit_editor)
        self.editor.cancel_requested.connect(self.cancel_editor)
        self.editor.show()
        self.editor.setFocus()
        self.editor.selectAll()

    def commit_editor(self) -> None:
        if not self.editor:
            return
        text = self.editor.toPlainText()
        rect = self._pdf_rect(self.editor.geometry())
        obj = self.editor_object
        self.editor.hide()
        self.editor.deleteLater()
        self.editor = None
        self.editor_object = None
        if obj:
            self.model.replace_text(self.model.page_index, obj, text, self.font_size, self.text_color, self.font_family)
        elif text:
            self.model.add_text(self.model.page_index, rect, text, self.font_size, self.text_color, self.font_family)

    def cancel_editor(self) -> None:
        if self.editor:
            self.editor.hide()
            self.editor.deleteLater()
        self.editor = None
        self.editor_object = None

    def _editor_style(self) -> str:
        r, g, b = (round(v * 255) for v in self.text_color)
        return f"QPlainTextEdit {{ color: rgb({r},{g},{b}); background: rgba(255,255,255,220); border: 2px solid #246bfd; padding: 2px; }}"

    def _pdf_point(self, point: QPoint) -> fitz.Point:
        return fitz.Point(point.x() / self.zoom, point.y() / self.zoom)

    def _pdf_rect(self, rect: QRect) -> fitz.Rect:
        return fitz.Rect(rect.left() / self.zoom, rect.top() / self.zoom, rect.right() / self.zoom, rect.bottom() / self.zoom)

    def _screen_rect(self, rect: fitz.Rect) -> QRect:
        return QRect(round(rect.x0 * self.zoom), round(rect.y0 * self.zoom), round(rect.width * self.zoom), round(rect.height * self.zoom))

    @staticmethod
    def _handle_rects(rect: QRect) -> dict[str, QRect]:
        size = 9
        half = size // 2
        x0, xc, x1 = rect.left(), rect.center().x(), rect.right()
        y0, yc, y1 = rect.top(), rect.center().y(), rect.bottom()
        return {
            "nw": QRect(x0 - half, y0 - half, size, size), "n": QRect(xc - half, y0 - half, size, size),
            "ne": QRect(x1 - half, y0 - half, size, size), "e": QRect(x1 - half, yc - half, size, size),
            "se": QRect(x1 - half, y1 - half, size, size), "s": QRect(xc - half, y1 - half, size, size),
            "sw": QRect(x0 - half, y1 - half, size, size), "w": QRect(x0 - half, yc - half, size, size),
        }

    def _handle_at(self, point: QPoint, rect: QRect) -> str | None:
        return next((name for name, area in self._handle_rects(rect).items() if area.adjusted(-4, -4, 4, 4).contains(point)), None)

    @staticmethod
    def _cursor_for_handle(handle: str | None) -> Qt.CursorShape:
        if handle in ("nw", "se"):
            return Qt.CursorShape.SizeFDiagCursor
        if handle in ("ne", "sw"):
            return Qt.CursorShape.SizeBDiagCursor
        if handle in ("n", "s"):
            return Qt.CursorShape.SizeVerCursor
        if handle in ("e", "w"):
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.OpenHandCursor

    @staticmethod
    def _resized_rect(original: fitz.Rect, handle: str, dx: float, dy: float) -> fitz.Rect:
        rect = fitz.Rect(original)
        if "w" in handle:
            rect.x0 = min(rect.x1 - 10, rect.x0 + dx)
        if "e" in handle:
            rect.x1 = max(rect.x0 + 10, rect.x1 + dx)
        if "n" in handle:
            rect.y0 = min(rect.y1 - 10, rect.y0 + dy)
        if "s" in handle:
            rect.y1 = max(rect.y0 + 10, rect.y1 + dy)
        return rect
