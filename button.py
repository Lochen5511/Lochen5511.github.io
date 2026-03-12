import argparse
import time
import requests
from datetime import datetime

# ──────────────────────────────────────────
# 接收來自 name.py 的變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知', help='使用者名稱')
parser.add_argument('--session_id', default='',    help='登入時間戳')
parser.add_argument('--log_path',   default='',    help='對應的 log 檔路徑')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[button.py 啟動]")
print(f"  使用者：{username}")
print(f"  Session ID：{session_id}")
print(f"  Log 路徑：{log_path}")
print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("─" * 40)


# ──────────────────────────────────────────
# 工具函數：寫入 log
# ──────────────────────────────────────────
def write_log(message: str):
    """將訊息追加寫入該用戶的 log 檔"""
    if not log_path:
        return
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] [button.py] {message}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")


# ──────────────────────────────────────────
# 工具函數：發送訊息到隊列
# ──────────────────────────────────────────
def send(text: str, delay: float = 0):
    """等待 delay 秒後，將訊息推入 name.py 的隊列"""
    if delay > 0:
        # 通知前端顯示思考動畫
        try:
            requests.post('http://localhost:5000/thinking', json={
                'username':   username,
                'session_id': session_id,
                'thinking':   True
            })
        except Exception as e:
            print(f"[thinking 通知失敗] {e}")

        time.sleep(delay)

        # 通知前端隱藏思考動畫
        try:
            requests.post('http://localhost:5000/thinking', json={
                'username':   username,
                'session_id': session_id,
                'thinking':   False
            })
        except Exception as e:
            print(f"[thinking 通知失敗] {e}")
    
    try:
        requests.post('http://localhost:5000/push', json={
            'text':       text,
            'username':   username,
            'session_id': session_id,
            'log_path':   log_path,
        })
        print(f"[送出] {text}")
    except Exception as e:
        print(f"[送出失敗] {e}")


# ──────────────────────────────────────────
# 主要執行區塊（在此放置你的代碼）
# ──────────────────────────────────────────
def wait_for_user(interval: float = 0.5) -> str:
    """阻塞直到用戶發送訊息，回傳用戶說的話"""
    while True:
        try:
            res = requests.get('http://localhost:5000/fetch_user_input',
                               params={'session_id': session_id})
            data = res.json()
            if data.get('message'):
                return data['message']
        except Exception as e:
            print(f"[等待用戶失敗] {e}")
        time.sleep(interval)


# ──────────────────────────────────────────
# 主要執行區塊（在此放置你的代碼）
# ──────────────────────────────────────────
def main():
    # ↓↓↓ 在這裡加入你的代碼 ↓↓↓

    send('你好，{username}！我是艾評。')
    send('現在，讓我們開始校標關聯效度的問答。', delay=10)
    send('首先是闡發性問題', delay=2)

    # ── 示範：等待用戶回應並做出對應回應 ──
    send('請問你對「效度」的理解是什麼？', delay=1)

    user_reply = wait_for_user()          # 等待用戶發送訊息
    print(f"[用戶說] {user_reply}")

    # 根據用戶內容做出回應
    if '測量' in user_reply or '準確' in user_reply:
        send('很好！你掌握了效度的核心概念。', delay=1)
    else:
        send(f'你提到了「{user_reply}」，讓我們再深入討論一下。', delay=1)

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[button.py 執行完畢]")


if __name__ == '__main__':
    main()