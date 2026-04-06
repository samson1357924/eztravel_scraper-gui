# -*- coding: utf-8 -*-
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

# 定義適合台灣 Windows 的繁體中文字體
DEFAULT_FONT_FAMILY = "Microsoft JhengHei" if os.name == "nt" else "Arial Unicode MS"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("易遊網機票爬蟲-gui (Excel 支援版)")
        self.geometry("900x720")
        
        # 設定全域字體物件
        self.main_font = ctk.CTkFont(family=DEFAULT_FONT_FAMILY, size=14)
        self.title_font = ctk.CTkFont(family=DEFAULT_FONT_FAMILY, size=20, weight="bold")
        self.label_font = ctk.CTkFont(family=DEFAULT_FONT_FAMILY, size=13)

        # 狀態控制
        self.scrape_thread = None
        self.stop_requested = False
        self.is_scheduled = False
        self.next_run_time = None
        self.timer_job = None

        # 網格配置
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 左側邊欄 ===
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="易遊網爬蟲", font=self.title_font)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 5))

        # 保存按鈕 (上移)
        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="儲存目前分頁設定", command=self.save_settings, font=self.main_font)
        self.save_btn.grid(row=1, column=0, padx=20, pady=(0, 10))

        # 建立分頁視窗
        self.tabview = ctk.CTkTabview(self.sidebar_frame, width=250)
        try:
            self.tabview._segmented_button.configure(font=self.label_font)
        except:
            pass
        self.tabview.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1)

        self.tabview.add("LINE 設定")
        self.tabview.add("Email 設定")
        self.tabview.add("Excel 記錄")
        self.tabview.add("爬蟲參數")

        # --- LINE 分頁 ---
        self.line_enable_var = ctk.BooleanVar(value=getattr(config, 'LINE_ENABLE', True))
        self.line_enable_switch = ctk.CTkSwitch(self.tabview.tab("LINE 設定"), text="啟用 LINE 通知", 
                                                variable=self.line_enable_var, command=self.quick_save_line_enable, font=self.label_font)
        self.line_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        self.line_token_entry = self.create_input("LINE Token", getattr(config, 'LINE_CHANNEL_ACCESS_TOKEN', ''), 1, self.tabview.tab("LINE 設定"))
        self.line_uid_entry = self.create_input("LINE UserID", getattr(config, 'LINE_USER_ID', ''), 2, self.tabview.tab("LINE 設定"))
        
        # --- Email 分頁 ---
        self.email_enable_var = ctk.BooleanVar(value=getattr(config, 'EMAIL_ENABLE', True))
        self.email_enable_switch = ctk.CTkSwitch(self.tabview.tab("Email 設定"), text="啟用 Email 通知", 
                                                 variable=self.email_enable_var, command=self.quick_save_email_enable, font=self.label_font)
        self.email_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        self.gmail_user_entry = self.create_input("Gmail 帳號", getattr(config, 'GMAIL_USER', ''), 1, self.tabview.tab("Email 設定"))
        self.gmail_pass_entry = self.create_input("Gmail 密碼", getattr(config, 'GMAIL_PASSWORD', ''), 2, self.tabview.tab("Email 設定"))
        self.to_email_entry = self.create_input("接收通知 Email", getattr(config, 'TO_EMAIL', ''), 3, self.tabview.tab("Email 設定"))

        # --- Excel 記錄 分頁 ---
        self.excel_enable_var = ctk.BooleanVar(value=getattr(config, 'EXCEL_ENABLE', False))
        self.excel_enable_switch = ctk.CTkSwitch(self.tabview.tab("Excel 記錄"), text="啟用 Excel 記錄", 
                                                 variable=self.excel_enable_var, command=self.quick_save_excel_enable, font=self.label_font)
        self.excel_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        self.excel_filename_entry = self.create_input("Excel 檔名", getattr(config, 'EXCEL_FILENAME', 'prices.xlsx'), 1, self.tabview.tab("Excel 記錄"))
        self.excel_top_n_entry = self.create_input("記錄前 N 低票價", str(getattr(config, 'EXCEL_TOP_N', 3)), 2, self.tabview.tab("Excel 記錄"))

        # --- 爬蟲參數 分頁 ---
        self.target_price_entry = self.create_input("目標價格 (台幣)", str(getattr(config, 'TARGET_PRICE', 4000)), 1, self.tabview.tab("爬蟲參數"))
        self.start_date_entry = self.create_input("開始日期", getattr(config, 'START_DATE', '2026-06-01'), 2, self.tabview.tab("爬蟲參數"))
        self.end_date_entry = self.create_input("結束日期", getattr(config, 'END_DATE', '2026-07-01'), 3, self.tabview.tab("爬蟲參數"))
        self.interval_label = ctk.CTkLabel(self.tabview.tab("爬蟲參數"), text="監控頻率 (分)", anchor="w", font=self.label_font)
        self.interval_label.grid(row=7, column=0, padx=20, pady=(5, 0), sticky="w")
        self.interval_entry = ctk.CTkEntry(self.tabview.tab("爬蟲參數"))
        self.interval_entry.insert(0, "15")
        self.interval_entry.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="ew")

        # === 右側主視窗 ===
        self.creds_label = ctk.CTkLabel(self, text="瀏覽器憑證:", font=self.main_font)
        self.creds_label.grid(row=0, column=1, padx=20, pady=(10, 0), sticky="w")
        self.creds_textbox = ctk.CTkTextbox(self, height=200, font=ctk.CTkFont(family="Consolas", size=12))
        self.creds_textbox.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")
        if os.path.exists("credentials.py"):
            with open("credentials.py", "r", encoding="utf-8") as f:
                self.creds_textbox.insert("0.0", f.read())

        self.log_label = ctk.CTkLabel(self, text="執行狀態:", font=self.main_font)
        self.log_label.grid(row=2, column=1, padx=20, pady=(10, 0), sticky="w")
        self.log_textbox = ctk.CTkTextbox(self, height=200, state="disabled", font=self.label_font)
        self.log_textbox.grid(row=3, column=1, padx=20, pady=10, sticky="nsew")

        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=4, column=1, padx=20, pady=20, sticky="e")
        self.run_btn = ctk.CTkButton(self.button_frame, text="執行單次抓取", command=self.start_scrape_thread, fg_color="green", font=self.main_font)
        self.run_btn.pack(side="left", padx=10)
        self.schedule_btn = ctk.CTkButton(self.button_frame, text="啟動自動監控", command=self.toggle_schedule, fg_color="#1f538d", font=self.main_font)
        self.schedule_btn.pack(side="left", padx=10)
        self.stop_btn = ctk.CTkButton(self.button_frame, text="停止抓取", command=self.stop_scrape, fg_color="red", state="disabled", font=self.main_font)
        self.stop_btn.pack(side="left", padx=10)
        self.timer_label = ctk.CTkLabel(self, text="", font=self.label_font)
        self.timer_label.grid(row=5, column=1, padx=20, pady=(0, 10), sticky="e")

        self.load_settings_from_file()

    def create_input(self, label_text, default_value, row, master):
        label = ctk.CTkLabel(master, text=label_text, anchor="w", font=self.label_font)
        label.grid(row=row*2-1, column=0, padx=20, pady=(5, 0), sticky="w")
        entry = ctk.CTkEntry(master)
        entry.insert(0, str(default_value))
        entry.grid(row=row*2, column=0, padx=20, pady=(0, 10), sticky="ew")
        return entry

    def add_log(self, text):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def quick_save_line_enable(self): self.update_single_config("LINE_ENABLE", str(self.line_enable_var.get()))
    def quick_save_email_enable(self): self.update_single_config("EMAIL_ENABLE", str(self.email_enable_var.get()))
    def quick_save_excel_enable(self): self.update_single_config("EXCEL_ENABLE", str(self.excel_enable_var.get()))

    def update_single_config(self, key, val):
        c = {}
        if os.path.exists("config.py"):
            with open("config.py", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line: k, v = line.split("=", 1); c[k.strip()] = v.strip()
        c[key] = val
        with open("config.py", "w", encoding="utf-8") as f:
            for k, v in c.items(): f.write(f"{k} = {v}\n")
        import importlib; importlib.reload(config)

    def load_settings_from_file(self):
        if not os.path.exists("config.py"): return
        try:
            s = {}
            with open("config.py", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line: k, v = line.split("=", 1); s[k.strip()] = v.strip().strip("'").strip('"')
            if "LINE_ENABLE" in s: self.line_enable_var.set(s["LINE_ENABLE"] == "True")
            if "EMAIL_ENABLE" in s: self.email_enable_var.set(s["EMAIL_ENABLE"] == "True")
            if "EXCEL_ENABLE" in s: self.excel_enable_var.set(s["EXCEL_ENABLE"] == "True")
            if "LINE_CHANNEL_ACCESS_TOKEN" in s: self.line_token_entry.delete(0, "end"); self.line_token_entry.insert(0, s["LINE_CHANNEL_ACCESS_TOKEN"])
            if "LINE_USER_ID" in s: self.line_uid_entry.delete(0, "end"); self.line_uid_entry.insert(0, s["LINE_USER_ID"])
            if "GMAIL_USER" in s: self.gmail_user_entry.delete(0, "end"); self.gmail_user_entry.insert(0, s["GMAIL_USER"])
            if "GMAIL_PASSWORD" in s: self.gmail_pass_entry.delete(0, "end"); self.gmail_pass_entry.insert(0, s["GMAIL_PASSWORD"])
            if "TO_EMAIL" in s: self.to_email_entry.delete(0, "end"); self.to_email_entry.insert(0, s["TO_EMAIL"])
            if "EXCEL_FILENAME" in s: self.excel_filename_entry.delete(0, "end"); self.excel_filename_entry.insert(0, s["EXCEL_FILENAME"])
            if "EXCEL_TOP_N" in s: self.excel_top_n_entry.delete(0, "end"); self.excel_top_n_entry.insert(0, s["EXCEL_TOP_N"])
            if "TARGET_PRICE" in s: self.target_price_entry.delete(0, "end"); self.target_price_entry.insert(0, s["TARGET_PRICE"])
            if "START_DATE" in s: self.start_date_entry.delete(0, "end"); self.start_date_entry.insert(0, s["START_DATE"])
            if "END_DATE" in s: self.end_date_entry.delete(0, "end"); self.end_date_entry.insert(0, s["END_DATE"])
        except: pass

    def save_settings(self):
        c = {}
        if os.path.exists("config.py"):
            with open("config.py", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line: k, v = line.split("=", 1); c[k.strip()] = v.strip()
        t = self.tabview.get()
        if t == "LINE 設定":
            c["LINE_ENABLE"] = str(self.line_enable_var.get())
            c["LINE_CHANNEL_ACCESS_TOKEN"] = f"'{self.line_token_entry.get()}'"
            c["LINE_USER_ID"] = f"'{self.line_uid_entry.get()}'"
        elif t == "Email 設定":
            c["EMAIL_ENABLE"] = str(self.email_enable_var.get())
            c["GMAIL_USER"] = f"'{self.gmail_user_entry.get()}'"
            c["GMAIL_PASSWORD"] = f"'{self.gmail_pass_entry.get()}'"
            c["TO_EMAIL"] = f"'{self.to_email_entry.get()}'"
        elif t == "Excel 記錄":
            c["EXCEL_ENABLE"] = str(self.excel_enable_var.get())
            c["EXCEL_FILENAME"] = f"'{self.excel_filename_entry.get()}'"
            c["EXCEL_TOP_N"] = self.excel_top_n_entry.get()
        elif t == "爬蟲參數":
            c["TARGET_PRICE"] = self.target_price_entry.get()
            c["START_DATE"] = f"'{self.start_date_entry.get()}'"
            c["END_DATE"] = f"'{self.end_date_entry.get()}'"
        with open("config.py", "w", encoding="utf-8") as f:
            for k, v in c.items(): f.write(f"{k} = {v}\n")
        with open("credentials.py", "w", encoding="utf-8") as f:
            f.write(self.creds_textbox.get("1.0", "end-1c"))
        self.add_log("設定已儲存。")

    def toggle_schedule(self):
        if not self.is_scheduled:
            try: interval = int(self.interval_entry.get())
            except: self.add_log("❌ 頻率錯誤"); return
            self.is_scheduled = True
            self.schedule_btn.configure(text="關閉自動監控", fg_color="#A9A9A9")
            self.run_scheduled_task()
        else:
            self.is_scheduled = False
            self.schedule_btn.configure(text="啟動自動監控", fg_color="#1f538d")
            self.timer_label.configure(text="")
            if self.timer_job: self.after_cancel(self.timer_job)

    def run_scheduled_task(self):
        if not self.is_scheduled: return
        self.start_scrape_thread()
        self.next_run_time = datetime.now().timestamp() + (int(self.interval_entry.get()) * 60)
        self.update_timer()

    def update_timer(self):
        if not self.is_scheduled: return
        rem = int(self.next_run_time - datetime.now().timestamp())
        if rem <= 0: self.run_scheduled_task()
        else:
            m, s = divmod(rem, 60); self.timer_label.configure(text=f"下次倒數: {m:02d}:{s:02d}")
            self.timer_job = self.after(1000, self.update_timer)

    def start_scrape_thread(self):
        self.stop_requested = False
        self.run_btn.configure(state="disabled"); self.stop_btn.configure(state="normal")
        self.scrape_thread = threading.Thread(target=self.run_scrape, daemon=True)
        self.scrape_thread.start()

    def stop_scrape(self):
        if self.scrape_thread and self.scrape_thread.is_alive():
            self.stop_requested = True; self.add_log("🛑 終止中..."); self.stop_btn.configure(state="disabled")

    def run_scrape(self):
        try:
            import importlib; importlib.reload(config); importlib.reload(scraper)
            def cb(msg):
                if self.stop_requested: raise KeyboardInterrupt
                if msg: self.add_log(msg)
            scraper.run_scraper(config.START_DATE, config.END_DATE, log_callback=cb)
        except KeyboardInterrupt: self.add_log("⚠️ 已中斷")
        except Exception as e: self.add_log(f"❌ 出錯: {e}")
        finally:
            self.stop_requested = False
            self.run_btn.configure(state="normal"); self.stop_btn.configure(state="disabled")

if __name__ == "__main__":
    app = App(); app.mainloop()
