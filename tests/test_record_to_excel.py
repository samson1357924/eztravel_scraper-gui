# -*- coding: utf-8 -*-
"""record_to_excel 與「Excel 失敗不阻斷通知鏈」的離線單元測試（不連網）。

record_to_excel 只碰本機暫存檔（tempfile.mkdtemp 建立的隔離目錄），不發送任何網路請求；
run_scraper 流程也以 monkeypatch 隔離（query_one_resource / send_notification_text 皆為替身）。

用法：
    python3 -m unittest discover -s tests
"""
import sys
import os
import glob
import shutil
import tempfile
import types
import unittest
from datetime import datetime, timedelta

# Repository root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FUTURE = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
FUTURE2 = (datetime.now() + timedelta(days=31)).strftime('%Y-%m-%d')

# 在 import scraper 之前塞一個假的 config 模組，讓測試不需依賴本地 config.py
fake_config = types.ModuleType('config')
fake_config.LINE_CHANNEL_ACCESS_TOKEN = ''
fake_config.LINE_USER_ID = ''
fake_config.GMAIL_USER = ''
fake_config.GMAIL_PASSWORD = ''
fake_config.TO_EMAIL = ''
fake_config.TARGET_PRICE = 4000
fake_config.START_DATE = FUTURE
fake_config.END_DATE = FUTURE2
fake_config.FROM_CITY = 'SPK'
fake_config.TO_CITY = 'TPE'
fake_config.RESOURCE_TYPES = ['Ct', 'EzTravel']
fake_config.REQUEST_DELAY_SECONDS = 0
fake_config.EXCEL_ENABLE = False  # 預設關閉；需要 Excel 的測試自行開啟，並於結束時復原
sys.modules['config'] = fake_config

import scraper  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

_MISSING = object()
TODAY = datetime.now().date()
D1 = (TODAY + timedelta(days=1)).strftime('%Y-%m-%d')
D2 = (TODAY + timedelta(days=2)).strftime('%Y-%m-%d')

GARBAGE = "這不是 Excel 檔，只是純文字垃圾".encode("utf-8")


def make_results():
    return [
        {"date": D1, "price": 1000.0, "link": "l1"},
        {"date": D1, "price": 1000.0, "link": "l1-dup"},   # 雙 resourceType 記到同價
        {"date": D1, "price": 2000.0, "link": "l2"},
        {"date": D1, "price": 3000.0, "link": "l3"},
        {"date": D2, "price": 1500.0, "link": "l4"},
    ]


def data_rows(rows):
    """回傳「非 Time 表頭列且有內容」的資料列。"""
    return [r for r in rows if r and r[0] != "Time" and any(v not in (None, "") for v in r)]


class RecordToExcelTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='eztravel_excel_test_')
        self.addCleanup(shutil.rmtree, self.tmpdir, True)

    def patch(self, obj, name, value):
        """暫時替換 obj.name，測試結束（或 addCleanup）時自動還原。"""
        orig = getattr(obj, name, _MISSING)

        def restore():
            if orig is _MISSING:
                try:
                    delattr(obj, name)
                except AttributeError:
                    pass
            else:
                setattr(obj, name, orig)

        self.addCleanup(restore)
        setattr(obj, name, value)

    def enable_excel(self, filename):
        self.patch(scraper.config, 'EXCEL_ENABLE', True)
        self.patch(scraper.config, 'EXCEL_FILENAME', filename)
        self.patch(scraper.config, 'EXCEL_TOP_N', 3)

    def test_a_header_unique_across_runs(self):
        """測試 A：兩次連跑寫入同一 xlsx，col1 == 'Time' 的列只有 1 列。"""
        fn = os.path.join(self.tmpdir, 'header_unique.xlsx')
        self.enable_excel(fn)
        scraper.record_to_excel(make_results(), D1, D2, log=lambda m: None)
        scraper.record_to_excel(make_results(), D1, D2, log=lambda m: None)
        rows = list(load_workbook(fn).active.iter_rows(values_only=True))
        time_rows = [r for r in rows if r and r[0] == "Time"]
        self.assertEqual(len(time_rows), 1, f"表頭列數={len(time_rows)}, 總列數={len(rows)}")

    def test_b_same_day_duplicate_prices_deduped(self):
        """測試 B：同日重複價去重，表頭列之後的資料列前三格應為 1000,2000,3000。"""
        fn = os.path.join(self.tmpdir, 'dedup.xlsx')
        self.enable_excel(fn)
        scraper.record_to_excel(make_results(), D1, D2, log=lambda m: None)
        rows = list(load_workbook(fn).active.iter_rows(values_only=True))
        body = data_rows(rows)
        self.assertTrue(body, "沒有任何資料列")
        for r in body:
            self.assertEqual(list(r[1:4]), [1000.0, 2000.0, 3000.0],
                             f"D1 前三格應為去重後的最低價，實際為 {r[1:4]}")

    def test_c_corrupt_xlsx_backed_up_not_overwritten(self):
        """測試 C：純文字垃圾 .xlsx → 備份為 .bak-<timestamp> 且內容不變；原檔重建為有效 xlsx 含表頭。"""
        fn = os.path.join(self.tmpdir, 'corrupt.xlsx')
        with open(fn, 'wb') as f:
            f.write(GARBAGE)
        self.enable_excel(fn)
        scraper.record_to_excel(make_results(), D1, D2, log=lambda m: None)
        # (i) 產生 .bak-<timestamp> 備份且內容不變
        baks = glob.glob(fn + '.bak-*')
        self.assertEqual(len(baks), 1, f"備份檔應恰好 1 個，實際為 {baks}")
        with open(baks[0], 'rb') as f:
            self.assertEqual(f.read(), GARBAGE, "備份檔內容必須保留原垃圾內容（不得覆蓋）")
        # (ii) 新原檔可用 openpyxl 開啟且含表頭
        rows = list(load_workbook(fn).active.iter_rows(values_only=True))
        self.assertTrue(rows and rows[0] and rows[0][0] == "Time",
                        f"重建後首列應為 Time 表頭，實際為 {rows[0][:3] if rows else None}")

    def test_d_excel_failure_does_not_break_notification_chain(self):
        """測試 D：record_to_excel 拋 PermissionError 時，send_notification_text 仍被呼叫一次。"""
        sent = []

        def boom(*a, **k):
            raise PermissionError(13, "Permission denied", "flight_prices.xlsx")

        self.patch(scraper, 'record_to_excel', boom)
        self.patch(scraper, 'send_notification_text', lambda text: sent.append(text))
        self.patch(scraper, 'query_one_resource',
                   lambda date, rt, ids, log=None: (True, 100.0, None, [100.0]))
        self.patch(scraper, 'STATE_FILE', os.path.join(self.tmpdir, 'state.json'))
        self.patch(scraper.config, 'TARGET_PRICE', 4000.0)
        scraper.run_scraper(FUTURE, FUTURE, log_callback=lambda m: None)
        self.assertEqual(len(sent), 1,
                         f"Excel 失敗不應影響通知，send_notification_text 應被呼叫 1 次，實際 {len(sent)} 次")


if __name__ == '__main__':
    unittest.main()
