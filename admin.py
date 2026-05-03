"""
admin.py
──────────────────────────────────────────
管理員模式（Tempus_Aeternum）：
1. 讀取 log 資料夾中的 test_data.txt（que_set_log 格式）
2. 將 test_data.txt 直接作為 {session_id}_que_set_log.txt 複製輸出
3. 同時以 [命題N完成] 格式寫入原始 log（保留 fallback 相容性）
4. 直接啟動 va_que_ana.py，模擬 va_set_que 完成的狀態
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
# 讀取並解析 test_data.txt（que_set_log 格式）
# ──────────────────────────────────────────
def load_test_data() -> tuple:
    """
    讀取 test_data.txt（que_set_log 格式），
    回傳 (test_data_path, questions)。
    questions 為 list of dict：
        [{'stem': ..., 'options': {'A': ..., 'B': ..., 'C': ..., 'D': ...}}, ...]
    """
    for search_dir in [LOG_DIR, BASE_DIR]:
        path = os.path.join(search_dir, 'test_data.txt')
        if os.path.exists(path):
            test_data_path = path
            break
    else:
        print(f"[admin] 找不到 test_data.txt（已搜尋 {LOG_DIR} 和 {BASE_DIR}）")
        return '', []

    print(f"[admin] 讀取 test_data.txt：{test_data_path}")

    questions = []
    current_q = None
    current_d = {}

    try:
        with open(test_data_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # 去掉時間戳記（若有，格式為 [YYYY-MM-DD HH:MM:SS]）
                if re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ', line):
                    _, line = line.split('] ', 1)
                    line = line.strip()

                # [QN_START]
                if re.match(r'^\[Q\d+_START\]$', line):
                    n = int(re.search(r'\d+', line).group())
                    current_q = n
                    current_d = {}
                    continue

                # [QN_END]
                if re.match(r'^\[Q\d+_END\]$', line):
                    if current_d.get('題幹') and all(
                        current_d.get(k) for k in ('正確答案A', '錯誤選項B', '錯誤選項C', '錯誤選項D')
                    ):
                        questions.append({
                            'stem':    current_d['題幹'],
                            'options': {
                                'A': current_d['正確答案A'],
                                'B': current_d['錯誤選項B'],
                                'C': current_d['錯誤選項C'],
                                'D': current_d['錯誤選項D'],
                            }
                        })
                    current_q = None
                    current_d = {}
                    continue

                # [QN] key=value
                if current_q is not None:
                    m = re.match(r'^\[Q\d+\]\s*(.+?)=(.*)$', line)
                    if m:
                        current_d[m.group(1).strip()] = m.group(2).strip()

    except Exception as e:
        print(f"[admin] 解析失敗：{e}")
        return test_data_path, []

    print(f"[admin] 解析到 {len(questions)} 題")
    return test_data_path, questions


# ──────────────────────────────────────────
# 將 test_data.txt 直接輸出為 que_set_log
# ──────────────────────────────────────────
def setup_que_log(test_data_path: str) -> str:
    """
    test_data.txt 本身即為 que_set_log 格式，直接複製為
    {session_id}_que_set_log.txt，並在檔頭補上 session 資訊。
    回傳 que_log_path。
    """
    session_dir = os.path.dirname(log_path) if log_path else LOG_DIR
    out_path    = os.path.join(session_dir, f"{session_id}_que_set_log.txt")

    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(test_data_path, 'r', encoding='utf-8') as src:
            body = src.read()

        header = (
            f"# que_set_log | session={session_id} | user={username} | "
            f"建立時間={ts} | 來源=admin/test_data\n\n"
        )
        with open(out_path, 'w', encoding='utf-8') as dst:
            dst.write(header + body)

        print(f"[admin] que_set_log 已建立：{out_path}")
    except Exception as e:
        print(f"[admin] que_set_log 建立失敗：{e}")

    return out_path


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    send('管理員模式啟動，正在載入測試資料…', delay=0.5)

    test_data_path, questions = load_test_data()

    if len(questions) < 8:
        send(f'錯誤：test_data.txt 只解析到 {len(questions)} 題（需要 8 題）。', delay=0.3)
        print("[admin.py] 題目不足，終止")
        return

    # 原始 log：寫入 [命題N完成] 格式（保留 fallback 相容性）
    write_log('[admin] 使用 test_data.txt 模擬 va_set_que 完成')
    for i, q in enumerate(questions[:8], start=1):
        opts = q['options']
        write_log(
            f'[命題{i}完成] stem={q["stem"]} | '
            f'A={opts.get("A", "")} | B={opts.get("B", "")} | '
            f'C={opts.get("C", "")} | D={opts.get("D", "")}'
        )

    # test_data.txt 直接作為 que_set_log 輸出
    que_log = setup_que_log(test_data_path)

    send(f'已載入 8 題，正在召喚孿生 AI 學生作答…', delay=0.5)

    # 啟動 va_que_ana.py，傳入 --que_log
    base_args = [
        '--username',   username,
        '--session_id', session_id,
        '--log_path',   log_path,
        '--que_log',    que_log,
    ]
    subprocess.Popen(
        [sys.executable, 'va_que_ana.py'] + base_args,
        cwd=BASE_DIR
    )
    print("[admin.py] 已啟動 va_que_ana.py，執行完畢")


if __name__ == '__main__':
    main()