# -*- coding: utf-8 -*-
"""機票爬蟲排程器：每 N 分鐘執行一次 scraper.py（預設 60，可用 config.SCHEDULE_INTERVAL_MINUTES 調整）。"""

import os
import re
import sys
import json
import subprocess
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

import schedule

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_PATH = os.path.join(SCRIPT_DIR, 'scraper.py')
LOG_PATH = os.path.join(SCRIPT_DIR, 'schedule_log.log')

INTERVAL_MINUTES = 60
try:
    import config
    INTERVAL_MINUTES = max(1, int(getattr(config, 'SCHEDULE_INTERVAL_MINUTES', 60)))
except Exception as e:
    print(f"警告：讀取 config.py 的 SCHEDULE_INTERVAL_MINUTES 失敗（{e.__class__.__name__}），改用預設 {INTERVAL_MINUTES} 分鐘",
          file=sys.stderr)


class SecureRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler 讓每次輪替後新建的 log 檔維持 0600。"""

    def doRollover(self):
        super().doRollover()
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError:
            pass


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        SecureRotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=5, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
try:
    os.chmod(LOG_PATH, 0o600)  # log 內可能含路徑與 stderr 內容，僅擁有者可讀
except OSError:
    pass
logger = logging.getLogger('run_schedule')

STATE_PATH = os.path.join(SCRIPT_DIR, '.scheduler_state.json')


def load_alert_ts():
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            state = json.load(f)
        return float(state.get('scheduler_last_failure_alert', 0) or 0)
    except Exception:
        return 0.0


def save_alert_ts(ts):
    try:
        try:
            with open(STATE_PATH, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if not isinstance(state, dict):
                state = {}
        except Exception:
            state = {}
        state['scheduler_last_failure_alert'] = ts
        tmp_path = STATE_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp_path, STATE_PATH)
    except Exception as e:
        logger.warning(f"無法更新失敗通知冷卻狀態: {e.__class__.__name__}")


def sanitize(text):
    """遮蔽外送內容中的機密（config token/密碼、scheme://user:pass@ 代理憑證）。

    注意：本函式同時存在於 scraper.py 與 run_schedule.py（scheduler 需在 scraper 壞掉時獨立運作），
    修改時請同步兩處（邏輯需與 scraper.py 完全相同）。
    """
    try:
        try:
            import config
        except Exception:
            config = None
        s = _sanitize_impl(str(text), config)
    except Exception:
        # 脫敏自身失敗時，寧可遮掉整個訊息（fail-safe），也不能讓呼叫端崩潰
        return '***（脫敏失敗）'
    return s


def _sanitize_impl(s, config):
    if config is not None:
        for key in ('LINE_CHANNEL_ACCESS_TOKEN', 'GMAIL_PASSWORD', 'TELEGRAM_BOT_TOKEN'):
            val = getattr(config, key, '') or ''
            if isinstance(val, str) and len(val) >= 6 and not val.startswith('YOUR_'):
                s = s.replace(val, '***')
    # 先暫存日期（YYYY-MM-DD / DD/MM/YYYY），避免被下面的樣式遮蔽誤傷
    dates = []

    def keep_date(m):
        dates.append(m.group(0))
        return f'\x00{len(dates) - 1}\x00'

    s = re.sub(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}', keep_date, s)
    # scheme://user:pass@host → scheme://***@host
    s = re.sub(r'([a-z][a-z0-9+.-]*://)[^/@:\s]+:[^/@\s]+@', r'\1***@', s, flags=re.IGNORECASE)
    # 設定檔無法 import 時（語法錯誤）的樣式遮蔽（引號可有可無、可不閉合），(?!//) 保護連結
    s = re.sub(r"([=:]\s*['\"]?)(?!//)[A-Za-z0-9_\-/+=.\-]{24,}", r"\1***", s)
    # 含空格的引號內容（如 'abcd efgh ijkl mnop'）→ 引號完整與未閉合各遮一次
    s = re.sub(r"'[^'\n]{12,}'", "'***'", s)
    s = re.sub(r"([=:]\s*['\"])[^'\n]{12,}", r"\1***", s)
    s = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.=]+", "Bearer ***", s, flags=re.IGNORECASE)
    # 還原日期（越界索引回退為空字串）
    s = re.sub(r'\x00(\d+)\x00', lambda m: dates[int(m.group(1))] if int(m.group(1)) < len(dates) else '', s)
    return s


# 連續失敗通知的冷卻時間（避免排程每輪失敗就轟炸使用者的 LINE/Telegram）
FAILURE_ALERT_COOLDOWN_SECONDS = 6 * 3600


def notify_failure(job_name, detail):
    """爬蟲執行失敗時，盡力發出通知（LINE + Telegram）。任何失敗都只記 log，絕不拋出。

    硬性前提：config 無法匯入時，絕對不能嘗試發送——detail 裡可能含 token 原值
    （traceback 會印出引發例外的原始碼行）。此時直接放棄發送，只記 log。
    """
    # 對外送內容脫敏：stdout/stderr 可能含 config 語法錯誤行（含 token 原值）或代理憑證
    detail = sanitize(detail)
    if time.time() - load_alert_ts() < FAILURE_ALERT_COOLDOWN_SECONDS:
        logger.warning("失敗通知在冷卻期內，略過（避免洗版）")
        return
    try:
        try:
            import config
        except Exception as e:
            logger.error(f"無法讀取 config.py（{e.__class__.__name__}），警報管道可能已癱瘓，請人工檢查 {LOG_PATH}")
            return

        text = f"機票爬蟲任務 - 執行失敗！\n{job_name}\n{detail}\n價格警報可能已靜默停止，請於執行目錄檢查 schedule_log.log"
        text = text[:1500]  # 控制長度，避免 LINE/Telegram 因訊息過長拒收而整個送不出去
        sent = False

        line_enable = getattr(config, 'LINE_ENABLE', True)
        tg_enable = getattr(config, 'TELEGRAM_ENABLE', True)

        line_token = getattr(config, 'LINE_CHANNEL_ACCESS_TOKEN', '') or ''
        line_user = getattr(config, 'LINE_USER_ID', '') or ''
        if line_enable and line_token and line_user and not line_token.startswith('YOUR_'):
            try:
                import requests
                r = requests.post(
                    'https://api.line.me/v2/bot/message/push',
                    headers={'Authorization': f'Bearer {line_token}', 'Content-Type': 'application/json'},
                    json={'to': line_user, 'messages': [{'type': 'text', 'text': text}]},
                    timeout=10,
                )
                if r.status_code == 200:
                    sent = True
                    logger.info('已發送 LINE 失敗通知')
                else:
                    logger.error(f"LINE 失敗通知發送失敗: HTTP {r.status_code}")
            except Exception as e:
                logger.error(f"LINE 失敗通知發送失敗: {e.__class__.__name__}")

        tg_token = getattr(config, 'TELEGRAM_BOT_TOKEN', '') or ''
        tg_chat = getattr(config, 'TELEGRAM_CHAT_ID', '') or ''
        if tg_enable and tg_token and tg_chat:
            try:
                import requests
                r = requests.post(
                    f'https://api.telegram.org/bot{tg_token}/sendMessage',
                    json={'chat_id': tg_chat, 'text': text},
                    timeout=10,
                )
                if r.status_code == 200 and r.json().get('ok'):
                    sent = True
                    logger.info('已發送 Telegram 失敗通知')
                else:
                    logger.error(f"Telegram 失敗通知發送失敗: HTTP {r.status_code}")
            except Exception as e:
                logger.error(f"Telegram 失敗通知發送失敗: {e.__class__.__name__}")

        if sent:
            save_alert_ts(time.time())
        else:
            logger.error("失敗通知未能送出（LINE/Telegram 皆未成功），價格警報可能已靜默停止")
    except Exception as e:
        logger.error(f"發送失敗通知時發生錯誤: {e.__class__.__name__}")


# --- 通用執行函式 ---
def run_script(script_name, job_name):
    logger.info(f"⏳ 正在執行：{job_name}...")

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=600,
            cwd=SCRIPT_DIR,  # 錨定到本檔所在目錄，避免 cwd 不同導致 scraper 讀到錯誤的 config.py / 寫到錯誤目錄
        )

        finish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if result.returncode == 0:
            logger.info(f"{job_name} 完成時間：{finish_time}")
            # 把爬蟲輸出帶入 log，保留每日票價紀錄（脫敏後寫入）
            for line in (result.stdout or '').strip().splitlines():
                logger.info(f"  {sanitize(line)}")
        else:
            logger.error(f"❌ {job_name} 執行失敗 (時間：{finish_time})")
            stdout_tail = (result.stdout or '').strip().splitlines()[-20:]
            stderr_tail = (result.stderr or '').strip().splitlines()[-20:]
            if stdout_tail:
                logger.error("標準輸出（最後 20 行）:\n" + sanitize("\n".join(stdout_tail)))
            if stderr_tail:
                logger.error("錯誤訊息（最後 20 行）:\n" + sanitize("\n".join(stderr_tail)))
            notify_failure(job_name, f"exit code={result.returncode}\n" + "\n".join(stdout_tail + stderr_tail))

    except subprocess.TimeoutExpired:
        logger.error(f"❌ {job_name} 執行逾時（超過 600 秒），已強制終止")
        notify_failure(job_name, "執行逾時（超過 600 秒）已強制終止")
    except Exception as e:
        logger.error(f"❌ {job_name} 發生系統錯誤: {e.__class__.__name__}: {sanitize(e)}")
        notify_failure(job_name, f"系統錯誤: {e.__class__.__name__}")


# --- 定義任務 ---
def job():
    # 執行統一的 scraper.py
    run_script(SCRAPER_PATH, "機票爬蟲任務")


def main():
    logger.info(f"🚀 排程系統已啟動 (每 {INTERVAL_MINUTES} 分鐘執行一次) ...")

    # 啟動時先執行一次，不用等第一個排程週期
    job()

    schedule.every(INTERVAL_MINUTES).minutes.do(job)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("排程已停止（使用者中斷）")
        sys.exit(0)


if __name__ == "__main__":
    main()
