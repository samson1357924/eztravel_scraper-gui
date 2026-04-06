# 易遊網機票監控爬蟲 (eztravel_scraper) V1

這是一個專門監控易遊網 (ezTravel) 機票價格的自動化爬蟲工具，支援 LINE 與 Email 即時通知。

## 🚀 主要功能 (V1)
... (略)

## 🛠 操作教學
1. **環境準備**:
   - 確保安裝 Python 3.10+。
   - 執行 `pip install -r requirements.txt` 安裝必要套件。

2. **取得憑證 (Credentials)**:
   - 開啟瀏覽器，登入易遊網並進入機票搜尋頁面。
   - 按下 `F12` 開啟開發者工具，切換到 `Network` 標籤。
   - 執行一次搜尋任務，找到 `POST` 到 `/apiv2/flight/list` 的請求。
   - 右鍵點擊該請求 -> `Copy` -> `Copy as cURL (bash)`。
   - 前往 [curlconverter.com](https://curlconverter.com/python/)，將 cURL 貼入並轉換為 Python。
   - 將產生的 `cookies`, `headers`, `json_data` 貼入 `credentials.py`。

3. **進行設定 (Config)**:
   - 編輯 `config.py`，填入你的 LINE Channel Access Token 與 User ID。
   - 設定目標價格 `TARGET_PRICE` 與抓取日期範圍 `START_DATE`, `END_DATE`。

4. **執行爬蟲**:
   - 執行 `python3 scraper.py` 進行單次測試。
   - 執行 `python3 run_schedule.py` 開啟自動化排程（預設每 15 分鐘抓取一次）。

## 📋 Changelog
### [V1] - 2026-04-06
- **SDK 升級**：將 LINE SDK 升級至 v3 版本的 `linebot.v3.messaging`。
- **架構優化**：將日期範圍 (`START_DATE`, `END_DATE`) 移入 `config.py` 方便使用者操作。
- **動態連結**：修正連結為動態產生，支援不同起降機場的跳轉連結。
- **即時回報**：增加每日票價的 `print` 輸出（`已抓取 日期 票價，當日最低價: xxx`）。
- **安全機制**：新增 `.gitignore` 排除敏感設定檔，並加入檔案格式檢測機制。

### [V0] - 初始版本
- 基本爬蟲邏輯實現。
- 基礎 LINE Notify 整合（舊版）。
