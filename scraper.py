import sys
import re
import os
import json
import random
import string
import time
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)

try:
    import config
except ImportError:
    raise ValueError("找不到 config.py，請先執行: cp config.py.template config.py，並填入設定")

# Basic field validation for critical settings
# 注意：LINE/Gmail/Telegram 皆為選配管道，未設定即略過，不強制要求
required_config = ['START_DATE', 'END_DATE', 'TARGET_PRICE']

_MISSING = object()
for field in required_config:
    if getattr(config, field, _MISSING) is _MISSING:
        raise ValueError(f"config.py 缺少必要欄位: {field}")

try:
    config.TARGET_PRICE = float(config.TARGET_PRICE)
except (TypeError, ValueError):
    raise ValueError(f"config.py 格式錯誤: TARGET_PRICE 必須是數字（收到 {config.TARGET_PRICE!r}）")

# === ezTravel API 設定 ===
API_URL = 'https://flight.eztravel.com.tw/apiv2/flight/list'
APP_ID = '10101'
USER_AGENT = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
# 前端每次搜尋會同時查兩種資源（直營 / 聯營），任一單邊都會漏價，
# 因此預設兩種都查並取全域最低價。
_resource_types = getattr(config, 'RESOURCE_TYPES', ['Ct', 'EzTravel'])
if not isinstance(_resource_types, (list, tuple)) or not _resource_types:
    print(f"警告：RESOURCE_TYPES 必須是非空清單（收到 {_resource_types!r}），改用預設 ['Ct', 'EzTravel']")
    _resource_types = ['Ct', 'EzTravel']
RESOURCE_TYPES = [str(rt) for rt in _resource_types]
FROM_CITY = (getattr(config, 'FROM_CITY', 'SPK') or 'SPK').upper()
TO_CITY = (getattr(config, 'TO_CITY', 'TPE') or 'TPE').upper()
# 每個請求之間的禮貌性間隔（秒），避免連續轟炸 ezTravel
try:
    REQUEST_DELAY = max(0.0, float(getattr(config, 'REQUEST_DELAY_SECONDS', 0.7)))
except (TypeError, ValueError):
    print("警告：REQUEST_DELAY_SECONDS 必須是非負數字，改用預設 0.7 秒")
    REQUEST_DELAY = 0.7


# 通知去重狀態檔（記錄已通知的日期→價格），避免同一張便宜票在每次排程重複發送
# 注意：GUI 與 CLI 共用同一份狀態檔（同一目錄）
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.scraper_state.json')
FAILURE_ALERT_COOLDOWN_SECONDS = 6 * 3600  # 全部查詢失敗時的告警冷卻時間（6 小時）
MAX_FLIGHTS_PER_MESSAGE = 20               # 單則通知最多列出的筆數，避免超過 LINE/Telegram 長度上限


def load_state():
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except Exception as e:
        if os.path.exists(STATE_FILE):
            print(f"警告：狀態檔 {STATE_FILE} 讀取失敗（{e.__class__.__name__}），去重狀態已重置")
        return {}


def save_state(state):
    try:
        # 讀取現有狀態後合併再寫回，保留未知鍵以前向相容
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                current = json.load(f)
            if isinstance(current, dict):
                merged = {**current, **state}
            else:
                merged = state
        except Exception:
            merged = state
        tmp_path = STATE_FILE + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=1)
        os.replace(tmp_path, STATE_FILE)
    except Exception as e:
        print(f"警告：無法寫入狀態檔 {STATE_FILE}: {e}")


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sanitize(text):
    """遮蔽對外訊息中的機密：config 內的 token/密碼，以及 scheme://user:pass@host、Bearer 等樣式。

    注意：本函式同時存在於 scraper.py 與 run_schedule.py（scheduler 需在 scraper 壞掉時獨立運作），
    修改時請同步兩處。
    """
    try:
        s = _sanitize_impl(str(text), config)
    except Exception:
        # 脫敏自身失敗時，寧可遮掉整個訊息（fail-safe），也不能讓呼叫端崩潰
        return '***（脫敏失敗）'
    return s


def _sanitize_impl(s, config):
    for key in ('LINE_CHANNEL_ACCESS_TOKEN', 'GMAIL_PASSWORD', 'TELEGRAM_BOT_TOKEN'):
        val = getattr(config, key, '') or ''
        if isinstance(val, str) and len(val) >= 6 and not val.startswith('YOUR_'):
            s = s.replace(val, '***')
    # 先暫存日期（YYYY-MM-DD / DD/MM/YYYY），避免被下面的樣式遮蔽誤傷
    dates = []

    def keep_date(m):
        dates.append(m.group(0))
        return f'\x00{len(dates) - 1}\x00'

    s = re.sub(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}', keep_date, s)
    # scheme://user:pass@host → scheme://***@host
    s = re.sub(r'([a-z][a-z0-9+.-]*://)[^/@:\s]+:[^/@\s]+@', r'\1***@', s, flags=re.IGNORECASE)
    # 設定檔無法 import 時（語法錯誤）的樣式遮蔽（引號可有可無、可不閉合），(?!//) 保護連結
    s = re.sub(r"([=:]\s*['\"]?)(?!//)[A-Za-z0-9_\-/+=.\-]{24,}", r"\1***", s)
    # 含空格的引號內容（如 'abcd efgh ijkl mnop'）→ 引號完整與未閉合各遮一次
    s = re.sub(r"'[^'\n]{12,}'", "'***'", s)
    s = re.sub(r"([=:]\s*['\"])[^'\n]{12,}", r"\1***", s)
    s = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.=]+", "Bearer ***", s, flags=re.IGNORECASE)
    # 還原日期（越界索引回退為空字串）
    s = re.sub(r'\x00(\d+)\x00', lambda m: dates[int(m.group(1))] if int(m.group(1)) < len(dates) else '', s)
    return s


def generate_ids():
    """產生與前端相同格式的 clientID / transactionID（每次執行隨機）。"""
    client_id = '0317' + ''.join(random.choices(string.digits, k=16))
    transaction_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
    return client_id, transaction_id


def parse_price(value):
    """價格容錯解析：數字直接轉 float，字串去除非數字字元後轉 float。無法解析則回傳 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r'[^\d.]', '', str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def send_notification_text(text):
    """將純文字訊息送出到所有已啟用且已設定的通知管道（LINE / Email / Telegram）。

    各管道獨立 try/except，單一管道失敗不影響其他管道。
    """
    # 1. Send LINE Notification (Messaging API v3)
    if not getattr(config, 'LINE_ENABLE', True):
        print("LINE 通知已停用，跳過發送。")
    else:
        line_token = getattr(config, 'LINE_CHANNEL_ACCESS_TOKEN', '') or ''
        line_user_id = getattr(config, 'LINE_USER_ID', '') or ''
        try:
            if not line_token or not line_user_id or line_token.startswith('YOUR_') or line_user_id.startswith('YOUR_'):
                print("LINE 通知未設定（LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID 缺一或未修改），略過。")
            else:
                configuration = Configuration(access_token=line_token)
                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    text_message = TextMessage(text=text)
                    push_message_request = PushMessageRequest(
                        to=line_user_id,
                        messages=[text_message]
                    )
                    line_bot_api.push_message(push_message_request)
                    print("LINE notification sent successfully.")
        except Exception as e:
            print(f"Failed to send LINE notification: {e.__class__.__name__}: {sanitize(e)}")

    # 2. Send Email Notification
    if not getattr(config, 'EMAIL_ENABLE', True):
        print("Email 通知已停用，跳過發送。")
    else:
        gmail_password = getattr(config, 'GMAIL_PASSWORD', '') or ''
        try:
            gmail_user = getattr(config, 'GMAIL_USER', '') or ''
            to_email = getattr(config, 'TO_EMAIL', '') or ''
            if not gmail_user or not gmail_password or gmail_user.startswith('YOUR_') or gmail_password.startswith('YOUR_'):
                print("Email 通知未設定（GMAIL_USER / GMAIL_PASSWORD 缺一或未修改），略過。")
            elif not to_email or to_email.startswith('RECEIVER_'):
                print("Email 通知未設定（TO_EMAIL 缺或未修改），略過。")
            else:
                msg = MIMEMultipart()
                msg['From'] = gmail_user
                msg['To'] = to_email
                msg['Subject'] = "【便宜機票通知】易遊網爬蟲結果"
                msg.attach(MIMEText(text, 'plain', 'utf-8'))

                context = ssl.create_default_context()
                with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
                    server.starttls(context=context)
                    server.login(gmail_user, gmail_password)
                    server.send_message(msg)
                print("Email notification sent successfully.")
        except Exception as e:
            print(f"Failed to send Email notification: {e.__class__.__name__}: {sanitize(e)}")

    # 3. Send Telegram Notification（選配：同時設定 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID 才啟用）
    if not getattr(config, 'TELEGRAM_ENABLE', True):
        print("Telegram 通知已停用，跳過發送。")
    else:
        telegram_token = getattr(config, 'TELEGRAM_BOT_TOKEN', '') or ''
        telegram_chat_id = getattr(config, 'TELEGRAM_CHAT_ID', '') or ''
        if telegram_token and telegram_chat_id:
            try:
                tg_text = text
                if len(tg_text) > 4000:  # Telegram 上限 4096 字，保留餘裕
                    tg_text = tg_text[:4000] + "\n…(訊息過長已截斷)"
                resp = requests.post(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    json={
                        "chat_id": telegram_chat_id,
                        "text": tg_text,
                        "disable_web_page_preview": True,
                    },
                    timeout=10,
                )
                try:
                    body = resp.json()
                except ValueError:
                    body = {}
                if resp.status_code == 200 and body.get("ok"):
                    print("Telegram notification sent successfully.")
                else:
                    desc = sanitize(body.get("description", resp.text[:200]) if isinstance(body, dict) else resp.text[:200])
                    print(f"Failed to send Telegram notification: HTTP {resp.status_code} {desc}")
            except Exception as e:
                print(f"Failed to send Telegram notification: {e.__class__.__name__}: {sanitize(e)}")
        elif telegram_token or telegram_chat_id:
            print("Telegram 通知未啟用：TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID 必須同時設定，已略過。")


def build_found_message(found_flights):
    message_body = "機票爬蟲任務 - 發現便宜機票！\n（價格即時變動，請以下單頁為準）\n\n"
    shown_flights = found_flights[:MAX_FLIGHTS_PER_MESSAGE]
    for flight in shown_flights:
        message_body += (
            f"日期: {flight['date']}\n"
            f"價格: NT$ {flight['price']:,.0f}（門檻 NT$ {config.TARGET_PRICE:,.0f}）\n"
            f"連結: {flight['link']}\n\n"
        )
    if len(found_flights) > MAX_FLIGHTS_PER_MESSAGE:
        message_body += f"…其餘 {len(found_flights) - MAX_FLIGHTS_PER_MESSAGE} 筆已略，完整清單請看爬蟲 log。\n"
    return message_body


def record_to_excel(results, start_date_str, end_date_str, log=print):
    """將爬蟲結果記錄到 Excel，格式參考用戶提供圖片"""
    if not getattr(config, 'EXCEL_ENABLE', False):
        return

    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.utils.exceptions import InvalidFileException
        import zipfile
    except ImportError:
        log("缺少 openpyxl，跳過 Excel 記錄")
        return

    filename = getattr(config, 'EXCEL_FILENAME', 'flight_prices.xlsx')
    raw_top_n = getattr(config, 'EXCEL_TOP_N', 3)
    try:
        top_n = int(raw_top_n)
    except (TypeError, ValueError):
        log(f"EXCEL_TOP_N 格式錯誤（{raw_top_n!r}），改用預設 3")
        top_n = 3
    # Excel 上限 16384 欄，限制 top_n 避免產生過大的表頭
    top_n = max(1, min(top_n, 20))

    # 解析日期範圍
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    # 準備表頭
    headers = ["Time"]
    for d in date_range:
        d_str = d.strftime('%m/%d')
        for i in range(1, top_n + 1):
            headers.append(f"{d_str} - {i}")

    # 載入或建立活頁簿
    if os.path.exists(filename):
        try:
            wb = load_workbook(filename)
            ws = wb.active
        except (OSError, ValueError, KeyError, SyntaxError, zipfile.BadZipFile, InvalidFileException) as e:
            # 原檔可能損毀：先備份再重建，絕不覆蓋原檔（寧可不記，不毀歷史資料）
            backup = f"{filename}.bak-{datetime.now():%Y%m%d-%H%M%S}"
            try:
                os.replace(filename, backup)
            except OSError as be:
                log(f"Excel 檔案損毀（{e.__class__.__name__}: {e}），且備份原檔失敗（{be.__class__.__name__}: {be}），為避免覆蓋原檔，已略過 Excel 記錄")
                return
            log(f"Excel 檔案損毀（{e.__class__.__name__}: {e}），已備份原檔至 {backup}，重新建立新 Excel")
            wb = Workbook()
            ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active

    # 找出最後一個「Time」表頭列，並記錄最後一列是否為全空列
    # （用 iter_rows 讀取，避免在全新活頁簿上建立 cell 而產生前導空列）
    # 相同則只附加資料列；不同 / 不存在 / 檔案全新則先補表頭（已有資料時先空一行分隔）
    last_header_values = None
    last_row_values = ()
    for row in ws.iter_rows(values_only=True):
        row_values = list(row)
        if row_values and row_values[0] == "Time":
            last_header_values = row_values
        last_row_values = row_values
    while last_row_values and last_row_values[-1] is None:
        last_row_values.pop()
    if last_header_values is not None:
        while last_header_values and last_header_values[-1] is None:
            last_header_values.pop()
    if last_header_values != headers:
        if any(v is not None for v in last_row_values):
            ws.append([]) # 空行分隔
        ws.append(headers)

    # 準備當次數據行
    row_data = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]

    # 建立結果查找字典 (日期 -> 排序後的價格列表)
    results_map = {}
    for r in results:
        d = r['date']
        if d not in results_map:
            results_map[d] = []
        results_map[d].append(r['price'])

    for d in date_range:
        d_key = d.strftime('%Y-%m-%d')
        prices = sorted(set(results_map.get(d_key, [])))
        for i in range(top_n):
            if i < len(prices):
                row_data.append(prices[i])
            else:
                row_data.append("") # 無資料填空

    ws.append(row_data)
    wb.save(filename)
    log(f"數據已記錄至 Excel: {filename}")


def query_one_resource(date_obj, resource_type, ids, log=print):
    """查詢單一 resourceType；回傳 (ok, min_price, error_message, prices)。"""
    client_id, transaction_id = ids
    payload = {
        'head': {
            'clientID': client_id,
            'transactionID': transaction_id,
            'userAgent': USER_AGENT,
            'appid': APP_ID,
        },
        'data': {
            'journeyType': 1,
            'cabinType': 'Any',
            'airlineCode': '',
            'adultCnt': 1,
            'childCnt': 0,
            'infantCnt': 0,
            'isDirectFlight': False,
            'outboundDate': date_obj.strftime('%d/%m/%Y'),
            'fromCityCode': FROM_CITY,
            'toCityCode': TO_CITY,
            'fromAirportCode': '',
            'toAirportCode': '',
            'resourceType': resource_type,
        },
    }
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'appid': APP_ID,
        'clientid': client_id,
        'transactionid': transaction_id,
        'Origin': 'https://flight.eztravel.com.tw',
        'Referer': f'https://flight.eztravel.com.tw/tickets-oneway-{FROM_CITY.lower()}-{TO_CITY.lower()}/',
        'User-Agent': USER_AGENT,
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    except requests.RequestException as e:
        return False, None, f"請求失敗: {e.__class__.__name__}: {sanitize(e)}", []

    try:
        body = response.json()
    except ValueError:
        return False, None, f"HTTP {response.status_code}，回應不是 JSON（前 200 字: {sanitize(response.text[:200])}）", []

    if not isinstance(body, dict):
        return False, None, f"HTTP {response.status_code}，回應不是 JSON 物件（型別 {type(body).__name__}）", []

    head = body.get('head')
    if not isinstance(head, dict):
        head = {}
    code = head.get('code')
    if code != 0:
        # 400405 = 參數無效（程式 bug，不應重試）；其他錯誤也一律回報
        return False, None, f"HTTP {response.status_code}，head.code={code}，message={head.get('message', '')}", []

    data = body.get('data')
    if data is None:
        # 過去日期 / 無航班時 ezTravel 回 code:0 且 data:null，屬「當日無票」而非錯誤
        return True, None, None, []
    if not isinstance(data, dict):
        return False, None, f"回應結構異常：data 型別 {type(data).__name__}", []

    routings = data.get('routings')
    if routings is None:
        return True, None, None, []
    if not isinstance(routings, list):
        return False, None, f"回應結構異常：routings 型別 {type(routings).__name__}", []

    prices = []
    had_routings = False
    for routing in routings:
        if not isinstance(routing, dict):
            continue
        price_list = routing.get('prices')
        if not isinstance(price_list, list):
            continue
        if price_list:
            had_routings = True
        for price_info in price_list:
            if not isinstance(price_info, dict):
                continue
            price = parse_price(price_info.get('price'))
            if price is not None:
                prices.append(price)

    if had_routings and not prices:
        log(f"警告：{date_obj.strftime('%Y-%m-%d')} {resource_type} 有航班資料但價格全部解析失敗，ezTravel 回應格式可能已變更")

    return True, (min(prices) if prices else None), None, prices


def run_scraper(start_date_str, end_date_str, log_callback=None):
    """執行一次完整的爬蟲流程（抓取、Excel 記錄、通知）。

    心跳契約：log_callback 可拋 KeyboardInterrupt 以中斷監控流程（GUI 停止鈕依賴此行為），
    任何例外包裝都不得吞掉 KeyboardInterrupt。
    """
    def log(message):
        if log_callback is not None:
            log_callback(message)
        elif message:
            print(message)

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"日期格式錯誤：START_DATE/END_DATE 必須是 YYYY-MM-DD（收到 '{start_date_str}' ~ '{end_date_str}'）")

    if end_date < start_date:
        raise ValueError(f"START_DATE ({start_date_str}) 晚於 END_DATE ({end_date_str})，請修改 config.py")

    if end_date.date() < datetime.now().date():
        raise ValueError(f"END_DATE ({end_date_str}) 已過期（所有日期皆為過去），ezTravel 對過去日期只會回 data:null。請更新 config.py")

    today = datetime.now().date()
    if start_date.date() < today:
        log(f"警告：START_DATE ({start_date_str}) 在過去，已自動裁切至今天 {today.strftime('%Y-%m-%d')}")
        start_date = datetime.combine(today, datetime.min.time())

    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
    if len(date_range) > 62:
        if os.environ.get('EZTRAVEL_ALLOW_LONG_RANGE') != '1':
            raise ValueError(f"日期範圍 {len(date_range)} 天超過 62 天上限（{len(date_range) * len(RESOURCE_TYPES)} 次請求）：為避免對 ezTravel 造成過大負擔已拒絕執行。\n若確定要執行，請設環境變數 EZTRAVEL_ALLOW_LONG_RANGE=1 後再試。")
        log(f"警告：日期範圍 {len(date_range)} 天偏大（已用 EZTRAVEL_ALLOW_LONG_RANGE=1 放行），請求數會是 {len(date_range) * len(RESOURCE_TYPES)} 次")

    found_cheap_flights = []
    all_price_entries = []  # 所有解析成功的價格條目（date→prices），供 Excel 記錄；只有門檻內的才進通知清單
    success_days = 0
    fail_days = []
    ok_resource_calls = 0  # 成功的 resourceType 請求次數（HTTP ok 且 head.code==0）
    link_base = f"https://flight.eztravel.com.tw/tickets-oneway-{FROM_CITY.lower()}-{TO_CITY.lower()}/"

    for idx, date in enumerate(date_range):
        log(None)  # 心跳：傳入 None 讓 GUI 檢查停止旗標，log 內會略過輸出
        is_last_day = idx == len(date_range) - 1
        ids = generate_ids()  # transactionID/clientID 每次執行隨機，避免被當作重複交易去重
        day_min = None
        day_errors = []
        day_any_ok = False
        day_link = f"{link_base}?outbounddate={date.strftime('%d%%2F%m%%2F%Y')}"  # 每日連結與 resourceType 無關，只算一次
        for resource_type in RESOURCE_TYPES:
            ok, min_price, error, prices = query_one_resource(date, resource_type, ids, log)
            if ok:
                day_any_ok = True
                ok_resource_calls += 1
                for p in prices:
                    all_price_entries.append({
                        "date": date.strftime('%Y-%m-%d'),
                        "price": p,
                        "link": day_link,
                    })
                if min_price is not None:
                    day_min = min_price if day_min is None else min(day_min, min_price)
            else:
                day_errors.append(f"{resource_type}: {error}")
            if not is_last_day:
                time.sleep(REQUEST_DELAY)

        if day_min is not None:
            # 至少一種 resourceType 成功：照常評估門檻（部分失敗僅警告）
            success_days += 1
            if day_errors:
                log(f"警告：{date.strftime('%Y-%m-%d')} 部分查詢失敗（僅依未失敗的來源取價，可能漏掉較便宜的票）: {'; '.join(day_errors)}")
            log(f"已抓取 {date.strftime('%Y-%m-%d')} 票價，當日最低價(含稅): NT$ {day_min:,.0f}")
            if day_min <= config.TARGET_PRICE:
                found_cheap_flights.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "price": day_min,
                    "link": day_link,
                })
        elif day_any_ok:
            # 至少一個來源成功但當日無票（過去日期 / 無航班 → data:null）
            success_days += 1
            if day_errors:
                log(f"警告：{date.strftime('%Y-%m-%d')} 部分來源失敗（當日依成功來源判無票）: {'; '.join(day_errors)}")
            log(f"已抓取 {date.strftime('%Y-%m-%d')} 票價，當日無票價資訊")
        else:
            # 所有來源都失敗
            fail_days.append(date.strftime('%Y-%m-%d'))
            log(f"查詢 {date.strftime('%Y-%m-%d')} 失敗: {'; '.join(day_errors)}")

    # Excel 記錄（記錄當日全部票價，不論是否低於 TARGET_PRICE 門檻）先於通知執行，兩段流程有耦合：
    # record_to_excel 若拋出例外會中斷整個通知流程（便宜機票通知會靜默遺失），
    # 因此此處必須獨立 try/except，不得讓 Excel 失敗影響通知。
    if all_price_entries:
        try:
            record_to_excel(all_price_entries, start_date_str, end_date_str, log)
        except Exception as e:
            log(f"Excel 記錄失敗（{e.__class__.__name__}: {e}），已略過 Excel，繼續執行通知流程")

    summary_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = load_state()
    if ok_resource_calls == 0 and date_range:
        log(f"[{summary_time}] 全部查詢失敗（{len(date_range) * len(RESOURCE_TYPES)} 次請求皆未成功），ezTravel API 可能已變更或網路異常")
        last_alert = safe_float(state.get('last_failure_alert', 0))
        if time.time() - last_alert > FAILURE_ALERT_COOLDOWN_SECONDS:
            send_notification_text(
                f"機票爬蟲任務 - 全部查詢失敗！\n"
                f"範圍: {date_range[0].strftime('%Y-%m-%d')} ~ {end_date_str}（{len(date_range)} 個日期）\n"
                f"失敗範例: {'; '.join(fail_days[:3])}\n"
                f"請檢查網路連線與 ezTravel API 是否變更。"
            )
            state['last_failure_alert'] = time.time()
            save_state(state)
        else:
            log("（全部查詢失敗告警在冷卻期內，略過本次通知）")
    elif found_cheap_flights:
        # 去重：同日期同價或更高價已通知過 → 不重發；只有新日期或價格再跌才通知
        notified = state.get('notified', {}) if isinstance(state.get('notified', {}), dict) else {}
        new_items = [
            f for f in found_cheap_flights
            if f['date'] not in notified or f['price'] < safe_float(notified[f['date']], float('inf'))
        ]
        if new_items:
            msg = build_found_message(new_items)
            skipped = len(found_cheap_flights) - len(new_items)
            if skipped:
                msg += f"（其餘 {skipped} 筆價格未再下跌，已通知過，未重發）\n"
            log(f"[{summary_time}] Found {len(new_items)} new flights under budget!")
            send_notification_text(msg)
            for f in new_items:
                notified[f['date']] = f['price']
            state['notified'] = notified
            save_state(state)
        else:
            log(f"[{summary_time}] 便宜機票與先前通知相同（價格未再下跌），略過重複通知。")
    else:
        log(f"[{summary_time}] No flights under target price.")

    if fail_days:
        log(f"[{summary_time}] 成功 {success_days} 天 / 失敗 {len(fail_days)} 天: {', '.join(fail_days)}")

    return found_cheap_flights


if __name__ == "__main__":
    # 使用 config.py 中設定的日期範圍
    try:
        run_scraper(config.START_DATE, config.END_DATE)
    except ValueError as e:
        print(e)
        sys.exit(1)
