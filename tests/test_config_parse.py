# -*- coding: utf-8 -*-
"""config.py 解析與寫檔的離線回歸測試（不連網、不需真實 config.py）。

用 AST 從 gui_main.py 抽取 _strip_inline_comment / parse_config_text / _write_config_preserving，
因此無需 import customtkinter（本環境 headless 無法實例化 Tk）。

用法：python3 -m unittest discover -s tests
"""
import ast
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SRC = open(os.path.join(ROOT, "gui_main.py"), encoding="utf-8").read()


def _extract(name, src=SRC):
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f"{name} not found in gui_main.py")


_NS = {}
exec(_extract("_strip_inline_comment"), _NS)
exec(_extract("parse_config_text"), _NS)
strip_inline_comment = _NS["_strip_inline_comment"]
parse_config_text = _NS["parse_config_text"]

# _write_config_preserving 相依 os/shutil，個別執行
_NS2 = {"os": os, "shutil": __import__("shutil"), "CONFIG_PATH": "/nonexistent/config.py"}
exec(_extract("_write_config_preserving"), _NS2)
write_config = _NS2["_write_config_preserving"]


class TestParseConfigText(unittest.TestCase):
    def test_template_parses_fully(self):
        template = open(os.path.join(ROOT, "config.py.template"), encoding="utf-8").read()
        s = parse_config_text(template)
        self.assertEqual(s["TARGET_PRICE"], "4000")
        self.assertEqual(s["START_DATE"], "2026-12-01")
        self.assertEqual(s["END_DATE"], "2026-12-31")
        self.assertEqual(s["INTERVAL_MINS"], "60")
        self.assertEqual(s["SCHEDULE_INTERVAL_MINUTES"], "60")
        self.assertEqual(s["FROM_CITY"], "SPK")
        self.assertEqual(s["TO_CITY"], "TPE")
        self.assertEqual(s["LINE_ENABLE"], "True")
        self.assertEqual(s["TELEGRAM_ENABLE"], "True")

    def test_comment_line_with_equals_does_not_crash(self):
        text = "# === 通知開關（True/False）===\nA = 1\n"
        self.assertEqual(parse_config_text(text), {"A": "1"})

    def test_hash_inside_quotes_preserved(self):
        text = "B = 'it # note'  # real comment\n"
        self.assertEqual(parse_config_text(text), {"B": "it # note"})

    def test_inline_comment_stripped(self):
        self.assertEqual(strip_inline_comment("X = 1  # note").strip(), "X = 1")
        self.assertEqual(strip_inline_comment("Y = 'a # b' # tail").strip(), "Y = 'a # b'")


class TestWriteConfigPreserving(unittest.TestCase):
    def test_roundtrip_quotes_and_comments(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("# comment\nTARGET_PRICE = 4000\nKEEP_ME = 'keep'\n")
            path = f.name
        try:
            write_config({"TARGET_PRICE": repr(9000), "TELEGRAM_BOT_TOKEN": repr("it's \"quoted\" #pw")}, path)
            out = open(path, encoding="utf-8").read()
            self.assertIn("# comment", out)
            self.assertIn("KEEP_ME = 'keep'", out)
            self.assertIn("TARGET_PRICE = 9000", out)
            ns = {}
            exec(out, ns)
            self.assertEqual(ns["TARGET_PRICE"], 9000)
            # 含引號與 # 的值仍為合法 Python literal
            self.assertEqual(ns["TELEGRAM_BOT_TOKEN"], "it's \"quoted\" #pw")
        finally:
            os.unlink(path)
            if os.path.exists(path + ".bak"):
                os.unlink(path + ".bak")
            if os.path.exists(path + ".tmp"):
                os.unlink(path + ".tmp")

    def test_replace_failure_calls_on_error_exactly_once(self):
        import unittest.mock as mock
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("TARGET_PRICE = 4000\n")
            path = f.name
        try:
            errors = []

            def boom(*a, **k):
                raise OSError("disk full (simulated)")

            with mock.patch.object(_NS2["os"], "replace", boom):
                result = write_config({"TARGET_PRICE": "1000"}, path, on_error=errors.append)
            self.assertFalse(result)
            self.assertEqual(len(errors), 1)
            # 原檔未被破壞（os.replace 失敗 → 原檔保留）
            self.assertEqual(open(path, encoding="utf-8").read(), "TARGET_PRICE = 4000\n")
        finally:
            for p in (path, path + ".bak", path + ".tmp"):
                if os.path.exists(p):
                    os.unlink(p)

    def test_bak_created_before_overwrite(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("TARGET_PRICE = 4000\n")
            path = f.name
        try:
            write_config({"TARGET_PRICE": "1000"}, path)
            self.assertTrue(os.path.exists(path + ".bak"))
            self.assertEqual(open(path + ".bak", encoding="utf-8").read(), "TARGET_PRICE = 4000\n")
        finally:
            for p in (path, path + ".bak", path + ".tmp"):
                if os.path.exists(p):
                    os.unlink(p)


if __name__ == "__main__":
    unittest.main()
