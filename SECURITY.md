# 安全性政策 (SECURITY.md)

感謝你關心本專案的安全性。本文件說明曾發生的憑證外洩事件、目前的防範措施，以及如何回報安全性問題。

## 曾發生的外洩事件

本公開儲存庫曾意外洩漏下列類型的機敏資訊（以下僅描述類別，**不包含任何實際憑證值**）：

- LINE Channel Access Token
- Gmail 應用程式密碼 (App Password)
- LINE User ID
- 易遊網 (ezTravel) 的 Incapsula cookies（因存在於被 git 追蹤的 `.pyc` 編譯檔中而間接外洩）

事件成因主要是：本機設定檔與編譯快取被誤加入 git 追蹤，且未在上傳前完成檢查。

### 已採取的補救措施

- 上述所有外洩憑證**皆已由擁有者輪換 / 作廢**，舊憑證不再有效。
- 已將 `config.py`、`credentials.py`、`__pycache__/` 自 git 追蹤中移除，並加入 `.gitignore`。
- **credentials.py 流程已廢棄**：ezTravel 公開 API 不再需要任何 cookies，`credentials.py` 不應再建立或使用。
- 本機工作目錄中的 `config.py` 與 `credentials.py` 仍然保留，僅不再被 git 追蹤。
- 新增 pre-commit 與 CI 檢查，防止同類事件再次發生。
- 注意：上述檔案仍可能存在於**舊的 git 歷史與既有的 clone / fork** 中，輪換憑證是唯一可靠的補救手段。
- `.gitleaksignore`：CI 的 gitleaks 歷史掃描基準化（baseline）了 2 筆發現項——皆為 commit `1ecc12c` 中的**人造測試字串**（sanitize 測試用的假 LINE token 前綴，非真實憑證，實值已於 `9d80a87` 改為全虛構字串）。全新的 commit 不會受這 2 筆影響。如果將來 CI 掃描出其他發現項，請勿直接加入 ignore，務必先確認是否為真實憑證。

## 防範措施

### 1. 永不入庫的檔案

以下檔案一律不得提交至 git（已列入 `.gitignore`）：

- `config.py` — 本機 LINE / Gmail 等實際設定
- `credentials.py` — 本機易遊網 cookies / headers / json_data（credentials.py 流程已廢棄，不需要 cookies；仍禁止入庫）
- `__pycache__/`、`*.py[cod]` 等 Python 編譯產物（可能含有硬編碼的敏感字串）
- `.env`、`.env.*` — 環境變數檔
- `.envrc`、`*.pem`、`*.key`、`*.p12`、`secrets.*` — 其他常見私鑰或機敏檔

請改以 `config.py.template` 作為範本，複製後填入自己的資料，且僅保存在本機。credentials.py 流程已廢棄，不需要 cookies。

### 2. Token 輪換流程

若懷疑任何憑證可能已外洩，請依下列步驟處理：

1. **立即輪換**：到 LINE Developers 主控台重新發行 Channel Access Token；到 Google 帳戶設定撤銷並重新產生 Gmail 應用程式密碼。不需任何 cookies（ezTravel 公開 API）。
2. **更新本機設定**：修改本機的 `config.py` / `.env`。credentials.py 流程已廢棄，不需要 cookies。
3. **確認未入庫**：執行 `git status`，確認機敏檔案未被追蹤。
4. **從歷史清除（必要時）**：由儲存庫擁有者使用 `git filter-repo` 等工具改寫歷史，並通知所有協作者重新 clone。
5. **私下通報**：依下方「回報方式」通知維護者。

### 3. .env 建議

- 機敏設定優先使用環境變數（`.env`）注入，而非寫死在程式碼中。
- `.env` 必須列入 `.gitignore`；本儲存庫已預設忽略 `.env` 與 `.env.*`。
- 可提供 `.env.example`（不含真實值）作為範本，說明需要哪些變數。
- 切勿為了圖方便將 token 貼在 issue、PR、comment 或 commit message 中。

### 4. 自動化檢查

- **pre-commit**：`.pre-commit-config.yaml` 內含 gitleaks hook（掃描機敏字串）與 `forbidden-files` hook（鏡像 CI，攔截機敏檔名入庫）；Windows 環境若無 Git Bash 可改為 `language: python`。
- **CI**：`.github/workflows/security.yml` 會在 push / PR 時檢查 git 追蹤清單中不得出現機敏檔案，並以 gitleaks 掃描歷史紀錄。
  - 注意：gitleaks 預設規則無法識別所有憑證格式（本儲存庫曾外洩的 Incapsula cookies / Gmail 應用程式密碼即未被該規則命中），綠燈**不代表**歷史乾淨；此檢查為防禦縱深，真正的防線是 tracked-files 檢查 + 憑證輪換 + `.gitignore`。
- 建議貢獻者在本機執行 `pre-commit install` 啟用檢查。

## 回報方式

若你發現本專案存在安全性問題（包含憑證外洩、權限錯誤、依賴套件漏洞等），請**不要開公開 Issue**，改以以下方式私下回報：

- 使用 GitHub 的 [Security Advisories](https://github.com/samson1357924/eztravel_scraper-gui/security/advisories/new)「Report a vulnerability」功能私下通報。

我們會盡快確認並處理，感謝你協助讓本專案更安全。

## 貢獻者注意事項

- **絕對不要**將任何真實憑證（token、cookies、密碼、User ID）提交到 git，即使是「暫時」也不行。
- 只提交 `.template` 檔案，且範本內只放佔位符（如 `YOUR_LINE_TOKEN`），不放真實或看似真實的值。
- 提交前請執行 `git status` 與 `git diff --cached`，確認沒有機敏檔案或內容被 staged。
- 啟用本專案的 pre-commit hook：`pip install pre-commit && pre-commit install`。
- 若你不慎提交了憑證，請**立即輪換該憑證**（光是 revert commit 無法使外洩的憑證失效），並私下通知維護者。
- 新增任何可能含機敏資料的檔案類型時，請一併更新 `.gitignore`、CI 檢查與本文件。
