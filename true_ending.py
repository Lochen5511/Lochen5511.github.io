import argparse
import os
import re

# ──────────────────────────────────────────
# 接收變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[true_ending.py] 啟動  user={username}  session={session_id}")

# ──────────────────────────────────────────
# 路徑設定
# ──────────────────────────────────────────
# 從 log_path 反推舊 session_id 與題庫路徑
session_dir     = os.path.dirname(log_path)
old_folder_name = os.path.basename(session_dir)
old_session_id  = old_folder_name.replace(f"{username}_", "", 1)

pd_txt_path  = log_path
que_log_path = os.path.join(session_dir, f"{old_session_id}_que_set_log.txt")

print(f"[true_ending] PD 報告路徑：{pd_txt_path}")
print(f"[true_ending] 題庫路徑：  {que_log_path}")


# ──────────────────────────────────────────
# 讀取 PD 報告，回傳 dict
# {'Q1': {'p': 0.7, 'd': 0.9, 'label': '優異'}, ...}
# ──────────────────────────────────────────
def load_pd_report(path: str) -> dict:
    result = {}
    if not os.path.exists(path):
        print(f"[true_ending] PD 報告不存在：{path}")
        return result

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[true_ending] PD 報告讀取失敗：{e}")
        return result

    # 跳過標題行與分隔線，解析資料行
    # 格式：Q1　｜0.7　｜0.9　｜優異
    for line in lines:
        line = line.strip()
        if not line or line.startswith('題目') or line.startswith('─'):
            continue

        parts = [p.strip() for p in line.split('｜')]
        if len(parts) < 4:
            continue

        q_key = parts[0].replace('\u3000', '').replace(' ', '')  # 去除全形空格
        try:
            p_val = float(parts[1])
            d_val = float(parts[2])
        except ValueError:
            continue

        label = parts[3]
        result[q_key] = {'p': p_val, 'd': d_val, 'label': label}

    print(f"[true_ending] 讀取 PD 報告：{len(result)} 題")
    return result


# ──────────────────────────────────────────
# 讀取題庫 log，回傳 dict
# {'Q1': {'stem': ..., 'correct': ..., 'options': {...}, ...}, ...}
# ──────────────────────────────────────────
def load_que_log(path: str) -> dict:
    result = {}
    if not os.path.exists(path):
        print(f"[true_ending] 題庫不存在：{path}")
        return result

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[true_ending] 題庫讀取失敗：{e}")
        return result

    # 以 [QN_START] ... [QN_END] 切割每題區塊
    blocks = re.findall(r'\[Q(\d+)_START\](.*?)\[Q\1_END\]', content, re.DOTALL)

    for num_str, block in blocks:
        q_key  = f'Q{num_str}'
        q_data = {}

        for line in block.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            # 格式：[QN] 欄位名=值
            m = re.match(r'\[Q\d+\]\s*(.+?)=(.+)', line)
            if not m:
                continue

            field = m.group(1).strip()
            value = m.group(2).strip()

            field_map = {
                '題幹':     'stem',
                '概念標籤': 'concept',
                '關鍵線索': 'clues',
                '正確答案A': 'correct',
                '錯誤選項B': 'opt_b',
                '錯誤選項C': 'opt_c',
                '錯誤選項D': 'opt_d',
                '易錯選項1': 'distractor_1',
                '易錯選項2': 'distractor_2',
                '易錯推測1': 'misconception_1',
                '易錯推測2': 'misconception_2',
            }

            key = field_map.get(field)
            if key:
                q_data[key] = value

        result[q_key] = q_data

    print(f"[true_ending] 讀取題庫：{len(result)} 題")
    return result


# ──────────────────────────────────────────
# 篩選 D < 0.25 的題目，對照題庫合併資訊
# ──────────────────────────────────────────
def find_weak_questions(pd_data: dict, que_data: dict, threshold=0.25) -> list:
    """
    回傳清單，每筆為 dict：
    {
        'q_key':          'Q2',
        'p':              1.0,
        'd':              0.0,
        'label':          '待加強',
        'concept':        '表面效度',
        'stem':           '某學生看到…',
        'correct':        '表面效度',
        'opt_b':          '內容效度',
        'opt_c':          '建構效度',
        'opt_d':          '效標關聯效度',
        'distractor_1':   'B. 內容效度',
        'distractor_2':   'C. 建構效度',
        'misconception_1':'將直覺合理誤當內容代表性（V1a）',
        'misconception_2':'將外觀合理誤當構念驗證（V3a）',
        'clues':          '看起來合理、直覺判斷',
    }
    """
    weak = []
    for q_key, pd_info in sorted(pd_data.items(),
                                  key=lambda x: int(x[0].replace('Q', ''))):
        if pd_info['d'] < threshold:
            entry = {
                'q_key': q_key,
                'p':     pd_info['p'],
                'd':     pd_info['d'],
                'label': pd_info['label'],
            }
            # 合併題庫資訊（若題庫有該題）
            entry.update(que_data.get(q_key, {}))
            weak.append(entry)

    return weak


# ──────────────────────────────────────────
# 主程式（目前僅做讀取與印出，供後續開發驗證）
# ──────────────────────────────────────────
def main():
    pd_data  = load_pd_report(pd_txt_path)
    que_data = load_que_log(que_log_path)
    weak     = find_weak_questions(pd_data, que_data)

    print(f"\n[true_ending] D < 0.25 的題目共 {len(weak)} 題：")
    for q in weak:
        print(f"\n  ── {q['q_key']} ──")
        print(f"  難度 P={q['p']}　鑑別度 D={q['d']}　評價={q['label']}")
        print(f"  概念：{q.get('concept', '（無）')}")
        print(f"  題幹：{q.get('stem',    '（無）')}")
        print(f"  正確答案：{q.get('correct', '（無）')}")
        print(f"  易錯選項：{q.get('distractor_1','—')} / {q.get('distractor_2','—')}")
        print(f"  易錯推測：{q.get('misconception_1','—')}")
        print(f"            {q.get('misconception_2','—')}")
        print(f"  關鍵線索：{q.get('clues', '（無）')}")


if __name__ == '__main__':
    main()