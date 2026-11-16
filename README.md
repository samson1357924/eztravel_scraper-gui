# 易遊網機票爬蟲-gui (eztravel_scraper-gui) V1.3.0

這是一個具備現代化圖形介面 (GUI) 的易遊網 (ezTravel) 機票監控工具，專為需要直觀操作、自動記錄與多平台通知的使用者設計。功能涵蓋 **LINE / Email / Telegram 通知、Excel 票價記錄、自動排程監控**。

> 本工具為非官方工具，與易遊網 (ezTravel)、LINE、Telegram、Google 無任何關係；機票價格即時變動，請以下單頁顯示為準。

## 🌟 功能特色
- **多管道通知**：LINE Messaging API、Gmail、Telegram，各管道獨立運作，單一失敗不影響其他。
- **Telegram 通知**：選配啟用，填入 Bot Token 與 Chat ID 即可推播。
- **全量票價 Excel 記錄**：每日自動記錄市場票價，可設定記錄前 N 名最低價；表頭唯一、去重、corrupt 檔自動備份，不破壞使用者原本的 Excel 公式。
- **去重通知**：同一張便宜票不會重複轟炸——只有新日期或價格再跌才通知。
- **任務失敗告警**：所有查詢都失敗時會發出通知，不會靜默停擺（全敗告警每 6 小時最多一次）。
- **自動監控 + 倒數**：自定義監控頻率，具備即時倒數計時與強制停止功能。
- **全域一鍵儲存**：點擊一次即可同步所有分頁設定。
- **繁體中文優化**：強制指定 Windows「微軟正黑體」，徹底解決介面字體回退至簡體字的問題。
- **ezTravel 查價不需憑證/Cookies**（LINE/Gmail/Telegram 仍需各自 token）：使用公開 API，開箱即用。

## 🛠 操作教學
1. **下載執行檔**：
   - 前往 [Releases](https://github.com/samson1357924/eztravel_scraper-gui/releases) 下載適合你系統的執行檔。
2. **基本設定**（左側邊欄四個分頁）：
   - **「LINE 設定」**：填入 LINE Channel Access Token 與 User ID，點擊開關啟用。
   - **「Email 設定」**：填入 Gmail 帳號與「應用程式密碼」（非帳號密碼）及收件人，點擊開關啟用。
   - **「Telegram 設定」**：填入 Bot Token 與 Chat ID（申請步驟見下方「Telegram 設定（選配）」），點擊開關啟用。
   - **「Excel 記錄」**：設定 Excel 檔名與記錄前 N 名最低票價。
3. **爬蟲參數**（下方獨立方塊）：
   - 設定目標價格（含稅，台幣）、開始/結束日期，以及監控頻率。
   - **頻率建議 ≥ 60 分鐘**；ezTravel 會對頻繁請求啟動限流，過於頻繁容易被擋。
4. **執行**：
   - 點擊 **「儲存設定」** 確保所有變更已寫入。
   - 點擊 **「執行單次抓取」** 或 **「啟動自動監控」**。


### 🍎 macOS 使用者注意 (未認證開發者繞過)
由於此執行檔未經過 Apple 付費簽名，初次啟動時會被 macOS 攔截。請按照以下步驟開啟：
1. **右鍵開啟**：在下載解壓後的 `ezTravel-Scraper` 檔案上按 **「右鍵」**，選擇 **「打開」**。
2. **手動授權**：在彈出的警示視窗中，點擊 **「仍要開啟」** 或是再次點擊 **「打開」**。
3. **系統設定 (若上述失效)**：
   - 前往 **「系統設定」** -> **「隱私權與安全性」**。
   - 捲動到安全性區塊，點擊 **「仍要開啟」** 並輸入 Mac 密碼。
一旦完成一次手動開啟，之後即可直接點擊啟動。

## 🤖 Telegram 設定（選配）
Telegram 通知為選配管道，未設定即自動略過，不影響其他管道。

### 1. 建立 bot
1. Telegram 搜尋 **@BotFather**（[官方帳號](https://t.me/BotFather)）→ 開始對話 → 傳 `/newbot`
2. 輸入 bot 顯示名稱（可中文）與 username（必須全域唯一且以 `bot` 結尾）
3. BotFather 回覆的 token 就是 Bot Token（等同密碼，**勿外洩**）

### 2. 取得 chat_id
**私聊（最常用）**：
1. 先私聊你的 bot 並按 `/start`（bot 不能主動先發訊給你）
2. 瀏覽器開啟 `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. 回應中找 `result[].message.chat.id`（私聊為正整數，如 `123456789`）

**群組 / 超級群組**：
1. 把 bot 加入群組
2. 群組內任一成員傳一則訊息
3. 再查 getUpdates，`chat.id` 為負數；超級群組（supergroup）/頻道為 `-100` 開頭（如 `-1001234567890`），一般群組為負數但無 `-100` 前綴

> getUpdates 回傳 409 Conflict？常見原因：webhook 已設（webhook 啟用時 getUpdates 會被拒），需先執行 `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"` 移除。

### 3. 填入 GUI 並測試
在 **「Telegram 設定」** 分頁填入 Bot Token 與 Chat ID，**「啟用 Telegram 通知」** 開關打開後點 **「儲存設定」**。

也可以用 curl 直接測試：
```bash
curl -s -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "<CHAT_ID>", "text": "機票爬蟲測試訊息"}'
```

### 疑難排解
| 症狀 | 原因 | 解法 |
|---|---|---|
| 401 Unauthorized | Bot Token 錯誤或已撤銷 | 到 @BotFather 以 `/revoke` 重發 |
| 400 chat not found | Chat ID 錯誤；私聊未先 `/start`；或 bot 不在群組 | 完成上面步驟 2 |
| 403 bot was blocked | 你封鎖了 bot | 私聊 bot 傳 `/start` 解除封鎖 |
| 429 Too Many Requests | 發送太頻繁 | 加大監控頻率（建議 ≥ 60 分鐘）後稍後重試 |
| getUpdates 空 | bot 未被 `/start` | 先 `/start` 後再查 |
| getUpdates 409 Conflict | webhook 擋住 getUpdates | 先刪除 webhook 後再查 |

官方文件：[Telegram Bot API](https://core.telegram.org/bots/api) ・ [getUpdates](https://core.telegram.org/bots/api#getupdates) ・ [sendMessage](https://core.telegram.org/bots/api#sendmessage) ・ [deleteWebhook](https://core.telegram.org/bots/api#deletewebhook) ・ [@BotFather](https://t.me/BotFather)

> 安全性：Bot Token 等同密碼，僅存放在本機已 gitignore 的 `config.py`（GUI 的 Bot Token 欄位會遮蔽顯示），洩漏立即向 @BotFather `/revoke`。詳見 [SECURITY.md](SECURITY.md)。

## 📱 LINE / 📧 Email 設定（簡要）
- **LINE（Messaging API）**：到 [LINE Developers Console](https://developers.line.com/console/) 建立 Provider 與 Messaging API channel，發行長效 **Channel Access Token**，並取得 **User ID**（`U` 開頭 + 32 碼 hex；bot 需先加為好友）。注意 LINE Notify 已於 2025-03-31 終止服務，本工具使用 Messaging API。
- **Email（Gmail）**：Google 帳號先開啟**兩步驟驗證**，再到 [Google 帳號 > 安全性 > 應用程式密碼](https://myaccount.google.com/apppasswords) 產生 **App Password**（16 碼），這是「應用程式密碼」**不是**帳號密碼。

更多細節與外洩事件後的政策、輪換流程，請見 [SECURITY.md](SECURITY.md)。

## 👩‍💻 開發者 / 從原始碼安裝
```bash
git clone https://github.com/samson1357924/eztravel_scraper-gui
cd eztravel_scraper-gui
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp config.py.template config.py   # 然後編輯 config.py 填入你的設定
python gui_main.py
```
`config.py` 已在 `.gitignore` 中，不會被提交到 git。

可選：啟用 pre-commit 檢查（gitleaks 防機敏入庫）：
```bash
pip install pre-commit && pre-commit install
```

## 🔒 安全
本專案曾發生憑證外洩事件，相關憑證均已輪換作廢。目前的防護包含：`.gitignore` 排除 `config.py`、pre-commit（gitleaks + 禁止機敏檔案）、CI 檢查（`.github/workflows/security.yml`），以及 release 打包僅含 config.py.template（不含本機 config.py/credentials.py）。完整政策、輪換流程與回報方式請見 **[SECURITY.md](SECURITY.md)**。

## 📁 檔案結構
```
eztravel_scraper-gui/
├── gui_main.py                      # GUI 主程式（CustomTkinter）
├── .gitignore                      # 機敏檔案/產物忽略清單
├── .github/workflows/release.yml   # tag 觸發 PyInstaller 打包與發佈
├── scraper.py                       # 主爬蟲程式（LINE / Email / Telegram 通知）
├── run_schedule.py                  # headless 排程器（失敗通知、log 輪替）
├── config.py.template               # 設定範本（config.py 不入庫）
├── requirements.txt                 # 依賴套件
├── tests/                           # 離線單元測試（15 tests，不連網）
│   ├── test_scraper.py             # API 封包/價格解析/去重/sanitize
│   └── test_record_to_excel.py     # Excel 表頭唯一/去重/corrupt 備份/失敗不阻斷通知
├── SECURITY.md                      # 安全性政策
├── .github/workflows/security.yml   # CI 防洩密檢查
├── .pre-commit-config.yaml          # pre-commit：gitleaks + 禁止機敏檔案入庫
├── LICENSE                          # MIT
└── README.md                        # 本文件
```

## 📋 Changelog
### [V1.3.0] - 2026-11-17
- **API 適配**：適配 ezTravel 新版公開 API（公開查價不需憑證/cookies；新封包格式、`data:null` 判讀），移除過期的 F12 抓包教學。
- **新增 Telegram 通知管道**：GUI 新增「Telegram 設定」分頁（Bot Token / Chat ID / 啟用開關），Bot Token 欄位遮蔽顯示。
- **Excel 記錄修復**：表頭唯一、去重、corrupt 檔自動備份。
- **全通知管道去重與失敗告警**：去重通知（新日期或價格再跌才通知）；所有查詢失敗時發出告警。
- **防洩密護欄**：新增 pre-commit（gitleaks + 禁止機敏檔案）、CI 檢查。
- **文件全面更新**：README 改寫（Telegram 設定教學、開發者章節、V1.3.0）。
- **測試**：新增 `tests/` 離線單元測試（15 個測試，不連網）。

### [V1.2.0] - 2026-04-07
- **Excel 整合**：新增「Excel 記錄」分頁，支援自動追蹤每日票價變動。
- **互動優化**：
    - 將「儲存設定」移動至右下角執行區域，實現全域配置同步。
    - 移除原本的分頁儲存按鈕，簡化操作流程。
- **佈局調整**：
    - 增大預設視窗尺寸至 1000x800。
    - 將爬蟲核心參數（目標價、日期、頻率）移出分頁標籤，設為始終可見的獨立區塊。
- **數據邏輯**：更新 `scraper.py` 以支援完整票價採集，確保 Excel 記錄的數據完整性。

### [V1.1.0] - 2026-04-06
- **繁體字體修正**：修正 Windows 平台上分頁標籤顯示為簡體字的問題。
- **啟動穩定性**：優化初始化順序，修復啟動時可能發生的崩潰。

### [V1.0.0] - 2026-04-06
- **GUI 正式版**：從 CLI 遷移至 CustomTkinter 圖形介面。

## ⚖️ License
本專案採用 **MIT License**。
