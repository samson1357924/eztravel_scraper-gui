# -*- coding: utf-8 -*-
"""scraper.py 的離線單元測試（不連網、不需要真實 config.py）。

所有測試都不發送任何網路請求（query_one_resource 以假 response 隔離）。
用法：
    python3 tests/test_scraper.py          # 直接執行（無需任何額外依賴）
    python3 -m unittest discover -s tests  # 由 unittest 探索（檔尾相容層會收集本檔測試）
"""
import sys
import os
import tempfile
import json
import types

# Repository root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from datetime import datetime, timedelta
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
fake_config.EXCEL_ENABLE = False  # 確保 record_to_excel 不執行（避免污染 repo 目錄）
sys.modules['config'] = fake_config

import scraper  # noqa: E402


class FakeDate:
    def strftime(self, fmt):
        if fmt.startswith('%Y-%m-%d'):
            return '2026-12-01'
        return '01/12/2026'


def fake_resp(body, status=200):
    class R:
        status_code = status
        text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)

        def json(self):
            if isinstance(body, Exception):
                raise body
            return body
    return R()


def with_mocked_post(body, status=200):
    """暫時把 scraper.requests.post 換成回傳固定 body 的假函式。"""
    import atexit
    real = scraper.requests.post
    scraper.requests.post = lambda *a, **k: fake_resp(body, status)
    # 測試中途 assert 失敗時也能在程式結束時還原，避免污染後續測試
    atexit.register(restore_post, real)
    return real


def restore_post(real):
    scraper.requests.post = real


def test_parse_price():
    assert scraper.parse_price(4518) == 4518.0
    assert scraper.parse_price('4,518') == 4518.0
    assert scraper.parse_price('NT$ 4518') == 4518.0
    assert scraper.parse_price('abc') is None
    assert scraper.parse_price(None) is None


def test_build_found_message_cap():
    flights = [{'date': f'2026-12-{d:02d}', 'price': 1000 + d, 'link': 'https://x'} for d in range(1, 31)]
    msg = scraper.build_found_message(flights)
    assert '…其餘' in msg
    assert msg.count('日期:') == scraper.MAX_FLIGHTS_PER_MESSAGE


def test_query_one_resource_non_dict_body():
    real = with_mocked_post(['not', 'a', 'dict'])
    ok, price, err, _prices = scraper.query_one_resource(FakeDate(), 'Ct', ('0317' + '1' * 16, 'x' * 16))
    restore_post(real)
    assert not ok and 'JSON' in err


def test_query_one_resource_past_date_data_null():
    real = with_mocked_post({'head': {'code': 0}, 'data': None})
    ok, price, err, _prices = scraper.query_one_resource(FakeDate(), 'Ct', ('0317' + '1' * 16, 'x' * 16))
    restore_post(real)
    assert ok and price is None and err is None


def test_query_one_resource_bad_code():
    real = with_mocked_post({'head': {'code': 400405, 'message': '請求參數無效'}})
    ok, price, err, _prices = scraper.query_one_resource(FakeDate(), 'Ct', ('0317' + '1' * 16, 'x' * 16))
    restore_post(real)
    assert not ok and '400405' in err


def test_query_one_resource_price_parsing():
    real = with_mocked_post({'head': {'code': 0}, 'data': {'routings': [
        {'prices': [{'price': '4,998'}, {'price': None}, 'bad']},
        {'prices': [{'price': 4500}]},
    ]}})
    ok, price, err, _prices = scraper.query_one_resource(FakeDate(), 'Ct', ('0317' + '1' * 16, 'x' * 16))
    restore_post(real)
    assert ok and price == 4500.0


def test_query_one_resource_malformed_nested():
    real = with_mocked_post({'head': {'code': 0}, 'data': {'routings': ['oops', {'prices': 'oops'}, None]}})
    ok, price, err, _prices = scraper.query_one_resource(FakeDate(), 'Ct', ('0317' + '1' * 16, 'x' * 16))
    restore_post(real)
    assert ok and price is None  # 全被跳過 → 視為無票，不崩潰


def test_state_safe_float_and_roundtrip():
    assert scraper.safe_float('abc', 1.5) == 1.5
    assert scraper.safe_float('4000') == 4000.0
    real_state = scraper.STATE_FILE
    try:
        scraper.STATE_FILE = os.path.join(tempfile.mkdtemp(prefix='test_scraper_state_'), 'state.json')
        state = scraper.load_state()
        assert state == {}
        scraper.save_state({'notified': {'2026-12-01': 4000}})
        assert scraper.load_state()['notified']['2026-12-01'] == 4000
    finally:
        if os.path.exists(scraper.STATE_FILE):
            os.remove(scraper.STATE_FILE)
        scraper.STATE_FILE = real_state


def test_run_scraper_dedups_notifications():
    sends = []
    real_send = scraper.send_notification_text
    real_query = scraper.query_one_resource
    real_state = scraper.STATE_FILE
    state_tmp = os.path.join(tempfile.mkdtemp(prefix='test_scraper_state_'), 'state.json')
    if os.path.exists(state_tmp):
        os.remove(state_tmp)
    scraper.send_notification_text = lambda text, log=None: sends.append(text) or 1
    scraper.STATE_FILE = state_tmp
    try:
        # gui 版 run_scraper 以 (date, resource_type, ids, log) 呼叫，mock 須接收 log
        scraper.query_one_resource = lambda date, rt, ids, log=None: (True, 3999.0, None, [3999.0])
        scraper.run_scraper(FUTURE, FUTURE)
        assert len(sends) == 1  # 第一次：發出通知
        scraper.run_scraper(FUTURE, FUTURE)
        assert len(sends) == 1  # 同價：不重發
        scraper.query_one_resource = lambda date, rt, ids, log=None: (True, 3000.0, None, [3000.0])
        scraper.run_scraper(FUTURE, FUTURE)
        assert len(sends) == 2  # 價格再跌：再發一次
    finally:
        scraper.send_notification_text = real_send
        scraper.query_one_resource = real_query
        scraper.STATE_FILE = real_state
        if os.path.exists(state_tmp):
            os.remove(state_tmp)


def test_notification_failure_not_marked_notified():
    """所有通知管道都失敗（send 回 0）時，不得標記已通知；下次執行必須再次提醒。"""
    sends = []
    real_send = scraper.send_notification_text
    real_query = scraper.query_one_resource
    real_state = scraper.STATE_FILE
    state_tmp = os.path.join(tempfile.mkdtemp(prefix='test_scraper_state_'), 'state.json')
    if os.path.exists(state_tmp):
        os.remove(state_tmp)
    scraper.send_notification_text = lambda text, log=None: sends.append(text) or 0
    scraper.STATE_FILE = state_tmp
    try:
        scraper.query_one_resource = lambda date, rt, ids, log=None: (True, 3000.0, None, [3000.0])
        scraper.run_scraper(FUTURE, FUTURE)
        scraper.run_scraper(FUTURE, FUTURE)
        assert len(sends) == 2  # 未標記已通知：兩次執行都嘗試發送
        # state 檔（若存在）不得含 notified 鍵
        if os.path.exists(state_tmp):
            with open(state_tmp, encoding='utf-8') as f:
                assert 'notified' not in json.load(f)
    finally:
        scraper.send_notification_text = real_send
        scraper.query_one_resource = real_query
        scraper.STATE_FILE = real_state
        if os.path.exists(state_tmp):
            os.remove(state_tmp)


def test_sanitize_masks_secrets():
    real_line = getattr(scraper.config, 'LINE_CHANNEL_ACCESS_TOKEN', '')
    real_tg = getattr(scraper.config, 'TELEGRAM_BOT_TOKEN', '')
    try:
        _test_sanitize_masks_secrets_body()
    finally:
        scraper.config.TELEGRAM_BOT_TOKEN = real_tg
        scraper.config.LINE_CHANNEL_ACCESS_TOKEN = real_line


def _test_sanitize_masks_secrets_body():
    scraper.config.TELEGRAM_BOT_TOKEN = 'TOKEN_SECRET_123'
    scraper.config.LINE_CHANNEL_ACCESS_TOKEN = 'LINE_SECRET_ABCDEF'
    leaked = 'Error for https://api.telegram.org/botTOKEN_SECRET_123/sendMessage and line https://api.line.me/v2/bot/message/push TOKEN_SECRET_123 LINE_SECRET_ABCDEF proxy http://u:p@127.0.0.1:1/x'
    out = scraper.sanitize(leaked)
    assert 'TOKEN_SECRET_123' not in out
    assert 'LINE_SECRET_ABCDEF' not in out
    assert 'u:p@' not in out
    # 連結不可被誤傷
    link = '連結: https://flight.eztravel.com.tw/tickets-oneway-spk-tpe/?outbounddate=01%2F12%2F2026'
    assert scraper.sanitize(link) == link
    assert '2026-12-01' in scraper.sanitize('日期: 2026-12-01')
    # config 無法 import 的語法錯誤場景：用樣式遮蔽
    leaked2 = "  File \"config.py\", line 3\nLINE_CHANNEL_ACCESS_TOKEN = 'FAKE_TOKEN_for_sanitize_test_0123456789abcdef'\n"
    out2 = scraper.sanitize(leaked2)
    assert 'FAKE_TOKEN_for_sanitize_test_0123456789abcdef' not in out2
    # v1 引號未閉合
    out3 = scraper.sanitize("LINE_CHANNEL_ACCESS_TOKEN = 'FAKE_TOKEN_for_sanitize_test_0123456789abcdef")
    assert 'FAKE_TOKEN_for_sanitize_test_0123456789abcdef' not in out3
    # v2 裸貼無引號（BotFather 標準複製法）
    out4 = scraper.sanitize('TELEGRAM_BOT_TOKEN = 000000000:FAKE_TEST_TOKEN_NOT_REAL_000000000000000')
    assert '000000000:FAKE_TEST_TOKEN_NOT_REAL_000000000000000' not in out4
    # v6 NameError 內嵌 secret
    out5 = scraper.sanitize("NameError: name 'fakegmailapppassword0xDEADBEEF1234567890' is not defined")
    assert 'fakegmailapppassword0xDEADBEEF1234567890' not in out5


def test_sanitize_never_crashes_on_nul():
    # 惡意/損毀的上游回應含 NUL：sanitize 不得丟例外（曾導致排程器長駐進程死亡）
    out = scraper.sanitize('日期 2026-12-01 \x0012\x00 後續')
    assert isinstance(out, str) and len(out) >= 0
    out2 = scraper.sanitize('\x00\x00\x00' + 'x' * 3000 + '\x00')
    assert isinstance(out2, str)


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'PASS {t.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL {t.__name__}: {e}')
        except Exception as e:
            failed += 1
            print(f'ERROR {t.__name__}: {e.__class__.__name__}: {e}')
    print(f'{len(tests) - failed}/{len(tests)} passed')
    sys.exit(1 if failed else 0)


# unittest discover 相容層：讓 `python3 -m unittest discover -s tests` 也能收集上面的函式式測試。
# 不變更任何既有測試函式；若不需要，刪除本段即可。
def _make_test(fn):
    def test(self):
        fn()
    test.__name__ = fn.__name__
    test.__doc__ = fn.__doc__
    return test


import unittest as _unittest  # noqa: E402


class TestScraperFunctions(_unittest.TestCase):
    pass


for _name, _fn in list(globals().items()):
    if _name.startswith('test_') and callable(_fn):
        setattr(TestScraperFunctions, _name, _make_test(_fn))
del _name, _fn


if __name__ == '__main__':
    run_all()
