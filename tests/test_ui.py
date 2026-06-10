from pathlib import Path

import fitz
from PySide6.QtWidgets import QApplication

from pdf_editor.canvas import Tool
from pdf_editor.window import MainWindow


def test_inline_editor_and_selection_mode(tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    source = tmp_path / "ui-source.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 90), "Texte à modifier", fontsize=14)
    doc.save(source)
    doc.close()

    window = MainWindow()
    assert window.model.open(str(source))
    window.set_tool(Tool.SELECT)
    obj = window.model.object_at(0, fitz.Point(100, 85))
    assert obj and obj.kind == "text"
    window.canvas.start_editor(obj.rect, obj.text, obj)
    assert window.canvas.editor is not None
    window.canvas.editor.setPlainText("Modification directe réussie")
    window.canvas.commit_editor()
    assert "Modification directe réussie" in window.model.doc[0].get_text().replace("\xa0", " ")
    window.model.close()
    window.close()
