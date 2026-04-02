# eztravel_scraper

一個基於 Python 的 eztravel (易遊網) 機票爬蟲，具備 Email 與 LINE 通知功能。

## 功能特點
- 自動抓取指定日期範圍內的最低票價。
- 將歷史票價數據儲存於 Excel 檔案中。
- 當票價低於設定的目標價時，自動發送 Email 與 LINE 訊息通知。
- 支援排程執行。

## 教學：如何獲取最新的 Cookies 與 Headers
eztravel 有防爬蟲機制，建議使用以下方法手動更新腳本中的驗證資料：

1. 開啟瀏覽器並前往 [eztravel 機票搜尋頁面](https://flight.eztravel.com.tw/)。
2. 按下 `F12` 開啟開發者工具，切換到 **Network (網路)** 分頁。
3. 執行一次機票搜尋。
4. 在 Network 列表中找到名稱為 `list` 的請求（這是主要的 API 請求）。
5. 在該請求上點擊右鍵 -> **Copy (複製)** -> **Copy as cURL (bash)**。
6. 前往 [curlconverter.com](https://curlconverter.com/)。
7. 將複製的 cURL 貼入，選擇 **Python**。
8. 將轉換出的 `cookies`、`headers` 以及 `json_data` 中的 `head` 欄位更新到腳本中。

## 安裝與使用
1. 克隆此專案：`git clone ...`
2. 安裝依賴：`pip install requests pandas openpyxl line-bot-sdk schedule`
3. 設定環境變數或直接修改腳本中的通知權杖（Token）。
4. 執行爬蟲：`python scraper.py` 或 `python run_schedule.py`

---

# eztravel_scraper

A Python-based scraper for eztravel flight tickets with automated Email and LINE notifications.

## Features
- Automatically crawls lowest fares within a specified date range.
- Stores historical price data in an Excel file.
- Sends instant notifications via Email and LINE when prices drop below your target.
- Supports scheduled execution.

## Tutorial: How to obtain Cookies and Headers
eztravel uses anti-bot measures. Follow these steps to update the credentials in the script:

1. Open your browser and navigate to the [eztravel flight search page](https://flight.eztravel.com.tw/).
2. Press `F12` to open Developer Tools and switch to the **Network** tab.
3. Perform a flight search.
4. Locate the request named `list` in the Network list (this is the main API endpoint).
5. Right-click the request -> **Copy** -> **Copy as cURL (bash)**.
6. Go to [curlconverter.com](https://curlconverter.com/).
7. Paste the cURL command and select **Python**.
8. Copy the generated `cookies`, `headers`, and the `head` section from `json_data` into the script.

## Installation & Usage
1. Clone the repository.
2. Install dependencies: `pip install requests pandas openpyxl line-bot-sdk schedule`
3. Configure your notification tokens (Environment variables or script constants).
4. Run the scraper: `python scraper.py` or `python run_schedule.py`
