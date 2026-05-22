import argparse
import re
import time
import requests
import os
import openai
from dotenv import load_dotenv
from datetime import datetime

# ──────────────────────────────────────────
# 環境變數 & OpenAI
# ──────────────────────────────────────────
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
openai.api_key = os.getenv("AIKEY")

# ──────────────────────────────────────────
# 接收變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
parser.add_argument('--que_log',    default='')   # ← 新增：接收 que_set_log 路徑
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path
que_log    = args.que_log    # {session_id}_que_set_log.txt 路徑

print(f"[que_ana.py] 啟動  user={username}  session={session_id}")
print(f"[que_ana.py] que_log={que_log}")

BACKEND      = 'http://localhost:5000'
USER_TIMEOUT = 300


# ──────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────
def _post(path, body):
    try:
        requests.post(f"{BACKEND}{path}", json=body, timeout=5)
    except Exception as e:
        print(f"[post {path}] {e}")

def _get(path, params=None):
    try:
        res = requests.get(f"{BACKEND}{path}", params=params, timeout=5)
        return res.json()
    except Exception as e:
        print(f"[get {path}] {e}")
        return {}

def _thinking(state):
    _post('/thinking', {'username': username, 'session_id': session_id, 'thinking': state})

def _lock(locked):
    _post('/lock_input', {'session_id': session_id, 'locked': locked})

def send(text, delay=0):
    if delay > 0:
        _thinking(True); time.sleep(delay); _thinking(False)
    _post('/push', {
        'text': text, 'username': username,
        'session_id': session_id, 'log_path': log_path,
    })
    print(f"[send] {text[:50]}")

def send_buttons(labels, delay=0, colors=None, size='medium',
                 sizes=None, button_ids=None):
    if delay > 0:
        _thinking(True); time.sleep(delay); _thinking(False)
    n          = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    size_list  = sizes      or [size]  * n
    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )
    _post('/push', {
        'text': f'__BUTTONS__{parts}', 'username': username,
        'session_id': session_id, 'log_path': '',
    })
    _lock(True)
    print(f"[buttons] {labels}")

def wait_for_user(interval=0.5, timeout=USER_TIMEOUT):
    while True:
        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            write_log('[中斷] 用戶輸入 ID，流程中斷')
            return '__INTERRUPTED__'

        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

        online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
        if not online.get('online', True):
            write_log('用戶已離開系統')
            return None

        time.sleep(interval)

def is_exit(val):
    return val is None or val == '__INTERRUPTED__'

def write_log(content):
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def ask_openai(system_prompt, user_prompt, model='gpt-4o', temperature=0.7):
    try:
        response = openai.ChatCompletion.create(
            model=model,
            temperature=temperature,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ]
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"[OpenAI 失敗] {e}")
        return None


LOG_DIR = Path(__file__).parent.parent / "log"
WIDE_TABLE   = os.path.join(LOG_DIR, 'validity_wide_table.csv')
MAX_STUDENTS = 30

SYSTEM_PROMPT = """\
請依據以下註釋與學生的認知數值，預測這個學生回答以下八題的答案，依據「?,?,?,?,?,?,?,?」的格式生成答案。

accuracy = 答對題數 ÷ 總題數。例如答對 6 題共 8 題 → 0.75。
avg_confidence = 所有題目的信心分數（1-5）加總 ÷ 題數。反映用戶對自己答案的整體把握程度。
low_conf_ratio = 信心分數 ≤ 2 的題目數 ÷ 總題數。比例越高代表用戶越不確定自己的答案。
high_conf_wrong_ratio = 信心分數 ≥ 4 但答錯的題目數 ÷ 總題數。這是最重要的指標之一，反映用戶「自信但錯誤」的程度，也就是迷思概念最強固的狀態。
V1a = V_FACE_OVERUSE（用外觀直覺當主要效度證據）
V1b = V_CONTENT_CRITERION_CONFUSE（把效標關聯/相關/預測的證據誤當內容效度或反之）
V1c = V_RELIABILITY_AS_VALIDITY（把信度指標/α 當效度證據）
V2a = V_CONCUR_PRED_SWAP（同時效度與預測效度顛倒）
V2b = V_TIME_BLIND（忽略時間線索，只要看到「相關」就固定選某一類）
X1 = X_REL_VALID_RELATION_ERROR（信度—效度關係推論錯：必要但不充分不懂/推反/否認關係）
V3a = V_CONSTRUCT_CONTENT_CONFUSE（把建構效度證據誤當內容效度）
V3b = V_CONSTRUCT_CRITERION_CONFUSE（把建構效度證據誤當效標關聯效度）

只輸出答案，格式嚴格為「X,X,X,X,X,X,X,X」（8 個大寫字母，以逗號分隔），不要任何其他文字。\
"""


def _acquire_lock(lock_path: str, timeout: float = 10.0) -> bool:
    import time as _time
    start = _time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            if _time.time() - start > timeout:
                print(f"[wide_table] 鎖定逾時，強制繼續讀取")
                return False
            _time.sleep(0.05)

def _release_lock(lock_path: str):
    try:
        os.remove(lock_path)
    except: pass

def load_wide_table() -> list:
    import csv
    lock_path = WIDE_TABLE + '.lock'
    acquired  = _acquire_lock(lock_path)
    rows = []
    try:
        with open(WIDE_TABLE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        print(f"[wide_table] 讀取 {len(rows)} 筆")
    except Exception as e:
        print(f"[wide_table 讀取失敗] {e}")
    finally:
        if acquired:
            _release_lock(lock_path)
    return rows


# ──────────────────────────────────────────
# que_set_log 讀取
# ──────────────────────────────────────────
def load_que_set_log() -> dict:
    """
    讀取 {session_id}_que_set_log.txt，
    回傳 dict：{題號(int): {concept, stem, clue, A, B, C, D,
                            易錯選項1, 易錯選項2, 易錯推測1, 易錯推測2}}
    """
    result = {}
    path   = que_log

    # 若 --que_log 未傳入，嘗試由 log_path 目錄推算
    if not path:
        session_dir = os.path.dirname(log_path) if log_path else LOG_DIR
        path = os.path.join(session_dir, f"{session_id}_que_set_log.txt")

    if not os.path.exists(path):
        print(f"[que_set_log] 檔案不存在：{path}")
        return result

    current_q = None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # 去掉時間戳記（若有，格式為 [YYYY-MM-DD HH:MM:SS]）
                if re.match(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ', line):
                    _, line = line.split('] ', 1)
                    line = line.strip()

                # 偵測 [QN_START]
                if line.startswith('[Q') and line.endswith('_START]'):
                    try:
                        n = int(line[2:-7])
                        current_q = n
                        result[n] = {}
                    except ValueError:
                        pass
                    continue

                # 偵測 [QN_END]
                if line.startswith('[Q') and line.endswith('_END]'):
                    current_q = None
                    continue

                # 解析 [QN] key=value
                if current_q is not None and line.startswith(f'[Q{current_q}]'):
                    body = line[len(f'[Q{current_q}]'):].strip()
                    if '=' in body:
                        key, val = body.split('=', 1)
                        result[current_q][key.strip()] = val.strip()

        print(f"[que_set_log] 讀取完成，共 {len(result)} 題")
    except Exception as e:
        print(f"[que_set_log 讀取失敗] {e}")

    return result


def que_info_summary(que_data: dict) -> str:
    """
    將 que_set_log 中所有題目的出題資訊整理為純文字，
    供注入 OpenAI prompt 使用。
    """
    if not que_data:
        return ''
    lines = ['【出題者提供的額外資訊】']
    for n in sorted(que_data.keys()):
        q = que_data[n]
        lines.append(
            f"第{n}題｜概念：{q.get('概念標籤','')}｜"
            f"關鍵線索：{q.get('關鍵線索','')}｜"
            f"易錯選項：{q.get('易錯選項1','')} / {q.get('易錯選項2','')}｜"
            f"易錯推測：{q.get('易錯推測1','')} / {q.get('易錯推測2','')}"
        )
    return '\n'.join(lines)


# ──────────────────────────────────────────
# prompt 組裝
# ──────────────────────────────────────────
def row_to_prompt(row: dict, questions: list, que_data: dict) -> str:
    stats = (
        f"accuracy={row.get('accuracy','')}  "
        f"avg_confidence={row.get('avg_confidence','')}  "
        f"low_conf_ratio={row.get('low_conf_ratio','')}  "
        f"high_conf_wrong_ratio={row.get('high_conf_wrong_ratio','')}\n"
        f"V1a={row.get('V1a','')}  V1b={row.get('V1b','')}  V1c={row.get('V1c','')}  "
        f"V2a={row.get('V2a','')}  V2b={row.get('V2b','')}  X1={row.get('X1','')}  "
        f"V3a={row.get('V3a','')}  V3b={row.get('V3b','')}"
    )
    ques = '\n'.join(
        f"題{i+1}：{q['stem']}\n選項：{', '.join(f'{k}. {v}' for k, v in q['options'].items())}"
        for i, q in enumerate(questions)
    )

    # 從 que_set_log 補充出題者設計意圖
    extra = que_info_summary(que_data)

    prompt = f"學生數值：\n{stats}\n\n題目：\n{ques}"
    if extra:
        prompt += f"\n\n{extra}"
    return prompt


# ──────────────────────────────────────────
# 答案矩陣存檔
# ──────────────────────────────────────────
def save_answer_matrix(answers: list, questions: list):
    import csv
    session_dir = os.path.dirname(log_path) if log_path else LOG_DIR
    out_path    = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    correct_answers = ['A'] * 8
    header = [f'Q{i+1}' for i in range(8)] + ['Total']
    try:
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in answers:
                binary = [1 if ans == 'A' else 0 for ans in row[:8]]
                score  = sum(binary)
                writer.writerow(binary + [score])
        print(f"[AnswerMatrix] 已儲存：{out_path}（{len(answers)} 筆）")
        write_log(f'[que_ana] AnswerMatrix 已儲存：{out_path}')
    except Exception as e:
        print(f"[AnswerMatrix 儲存失敗] {e}")
    return out_path


# ──────────────────────────────────────────
# 題目解析：優先 que_set_log，fallback 原 log
# ──────────────────────────────────────────
def parse_questions_from_que_log(que_data: dict) -> list:
    """從 que_set_log dict 組裝 questions list"""
    questions = []
    for n in sorted(que_data.keys()):
        q = que_data[n]
        if all(k in q for k in ('題幹', '正確答案A', '錯誤選項B', '錯誤選項C', '錯誤選項D')):
            questions.append({
                'stem':    q['題幹'],
                'options': {
                    'A': q['正確答案A'],
                    'B': q['錯誤選項B'],
                    'C': q['錯誤選項C'],
                    'D': q['錯誤選項D'],
                }
            })
    print(f"[parse_que_log] 解析到 {len(questions)} 題")
    return questions

def parse_questions_from_log() -> list:
    """Fallback：從原始 log_path 解析題目（與舊版相同）"""
    questions = []
    if not log_path or not os.path.exists(log_path):
        print(f"[parse] log 不存在：{log_path}")
        return questions
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '[命題' not in line or '完成]' not in line:
                    continue
                stripped = line.strip()
                if stripped.startswith('[') and '] ' in stripped:
                    stripped = stripped.split('] ', 1)[-1]
                body  = stripped.split(']', 1)[-1].strip()
                parts = {p.split('=', 1)[0].strip(): p.split('=', 1)[1].strip()
                         for p in body.split('|') if '=' in p}
                if all(k in parts for k in ('stem', 'A', 'B', 'C', 'D')):
                    questions.append({
                        'stem':    parts['stem'],
                        'options': {
                            'A': parts['A'],
                            'B': parts['B'],
                            'C': parts['C'],
                            'D': parts['D'],
                        }
                    })
    except Exception as e:
        print(f"[parse log 失敗] {e}")
    print(f"[parse fallback] 解析到 {len(questions)} 題")
    return questions


# ──────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────
def main():
    rows = load_wide_table()
    if not rows:
        send('（孿生學生資料讀取失敗，請聯絡助教。）')
        return

    # 讀取 que_set_log（含出題者的設計資訊）
    que_data = load_que_set_log()

    # 優先從 que_set_log 解析題目，不足再 fallback
    if len(que_data) >= 8:
        questions = parse_questions_from_que_log(que_data)
    else:
        print("[que_ana] que_set_log 題數不足，改用原始 log fallback")
        questions = parse_questions_from_log()

    if len(questions) < 8:
        send(f'（題目解析失敗，僅讀到 {len(questions)} 題，請聯絡助教。）')
        return

    target_rows = rows[:MAX_STUDENTS]
    total       = len(target_rows)
    print(f"[que_ana] 將生成 {total} 筆孿生答案")

    send('孿生 AI 學生正在作答中，請稍候…', delay=1)
    _thinking(True)

    all_answers = []
    for idx, row in enumerate(target_rows):
        # 傳入 que_data，讓 prompt 包含出題者設計意圖
        user_prompt = row_to_prompt(row, questions, que_data)
        reply       = ask_openai(SYSTEM_PROMPT, user_prompt, temperature=0.3)

        if not reply:
            print(f"[que_ana] 第 {idx+1} 筆 OpenAI 無回應，跳過")
            continue

        parts = [p.strip().upper() for p in reply.split(',')]
        if len(parts) == 8 and all(p in 'ABCD' for p in parts):
            all_answers.append(parts)
            print(f"[que_ana] 第 {idx+1} 筆：{parts}")
        else:
            print(f"[que_ana] 第 {idx+1} 筆格式異常，跳過：{reply}")

    _thinking(False)

    if not all_answers:
        send('（孿生學生作答失敗，請聯絡助教。）')
        return

    save_answer_matrix(all_answers, questions)

    import json
    correct_answers = ['A'] * 8
    stats = {}
    for q_idx in range(8):
        key    = f'Q{q_idx+1}'
        counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for row in all_answers:
            ans = row[q_idx] if q_idx < len(row) else None
            if ans in counts:
                counts[ans] += 1
        stats[key] = counts

    students = []
    for i, row in enumerate(all_answers):
        score = sum(1 for q_idx, ans in enumerate(row)
                    if q_idx < 8 and ans == correct_answers[q_idx])
        students.append({'id': i + 1, 'answers': row, 'score': score})

    push_data = json.dumps({
        'type':       'answer_matrix',
        'stats':      stats,
        'n_students': len(all_answers),
        'students':   students,
        'correct':    correct_answers,
    }, ensure_ascii=False)
    _post('/push', {
        'text':       f'__DATA__{push_data}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f"[que_ana] 已 push 統計資料到前端")

    session_dir = os.path.dirname(log_path) if log_path else LOG_DIR
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    send(
        f'孿生 AI 學生作答完成！共生成 {len(all_answers)} 份答案。\n'
        f'__LINK__{matrix_path}||AnswerMatrix.csv',
        delay=1
    )
    write_log(f'[que_ana] 完成，共 {len(all_answers)} 筆答案')
    print("[que_ana.py] 執行完畢")

    import sys
    import subprocess
    base_args = [
        '--username',   username,
        '--session_id', session_id,
        '--log_path',   log_path,
    ]
    subprocess.Popen(
        [sys.executable, 'va_pd.py'] + base_args,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    print("[que_ana.py] 已啟動 va_pd.py")


if __name__ == '__main__':
    main()