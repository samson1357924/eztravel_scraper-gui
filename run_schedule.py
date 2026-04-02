# -*- coding: utf-8 -*-
"""
Created on Fri Dec  6 20:52:58 2024

@author: samso
"""

import schedule
import time
import subprocess
import logging
from datetime import datetime

# --- 1. 設定 Log 日誌功能 ---
logging.basicConfig(
    filename='schedule_log.log',
    level=logging.INFO,
    format='%(message)s', 
    encoding='utf-8'
)

# 讓螢幕也印出 Log
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger('').addHandler(console)

# --- 2. 通用執行函式 ---
def run_script(script_name, job_name):
    # 取得開始時間
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{start_time}] ⏳ 正在執行：{job_name}...") 

    try:
        # 執行 Python 腳本
        result = subprocess.run(
            ["python", script_name], 
            capture_output=True, 
            text=True, 
            encoding='utf-8'
        )
        
        # 取得「完成時間」
        finish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 檢查是否成功 (returncode 為 0 表示成功)
        if result.returncode == 0:
            log_msg = f"{job_name} 完成時間：{finish_time}"
            logging.info(log_msg) 
        else:
            # 失敗時的 Log
            logging.error(f"❌ {job_name} 執行失敗 (時間：{finish_time})")
            logging.error(f"錯誤訊息: {result.stderr}")
            
    except Exception as e:
        logging.error(f"❌ {job_name} 發生系統錯誤: {e}")

# --- 3. 定義任務 ---
def job():
    # 執行統一的 scraper.py
    run_script("scraper.py", "機票爬蟲任務")

# --- 4. 設定排程 ---
print("🚀 排程系統已啟動 (每 15 分鐘執行一次) ...")

# 設定：每 15 分鐘執行一次
schedule.every(15).minutes.do(job)

# --- 5. 主迴圈 ---
while True:
    schedule.run_pending()
    time.sleep(1)
