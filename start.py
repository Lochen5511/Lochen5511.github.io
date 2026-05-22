# start.py
import subprocess, threading, re, json, sys, os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"       # 與 name.py 同層
REPO_DIR    = Path(__file__).parent                       # git repo 根目錄（同層）

def update_config(url: str):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    config["backend"] = url
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"✅ config.json 已更新：{url}")

def git_push(url: str):
    try:
        subprocess.run(["git", "add", str(CONFIG_PATH)], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "commit", "-m", f"chore: update backend url to {url}"], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "push"], cwd=REPO_DIR, check=True)
        print("✅ 已 push 到 GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ git push 失敗：{e}")

def watch_cloudflared(proc):
    url_found = threading.Event()

    def _read():
        for line in proc.stderr:
            print(f"[cloudflared] {line}", end="")
            match = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', line)
            if match and not url_found.is_set():
                url_found.set()
                url = match.group(0)
                update_config(url)
                git_push(url)

    t = threading.Thread(target=_read, daemon=True)
    t.start()

    if not url_found.wait(timeout=30):
        print("❌ 超時：未取得 cloudflared URL")
        proc.terminate()
        sys.exit(1)

if __name__ == "__main__":
    # 修正 Windows 編碼問題
    os.environ["PYTHONIOENCODING"] = "utf-8"

    print("🚇 啟動 cloudflared tunnel...")
    cf = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:5000"],
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",       # ← 修正 cp950 問題
        errors="replace",       # ← 無法解碼的字元用 ? 取代，不會崩潰
        bufsize=1,
    )

    watch_cloudflared(cf)

    print("🚀 啟動 name.py...")
    server = subprocess.Popen([sys.executable, "name.py"])

    try:
        server.wait()
    except KeyboardInterrupt:
        print("\n🛑 關閉中...")
        cf.terminate()
        server.terminate()