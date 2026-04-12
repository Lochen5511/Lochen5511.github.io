import argparse
import time
import requests
import os
import csv
import openai
from datetime import datetime
from dotenv import load_dotenv

# ──────────────────────────────────────────
# 環境變數 & OpenAI
# ──────────────────────────────────────────
load_dotenv(r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\.env")
openai.api_key = os.getenv("AIKEY")

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

print(f"[va_pd.py] 啟動  user={username}  session={session_id}")

BACKEND      = 'http://localhost:5000'
USER_TIMEOUT = 300
N_TOTAL      = 30   # 模擬學生總數
N_GROUP      = 8    # 高低分組人數
N_QUESTIONS  = 8    # 題目數


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

def is_exit(val) -> bool:
    return val is None or val == '__INTERRUPTED__'

def write_log(content: str):
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def send(text, delay=0):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    _post('/push', {
        'text': text, 'username': username,
        'session_id': session_id, 'log_path': log_path,
    })
    print(f"[send] {text[:50]}")

def send_buttons(labels, delay=0, colors=None, size='medium',
                 sizes=None, button_ids=None):
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
        'text': f'__BUTTONS__{parts}', 'username': username,
        'session_id': session_id, 'log_path': '',
    })
    _lock(True)
    print(f"[buttons] {labels}")

def wait_for_user(interval=0.5, timeout=USER_TIMEOUT):
    while True:
        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            write_log('[中斷] 用戶輸入 ID，流程中斷')
            _lock(False)
            return '__INTERRUPTED__'

        online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
        if not online.get('online', True):
            write_log('用戶已離開系統')
            _lock(False)
            return None

        time.sleep(interval)


# ──────────────────────────────────────────
# 讀取 AnswerMatrix
# ──────────────────────────────────────────
def load_answer_matrix() -> list:
    """
    讀取 AnswerMatrix.csv，回傳每個學生的作答列表（不含標題列和正確答案列）。
    """
    session_dir = os.path.dirname(log_path) if log_path else '.'
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    if not os.path.exists(matrix_path):
        print(f"[va_pd] AnswerMatrix 不存在：{matrix_path}")
        return []

    answers = []
    try:
        with open(matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)

        # 第一列：標題（Q1~Q8, 總分）
        # 第二列：正確答案
        # 第三列起：學生作答
        for row in rows[2:]:
            if len(row) >= N_QUESTIONS:
                # 只取前 N_QUESTIONS 欄（排除總分欄）
                answers.append(row[:N_QUESTIONS])
    except Exception as e:
        print(f"[va_pd] AnswerMatrix 讀取失敗：{e}")

    print(f"[va_pd] 讀取 {len(answers)} 筆學生作答")
    return answers


# ──────────────────────────────────────────
# 計算難度與鑑別度
# ──────────────────────────────────────────
def calc_pd(answers: list) -> dict:
    """
    計算每題的難度（P）與鑑別度（D）。
    正確答案固定為 A（每題的 A 選項為正確答案）。
    回傳格式：{
        'Q1': {'p': 0.8, 'd': 0.5, 'correct': 24},
        ...
    }
    """
    n = len(answers)
    if n == 0:
        return {}

    correct_ans = 'A'

    # 計算每個學生的總分
    scores = []
    for row in answers:
        score = sum(1 for ans in row if ans == correct_ans)
        scores.append(score)

    # 依總分排序，取高低分組
    indexed = sorted(enumerate(scores), key=lambda x: x[1])
    low_indices  = [i for i, _ in indexed[:N_GROUP]]
    high_indices = [i for i, _ in indexed[-N_GROUP:]]

    result = {}
    for q_idx in range(N_QUESTIONS):
        q_key = f'Q{q_idx + 1}'

        correct_count = sum(1 for row in answers if row[q_idx] == correct_ans)
        p = round(correct_count / n, 3)

        high_correct = sum(1 for i in high_indices if answers[i][q_idx] == correct_ans)
        low_correct  = sum(1 for i in low_indices  if answers[i][q_idx] == correct_ans)
        d = round(high_correct / N_GROUP - low_correct / N_GROUP, 3)

        result[q_key] = {
            'p':       p,
            'd':       d,
            'correct': correct_count,
        }

    return result


# ──────────────────────────────────────────
# AI 解讀
# ──────────────────────────────────────────
SYSTEM_PROMPT_PD = """\
你是一位教育測驗專家，請根據以下難度（P）和鑑別度（D）的計算結果，用繁體中文給出簡明的解讀。

難度 P：答對人數 ÷ 總人數。P 越接近 1 越簡單，越接近 0 越困難。
鑑別度 D：高分組答對比例 − 低分組答對比例。D 越高（接近 1）鑑別力越強；D < 0 表示題目有問題。

請針對每一題給出：
1. 難度評價（偏易 / 適中 / 偏難）
2. 鑑別度評價（優良 ≥ 0.4 / 良好 0.3–0.39 / 尚可 0.2–0.29 / 偏低 < 0.2 / 負值=有問題）
3. 一句話建議

格式：每題一段，用「第 N 題」開頭，不要使用 Markdown 符號。\
"""

def ask_ai_interpretation(pd_result: dict) -> str:
    """呼叫 OpenAI 解讀難度與鑑別度"""
    lines = []
    for q_key, val in pd_result.items():
        lines.append(
            f"{q_key}：難度 P={val['p']}，鑑別度 D={val['d']}，"
            f"答對人數={val['correct']}/{N_TOTAL}"
        )
    user_prompt = '\n'.join(lines)

    try:
        response = openai.ChatCompletion.create(
            model='gpt-4o',
            temperature=0.5,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT_PD},
                {'role': 'user',   'content': user_prompt},
            ]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"[va_pd] OpenAI 失敗：{e}")
        return None


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    send(
        '請你先把檔案下載下來，接下來，我們來算難度和鑑別度',
        delay=0.5
    )

    # 讀取 AnswerMatrix
    answers = load_answer_matrix()
    if not answers:
        send('（無法讀取作答資料，請聯絡助教。）', delay=0.5)
        return

    send(f'已讀取 {len(answers)} 位孿生學生的作答，計算中…', delay=0.5)

    # 計算難度與鑑別度
    pd_result = calc_pd(answers)

    # 格式化結果訊息
    summary_lines = ['各題難度與鑑別度：\n']
    for q_key, val in pd_result.items():
        summary_lines.append(
            f'{q_key}｜難度 P = {val["p"]:.3f}｜鑑別度 D = {val["d"]:.3f}'
        )
    send('\n'.join(summary_lines), delay=0.5)
    write_log(f'[va_pd] 難度鑑別度計算完成：{pd_result}')

    # AI 解讀
    send('正在請 AI 解讀結果…', delay=0.3)
    _thinking(True)
    interpretation = ask_ai_interpretation(pd_result)
    _thinking(False)

    if interpretation:
        send(interpretation, delay=0.3)
        write_log(f'[va_pd] AI 解讀完成')
    else:
        send('（AI 解讀失敗，請聯絡助教。）', delay=0.3)

    # ↓↓↓ 後續流程在此繼續開發 ↓↓↓

    print("[va_pd.py] 執行完畢")


if __name__ == '__main__':
    main()