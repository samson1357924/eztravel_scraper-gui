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

# === Configuration (Use Environment Variables for Security) ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_TOKEN_HERE')
LINE_USER_ID = os.getenv('LINE_USER_ID', 'YOUR_USER_ID_HERE')

GMAIL_USER = os.getenv('GMAIL_USER', 'YOUR_EMAIL@gmail.com')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD', 'YOUR_APP_PASSWORD')
TO_EMAIL = os.getenv('TO_EMAIL', 'RECEIVER_EMAIL@gmail.com')
TARGET_PRICE = int(os.getenv('TARGET_PRICE', 3000))

file_name = "ticket_data.xlsx"

# Scraper configuration (Update these using the F12 -> cURL method described in README)
cookies = {
    # 'visid_incap_xxx': '...',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'appid': '10101',
    'Origin': 'https://flight.eztravel.com.tw',
}

json_data_template = {
    'head': {
        'clientID': 'REPLACE_ME',
        'transactionID': 'REPLACE_ME',
        'appid': '10101',
    },
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

def run_scraper(start_date_str, end_date_str, trip_type="去程"):
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_data = {'Time': current_time, '行程': trip_type}
    found_cheap_flights = []

    for date in date_range:
        outbound_date = date.strftime('%d/%m/%Y')
        payload = json_data_template.copy()
        payload['data']['outboundDate'] = outbound_date

        try:
            response = requests.post(
                'https://flight.eztravel.com.tw/apiv2/flight/list',
                cookies=cookies,
                headers=headers,
                json=payload,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                prices = []
                for routing in data.get("data", {}).get("routings", []):
                    for p in routing.get("prices", []):
                        prices.append(p["price"])
                
                if prices:
                    min_prices = heapq.nsmallest(3, prices)
                    if min_prices[0] <= TARGET_PRICE:
                        found_cheap_flights.append({
                            "date": date.strftime('%Y-%m-%d'),
                            "price": min_prices[0],
                            "link": f"https://flight.eztravel.com.tw/tickets-oneway-tpe-spk/?outbounddate={date.strftime('%d%%2F%m%%2F%Y')}"
                        })
                
                    for j in range(3):
                        row_data[f"{date.strftime('%m/%d')} - {j+1}"] = min_prices[j] if len(min_prices) > j else None
            else:
                print(f"Error: {response.status_code} for {outbound_date}")
        except Exception as e:
            print(f"Exception for {outbound_date}: {e}")

    # Save to Excel and send notifications (Logic omitted for brevity in this cleaned template)
    # Refer to original scripts for full implementation.
    print(f"Scrape completed for {trip_type}. Found {len(found_cheap_flights)} cheap flights.")
    return found_cheap_flights

if __name__ == "__main__":
    run_scraper('2026-03-10', '2026-03-20')
