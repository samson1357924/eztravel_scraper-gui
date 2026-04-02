# eztravel_scraper

一個基於 Python 的 eztravel (易遊網) 機票爬蟲，具備 Email 與 LINE 通知功能。

## 專案結構
- `scraper.py`: 爬蟲主程式。
- `run_schedule.py`: 排程執行器（每 15 分鐘執行一次）。
- `config.py`: 個人設定（LINE Token、Email、目標價格）。
- `credentials.py`: 爬蟲驗證資料（Cookies、Headers、Payload Head）。

## 教學：如何獲取最新的 Credentials
eztravel 有防爬蟲機制，請依照以下步驟更新 `credentials.py`：

1. 開啟瀏覽器前往 [eztravel 機票搜尋頁面](https://flight.eztravel.com.tw/)。
2. 按下 `F12` 開啟開發者工具，切換到 **Network** 分頁。
3. 執行一次搜尋，找到名稱為 `list` 的 POST 請求。
4. 右鍵點擊該請求 -> **Copy** -> **Copy as cURL (bash)**。
5. 前往 [curlconverter.com](https://curlconverter.com/) 並貼上。
6. 將產生的內容分別填入 `credentials.py` 中的 `cookies`、`headers` 與 `payload_head` (即 json_data 中的 head 區塊)。

## 安裝與使用
1. 安裝依賴：`pip install requests pandas openpyxl line-bot-sdk schedule`
2. 在 `config.py` 填入你的通知資訊。
3. 在 `credentials.py` 填入獲取的驗證資料。
4. 執行：`python run_schedule.py`

---

# eztravel_scraper

A Python-based scraper for eztravel flight tickets with automated Email and LINE notifications.

## Project Structure
- `scraper.py`: Main scraper logic.
- `run_schedule.py`: Scheduler (runs every 15 minutes).
- `config.py`: Personal settings (Tokens, Emails, Target Price).
- `credentials.py`: Scraper credentials (Cookies, Headers, Payload Head).

## Tutorial: How to obtain Credentials
Update `credentials.py` using these steps:

1. Open browser to [eztravel flight search](https://flight.eztravel.com.tw/).
2. Press `F12`, go to **Network** tab.
3. Perform a search, locate the `list` POST request.
4. Right-click -> **Copy** -> **Copy as cURL (bash)**.
5. Use [curlconverter.com](https://curlconverter.com/) to convert to Python.
6. Fill `cookies`, `headers`, and `payload_head` in `credentials.py`.
