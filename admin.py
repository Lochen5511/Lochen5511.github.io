"""
admin.py
──────────────────────────────────────────
管理員模式（Tempus_Aeternum）：
1. 讀取 log 資料夾中的 test_data.txt
2. 解析 8 道題目，以 [命題N完成] 格式寫入 log
3. 直接啟動 va_que_ana.py，模擬 va_set_que 完成的狀態
"""

import argparse
import sys
import os
import re
import subprocess
import requests
import time
from datetime import datetime

# ──────────────────────────────────────────
# 接收變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='Tempus_Aeternum')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[admin.py] 啟動  user={username}  session={session_id}")

BACKEND  = 'http://localhost:5000'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"


# ──────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────
def _post(path, body):
    try:
        requests.post(f"{BACKEND}{path}", json=body, timeout=5)
    except Exception as e:
        print(f"[post {path}] {e}")

def _thinking(state):
    _post('/thinking', {'username': username, 'session_id': session_id, 'thinking': state})

def send(text, delay=0):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    _post('/push', {
        'text': text, 'username': username,
        'session_id': session_id, 'log_path': log_path,
    })
    print(f"[send] {text[:60]}")

def write_log(content: str):
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")


# ──────────────────────────────────────────
# 解析 test_data.txt
# ──────────────────────────────────────────
def load_test_data() -> list:
    """
    讀取並解析 test_data.txt。
    格式：
        1. 題幹
        A. 選項A
        B. 選項B
        C. 選項C
        D. 選項D
    回傳 list of dict：[{'stem': ..., 'options': {'A': ..., 'B': ..., 'C': ..., 'D': ...}}, ...]
    """
    # 優先從 LOG_DIR 找，找不到再從 BASE_DIR 找
    for search_dir in [LOG_DIR, BASE_DIR]:
        path = os.path.join(search_dir, 'test_data.txt')
        if os.path.exists(path):
            test_data_path = path
            break
    else:
        print(f"[admin] 找不到 test_data.txt（已搜尋 {LOG_DIR} 和 {BASE_DIR}）")
        return []

    print(f"[admin] 讀取 test_data.txt：{test_data_path}")

    try:
        with open(test_data_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[admin] 讀取失敗：{e}")
        return []

    questions = []
    # 以空行分隔每題
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 5:
            continue

        # 第一行：題號 + 題幹
        stem = re.sub(r'^\d+[\.\、]\s*', '', lines[0]).strip()

        # 後續行：選項
        opts = {}
        for line in lines[1:]:
            m = re.match(r'^([A-D])[\.\、]\s*(.+)', line)
            if m:
                opts[m.group(1)] = m.group(2).strip()

        if len(opts) == 4 and stem:
            questions.append({'stem': stem, 'options': opts})

    print(f"[admin] 解析到 {len(questions)} 題")
    return questions


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    send('管理員模式啟動，正在載入測試資料…', delay=0.5)

    questions = load_test_data()

    if len(questions) < 8:
        send(f'錯誤：test_data.txt 只解析到 {len(questions)} 題（需要 8 題）。', delay=0.3)
        print("[admin.py] 題目不足，終止")
        return

    # 將題目以 [命題N完成] 格式寫入 log，供 va_que_ana 的 parse_questions_from_log 使用
    write_log('[admin] 使用 test_data.txt 模擬 va_set_que 完成')
    for i, q in enumerate(questions[:8], start=1):
        opts = q['options']
        write_log(
            f'[命題{i}完成] stem={q["stem"]} | '
            f'A={opts.get("A", "")} | B={opts.get("B", "")} | '
            f'C={opts.get("C", "")} | D={opts.get("D", "")}'
        )

    send(f'已載入 8 題，正在召喚孿生 AI 學生作答…', delay=0.5)

    # 啟動 va_que_ana.py
    base_args = ['--username', username, '--session_id', session_id, '--log_path', log_path]
    subprocess.Popen(
        [sys.executable, 'va_que_ana.py'] + base_args,
        cwd=BASE_DIR
    )
    print("[admin.py] 已啟動 va_que_ana.py，執行完畢")


if __name__ == '__main__':
    main()