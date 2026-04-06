# 易遊網機票監控爬蟲 (eztravel_scraper) V1

這是一個專門監控易遊網 (ezTravel) 機票價格的自動化爬蟲工具，支援 LINE 與 Email 即時通知。

## 🚀 主要功能 (V1)
- **多管道通知**：支援 LINE Messaging API v3 與 Gmail 通知。
- **動態連結產生**：自動根據 `credentials.py` 的起降城市代碼產生成搜尋連結。
- **即時日誌**：執行時會逐日輸出當前最低票價，方便觀察市場波動。
- **配置與憑證分離**：透過 `config.py` 管理日期與目標價，`credentials.py` 管理瀏覽器權杖，安全性更高。
- **格式檢測**：自動檢測設定檔是否存在且格式正確。

## 🛠 設定說明
1. **config.py**: 設定抓取日期範圍、目標價格、LINE Token 與 Email 帳密。
2. **credentials.py**: 透過瀏覽器 F12 導出 cURL (POST /apiv2/flight/list)，使用 `curlconverter.com` 轉換為 Python 字典格式後貼入。

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
