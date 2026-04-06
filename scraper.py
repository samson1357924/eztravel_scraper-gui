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
import config
import credentials

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

def run_scraper(start_date_str, end_date_str, trip_type="機票爬蟲任務"):
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found_cheap_flights = []

    # Use the full template from credentials.py
    base_payload = credentials.json_data

    for date in date_range:
        outbound_date = date.strftime('%d/%m/%Y')
        
        # Create a deep copy to avoid modifying the template, and update the date
        payload = copy.deepcopy(base_payload)
        
        # Ensure the nested data/outboundDate structure exists before updating
        if 'data' in payload:
            payload['data']['outboundDate'] = outbound_date
        else:
            print("Warning: 'data' key not found in json_data from credentials.py")
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
                    if min_price <= config.TARGET_PRICE:
                        found_cheap_flights.append({
                            "date": date.strftime('%Y-%m-%d'),
                            "price": min_price,
                            "link": f"https://flight.eztravel.com.tw/tickets-oneway-spk-tpe/?outbounddate={date.strftime('%d%%2F%m%%2F%Y')}"
                        })
            else:
                print(f"Error: {response.status_code} for {outbound_date}")
        except Exception as e:
            print(f"Exception for {outbound_date}: {e}")

    if found_cheap_flights:
        print(f"[{current_time}] Found {len(found_cheap_flights)} flights under budget!")
        send_notifications(found_cheap_flights)
    else:
        print(f"[{current_time}] No flights under target price.")
    
    return found_cheap_flights

if __name__ == "__main__":
    # Default search range
    run_scraper('2026-06-01', '2026-07-01')
