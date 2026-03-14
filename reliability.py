import argparse
import time
import requests
from datetime import datetime
import os

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


# ──────────────────────────────────────────
# 工具函數（與 button.py 相同）
# ──────────────────────────────────────────
def _set_thinking(state):
    try:
        requests.post('http://localhost:5000/thinking', json={
            'username': username, 'session_id': session_id, 'thinking': state})
    except: pass

def send(text, delay=0):
    if delay > 0:
        _set_thinking(True); time.sleep(delay); _set_thinking(False)
    try:
        requests.post('http://localhost:5000/push', json={
            'text': text, 'username': username,
            'session_id': session_id, 'log_path': log_path})
    except Exception as e:
        print(f"[送出失敗] {e}")

def send_alert(message):
    try:
        requests.post('http://localhost:5000/push', json={
            'text': f'__ALERT__{message}', 'username': username,
            'session_id': session_id, 'log_path': ''})
    except Exception as e:
        print(f"[alert 失敗] {e}")

def send_button(label, delay=0, color='gold', size='medium', button_id=''):
    if delay > 0:
        _set_thinking(True); time.sleep(delay); _set_thinking(False)
    bid = button_id if button_id else label
    try:
        requests.post('http://localhost:5000/push', json={
            'text': f'__BUTTON__{label}||{color}||{size}||{bid}',
            'username': username, 'session_id': session_id, 'log_path': ''})
    except Exception as e:
        print(f"[按鈕失敗] {e}")

def send_buttons(labels, delay=0, colors=None, sizes=None, size='medium', button_ids=None):
    if delay > 0:
        _set_thinking(True); time.sleep(delay); _set_thinking(False)
    n = len(labels)
    colors = colors or ['gold'] * n
    button_ids = button_ids or labels
    size_list = sizes if sizes else [size] * n
    parts = ';'.join(f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}' for i in range(n))
    try:
        requests.post('http://localhost:5000/push', json={
            'text': f'__BUTTONS__{parts}', 'username': username,
            'session_id': session_id, 'log_path': ''})
    except Exception as e:
        print(f"[多按鈕失敗] {e}")

def wait_for_user(interval=0.5):
    while True:
        try:
            res = requests.get('http://localhost:5000/fetch_user_input',
                               params={'session_id': session_id})
            data = res.json()
            if data.get('message'):
                return data['message']
        except: pass
        time.sleep(interval)


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    # ↓↓↓ 在這裡加入你的代碼 ↓↓↓

    send_alert('很抱歉，此單元尚在開發中，請返回選擇其他選項。')

    # 彈出視窗關閉後，重新發送選擇按鈕
    send_buttons(
        labels     = ['效度', '信度'],
        colors     = ['gray', 'blue'],
        size       = 'small',
        button_ids = ['validity.py', 'btn_reliability']
    )

    user_reply = wait_for_user()
    print(f"[用戶點擊] {user_reply}")

    import subprocess
    base_args = ['--username', username, '--session_id', session_id, '--log_path', log_path]
    if 'btn_reliability' in user_reply:
        subprocess.Popen(['python', 'reliability.py'] + base_args,
                         cwd=os.path.dirname(os.path.abspath(__file__)))
    elif 'validity.py' in user_reply:
        subprocess.Popen(['python', 'validity.py'] + base_args,
                         cwd=os.path.dirname(os.path.abspath(__file__)))

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[reliability.py 執行完畢]")


if __name__ == '__main__':
    main()