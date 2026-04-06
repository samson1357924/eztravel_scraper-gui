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

    # 2. Send Email Notification
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
                    if min_price <= config.TARGET_PRICE:
                        found_cheap_flights.append({
                            "date": date.strftime('%Y-%m-%d'),
                            "price": min_price,
                            "link": f"{link_base}?outbounddate={date.strftime('%d%%2F%m%%2F%Y')}"
                        })
                else:
                    log(f"已抓取 {date.strftime('%Y-%m-%d')} 票價，當日無票價資訊")
            else:
                log(f"錯誤: HTTP {response.status_code} (日期: {outbound_date})")
        except Exception as e:
            log(f"例外狀況 ({outbound_date}): {e}")

    if found_cheap_flights:
        log(f"[{current_time}] 任務完成！發現 {len(found_cheap_flights)} 筆低於目標價的機票。")
        send_notifications(found_cheap_flights)
    else:
        log(f"[{current_time}] 任務完成，未發現低於目標價的機票。")
    
    return found_cheap_flights

if __name__ == "__main__":
    # 使用 config.py 中設定的日期範圍
    run_scraper(config.START_DATE, config.END_DATE)
