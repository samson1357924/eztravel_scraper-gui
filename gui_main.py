import customtkinter as ctk
import threading
import sys
import os
from datetime import datetime
import scraper
import config

# 設定主題
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ezTravel Flight Scraper V2-GUI")
        self.geometry("900x650")

        # 網格配置 (2x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 左側邊欄 (使用 Tabview 分組) ===
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="易遊網爬蟲", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # 建立分頁視窗來分類設定
        self.tabview = ctk.CTkTabview(self.sidebar_frame, width=250)
        self.tabview.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.tabview.add("LINE 設定")
        self.tabview.add("Email 設定")
        self.tabview.add("爬蟲參數")

        # LINE 分頁
        self.line_token_entry = self.create_input("LINE 通道存取權杖 (Token)", getattr(config, 'LINE_CHANNEL_ACCESS_TOKEN', ''), 1, self.tabview.tab("LINE 設定"))
        self.line_uid_entry = self.create_input("LINE 使用者 ID (UserID)", getattr(config, 'LINE_USER_ID', ''), 2, self.tabview.tab("LINE 設定"))
        
        # Email 分頁
        self.gmail_user_entry = self.create_input("Gmail 帳號", getattr(config, 'GMAIL_USER', ''), 1, self.tabview.tab("Email 設定"))
        self.gmail_pass_entry = self.create_input("Gmail 應用程式密碼", getattr(config, 'GMAIL_PASSWORD', ''), 2, self.tabview.tab("Email 設定"))
        self.to_email_entry = self.create_input("接收通知 Email", getattr(config, 'TO_EMAIL', ''), 3, self.tabview.tab("Email 設定"))

        # 爬蟲參數 分頁
        self.target_price_entry = self.create_input("目標價格 (台幣)", str(getattr(config, 'TARGET_PRICE', 4000)), 1, self.tabview.tab("爬蟲參數"))
        self.start_date_entry = self.create_input("開始日期 (YYYY-MM-DD)", getattr(config, 'START_DATE', '2026-06-01'), 2, self.tabview.tab("爬蟲參數"))
        self.end_date_entry = self.create_input("結束日期 (YYYY-MM-DD)", getattr(config, 'END_DATE', '2026-07-01'), 3, self.tabview.tab("爬蟲參數"))

        # 保存按鈕
        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="儲存設定", command=self.save_settings)
        self.save_btn.grid(row=3, column=0, padx=20, pady=20)

        # === 右側主視窗 ===
        # 1. 憑證編輯區
        self.creds_label = ctk.CTkLabel(self, text="瀏覽器憑證 (請貼入 credentials.py 的程式碼內容):", font=ctk.CTkFont(size=14, weight="bold"))
        self.creds_label.grid(row=0, column=1, padx=20, pady=(10, 0), sticky="w")
        
        self.creds_textbox = ctk.CTkTextbox(self, height=200)
        self.creds_textbox.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")
        
        # 載入現有的 credentials.py
        if os.path.exists("credentials.py"):
            with open("credentials.py", "r", encoding="utf-8") as f:
                self.creds_textbox.insert("0.0", f.read())

        # 2. 日誌顯示區
        self.log_label = ctk.CTkLabel(self, text="執行狀態與日誌:", font=ctk.CTkFont(size=14, weight="bold"))
        self.log_label.grid(row=2, column=1, padx=20, pady=(10, 0), sticky="w")
        
        self.log_textbox = ctk.CTkTextbox(self, height=200, state="disabled")
        self.log_textbox.grid(row=3, column=1, padx=20, pady=10, sticky="nsew")

        # 3. 按鈕區
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=4, column=1, padx=20, pady=20, sticky="e")
        
        self.run_btn = ctk.CTkButton(self.button_frame, text="開始執行單次抓取", command=self.start_scrape_thread, fg_color="green", hover_color="#006400")
        self.run_btn.pack(side="left", padx=10)

    def create_input(self, label_text, default_value, row, master=None):
        if master is None: master = self.sidebar_frame
        label = ctk.CTkLabel(master, text=label_text, anchor="w")
        label.grid(row=row*2-1, column=0, padx=20, pady=(5, 0), sticky="w")
        entry = ctk.CTkEntry(master)
        entry.insert(0, default_value)
        entry.grid(row=row*2, column=0, padx=20, pady=(0, 10), sticky="ew")
        return entry

    def add_log(self, text):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def save_settings(self):
        # 更新 config.py
        with open("config.py", "w", encoding="utf-8") as f:
            f.write(f"LINE_CHANNEL_ACCESS_TOKEN = '{self.line_token_entry.get()}'\n")
            f.write(f"LINE_USER_ID = '{self.line_uid_entry.get()}'\n")
            f.write(f"GMAIL_USER = '{self.gmail_user_entry.get()}'\n")
            f.write(f"GMAIL_PASSWORD = '{self.gmail_pass_entry.get()}'\n")
            f.write(f"TO_EMAIL = '{self.to_email_entry.get()}'\n")
            f.write(f"TARGET_PRICE = {self.target_price_entry.get()}\n")
            f.write(f"START_DATE = '{self.start_date_entry.get()}'\n")
            f.write(f"END_DATE = '{self.end_date_entry.get()}'\n")
        
        # 更新 credentials.py
        with open("credentials.py", "w", encoding="utf-8") as f:
            f.write(self.creds_textbox.get("1.0", "end-1c"))
        
        self.add_log("設定已儲存至本地檔案。")

    def start_scrape_thread(self):
        self.run_btn.configure(state="disabled", text="正在抓取...")
        thread = threading.Thread(target=self.run_scrape)
        thread.daemon = True
        thread.start()

    def run_scrape(self):
        try:
            # 重新載入 config 以確保使用最新值
            import importlib
            importlib.reload(config)
            
            self.add_log(f"開始抓取任務: {config.START_DATE} 至 {config.END_DATE}...")
            
            # 使用我們原本的 scraper 邏輯
            # 注意：這裡我們需要修改 scraper.py 的 print，讓它能導向到 GUI，或者手動調用
            results = scraper.run_scraper(config.START_DATE, config.END_DATE)
            
            if results:
                self.add_log(f"任務完成！發現 {len(results)} 筆便宜機票。")
            else:
                self.add_log("任務完成，未發現低於目標價的機票。")

        except Exception as e:
            self.add_log(f"執行出錯: {e}")
        finally:
            self.run_btn.configure(state="normal", text="執行單次抓取")

if __name__ == "__main__":
    app = App()
    app.mainloop()
