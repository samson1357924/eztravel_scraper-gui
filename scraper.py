import requests
import pandas as pd
from datetime import datetime, timedelta
import heapq
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from linebot import LineBotApi
from linebot.models import TextSendMessage
import os

# Import external configurations
import config
import credentials

# === Configuration ===
line_bot_api = LineBotApi(config.LINE_CHANNEL_ACCESS_TOKEN)

json_data_template = {
    'head': credentials.payload_head,
    'data': {
        'journeyType': 1,
        'cabinType': 'Any',
        'adultCnt': 1,
        'isDirectFlight': True,
        'fromCityCode': 'TPE',
        'toCityCode': 'SPK',
        'resourceType': 'Ct',
    },
}

def run_scraper(start_date_str, end_date_str, trip_type="機票爬蟲任務"):
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found_cheap_flights = []

    for date in date_range:
        outbound_date = date.strftime('%d/%m/%Y')
        payload = json_data_template.copy()
        payload['data']['outboundDate'] = outbound_date

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
                # Extraction logic from routings
                for routing in data.get("data", {}).get("routings", []):
                    for p in routing.get("prices", []):
                        prices.append(p["price"])
                
                if prices:
                    min_price = min(prices)
                    if min_price <= config.TARGET_PRICE:
                        found_cheap_flights.append({
                            "date": date.strftime('%Y-%m-%d'),
                            "price": min_price,
                            "link": f"https://flight.eztravel.com.tw/tickets-oneway-tpe-spk/?outbounddate={date.strftime('%d%%2F%m%%2F%Y')}"
                        })
            else:
                print(f"Error: {response.status_code} for {outbound_date}")
        except Exception as e:
            print(f"Exception for {outbound_date}: {e}")

    # Simplified summary output for demonstration
    if found_cheap_flights:
        print(f"[{current_time}] Found {len(found_cheap_flights)} flights under budget!")
    else:
        print(f"[{current_time}] No flights under target price.")
    
    return found_cheap_flights

if __name__ == "__main__":
    # Default search range
    run_scraper('2026-03-10', '2026-03-20')
