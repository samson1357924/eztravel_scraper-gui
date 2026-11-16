# -*- coding: utf-8 -*-
import sys
import os
import shutil
import threading
from datetime import datetime, timedelta

# config.py 的絕對路徑：所有 config 讀寫都錨定到本檔所在目錄，避免 cwd 不同導致讀到/寫到錯誤的 config.py
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")

# 首次啟動：config.py 不存在時，自動從 config.py.template 複製一份（exe 直接內嵌 template）
if not os.path.exists(CONFIG_PATH):
    _template = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "config.py.template")
    if os.path.isfile(_template):
        try:
            shutil.copyfile(_template, CONFIG_PATH)
        except OSError:
            pass

def _strip_inline_comment(line):
    """移除不在引號內的 # 之後的內容（逐字掃描，追蹤引號狀態）。"""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == '#':
            return line[:i]
    return line

def parse_config_text(text):
    """解析 config.py 內容，回傳 {key: value}（值已 strip 引號與行尾註解）。"""
    s = {}
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw:
            continue
        k, v = _strip_inline_comment(raw).split("=", 1)
        s[k.strip()] = v.strip().strip("'").strip('"')
    return s

try:
    import math
    import customtkinter as ctk
    import scraper
    import config
except Exception as e:
    # --windowed 打包的 exe 沒有 console，import 失敗會變成無聲閃退；改以 messagebox 顯示錯誤
    try:
        import tkinter as tk
        from tkinter import messagebox
        _root = tk.Tk()
        _root.withdraw()
        messagebox.showerror("設定錯誤", f"無法載入程式所需的模組或設定：\n{e.__class__.__name__}: {e}")
        _root.destroy()
    except Exception:
        pass
    sys.exit(1)

# 設定主題
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# 定義適合台灣 Windows 的繁體中文字體
DEFAULT_FONT_FAMILY = "Microsoft JhengHei" if os.name == "nt" else "Arial Unicode MS"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("易遊網機票爬蟲-gui V1.3.0")
        self.geometry("1000x800") # 增加預設高度至 800
        
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
        self.grid_rowconfigure(1, weight=1)

        # === 左側邊欄 ===
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="易遊網爬蟲", font=self.title_font)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 5))

        # 建立分頁視窗 (固定高度確保不遮擋下方參數)
        self.tabview = ctk.CTkTabview(self.sidebar_frame, width=250, height=320)
        try:
            self.tabview._segmented_button.configure(font=self.label_font)
        except:
            pass
        self.tabview.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1)

        self.tabview.add("LINE 設定")
        self.tabview.add("Email 設定")
        self.tabview.add("Telegram 設定")
        self.tabview.add("Excel 記錄")

        # --- LINE 分頁 ---
        self.line_enable_var = ctk.BooleanVar(value=getattr(config, 'LINE_ENABLE', True))
        self.line_enable_switch = ctk.CTkSwitch(self.tabview.tab("LINE 設定"), text="啟用 LINE 通知", 
                                                variable=self.line_enable_var, command=self.quick_save_line_enable, font=self.label_font)
        self.line_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        self.line_token_entry = self.create_input("LINE Token", getattr(config, 'LINE_CHANNEL_ACCESS_TOKEN', ''), 1, self.tabview.tab("LINE 設定"), show="•")
        self.line_uid_entry = self.create_input("LINE UserID", getattr(config, 'LINE_USER_ID', ''), 2, self.tabview.tab("LINE 設定"))
        
        # --- Email 分頁 ---
        self.email_enable_var = ctk.BooleanVar(value=getattr(config, 'EMAIL_ENABLE', True))
        self.email_enable_switch = ctk.CTkSwitch(self.tabview.tab("Email 設定"), text="啟用 Email 通知", 
                                                 variable=self.email_enable_var, command=self.quick_save_email_enable, font=self.label_font)
        self.email_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        
        # 增加 Email 欄位的 pady 間距，並確保第三個欄位有足夠空間
        self.gmail_user_entry = self.create_input("Gmail 帳號", getattr(config, 'GMAIL_USER', ''), 1, self.tabview.tab("Email 設定"))
        self.gmail_pass_entry = self.create_input("Gmail 密碼", getattr(config, 'GMAIL_PASSWORD', ''), 2, self.tabview.tab("Email 設定"), show="•")
        self.to_email_entry = self.create_input("接收通知 Email", getattr(config, 'TO_EMAIL', ''), 3, self.tabview.tab("Email 設定"))

        # --- Telegram 分頁 ---
        self.telegram_enable_var = ctk.BooleanVar(value=getattr(config, 'TELEGRAM_ENABLE', True))
        self.telegram_enable_switch = ctk.CTkSwitch(self.tabview.tab("Telegram 設定"), text="啟用 Telegram 通知",
                                                    variable=self.telegram_enable_var, command=self.quick_save_telegram_enable, font=self.label_font)
        self.telegram_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        self.telegram_token_entry = self.create_input("Bot Token", getattr(config, 'TELEGRAM_BOT_TOKEN', ''), 1, self.tabview.tab("Telegram 設定"), show="•")
        self.telegram_chat_id_entry = self.create_input("Chat ID", getattr(config, 'TELEGRAM_CHAT_ID', ''), 2, self.tabview.tab("Telegram 設定"))

        # --- Excel 記錄 分頁 ---
        self.excel_enable_var = ctk.BooleanVar(value=getattr(config, 'EXCEL_ENABLE', False))
        self.excel_enable_switch = ctk.CTkSwitch(self.tabview.tab("Excel 記錄"), text="啟用 Excel 記錄", 
                                                 variable=self.excel_enable_var, command=self.quick_save_excel_enable, font=self.label_font)
        self.excel_enable_switch.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        self.excel_filename_entry = self.create_input("Excel 檔名", getattr(config, 'EXCEL_FILENAME', 'flight_prices.xlsx'), 1, self.tabview.tab("Excel 記錄"))
        self.excel_top_n_entry = self.create_input("記錄前 N 低票價", str(getattr(config, 'EXCEL_TOP_N', 3)), 2, self.tabview.tab("Excel 記錄"))

        # --- 獨立的爬蟲參數方塊 (在 Tabview 下方) ---
        self.params_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.params_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        
        self.target_price_entry = self.create_input("目標價格 (台幣)", str(getattr(config, 'TARGET_PRICE', 4000)), 1, self.params_frame)
        self.start_date_entry = self.create_input("開始日期", getattr(config, 'START_DATE', datetime.now().strftime('%Y-%m-%d')), 2, self.params_frame)
        self.end_date_entry = self.create_input("結束日期", getattr(config, 'END_DATE', (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')), 3, self.params_frame)
        
        self.interval_label = ctk.CTkLabel(self.params_frame, text="監控頻率 (分)", anchor="w", font=self.label_font)
        self.interval_label.grid(row=7, column=0, padx=20, pady=(5, 0), sticky="w")
        self.interval_entry = ctk.CTkEntry(self.params_frame)
        self.interval_entry.insert(0, str(getattr(config, 'INTERVAL_MINS', 60)))
        self.interval_entry.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="ew")

        # === 右側主視窗 ===
        self.log_label = ctk.CTkLabel(self, text="執行狀態:", font=self.main_font)
        self.log_label.grid(row=0, column=1, padx=20, pady=(10, 0), sticky="w")
        self.log_textbox = ctk.CTkTextbox(self, height=250, state="disabled", font=self.label_font)
        self.log_textbox.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")

        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=2, column=1, padx=20, pady=20, sticky="e")
        
        self.save_btn = ctk.CTkButton(self.button_frame, text="儲存設定", command=self.save_settings, font=self.main_font, fg_color="orange", hover_color="#FF8C00")
        self.save_btn.pack(side="left", padx=10)
        
        self.run_btn = ctk.CTkButton(self.button_frame, text="執行單次抓取", command=self.start_scrape_thread, fg_color="green", font=self.main_font)
        self.run_btn.pack(side="left", padx=10)
        self.schedule_btn = ctk.CTkButton(self.button_frame, text="啟動自動監控", command=self.toggle_schedule, fg_color="#1f538d", font=self.main_font)
        self.schedule_btn.pack(side="left", padx=10)
        self.stop_btn = ctk.CTkButton(self.button_frame, text="停止抓取", command=self.stop_scrape, fg_color="red", state="disabled", font=self.main_font)
        self.stop_btn.pack(side="left", padx=10)
        self.timer_label = ctk.CTkLabel(self, text="", font=self.label_font)
        self.timer_label.grid(row=3, column=1, padx=20, pady=(0, 10), sticky="e")

        self.load_settings_from_file()

    def create_input(self, label_text, default_value, row, master, show=None):
        label = ctk.CTkLabel(master, text=label_text, anchor="w", font=self.label_font)
        label.grid(row=row*2-1, column=0, padx=20, pady=(5, 0), sticky="w")
        if show is not None:
            entry = ctk.CTkEntry(master, show=show)
        else:
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
    def quick_save_telegram_enable(self): self.update_single_config("TELEGRAM_ENABLE", str(self.telegram_enable_var.get()))
    def quick_save_excel_enable(self): self.update_single_config("EXCEL_ENABLE", str(self.excel_enable_var.get()))

    @staticmethod
    def _quote(v):
        """把字串寫成 config.py 的合法字面量：直接 repr(v)，確保產生的檔案可被 ast.literal_eval / import 解析。"""
        return repr(v)

    @staticmethod
    def _write_config_preserving(values, path=CONFIG_PATH, on_error=None):
        """重寫 config.py：保留既有註解、空行與未知鍵，僅更新或新增 values 中的鍵。

        被更新的鍵，其行尾註解會被替換（其餘行的註解完整保留）。
        寫檔為原子操作：先寫 path+'.tmp' 再 os.replace；覆蓋前若原檔存在會先留一份 path+'.bak'。
        讀檔採 utf-8-sig 以相容 BOM 開頭的 config.py。失敗時經 on_error 回報（或印出），絕不拋例外。
        """
        lines = []
        written = set()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8-sig") as f:
                    for raw in f:
                        stripped = raw.strip()
                        if not stripped or stripped.startswith("#") or "=" not in raw:
                            lines.append(raw if raw.endswith("\n") else raw + "\n")
                            continue
                        k, _ = raw.split("=", 1)
                        key = k.strip()
                        if key in values:
                            lines.append(f"{key} = {values[key]}\n")
                            written.add(key)
                        else:
                            lines.append(raw if raw.endswith("\n") else raw + "\n")
            for key, val in values.items():
                if key not in written:
                    lines.append(f"{key} = {val}\n")
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                os.chmod(tmp_path, 0o600)
                f.writelines(lines)
            if os.path.exists(path):
                # 覆蓋前先備份原檔，避免寫到一半出錯時失去舊設定
                shutil.copyfile(path, path + ".bak")
                os.chmod(path + ".bak", 0o600)
            os.replace(tmp_path, path)
            return True
        except OSError as e:
            if on_error:
                on_error(e)
            else:
                print(f"寫入 config.py 失敗：{e}")
            return False

    def update_single_config(self, key, val):
        if not self._write_config_preserving({key: val}, on_error=lambda e: self.add_log(f"❌ 寫入 config.py 失敗：{e}")):
            return
        import importlib
        try:
            importlib.reload(config)
        except Exception as e:
            self.add_log(f"❌ 設定檔重新載入失敗：{e}")

    def load_settings_from_file(self):
        if not os.path.exists(CONFIG_PATH): return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                s = parse_config_text(f.read())
            if "LINE_ENABLE" in s: self.line_enable_var.set(s["LINE_ENABLE"] == "True")
            if "EMAIL_ENABLE" in s: self.email_enable_var.set(s["EMAIL_ENABLE"] == "True")
            if "TELEGRAM_ENABLE" in s: self.telegram_enable_var.set(s["TELEGRAM_ENABLE"] == "True")
            if "EXCEL_ENABLE" in s: self.excel_enable_var.set(s["EXCEL_ENABLE"] == "True")
            if "LINE_CHANNEL_ACCESS_TOKEN" in s: self.line_token_entry.delete(0, "end"); self.line_token_entry.insert(0, s["LINE_CHANNEL_ACCESS_TOKEN"])
            if "LINE_USER_ID" in s: self.line_uid_entry.delete(0, "end"); self.line_uid_entry.insert(0, s["LINE_USER_ID"])
            if "GMAIL_USER" in s: self.gmail_user_entry.delete(0, "end"); self.gmail_user_entry.insert(0, s["GMAIL_USER"])
            if "GMAIL_PASSWORD" in s: self.gmail_pass_entry.delete(0, "end"); self.gmail_pass_entry.insert(0, s["GMAIL_PASSWORD"])
            if "TO_EMAIL" in s: self.to_email_entry.delete(0, "end"); self.to_email_entry.insert(0, s["TO_EMAIL"])
            if "TELEGRAM_BOT_TOKEN" in s: self.telegram_token_entry.delete(0, "end"); self.telegram_token_entry.insert(0, s["TELEGRAM_BOT_TOKEN"])
            if "TELEGRAM_CHAT_ID" in s: self.telegram_chat_id_entry.delete(0, "end"); self.telegram_chat_id_entry.insert(0, s["TELEGRAM_CHAT_ID"])
            if "EXCEL_FILENAME" in s: self.excel_filename_entry.delete(0, "end"); self.excel_filename_entry.insert(0, s["EXCEL_FILENAME"])
            if "EXCEL_TOP_N" in s: self.excel_top_n_entry.delete(0, "end"); self.excel_top_n_entry.insert(0, s["EXCEL_TOP_N"])
            if "INTERVAL_MINS" in s: self.interval_entry.delete(0, "end"); self.interval_entry.insert(0, s["INTERVAL_MINS"])
            if "TARGET_PRICE" in s: self.target_price_entry.delete(0, "end"); self.target_price_entry.insert(0, s["TARGET_PRICE"])
            if "START_DATE" in s: self.start_date_entry.delete(0, "end"); self.start_date_entry.insert(0, s["START_DATE"])
            if "END_DATE" in s: self.end_date_entry.delete(0, "end"); self.end_date_entry.insert(0, s["END_DATE"])
        except Exception as e:
            self.add_log(f"⚠️ 讀取 config.py 失敗：{e}")

    def save_settings(self):
        # 先驗證 START_DATE / END_DATE：任一檢查失敗即取消儲存，config.py 完全不動
        start_str = self.start_date_entry.get().strip()
        end_str = self.end_date_entry.get().strip()
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_str, '%Y-%m-%d')
        except ValueError:
            self.add_log("開始/結束日期格式錯誤，已取消儲存")
            return
        if end_date < start_date:
            self.add_log("結束日期不得早於開始日期，已取消儲存")
            return
        if end_date.date() < datetime.now().date():
            self.add_log("結束日期不得早於今天，已取消儲存")
            return

        c = {}

        # 儲存底部的「爬蟲參數」
        try:
            _v = float(self.target_price_entry.get())
            if not (math.isfinite(_v) and _v > 0):
                raise ValueError
            c["TARGET_PRICE"] = self.target_price_entry.get()
        except ValueError:
            self.add_log("⚠️ TARGET_PRICE 格式錯誤，已改用預設值 4000")
            c["TARGET_PRICE"] = "4000"
        c["START_DATE"] = self._quote(start_str)
        c["END_DATE"] = self._quote(end_str)
        try:
            _iv = int(self.interval_entry.get())
            if _iv < 1:
                raise ValueError
            c["INTERVAL_MINS"] = str(_iv)
        except ValueError:
            self.add_log("⚠️ INTERVAL_MINS 格式錯誤，已改用預設值 60")
            c["INTERVAL_MINS"] = "60"

        # 儲存所有分頁的設定 (LINE, Email, Telegram, Excel)
        c["LINE_ENABLE"] = str(self.line_enable_var.get())
        c["LINE_CHANNEL_ACCESS_TOKEN"] = self._quote(self.line_token_entry.get().strip())
        c["LINE_USER_ID"] = self._quote(self.line_uid_entry.get().strip())

        c["EMAIL_ENABLE"] = str(self.email_enable_var.get())
        c["GMAIL_USER"] = self._quote(self.gmail_user_entry.get().strip())
        c["GMAIL_PASSWORD"] = self._quote(self.gmail_pass_entry.get().strip())
        c["TO_EMAIL"] = self._quote(self.to_email_entry.get().strip())

        c["TELEGRAM_ENABLE"] = str(self.telegram_enable_var.get())
        c["TELEGRAM_BOT_TOKEN"] = self._quote(self.telegram_token_entry.get().strip())
        c["TELEGRAM_CHAT_ID"] = self._quote(self.telegram_chat_id_entry.get().strip())

        c["EXCEL_ENABLE"] = str(self.excel_enable_var.get())
        c["EXCEL_FILENAME"] = self._quote(self.excel_filename_entry.get())
        try:
            _v = float(self.excel_top_n_entry.get())
            if not (math.isfinite(_v) and _v > 0):
                raise ValueError
            c["EXCEL_TOP_N"] = self.excel_top_n_entry.get()
        except ValueError:
            self.add_log("⚠️ EXCEL_TOP_N 格式錯誤，已改用預設值 3")
            c["EXCEL_TOP_N"] = "3"

        if not self._write_config_preserving(c, on_error=lambda e: self.add_log(f"❌ 寫入 config.py 失敗：{e}")):
            return

        import importlib
        try:
            importlib.reload(config)
        except Exception as e:
            self.add_log(f"❌ 設定檔重新載入失敗：{e}")
            return
        self.add_log("✅ 所有設定已成功儲存。")

    def _reset_schedule(self):
        """把排程相關狀態重置為未啟動（還原按鈕、清空倒數、取消排程 timer）。"""
        self.is_scheduled = False
        self.schedule_btn.configure(text="啟動自動監控", fg_color="#1f538d")
        self.timer_label.configure(text="")
        if self.timer_job: self.after_cancel(self.timer_job)

    def toggle_schedule(self):
        if not self.is_scheduled:
            try: interval = int(self.interval_entry.get())
            except (TypeError, ValueError): self.add_log("❌ 頻率錯誤"); return
            if interval < 1:
                self.add_log("❌ 頻率必須 ≥ 1 分鐘")
                self._reset_schedule()
                return
            self.is_scheduled = True
            self.schedule_btn.configure(text="關閉自動監控", fg_color="#A9A9A9")
            self.run_scheduled_task()
        else:
            self._reset_schedule()

    def run_scheduled_task(self):
        if not self.is_scheduled: return
        try:
            interval_mins = int(self.interval_entry.get())
        except (TypeError, ValueError):
            interval_mins = None
        if interval_mins is None:
            self.add_log("❌ 頻率錯誤")
            self._reset_schedule()
            return
        if interval_mins < 1:
            self.add_log("❌ 頻率必須 ≥ 1 分鐘")
            self._reset_schedule()
            return
        self.start_scrape_thread()
        self.next_run_time = datetime.now().timestamp() + (interval_mins * 60)
        self.update_timer()

    def update_timer(self):
        if not self.is_scheduled: return
        rem = int(self.next_run_time - datetime.now().timestamp())
        if rem <= 0: self.run_scheduled_task()
        else:
            m, s = divmod(rem, 60); self.timer_label.configure(text=f"下次倒數: {m:02d}:{s:02d}")
            self.timer_job = self.after(1000, self.update_timer)

    def start_scrape_thread(self):
        # 上一次抓取尚未完成時略過本次排程，避免堆疊出多個抓取 thread
        if self.scrape_thread and self.scrape_thread.is_alive():
            self.add_log("⏳ 上一次抓取尚未完成，略過本次排程")
            return
        self.stop_requested = False
        self.run_btn.configure(state="disabled"); self.stop_btn.configure(state="normal")
        self.scrape_thread = threading.Thread(target=self.run_scrape, daemon=True)
        self.scrape_thread.start()

    def stop_scrape(self):
        if self.scrape_thread and self.scrape_thread.is_alive():
            self.stop_requested = True; self.add_log("🛑 終止中..."); self.stop_btn.configure(state="disabled")

    def run_scrape(self):
        try:
            import importlib
            try:
                importlib.reload(config)
                importlib.reload(scraper)
            except Exception as e:
                self.add_log(f"❌ 設定檔重新載入失敗：{e}")
                return
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
