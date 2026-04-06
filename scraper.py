import requests
import pandas as pd
from datetime import datetime, timedelta
import heapq
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
import os
import copy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import external configurations
try:
    import config
    import credentials
    
    # Basic field validation for critical settings
    required_config = ['LINE_CHANNEL_ACCESS_TOKEN', 'LINE_USER_ID', 'START_DATE', 'END_DATE', 'TARGET_PRICE']
    required_creds = ['cookies', 'headers', 'json_data']
    
    for field in required_config:
        if not hasattr(config, field): raise AttributeError
    for field in required_creds:
        if not hasattr(credentials, field): raise AttributeError
        
except (ImportError, AttributeError):
    print("檔案格式錯誤 (config.py 或 credentials.py 缺失或格式不正確)")
    exit(1)

# === Configuration ===
configuration = Configuration(access_token=config.LINE_CHANNEL_ACCESS_TOKEN)

def send_notifications(found_flights):
    if not found_flights:
        return

    message_body = "機票爬蟲任務 - 發現便宜機票！\n\n"
    for flight in found_flights:
        message_body += f"日期: {flight['date']}\n價格: {flight['price']}\n連結: {flight['link']}\n\n"

    # 1. Send LINE Notification (v3)
    if getattr(config, 'LINE_ENABLE', True):
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                text_message = TextMessage(text=message_body)
                push_message_request = PushMessageRequest(
                    to=config.LINE_USER_ID,
                    messages=[text_message]
                )
                line_bot_api.push_message(push_message_request)
                print("LINE notification sent successfully.")
        except Exception as e:
            print(f"Failed to send LINE notification: {e}")
    else:
        print("LINE 通知已停用，跳過發送。")

    # 2. Send Email Notification
    if getattr(config, 'EMAIL_ENABLE', True):
        try:
            msg = MIMEMultipart()
            msg['From'] = config.GMAIL_USER
            msg['To'] = config.TO_EMAIL
            msg['Subject'] = "【便宜機票通知】易遊網爬蟲結果"
            msg.attach(MIMEText(message_body, 'plain'))

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(config.GMAIL_USER, config.GMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            print("Email notification sent successfully.")
        except Exception as e:
            print(f"Failed to send Email notification: {e}")
    else:
        print("Email 通知已停用，跳過發送。")

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font
import os

def record_to_excel(results, start_date_str, end_date_str):
    """將爬蟲結果記錄到 Excel，格式參考用戶提供圖片"""
    if not getattr(config, 'EXCEL_ENABLE', False):
        return
    
    filename = getattr(config, 'EXCEL_FILENAME', 'flight_prices.xlsx')
    top_n = int(getattr(config, 'EXCEL_TOP_N', 3))
    
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
        except:
            wb = Workbook()
            ws = wb.active
            ws.append(headers)
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(headers)

    # 檢查現有表頭是否匹配，若不匹配則在下方重新插入一組新表頭（不破壞公式）
    current_headers = [cell.value for cell in ws[1]] if ws.max_row >= 1 else []
    if current_headers != headers:
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
        prices = sorted(results_map.get(d_key, []))
        for i in range(top_n):
            if i < len(prices):
                row_data.append(prices[i])
            else:
                row_data.append("") # 無資料填空
                
    ws.append(row_data)
    wb.save(filename)
    print(f"數據已記錄至 Excel: {filename}")

def run_scraper(start_date_str, end_date_str, trip_type="機票爬蟲任務", log_callback=None):
    def log(message):
        if log_callback:
            log_callback(message)
        else:
            print(message)

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found_cheap_flights = []

    # Use the full template from credentials.py
    base_payload = credentials.json_data
    
    # 動態產生連結基礎 (根據 credentials 中的起降城市代碼)
    from_city = base_payload.get('data', {}).get('fromCityCode', 'SPK').lower()
    to_city = base_payload.get('data', {}).get('toCityCode', 'TPE').lower()
    link_base = f"https://flight.eztravel.com.tw/tickets-oneway-{from_city}-{to_city}/"

    for date in date_range:
        # 檢查是否需要終止
        if log_callback:
            try:
                log_callback(None) # 傳入 None 作為心跳檢查
            except Exception:
                log("任務已被使用者手動中止。")
                return found_cheap_flights

        outbound_date = date.strftime('%d/%m/%Y')
        
        # Create a deep copy to avoid modifying the template, and update the date
        payload = copy.deepcopy(base_payload)
        
        # Ensure the nested data/outboundDate structure exists before updating
        if 'data' in payload:
            payload['data']['outboundDate'] = outbound_date
        else:
            log("警告: 在 credentials.py 的 json_data 中找不到 'data' 鍵值")
            continue

        try:
            response = requests.post(
                'https://flight.eztravel.com.tw/apiv2/flight/list',
                cookies=credentials.cookies,
                headers=credentials.headers,
                json=payload,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                prices = []
                # Extraction logic for eztravel response structure
                if "data" in data and "routings" in data["data"]:
                    for routing in data["data"]["routings"]:
                        for p in routing.get("prices", []):
                            prices.append(p["price"])
                
                if prices:
                    min_price = min(prices)
                    log(f"已抓取 {date.strftime('%Y-%m-%d')} 票價，當日最低價: {min_price}")
                    
                    # 收集當日所有票價以便 Excel 記錄 (不論是否低於 TARGET_PRICE)
                    for p in prices:
                        found_cheap_flights.append({
                            "date": date.strftime('%Y-%m-%d'),
                            "price": p,
                            "link": f"{link_base}?outbounddate={date.strftime('%d%%2F%m%%2F%Y')}"
                        })
                else:
                    log(f"已抓取 {date.strftime('%Y-%m-%d')} 票價，當日無票價資訊")
            else:
                log(f"錯誤: HTTP {response.status_code} (日期: {outbound_date})")
        except Exception as e:
            log(f"例外狀況 ({outbound_date}): {e}")

    if found_cheap_flights:
        # 1. Excel 記錄邏輯 (記錄完整原始數據)
        record_to_excel(found_cheap_flights, start_date_str, end_date_str)
        
        # 2. 通知邏輯 (僅針對低於 TARGET_PRICE 的最低價進行通知)
        notify_list = []
        date_min_prices = {}
        for f in found_cheap_flights:
            d = f['date']
            if d not in date_min_prices or f['price'] < date_min_prices[d]['price']:
                date_min_prices[d] = f
        
        for f in date_min_prices.values():
            if f['price'] <= config.TARGET_PRICE:
                notify_list.append(f)
        
        if notify_list:
            log(f"[{current_time}] 發現 {len(notify_list)} 筆低於目標價的機票，發送通知中...")
            send_notifications(notify_list)
        else:
            log(f"[{current_time}] 未發現低於目標價的機票 (已記錄至 Excel)。")
    else:
        log(f"[{current_time}] 任務完成，無任何回傳票價資料。")
    
    return found_cheap_flights

if __name__ == "__main__":
    # 使用 config.py 中設定的日期範圍
    run_scraper(config.START_DATE, config.END_DATE)
