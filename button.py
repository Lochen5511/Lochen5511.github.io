import argparse
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
# 主要執行區塊（在此放置你的代碼）
# ──────────────────────────────────────────
def main():
    write_log("button.py 已啟動")

    # ↓↓↓ 在這裡加入你的代碼 ↓↓↓


    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑

    write_log("button.py 執行完畢")
    print("[button.py 執行完畢]")


if __name__ == '__main__':
    main()