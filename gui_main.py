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
        self.geometry("900x680")
        
        # 狀態控制
        self.scrape_thread = None
        self.stop_requested = False
        self.is_scheduled = False
        self.next_run_time = None
        self.timer_job = None

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
        self.line_enable_var = ctk.BooleanVar(value=getattr(config, 'LINE_ENABLE', True))
        self.line_enable_switch = ctk.CTkSwitch(self.tabview.tab("LINE 設定"), text="啟用 LINE 通知", variable=self.line_enable_var)
        self.line_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.line_token_entry = self.create_input("LINE 通道存取權杖 (Token)", getattr(config, 'LINE_CHANNEL_ACCESS_TOKEN', ''), 1, self.tabview.tab("LINE 設定"))
        self.line_uid_entry = self.create_input("LINE 使用者 ID (UserID)", getattr(config, 'LINE_USER_ID', ''), 2, self.tabview.tab("LINE 設定"))
        
        # Email 分頁
        self.email_enable_var = ctk.BooleanVar(value=getattr(config, 'EMAIL_ENABLE', True))
        self.email_enable_switch = ctk.CTkSwitch(self.tabview.tab("Email 設定"), text="啟用 Email 通知", variable=self.email_enable_var)
        self.email_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.gmail_user_entry = self.create_input("Gmail 帳號", getattr(config, 'GMAIL_USER', ''), 1, self.tabview.tab("Email 設定"))
        self.gmail_pass_entry = self.create_input("Gmail 應用程式密碼", getattr(config, 'GMAIL_PASSWORD', ''), 2, self.tabview.tab("Email 設定"))
        self.to_email_entry = self.create_input("接收通知 Email", getattr(config, 'TO_EMAIL', ''), 3, self.tabview.tab("Email 設定"))

        # 爬蟲參數 分頁
        self.target_price_entry = self.create_input("目標價格 (台幣)", str(getattr(config, 'TARGET_PRICE', 4000)), 1, self.tabview.tab("爬蟲參數"))
        self.start_date_entry = self.create_input("開始日期 (YYYY-MM-DD)", getattr(config, 'START_DATE', '2026-06-01'), 2, self.tabview.tab("爬蟲參數"))
        self.end_date_entry = self.create_input("結束日期 (YYYY-MM-DD)", getattr(config, 'END_DATE', '2026-07-01'), 3, self.tabview.tab("爬蟲參數"))

        # 排程設定 (在爬蟲參數分頁新增)
        self.interval_label = ctk.CTkLabel(self.tabview.tab("爬蟲參數"), text="自動監控頻率 (分鐘，建議 >= 10):", anchor="w")
        self.interval_label.grid(row=7, column=0, padx=20, pady=(5, 0), sticky="w")
        self.interval_entry = ctk.CTkEntry(self.tabview.tab("爬蟲參數"))
        self.interval_entry.insert(0, "15")
        self.interval_entry.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="ew")

        # 保存按鈕
        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="儲存設定", command=self.save_settings)
        self.save_btn.grid(row=3, column=0, padx=20, pady=20)

        # 啟動時讀取 config.py 並填入內容 (確保獲取最新實體檔案內容)
        self.load_settings_from_file()

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
        
        self.schedule_btn = ctk.CTkButton(self.button_frame, text="啟動自動監控", command=self.toggle_schedule, fg_color="#1f538d")
        self.schedule_btn.pack(side="left", padx=10)
        
        self.stop_btn = ctk.CTkButton(self.button_frame, text="停止抓取", command=self.stop_scrape, fg_color="red", hover_color="#8B0000", state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        # 倒數計時顯示
        self.timer_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self.timer_label.grid(row=5, column=1, padx=20, pady=(0, 10), sticky="e")

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

    def load_settings_from_file(self):
        """從 config.py 實體檔案讀取內容並填入 Entry 欄位"""
        if not os.path.exists("config.py"):
            return
            
        try:
            settings = {}
            with open("config.py", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'").strip('"')
                        settings[key] = val
            
            # 填入對應欄位
            if "LINE_ENABLE" in settings:
                self.line_enable_var.set(settings["LINE_ENABLE"] == "True")
            if "EMAIL_ENABLE" in settings:
                self.email_enable_var.set(settings["EMAIL_ENABLE"] == "True")
            
            if "LINE_CHANNEL_ACCESS_TOKEN" in settings:
                self.line_token_entry.delete(0, "end")
                self.line_token_entry.insert(0, settings["LINE_CHANNEL_ACCESS_TOKEN"])
            if "LINE_USER_ID" in settings:
                self.line_uid_entry.delete(0, "end")
                self.line_uid_entry.insert(0, settings["LINE_USER_ID"])
            if "GMAIL_USER" in settings:
                self.gmail_user_entry.delete(0, "end")
                self.gmail_user_entry.insert(0, settings["GMAIL_USER"])
            if "GMAIL_PASSWORD" in settings:
                self.gmail_pass_entry.delete(0, "end")
                self.gmail_pass_entry.insert(0, settings["GMAIL_PASSWORD"])
            if "TO_EMAIL" in settings:
                self.to_email_entry.delete(0, "end")
                self.to_email_entry.insert(0, settings["TO_EMAIL"])
            if "TARGET_PRICE" in settings:
                self.target_price_entry.delete(0, "end")
                self.target_price_entry.insert(0, settings["TARGET_PRICE"])
            if "START_DATE" in settings:
                self.start_date_entry.delete(0, "end")
                self.start_date_entry.insert(0, settings["START_DATE"])
            if "END_DATE" in settings:
                self.end_date_entry.delete(0, "end")
                self.end_date_entry.insert(0, settings["END_DATE"])
                
        except Exception as e:
            self.add_log(f"讀取設定檔失敗: {e}")

    def save_settings(self):
        # 讀取現有的 config.py 內容
        current_config = {}
        if os.path.exists("config.py"):
            with open("config.py", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        key, val = line.split("=", 1)
                        current_config[key.strip()] = val.strip()

        # 根據目前選中的分頁，僅更新該分頁對應的欄位
        selected_tab = self.tabview.get()
        
        if selected_tab == "LINE 設定":
            current_config["LINE_ENABLE"] = str(self.line_enable_var.get())
            current_config["LINE_CHANNEL_ACCESS_TOKEN"] = f"'{self.line_token_entry.get()}'"
            current_config["LINE_USER_ID"] = f"'{self.line_uid_entry.get()}'"
            self.add_log("已更新 LINE 設定。")
            
        elif selected_tab == "Email 設定":
            current_config["EMAIL_ENABLE"] = str(self.email_enable_var.get())
            current_config["GMAIL_USER"] = f"'{self.gmail_user_entry.get()}'"
            current_config["GMAIL_PASSWORD"] = f"'{self.gmail_pass_entry.get()}'"
            current_config["TO_EMAIL"] = f"'{self.to_email_entry.get()}'"
            self.add_log("已更新 Email 設定。")
            
        elif selected_tab == "爬蟲參數":
            current_config["TARGET_PRICE"] = self.target_price_entry.get()
            current_config["START_DATE"] = f"'{self.start_date_entry.get()}'"
            current_config["END_DATE"] = f"'{self.end_date_entry.get()}'"
            self.add_log("已更新 爬蟲參數。")

        # 寫回 config.py
        with open("config.py", "w", encoding="utf-8") as f:
            for key, val in current_config.items():
                f.write(f"{key} = {val}\n")
        
        # 只有在「右側」憑證編輯區有變動時才更新 credentials.py (這裡維持手動儲存邏輯)
        # 或者如果你希望儲存按鈕也同步儲存憑證區：
        with open("credentials.py", "w", encoding="utf-8") as f:
            f.write(self.creds_textbox.get("1.0", "end-1c"))
        
        self.add_log("設定已同步至本地檔案。")

    def toggle_schedule(self):
        if not self.is_scheduled:
            # 啟動排程
            try:
                interval = int(self.interval_entry.get())
                if interval < 1: interval = 1 # 防呆
            except:
                self.add_log("❌ 錯誤：頻率必須是數字")
                return

            self.is_scheduled = True
            self.schedule_btn.configure(text="關閉自動監控", fg_color="#A9A9A9")
            self.add_log(f"✅ 已啟動自動監控，每 {interval} 分鐘執行一次。")
            self.run_scheduled_task()
        else:
            # 關閉排程
            self.is_scheduled = False
            self.schedule_btn.configure(text="啟動自動監控", fg_color="#1f538d")
            self.timer_label.configure(text="")
            if self.timer_job:
                self.after_cancel(self.timer_job)
            self.add_log("停止自動監控。")

    def run_scheduled_task(self):
        if not self.is_scheduled:
            return
            
        # 執行抓取 (複用現有線程邏輯)
        self.start_scrape_thread()
        
        # 設定下次執行時間
        interval_mins = int(self.interval_entry.get())
        import time
        self.next_run_time = time.time() + (interval_mins * 60)
        self.update_timer()

    def update_timer(self):
        if not self.is_scheduled or self.next_run_time is None:
            return
            
        import time
        remaining = int(self.next_run_time - time.time())
        if remaining <= 0:
            self.run_scheduled_task()
        else:
            mins, secs = divmod(remaining, 60)
            self.timer_label.configure(text=f"下次自動執行倒數: {mins:02d}:{secs:02d}")
            self.timer_job = self.after(1000, self.update_timer)

    def start_scrape_thread(self):
        self.stop_requested = False
        self.run_btn.configure(state="disabled", text="正在抓取...")
        self.stop_btn.configure(state="normal")
        
        self.scrape_thread = threading.Thread(target=self.run_scrape)
        self.scrape_thread.daemon = True
        self.scrape_thread.start()

    def stop_scrape(self):
        if self.scrape_thread and self.scrape_thread.is_alive():
            self.stop_requested = True
            self.add_log("🛑 正在強制終止抓取腳本...")
            # 由於 Python 無法直接 kill thread，我們透過拋出異常來打斷
            # 在 next iteration 檢查 stop_requested
            self.stop_btn.configure(state="disabled", text="正在終止...")

    def run_scrape(self):
        try:
            # 重新載入 config 以確保使用最新值
            import importlib
            importlib.reload(config)
            importlib.reload(scraper)
            
            self.add_log(f"開始抓取任務: {config.START_DATE} 至 {config.END_DATE}...")
            
            # 使用 callback 檢查停止狀態並拋出異常直接打斷執行
            def gui_log_callback(message):
                if self.stop_requested:
                    # 直接拋出異常來「打斷」當前 scraper 的執行流
                    raise KeyboardInterrupt("使用者手動終止執行")
                if message:
                    self.add_log(message)

            results = scraper.run_scraper(
                config.START_DATE, 
                config.END_DATE, 
                log_callback=gui_log_callback
            )
            
        except (KeyboardInterrupt, InterruptedError):
            self.add_log("⚠️ 腳本執行已強制中斷。")
        except Exception as e:
            self.add_log(f"執行出錯: {e}")
        finally:
            self.stop_requested = False
            self.run_btn.configure(state="normal", text="開始執行單次抓取")
            self.stop_btn.configure(state="disabled", text="停止抓取")

if __name__ == "__main__":
    app = App()
    app.mainloop()
