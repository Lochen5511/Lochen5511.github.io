import argparse
import os
import re
import time
import requests
import csv
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ──────────────────────────────────────────
# 接收變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
parser.add_argument('--que_log',    default='')
args = parser.parse_args()

username        = args.username
session_id      = args.session_id
log_path        = args.log_path
revised_que_log = args.que_log
BACKEND         = 'http://localhost:5000'

load_dotenv(Path(__file__).parent.parent / ".env")

print(f"[te_pd.py] 啟動  user={username}  session={session_id}")

# ──────────────────────────────────────────
# 路徑設定
# ──────────────────────────────────────────
session_dir        = os.path.dirname(log_path)
old_folder_name    = os.path.basename(session_dir)
old_session_id     = old_folder_name.replace(f"{username}_", "", 1)
te_pd_count_path   = os.path.join(session_dir, f"{old_session_id}_te_pd_count.txt")

print(f"[te_pd] session_dir：{session_dir}")

# ──────────────────────────────────────────
# 工具函數（與 true_ending.py 相同）
# ──────────────────────────────────────────
def _post(path: str, body: dict):
    try:
        requests.post(f"{BACKEND}{path}", json=body, timeout=5)
    except Exception as e:
        print(f"[post {path}] {e}")

def _get(path: str, params: dict = None):
    try:
        res = requests.get(f"{BACKEND}{path}", params=params, timeout=5)
        return res.json()
    except Exception as e:
        print(f"[get {path}] {e}")
        return {}

def _thinking(state: bool):
    _post('/thinking', {'username': username, 'session_id': session_id, 'thinking': state})

def _lock(locked: bool):
    _post('/lock_input', {'session_id': session_id, 'locked': locked})

def _write_log(content: str):
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def send(text: str, delay: float = 0):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    _post('/push', {
        'text':       text,
        'username':   username,
        'session_id': session_id,
        'log_path':   log_path,
    })
    print(f"[send] {text[:60]}")

def send_button(label: str, delay: float = 0,
                color: str = 'gold', size: str = 'medium',
                button_id: str = ''):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    bid = button_id or label
    _post('/push', {
        'text':       f'__BUTTON__{label}||{color}||{size}||{bid}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    _lock(True)
    print(f"[button] {label}  id={bid}")

def send_buttons(labels: list, delay: float = 0,
                 colors: list = None, size: str = 'medium',
                 sizes: list = None, button_ids: list = None):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    n          = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    size_list  = sizes      or [size]  * n
    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )
    _post('/push', {
        'text':       f'__BUTTONS__{parts}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    _lock(True)
    print(f"[buttons] {labels}")

def wait_for_user(interval: float = 0.5, timeout: int = 300, wait_limit: int = None) -> str | None:
    import time as _time
    start = _time.time()
    ONLINE_CHECK_DELAY = 10

    while True:
        elapsed = _time.time() - start

        if wait_limit and elapsed > wait_limit:
            print(f"[wait_for_user] 等待超時 wait_limit={wait_limit}s")
            _write_log(f'[逾時] 等待作答超過 {wait_limit} 秒，流程中斷')
            _lock(False)
            return None

        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            print(f"[wait_for_user] session={session_id} 被 ID 輸入中斷")
            _write_log('[中斷] 用戶輸入 ID，流程中斷')
            _lock(False)
            return '__INTERRUPTED__'

        if elapsed >= ONLINE_CHECK_DELAY:
            online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
            if not online.get('online', True):
                print(f"[wait_for_user] 用戶已離開 session={session_id}")
                _write_log('用戶已離開系統')
                _lock(False)
                return None

        _time.sleep(interval)


# ──────────────────────────────────────────
# 尋找最新的指定 round AnswerMatrix
# ──────────────────────────────────────────
def find_latest_matrix(round_tag: str = 'r2') -> str:
    """在 session_dir 中找最新的 *_AnswerMatrix_{round_tag}_*.csv"""
    candidates = []
    try:
        for fn in os.listdir(session_dir):
            if (fn.startswith(username)
                    and f'_AnswerMatrix_{round_tag}_' in fn
                    and fn.endswith('.csv')):
                full = os.path.join(session_dir, fn)
                candidates.append((os.path.getmtime(full), full))
    except Exception as e:
        print(f"[find_latest_matrix] 掃描失敗：{e}")
        return ''

    if not candidates:
        print(f"[find_latest_matrix] 找不到 {round_tag} AnswerMatrix")
        return ''

    candidates.sort(reverse=True)
    chosen = candidates[0][1]
    print(f"[find_latest_matrix] 使用：{chosen}")
    return chosen


# ──────────────────────────────────────────
# 從 AnswerMatrix CSV 計算 P 值與 D 值
# ──────────────────────────────────────────
def compute_pd_from_matrix(matrix_path: str) -> dict:
    """
    讀取 AnswerMatrix CSV（0/1 格式），計算每題的 P 值與 D 值。
    直接複製自 va_pd.py 的 calc_pd 邏輯。
    回傳 {q_key: {'p': float, 'd': float}} dict。
    """
    CORRECT_ANS = 1  # 整數 1 for binary answers
    N_GROUP = 10
    N_QUESTIONS = 8
    
    if not os.path.exists(matrix_path):
        print(f"[compute_pd] 檔案不存在：{matrix_path}")
        return {}

    answers = []
    question_cols = []
    try:
        with open(matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)

        header        = rows[0] if rows else []
        question_cols = [i for i, h in enumerate(header) if re.match(r'^Q\d+$', h)]
        n_questions   = len(question_cols)

        for row in rows[1:]:
            if not row:
                continue
            try:
                binary = [int(row[i]) for i in question_cols]
                answers.append(binary)
            except (ValueError, IndexError) as e:
                print(f"[compute_pd] 跳過無效行：{row}  原因：{e}")

    except Exception as e:
        print(f"[compute_pd] 讀取失敗：{e}")
        return {}

    n = len(answers)
    if n == 0 or not question_cols:
        print(f"[compute_pd] 無有效資料（n={n}, q={len(question_cols)}）")
        return {}

    scores = []
    for row in answers:
        score = sum(1 for ans in row if ans == CORRECT_ANS)
        scores.append(score)

    indexed      = sorted(enumerate(scores), key=lambda x: x[1])
    low_indices  = [i for i, _ in indexed[:N_GROUP]]
    high_indices = [i for i, _ in indexed[-N_GROUP:]]

    result = {}
    for q_idx in range(N_QUESTIONS):
        q_key = f'Q{q_idx + 1}'

        correct_count = sum(1 for row in answers if row[q_idx] == CORRECT_ANS)
        p = round(correct_count / n, 3)

        high_correct = sum(1 for i in high_indices if answers[i][q_idx] == CORRECT_ANS)
        low_correct  = sum(1 for i in low_indices  if answers[i][q_idx] == CORRECT_ANS)
        d = round(high_correct / N_GROUP - low_correct / N_GROUP, 3)

        result[q_key] = {
            'p':       p,
            'd':       d,
        }

    print(f"[compute_pd] 計算完成：{n} 人，{N_QUESTIONS} 題")
    return result


# ──────────────────────────────────────────
# 讀取第一輪 PD 報告（供比較用）
# ──────────────────────────────────────────
def load_r1_pd() -> dict:
    """
    嘗試從 session_dir 找到第一輪 PD txt，優先固定命名的 r1 檔案。
    格式：q_key｜p｜d｜label，與 true_ending.py 的 load_pd_report 相同。
    """
    r1_path    = os.path.join(session_dir, f"{old_session_id}_r1_pd_report.txt")
    candidates = [r1_path] if os.path.exists(r1_path) else []

    if not candidates:
        try:
            for fn in os.listdir(session_dir):
                if fn.endswith('_pd_report.txt') or fn.endswith('_pd.txt'):
                    candidates.append(os.path.join(session_dir, fn))
        except Exception as e:
            print(f"[load_r1_pd] 掃描失敗：{e}")

    for path in candidates:
        result = {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('題目') or line.startswith('─'):
                        continue
                    parts = [p.strip() for p in line.split('｜')]
                    if len(parts) < 3:
                        continue
                    q_key = parts[0].replace('\u3000', '').replace(' ', '')
                    if not re.match(r'^Q\d+$', q_key):
                        continue
                    try:
                        p_val = float(parts[1])
                        d_val = float(parts[2])
                    except ValueError:
                        continue
                    label = parts[3] if len(parts) > 3 else ''
                    result[q_key] = {'p': p_val, 'd': d_val, 'label': label}
        except Exception as e:
            print(f"[load_r1_pd] 讀取 {path} 失敗：{e}")
            continue

        if result:
            print(f"[load_r1_pd] 從 {path} 讀取到 {len(result)} 題")
            return result

    print("[load_r1_pd] 找不到第一輪 PD 報告")
    return {}


# ──────────────────────────────────────────
# 推送統計資料到前端側邊欄
# ──────────────────────────────────────────
def push_stats(all_answers_raw: list, question_count: int):
    """將作答矩陣（0/1 格式）推送為 __DATA__ 結構供側邊欄顯示。"""
    correct_answers = ['A'] * question_count
    stats = {}
    for q_idx in range(question_count):
        key    = f'Q{q_idx + 1}'
        counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for row in all_answers_raw:
            if q_idx < len(row):
                counts['A' if row[q_idx] == 1 else 'B'] += 1
        stats[key] = counts

    students = [
        {
            'id':      i + 1,
            'answers': ['A' if v == 1 else 'B' for v in row[:question_count]],
            'score':   sum(row[:question_count]),
        }
        for i, row in enumerate(all_answers_raw)
    ]

    push_data = json.dumps({
        'type':       'answer_matrix',
        'stats':      stats,
        'n_students': len(all_answers_raw),
        'students':   students,
        'correct':    correct_answers,
    }, ensure_ascii=False)

    _post('/push', {
        'text':       f'__DATA__{push_data}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f"[push_stats] 已推送統計，共 {len(all_answers_raw)} 筆")


# ──────────────────────────────────────────
# D 值評語
# ──────────────────────────────────────────
def d_label(d: float) -> str:
    if d >= 0.4:    return '優異'
    elif d >= 0.25: return '正常'
    else:           return '待加強'


# ──────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────
def main():
    _write_log('[te_pd] 啟動')

    # 讀取目前執行次數
    try:
        with open(te_pd_count_path, 'r', encoding='utf-8') as f:
            te_pd_run_count = int(f.read().strip())
    except Exception:
        te_pd_run_count = 0

    te_pd_run_count += 1
    try:
        with open(te_pd_count_path, 'w', encoding='utf-8') as f:
            f.write(str(te_pd_run_count))
    except Exception as e:
        print(f"[te_pd] 計數寫入失敗：{e}")

    print(f"[te_pd] 第 {te_pd_run_count} 次執行")

    send('孿生班級已完成作答，正在計算新的難度與鑑別度……', delay=1)
    _thinking(True)

    # ── 找最新一輪 r2 作答矩陣 ──
    r2_matrix_path = find_latest_matrix('r2')
    if not r2_matrix_path:
        _thinking(False)
        send('⚠️ 找不到作答矩陣，請通知系統管理員。', delay=0.3)
        _write_log('[te_pd] 找不到 r2 AnswerMatrix，流程中止')
        return

    # ── 計算 P/D ──
    r2_pd = compute_pd_from_matrix(r2_matrix_path)
    if not r2_pd:
        _thinking(False)
        send('⚠️ P/D 計算失敗，請通知系統管理員。', delay=0.3)
        _write_log('[te_pd] r2 PD 計算失敗，流程中止')
        return

    # ── 讀取矩陣原始內容供側邊欄推送 ──
    try:
        with open(r2_matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)
        header        = rows[0] if rows else []
        question_cols = [i for i, h in enumerate(header) if re.match(r'^Q\d+$', h)]
        raw_answers   = []
        for row in rows[1:]:
            if not row:
                continue
            try:
                raw_answers.append([int(row[i]) for i in question_cols])
            except (ValueError, IndexError):
                pass
        if raw_answers:
            push_stats(raw_answers, len(question_cols))
    except Exception as e:
        print(f"[te_pd] 推送側邊欄統計失敗：{e}")

    _thinking(False)

    # ── 讀取第一輪 PD 供比較 ──
    r1_pd = load_r1_pd()

    # ── 發送本輪 PD 表格（與 true_ending.py 格式相同）──
    table_lines = ['【修改後】各題難度與鑑別度總覽：\n']
    table_lines.append('題目｜難度 P｜鑑別度 D｜評價')
    table_lines.append('─' * 32)

    for q_key in sorted(r2_pd.keys(), key=lambda x: int(x.replace('Q', ''))):
        val   = r2_pd[q_key]
        label = d_label(val['d'])
        table_lines.append(f"{q_key}｜{val['p']}｜{val['d']}｜{label}")

    send('\n'.join(table_lines), delay=0.5)

    # ── 若有第一輪 PD，發送比較表 ──
    if r1_pd:
        compare_lines = ['【修改前 vs 修改後 鑑別度比較】\n']
        compare_lines.append('題目｜D（修改前）｜D（修改後）｜變化')
        compare_lines.append('─' * 36)

        for q_key in sorted(r2_pd.keys(), key=lambda x: int(x.replace('Q', ''))):
            d2  = r2_pd[q_key]['d']
            d1  = r1_pd.get(q_key, {}).get('d', None)
            if d1 is None:
                compare_lines.append(f"{q_key}｜ — ｜{d2}｜—")
            else:
                diff  = round(d2 - d1, 3)
                arrow = '↑' if diff > 0 else ('↓' if diff < 0 else '→')
                compare_lines.append(f"{q_key}｜{d1}｜{d2}｜{arrow}{abs(diff)}")

        send('\n'.join(compare_lines), delay=0.5)

    # ── 判斷是否仍有鑑別度不足的題目 ──
    still_weak = sorted(
        [q_key for q_key, val in r2_pd.items() if val['d'] < 0.25],
        key=lambda x: int(x.replace('Q', ''))
    )

    _write_log(f'[te_pd] PD 計算完成，仍待加強題目：{still_weak}')

    # ── 全部達標：結束流程 ──
    if not still_weak:
        send(
            '🎉 恭喜！修改後所有題目的鑑別度均已達標（D ≥ 0.25）。\n'
            '你的題目修改非常成功，孿生班級的作答結果確認了這一點！',
            delay=0.5,
        )
        send(f'課程流程到此完成，{username}，謝謝你的參與！', delay=0.5)
        _write_log('[te_pd] 所有題目鑑別度達標，流程結束')
        return

    # ── 達到上限：強制進入結束階段 ──
    if te_pd_run_count >= 2:
        send(
            f'目前仍有 {len(still_weak)} 題鑑別度未達標：{ "、".join(still_weak) }\n'
            f'已完成兩輪修改，進入最終總結階段。',
            delay=0.5,
        )
        _write_log('[te_pd] 已達執行上限（2次），強制結束')
        send(f'課程流程到此完成，{username}，謝謝你的參與！', delay=0.5)
        return

    # ── 仍有弱題：不提供結束選項，必須繼續修改 ──
    weak_summary = '、'.join(still_weak)
    send(
        f'目前仍有 {len(still_weak)} 題鑑別度未達標（D < 0.25）：{weak_summary}\n'
        f'讓我們繼續修改，直到所有題目都達標為止！',
        delay=0.5,
    )
    send_button(
        label     = '繼續修改弱題',
        color     = 'gold',
        size      = 'medium',
        button_id = 'btn_continue_revise',
        delay     = 0.3,
    )

    choice = wait_for_user()
    if choice is None or choice == '__INTERRUPTED__':
        _write_log('[te_pd] 用戶離開或中斷，流程結束')
        return

    # ── 重新啟動 true_ending.py，帶入 --round 2 跳過開頭 ──
    import sys
    import subprocess

    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_args  = [
        '--username',   username,
        '--session_id', session_id,
        '--log_path',   log_path,
        '--round',      '2',
        '--que_log',    revised_que_log,
    ]
    try:
        subprocess.Popen(
            [sys.executable, 'true_ending.py'] + base_args,
            cwd=script_dir,
        )
        print('[te_pd] 已重新啟動 true_ending.py（--round 2）')
        _write_log('[te_pd] 已重新啟動 true_ending.py（--round 2）進行下一輪修改')
    except Exception as e:
        print(f'[te_pd] 重新啟動 true_ending.py 失敗：{e}')
        send(f'⚠️ 重新啟動修題流程失敗，請通知系統管理員。\n錯誤訊息：{e}', delay=0.3)


if __name__ == '__main__':
    main()