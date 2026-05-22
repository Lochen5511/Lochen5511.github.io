"""
final_va.py
──────────────────────────────────────────
在 validity_analyze.analyze() 完成後呼叫。
輸入：analyze() 回傳的 report dict。
輸出：
  1. {username}_{session_id}_profile.json   （個人 JSON profile，存於 session 資料夾）
  2. validity_wide_table.csv                （wide table，存於 LOG_DIR 根目錄，全用戶共用）

使用方式（在 validity.py 末端）：
    from validity_analyze import analyze
    from final_va import export
    report = analyze(results, username, session_id, log_path)
    export(report, results, username, session_id, log_path)
"""

import json
import csv
import os
import time
from datetime import datetime


# ──────────────────────────────────────────
# 跨進程檔案鎖（Windows 相容）
# ──────────────────────────────────────────
def _acquire_lock(lock_path: str, timeout: float = 10.0):
    """建立 .lock 檔作為互斥鎖，最多等待 timeout 秒"""
    start = time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() - start > timeout:
                print(f"[final_va] 鎖定逾時，強制繼續寫入")
                return False
            time.sleep(0.1)

def _release_lock(lock_path: str):
    try:
        os.remove(lock_path)
    except: pass

# ──────────────────────────────────────────
# 常數
# ──────────────────────────────────────────
VERSION       = 'validity_branch_v1.1'
ALL_CODES     = ['V1a', 'V1b', 'V1c', 'V2a', 'V2b', 'X1', 'V3a', 'V3b']
V2_ITEMS      = {'V2_1', 'V2_2'}

# wide_table 固定存於此路徑，全用戶共用
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "log"
WIDE_TABLE = os.path.join(LOG_DIR, 'validity_wide_table.csv')

WIDE_TABLE_HEADER = [
    'admin_session_id',
    'accuracy', 'avg_confidence', 'low_conf_ratio', 'high_conf_wrong_ratio',
    'V1a', 'V1b', 'V1c', 'V2a', 'V2b', 'X1', 'V3a', 'V3b',
]


# ──────────────────────────────────────────
# 工具：建立 evidence 清單
# ──────────────────────────────────────────
def _build_evidence(results: list, v2_meta: dict) -> dict:
    evidence = {code: [] for code in ALL_CODES}

    for r in results:
        if r['item_id'] in V2_ITEMS:
            continue
        code = r.get('mistake_code')
        if code and not r['is_correct']:
            evidence[code].append(f"{r['item_id']}:{r['answer']}")

    # V2 pattern
    if v2_meta.get('V2a_severity') is not None or any(
        r['item_id'] == 'V2_1' and r['answer'] == 'B' for r in results
    ):
        v2_1 = next((r for r in results if r['item_id'] == 'V2_1'), None)
        v2_2 = next((r for r in results if r['item_id'] == 'V2_2'), None)
        if v2_1 and v2_2:
            a1, a2 = v2_1['answer'], v2_2['answer']
            if a1 == 'B' and a2 == 'A':
                evidence['V2a'].append(f'pattern:V2_swap(V2_1=B, V2_2=A)')
            elif (a1 == 'B' and a2 == 'B') or (a1 == 'A' and a2 == 'A'):
                evidence['V2b'].append(f'pattern:V2_always({a1},{a2})')

    # 清除空清單
    return {k: v for k, v in evidence.items() if v}


# ──────────────────────────────────────────
# 工具：建立 metrics
# ──────────────────────────────────────────
def _build_metrics(results: list) -> dict:
    n = len(results)
    if n == 0:
        return {}

    confs      = [r['confidence'] for r in results]
    avg_conf   = sum(confs) / n
    low_ratio  = sum(1 for c in confs if c <= 2) / n
    hcw_ratio  = sum(
        1 for r in results
        if not r['is_correct'] and r['confidence'] >= 4
    ) / n
    accuracy   = sum(1 for r in results if r['is_correct']) / n

    return {
        'n_items':               n,
        'accuracy':              round(accuracy, 3),
        'avg_confidence':        round(avg_conf, 3),
        'low_conf_ratio':        round(low_ratio, 3),
        'high_conf_wrong_ratio': round(hcw_ratio, 3),
    }


# ──────────────────────────────────────────
# 主輸出函數
# ──────────────────────────────────────────
def export(
    report:     dict,
    results:    list,
    username:   str,
    session_id: str,
    log_path:   str,
):
    """
    report    : validity_analyze.analyze() 的回傳值
    results   : validity.py 每題回傳的 dict list
    username  : 用戶名稱
    session_id: 登入時間戳
    log_path  : log 檔路徑（用於取得 session 資料夾）
    """

    # ── JSON profile 存於 session 資料夾（與 log 同層）──
    out_dir = os.path.dirname(log_path) if log_path else LOG_DIR
    os.makedirs(out_dir, exist_ok=True)

    strength   = report.get('strength', {})
    lci        = report.get('lci', {})
    v2_meta    = report.get('v2_meta', {})
    interview  = report.get('interview_candidates', [])
    metrics    = _build_metrics(results)
    evidence   = _build_evidence(results, v2_meta)

    # ── 1. JSON profile（session 資料夾）──
    profile = {
        'version':          VERSION,
        'student_id':       username,
        'admin_session_id': session_id,
        'branch':           'validity',
        'items': [
            {
                'item_id':    r['item_id'],
                'answer':     r['answer'],
                'is_correct': r['is_correct'],
                'confidence': r['confidence'],
            }
            for r in results
        ],
        'metrics': metrics,
        'misconception_strength': {
            code: round(strength.get(code, 0.0), 3)
            for code in ALL_CODES
        },
        'evidence': evidence,
        'interview_candidates': [
            {'code': c['code'], 'reason': ', '.join(c['reasons'])}
            for c in interview
        ],
        'twin_tags': {
            'hesitant':         lci.get('twin_tag_hesitant', False),
            'hesitant_subtype': lci.get('hesitant_subtype'),
            'LCI_score':        lci.get('LCI_score'),
        },
    }

    json_path = os.path.join(out_dir, f'{username}_{session_id}_profile.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(f"[final_va] JSON profile 已儲存：{json_path}")

    # ── 2. Wide table CSV（LOG_DIR 根目錄，全用戶共用，追加模式 + 跨進程鎖）──
    os.makedirs(LOG_DIR, exist_ok=True)
    lock_path = WIDE_TABLE + '.lock'

    acquired = _acquire_lock(lock_path)
    try:
        write_header = not os.path.exists(WIDE_TABLE)
        row = {
            'admin_session_id':      session_id,
            'accuracy':              metrics.get('accuracy', ''),
            'avg_confidence':        metrics.get('avg_confidence', ''),
            'low_conf_ratio':        metrics.get('low_conf_ratio', ''),
            'high_conf_wrong_ratio': metrics.get('high_conf_wrong_ratio', ''),
        }
        for code in ALL_CODES:
            row[code] = round(strength.get(code, 0.0), 3)

        with open(WIDE_TABLE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=WIDE_TABLE_HEADER)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        print(f"[final_va] Wide table 已追加：{WIDE_TABLE}")
    finally:
        if acquired:
            _release_lock(lock_path)


# ──────────────────────────────────────────
# 測試用
# ──────────────────────────────────────────
if __name__ == '__main__':
    from validity_analyze import analyze

    test_results = [
        {'item_id': 'V1_GATE', 'answer': 'A', 'is_correct': False, 'confidence': 5, 'mistake_code': 'V1a'},
        {'item_id': 'V2_1',    'answer': 'B', 'is_correct': False, 'confidence': 4, 'mistake_code': 'V2a'},
        {'item_id': 'V2_2',    'answer': 'A', 'is_correct': False, 'confidence': 4, 'mistake_code': 'V2a'},
        {'item_id': 'V1_1',    'answer': 'A', 'is_correct': False, 'confidence': 4, 'mistake_code': 'V1a'},
        {'item_id': 'VX_1',    'answer': 'A', 'is_correct': False, 'confidence': 5, 'mistake_code': 'X1'},
        {'item_id': 'V1_2',    'answer': 'A', 'is_correct': False, 'confidence': 4, 'mistake_code': 'V1a'},
        {'item_id': 'V3_1',    'answer': 'D', 'is_correct': False, 'confidence': 4, 'mistake_code': 'V3b'},
        {'item_id': 'V3_2',    'answer': 'C', 'is_correct': False, 'confidence': 4, 'mistake_code': 'V3b'},
    ]

    report = analyze(test_results, 'S032', '2026-02-11-AM-01', '')
    export(report, test_results, 'S032', '2026-02-11-AM-01', '')