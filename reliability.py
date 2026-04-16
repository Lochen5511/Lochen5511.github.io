import argparse
import time
import requests
import os
from datetime import datetime

# ──────────────────────────────────────────
# 接收來自 button.py 的變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[reliability.py] 啟動  user={username}  session={session_id}")

BACKEND      = 'http://localhost:5000'
USER_TIMEOUT = 300


# ──────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────
def _set_thinking(state):
    try:
        requests.post(f'{BACKEND}/thinking', json={
            'username': username, 'session_id': session_id, 'thinking': state}, timeout=5)
    except: pass

def _lock(locked):
    try:
        requests.post(f'{BACKEND}/lock_input', json={
            'session_id': session_id, 'locked': locked}, timeout=5)
    except: pass

def send(text, delay=0):
    if delay > 0:
        _set_thinking(True); time.sleep(delay); _set_thinking(False)
    try:
        requests.post(f'{BACKEND}/push', json={
            'text': text, 'username': username,
            'session_id': session_id, 'log_path': log_path}, timeout=5)
    except Exception as e:
        print(f"[送出失敗] {e}")

def send_alert(message):
    try:
        requests.post(f'{BACKEND}/push', json={
            'text': f'__ALERT__{message}', 'username': username,
            'session_id': session_id, 'log_path': ''}, timeout=5)
    except Exception as e:
        print(f"[alert 失敗] {e}")

def send_buttons(labels, delay=0, colors=None, sizes=None, size='medium', button_ids=None):
    if delay > 0:
        _set_thinking(True); time.sleep(delay); _set_thinking(False)
    n          = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    size_list  = sizes if sizes else [size] * n
    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )
    try:
        requests.post(f'{BACKEND}/push', json={
            'text': f'__BUTTONS__{parts}', 'username': username,
            'session_id': session_id, 'log_path': ''}, timeout=5)
        _lock(True)
    except Exception as e:
        print(f"[多按鈕失敗] {e}")

def wait_for_user(interval=0.5, timeout=USER_TIMEOUT):
    """等待用戶回應，離開回傳 None，被中斷回傳 '__INTERRUPTED__'"""
    while True:
        # 優先取用戶輸入，減少延遲
        try:
            res = requests.get(f'{BACKEND}/fetch_user_input',
                               params={'session_id': session_id}, timeout=5)
            data = res.json()
            if data.get('message'):
                _lock(False)
                return data['message']
        except: pass

        try:
            res = requests.get(f'{BACKEND}/check_interrupted',
                               params={'session_id': session_id}, timeout=5)
            if res.json().get('interrupted', False):
                write_log('[中斷] 用戶輸入 ID，流程中斷')
                return '__INTERRUPTED__'
        except: pass

        try:
            res = requests.get(f'{BACKEND}/check_online',
                               params={'session_id': session_id, 'timeout': timeout}, timeout=5)
            if not res.json().get('online', True):
                write_log('用戶已離開系統')
                return None
        except: pass

        time.sleep(interval)

def write_log(content):
    """寫入後端結構化 log（含時間戳記）"""
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    # ↓↓↓ 在這裡加入你的代碼 ↓↓↓

    send_alert('很抱歉，此單元尚在開發中，請返回選擇其他選項。')

    time.sleep(0.5)
    _set_thinking(False)  # 確保思考動畫不殘留
    send_buttons(
        labels     = ['效度', '信度'],
        colors     = ['gray', 'blue'],
        size       = 'small',
        button_ids = ['btn_validity', 'btn_reliability']
    )

    user_reply = wait_for_user()
    if user_reply is None or user_reply == '__INTERRUPTED__':
        return

    print(f"[用戶點擊] {user_reply}")

    base_args = ['--username', username, '--session_id', session_id, '--log_path', log_path]
    import subprocess
    if 'btn_validity' in user_reply:
        try:
            requests.post(f'{BACKEND}/update_unit',
                          json={'session_id': session_id, 'unit': '效度'}, timeout=5)
        except Exception as e:
            print(f"[update_unit 失敗] {e}")
        subprocess.Popen(['python', 'validity.py'] + base_args,
                         cwd=os.path.dirname(os.path.abspath(__file__)))
    elif 'btn_reliability' in user_reply:
        subprocess.Popen(['python', 'reliability.py'] + base_args,
                         cwd=os.path.dirname(os.path.abspath(__file__)))

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[reliability.py 執行完畢]")


if __name__ == '__main__':
    main()
