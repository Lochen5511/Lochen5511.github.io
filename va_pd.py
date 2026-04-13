import argparse
import time
import requests
import os
import csv
import random
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
CORRECT_ANS  = 'A'  # 每題正確答案固定為 A


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
    print(f"[send] {text[:80]}")

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
    回傳格式：{
        'Q1': {'p': 0.8, 'd': 0.5, 'correct': 24},
        ...
    }
    """
    n = len(answers)
    if n == 0:
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
            'correct': correct_count,
        }

    return result


# ──────────────────────────────────────────
# 計算每題各選項被選次數
# ──────────────────────────────────────────
def calc_option_dist(answers: list) -> dict:
    """
    計算每題各選項（A/B/C/D）被選的次數。
    回傳格式：{
        'Q1': {'A': 20, 'B': 5, 'C': 3, 'D': 2},
        ...
    }
    """
    result = {}
    for q_idx in range(N_QUESTIONS):
        q_key  = f'Q{q_idx + 1}'
        counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for row in answers:
            opt = row[q_idx].strip().upper()
            if opt in counts:
                counts[opt] += 1
        result[q_key] = counts
    return result


# ──────────────────────────────────────────
# 生成四選一按鈕選項（含正解與干擾）
# ──────────────────────────────────────────
def make_question_choices(correct_q_idx: int, other_indices: list) -> tuple:
    """
    從 correct_q_idx（正解題號，0-based）和 other_indices 中隨機挑 3 題當干擾，
    打亂後回傳 (labels, button_ids, correct_button_id)。
    """
    pool = list(other_indices)
    random.shuffle(pool)
    distractors = pool[:3]

    all_q = [correct_q_idx] + distractors
    random.shuffle(all_q)

    labels     = [f'第 {q + 1} 題' for q in all_q]
    button_ids = [f'Q{q + 1}'      for q in all_q]
    correct_id = f'Q{correct_q_idx + 1}'

    return labels, button_ids, correct_id


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
# 核對流程
# ──────────────────────────────────────────
def verify_flow(pd_result: dict, answers: list):
    """三題核對互動流程"""

    all_idx = list(range(N_QUESTIONS))  # [0..7]

    # ── 預先算出正解 ──────────────────────────
    # 核對題 1：鑑別度最低（D 最小）的題目
    lowest_d_idx  = min(all_idx, key=lambda i: pd_result[f'Q{i+1}']['d'])

    # 核對題 2：難度最極端（|p - 0.5| 最大）的題目
    extreme_p_idx = max(all_idx, key=lambda i: abs(pd_result[f'Q{i+1}']['p'] - 0.5))

    # 核對題 3：鑑別度最低那題中，錯誤選項被選最多的選項
    opt_dist      = calc_option_dist(answers)
    focus_q_key   = f'Q{lowest_d_idx + 1}'
    dist_focus    = opt_dist[focus_q_key]
    wrong_opts    = {k: v for k, v in dist_focus.items() if k != CORRECT_ANS}
    most_distract = max(wrong_opts, key=lambda k: wrong_opts[k])

    # ── 核對題 1 ──────────────────────────────
    send('接下來，我們先做一個「核對」吧～看你算得跟我一不一樣？', delay=0.8)
    send(
        '核對題 1：請選出「你最需要優先修改」的那一題\n'
        '（通常是鑑別度最低、或出現負值的那題）',
        delay=0.5
    )

    other_idx_1 = [i for i in all_idx if i != lowest_d_idx]
    labels_1, ids_1, correct_id_1 = make_question_choices(lowest_d_idx, other_idx_1)
    send_buttons(labels_1, button_ids=ids_1, delay=0.3)

    ans_1 = wait_for_user()
    if is_exit(ans_1):
        return

    if ans_1 == correct_id_1:
        send('很好，你的判讀是對的。', delay=0.5)
        write_log(f'[va_pd] 核對題1 答對，選={ans_1}')
    else:
        d_val = pd_result[focus_q_key]['d']
        send(
            f'沒關係，第 {lowest_d_idx + 1} 題的鑑別度（D={d_val}）其實更需要優先處理。',
            delay=0.5
        )
        write_log(f'[va_pd] 核對題1 答錯，選={ans_1}，正解={correct_id_1}')

    send_buttons(['下一題'], colors=['skyblue'], delay=0.5)
    if is_exit(wait_for_user()):
        return

    # ── 核對題 2 ──────────────────────────────
    send(
        '核對題 2：請選出「難度最極端」的那一題\n'
        '（最簡單或最困難都算，也就是 p 值距離 0.5 最遠的那題）',
        delay=0.5
    )

    other_idx_2 = [i for i in all_idx if i != extreme_p_idx]
    labels_2, ids_2, correct_id_2 = make_question_choices(extreme_p_idx, other_idx_2)
    send_buttons(labels_2, button_ids=ids_2, delay=0.3)

    ans_2 = wait_for_user()
    if is_exit(ans_2):
        return

    if ans_2 == correct_id_2:
        send('很好，你抓到最極端的那題了。', delay=0.5)
        write_log(f'[va_pd] 核對題2 答對，選={ans_2}')
    else:
        p_val     = pd_result[f'Q{extreme_p_idx+1}']['p']
        direction = '太簡單' if p_val > 0.5 else '太困難'
        send(
            f'算錯了？第 {extreme_p_idx + 1} 題才是最極端（{direction}，p={p_val}）的一題。',
            delay=0.5
        )
        write_log(f'[va_pd] 核對題2 答錯，選={ans_2}，正解={correct_id_2}')

    send_buttons(['下一題'], colors=['skyblue'], delay=0.5)
    if is_exit(wait_for_user()):
        return

    # ── 核對題 3 ──────────────────────────────
    send(
        f'核對題 3：針對第 {lowest_d_idx + 1} 題，請選出「最多人選錯的選項」\n'
        f'（排除正確答案 A，哪個選項最誘答？）',
        delay=0.5
    )

    opt_labels = ['選項 A', '選項 B', '選項 C', '選項 D']
    opt_ids    = ['A', 'B', 'C', 'D']
    send_buttons(opt_labels, button_ids=opt_ids, delay=0.3)

    ans_3 = wait_for_user()
    if is_exit(ans_3):
        return

    if ans_3 == most_distract:
        send(f'對，就是選項 {most_distract} 最容易誘答。', delay=0.5)
        write_log(f'[va_pd] 核對題3 答對，選={ans_3}')
    else:
        send(
            f'是嗎？我認為最容易誘答的是「選項 {most_distract}」\n'
            f'（共有 {wrong_opts[most_distract]} 人選了這個選項）。',
            delay=0.5
        )
        write_log(f'[va_pd] 核對題3 答錯，選={ans_3}，正解={most_distract}')

    send_buttons(['完成核對'], colors=['lightgreen'], delay=0.5)
    if is_exit(wait_for_user()):
        return

    send('三題核對完成！', delay=0.5)
    write_log('[va_pd] 核對流程完成')


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    session_dir  = os.path.dirname(log_path) if log_path else '.'
    matrix_path  = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    send(
        '你已完成 8 題命題，也拿到孿生班級的作答結果了。\n'
        '接下來我們要做「審題」的事情，也就是用數據回頭檢討你每一題的品質。',
        delay=0.5
    )

    send(
        f'我先把原始作答資料準備好了。\n'
        f'__LINK__/download?path={matrix_path}||下載：AnswerMatrix.csv\n'
        f'（30 位孿生學生 × 8 題，每題選了哪個選項）\n'
        f'你先把檔案下載下來，用它來算難度與鑑別度。',
        delay=0.5
    )

    send(
        '先算難度（p 值）：對每一題看 30 個人裡面，有幾個人答對。\n'
        '公式：難度 p = 答對人數 ÷ 30\n'
        '理解方式：p 越接近 1 越簡單；p 越接近 0 越困難。',
        delay=0.5
    )

    send(
        '再算鑑別度（D 值），這一步你只要做兩件事：\n\n'
        'A. 先把 30 個人分成兩群：\n'
        '   先算每個人的總分（0–8），依總分排序後分成兩群：\n'
        '   高分組（分數最高的 8 人）、低分組（分數最低的 8 人）。\n\n'
        'B. 對每一題算「兩群差距」：\n'
        '   鑑別度 D =（高分組答對人數 ÷ 8）−（低分組答對人數 ÷ 8）\n\n'
        '小提醒：因為每群只有 8 人，D 值會以 0.125 為刻度變動，這是正常的。',
        delay=0.5
    )

    # 讀取 AnswerMatrix
    answers = load_answer_matrix()
    if not answers:
        send('（無法讀取作答資料，請聯絡助教。）', delay=0.5)
        return

    # 計算難度與鑑別度
    _thinking(True)
    time.sleep(1)
    _thinking(False)
    pd_result = calc_pd(answers)

    # 顯示結果
    summary_lines = ['各題難度與鑑別度：\n']
    for q_key, val in pd_result.items():
        summary_lines.append(
            f'{q_key}｜難度 P = {val["p"]:.3f}｜鑑別度 D = {val["d"]:.3f}'
        )
    send('\n'.join(summary_lines), delay=0.3)
    write_log(f'[va_pd] 難度鑑別度計算完成：{pd_result}')

    # AI 解讀
    send('正在請 AI 解讀結果…', delay=0.3)
    _thinking(True)
    interpretation = ask_ai_interpretation(pd_result)
    _thinking(False)

    if interpretation:
        send(interpretation, delay=0.3)
        write_log('[va_pd] AI 解讀完成')
    else:
        send('（AI 解讀失敗，請聯絡助教。）', delay=0.3)

    # 核對流程入口
    send_buttons(['開始核對'], colors=['gold'], delay=0.8)
    btn = wait_for_user()
    if is_exit(btn):
        return

    verify_flow(pd_result, answers)

    # ↓↓↓ 後續流程在此繼續開發 ↓↓↓

    print("[va_pd.py] 執行完畢")


if __name__ == '__main__':
    main()