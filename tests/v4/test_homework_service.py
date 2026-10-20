"""Homework checklist privacy, photo metadata, review gates and print safety."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.homework.service import HomeworkService
from core.homework.printer import PrinterError, list_printers, submit_pdf

MEMBERS = {"dad": {}, "child1": {}, "child2": {}}


class TestHomeworkService(unittest.TestCase):
    def test_local_persistence_and_member_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            service = HomeworkService(home=td, members=MEMBERS)
            item = service.add_item(owner_member_id="child1", due_date="2026-10-21",
                                    subject="数学", title="课本第 30 页", expected_pages=1)
            self.assertEqual(len(service.list_items(viewer_member_id="child1")), 1)
            self.assertEqual(service.list_items(viewer_member_id="child2"), [])
            restored = HomeworkService(home=td, members=MEMBERS)
            self.assertEqual(restored.list_items(viewer_member_id="child1")[0].item_id, item.item_id)

    def test_rejects_unknown_member_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            service = HomeworkService(home=td, members=MEMBERS)
            item = service.add_item(owner_member_id="child1", due_date="2026-10-21",
                                    subject="语文", title="阅读")
            with self.assertRaises(ValueError):
                service.add_item(owner_member_id="stranger", due_date="2026-10-21",
                                 subject="语文", title="未知成员")
            with self.assertRaises(ValueError):
                service.add_evidence(item.item_id, owner_member_id="child1",
                                     local_relative_path="../../private.jpg")

    def test_ai_review_never_auto_marks_homework_complete(self):
        with tempfile.TemporaryDirectory() as td:
            service = HomeworkService(home=td, members=MEMBERS)
            item = service.add_item(owner_member_id="child1", due_date="2026-10-21",
                                    subject="英语", title="练习册")
            ev = service.add_evidence(item.item_id, owner_member_id="child1",
                                      local_relative_path="2026-10-21/child1/one.jpg")
            service.record_review(ev.evidence_id, owner_member_id="child1",
                                  review_status="looks_complete", summary="可见页面似乎已完成")
            self.assertEqual(service.items[item.item_id].status, "needs_review")
            with self.assertRaises(PermissionError):
                service.record_review(ev.evidence_id, owner_member_id="child2",
                                      review_status="looks_complete", summary="错误成员")

    def test_no_raw_image_bytes_or_full_transcript_are_required(self):
        with tempfile.TemporaryDirectory() as td:
            service = HomeworkService(home=td, members=MEMBERS)
            item = service.add_item(owner_member_id="child1", due_date="2026-10-21",
                                    subject="其他", title="手工作业")
            service.add_evidence(item.item_id, owner_member_id="child1",
                                 local_relative_path="2026-10-21/child1/craft.webp")
            saved = service.path.read_text(encoding="utf-8")
            self.assertNotIn("base64", saved.lower())
            self.assertNotIn("OCR transcript", saved)


class TestPrinterSafety(unittest.TestCase):
    def test_requires_explicit_confirmation_and_generated_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "generated"
            root.mkdir()
            pdf = root / "homework.pdf"
            pdf.write_bytes(b"%PDF-test")
            with patch("core.homework.printer.sys.platform", "darwin"):
                with self.assertRaises(PrinterError):
                    submit_pdf(pdf, printer="Epson", generated_dir=root, confirmed=False)
                with self.assertRaises(PrinterError):
                    submit_pdf(Path(td) / "outside.pdf", printer="Epson",
                               generated_dir=root, confirmed=True, runner=Mock())

    def test_lists_printers_without_shell(self):
        fake = Mock(return_value=Mock(returncode=0, stdout="printer Epson_ET_2850 is idle.\nprinter bad/name is idle.\n"))
        with patch("core.homework.printer.sys.platform", "darwin"):
            self.assertEqual(list_printers(runner=fake), ["Epson_ET_2850"])
        fake.assert_called_once_with(["/usr/bin/lpstat", "-p"], capture_output=True,
                                     text=True, timeout=8, check=False)


if __name__ == "__main__":
    unittest.main()
