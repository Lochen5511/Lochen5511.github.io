"""
convert_paths.py
────────────────────────────────────────────────────────
將 session_db.json 內所有 log_path 從絕對路徑轉換為相對路徑。

作用：
    本專案原本將 log_path 以絕對路徑形式（如
    C:\\Users\\Procidens_Pulvis\\...\\log\\...）儲存於
    session_db.json。當專案搬移至新電腦時，這些路徑會全部
    失效，導致系統找不到對應的 log 檔。

    執行此腳本後，所有 log_path 將改為相對於 LOG_DIR 的
    Unix 風格相對路徑（如 宋沐云_20260401_112720/宋沐云_20260401_112720.txt），
    使專案在任何電腦、任何磁碟位置都能正常運作。

執行前注意：
    1. 請先關閉 name.py 伺服器，避免同時寫入衝突。
    2. 腳本會自動備份原始檔案為 session_db.json.path_backup。
    3. 無法轉換的路徑（不在 LOG_DIR 內）會印出警告並跳過。

執行方式：
    python convert_paths.py
"""

import json
import shutil
from pathlib import Path

# LOG_DIR 根據腳本位置自動推算（腳本放在 Lochen5511.github.io\ 底下）
LOG_DIR = Path(__file__).parent.parent / "log"


def convert_to_relative_paths():
    db_path = LOG_DIR / "session_db.json"

    if not db_path.exists():
        print(f"❌ 找不到 session_db.json：{db_path}")
        return

    # 備份
    backup_path = str(db_path) + ".path_backup"
    shutil.copy(db_path, backup_path)
    print(f"✅ 已備份至：{backup_path}\n")

    with open(db_path, 'r', encoding='utf-8') as f:
        db = json.load(f)

    changed = 0
    skipped = 0
    warned  = 0

    for session_id, record in db.items():
        if not isinstance(record, dict):
            continue

        raw = record.get('log_path', '')
        if not raw:
            continue

        p = Path(raw)

        # 已經是相對路徑，跳過
        if not p.is_absolute():
            skipped += 1
            continue

        try:
            relative = p.relative_to(LOG_DIR).as_posix()
            record['log_path'] = relative
            changed += 1
            print(f"  ✔ {session_id}")
            print(f"      {raw}")
            print(f"    → {relative}\n")
        except ValueError:
            print(f"  ⚠️  {session_id}：路徑不在 LOG_DIR 內，跳過")
            print(f"      {raw}\n")
            warned += 1

    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print("─" * 50)
    print(f"完成。轉換 {changed} 筆 | 已是相對路徑跳過 {skipped} 筆 | 警告 {warned} 筆")


if __name__ == '__main__':
    convert_to_relative_paths()