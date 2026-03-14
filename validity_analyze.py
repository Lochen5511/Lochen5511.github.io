"""
validity_analyze.py
──────────────────
接收 validity.py 蒐集的作答結果（results list），
依規格執行計分、V2 pattern、LCI、訪談候選判定，
並將分析結果寫入 log。

使用方式（在 validity.py 末端呼叫）：
    from validity_analyze import analyze
    report = analyze(results, username, session_id, log_path)
"""

# ──────────────────────────────────────────
# 計分常數
# ──────────────────────────────────────────
POINT_STRONG_WRONG        = 0.6
POINT_SUPPORT_WRONG       = 0.2
HIGH_CONF_THRESHOLD       = 4
POINT_HIGH_CONF_BONUS     = 0.1
MAX_STRENGTH              = 1.0

V2A_SWAP_STRENGTH         = 0.9
V2B_ALWAYS_TYPE_STRENGTH  = 0.7

INTERVIEW_MIN_STRENGTH    = 0.7

# evidence_weight 對照表
EVIDENCE_WEIGHT = {
    'V1_GATE': 'supporting',
    'V1_1':    'supporting',
    'V1_2':    'strong',
    'V2_1':    'supporting',
    'V2_2':    'supporting',
    'VX_1':    'strong',
    'V3_1':    'strong',
    'V3_2':    'strong',
}

# V2 題組（不走單題加分）
V2_ITEMS = {'V2_1', 'V2_2'}

# 所有迷思代碼
ALL_CODES = ['V1a', 'V1b', 'V1c', 'V2a', 'V2b', 'X1', 'V3a', 'V3b']


# ──────────────────────────────────────────
# Step A：單題加分（非 V2）
# ──────────────────────────────────────────
def _step_a(results: list, strength: dict) -> dict:
    """對非 V2 題目做逐題累加。"""
    for r in results:
        if r['item_id'] in V2_ITEMS:
            continue
        code = r.get('mistake_code')
        if code is None:
            continue
        if r['is_correct']:
            continue

        weight = EVIDENCE_WEIGHT.get(r['item_id'], 'supporting')
        base   = POINT_STRONG_WRONG if weight == 'strong' else POINT_SUPPORT_WRONG
        add    = base
        if r['confidence'] >= HIGH_CONF_THRESHOLD:
            add += POINT_HIGH_CONF_BONUS

        strength[code] = min(MAX_STRENGTH, strength[code] + add)

    return strength


# ──────────────────────────────────────────
# Step B：V2 pattern rule
# ──────────────────────────────────────────
def _step_b(results: list, strength: dict) -> tuple:
    """
    只看 V2_1 / V2_2 的答案組合。
    回傳 (strength, v2_meta)：v2_meta 含 severity 旗標。
    """
    v2 = {r['item_id']: r for r in results if r['item_id'] in V2_ITEMS}
    v2_meta = {'V2a_severity': None, 'V2b_severity': None, 'V2_uncertain': False}

    if 'V2_1' not in v2 or 'V2_2' not in v2:
        return strength, v2_meta

    ans1 = v2['V2_1']['answer']   # A=同時, B=預測
    ans2 = v2['V2_2']['answer']   # A=同時, B=預測
    c1   = v2['V2_1']['confidence']
    c2   = v2['V2_2']['confidence']

    # V2a：顛倒型（V2_1=B 且 V2_2=A）
    if ans1 == 'B' and ans2 == 'A':
        strength['V2a'] = max(strength['V2a'], V2A_SWAP_STRENGTH)
        if c1 >= HIGH_CONF_THRESHOLD or c2 >= HIGH_CONF_THRESHOLD:
            v2_meta['V2a_severity'] = 'high'
        # V2a 成立 → 不判 V2b
        return strength, v2_meta

    # V2b：永遠選同一類
    if (ans1 == 'B' and ans2 == 'B') or (ans1 == 'A' and ans2 == 'A'):
        strength['V2b'] = max(strength['V2b'], V2B_ALWAYS_TYPE_STRENGTH)
        wrong_conf = []
        if ans1 != 'A':  # V2_1 答對是 A
            wrong_conf.append(c1)
        if ans2 != 'B':  # V2_2 答對是 B
            wrong_conf.append(c2)
        if any(c >= HIGH_CONF_THRESHOLD for c in wrong_conf):
            v2_meta['V2b_severity'] = 'high'
        return strength, v2_meta

    # 全對 (A, B)：不標
    if ans1 == 'A' and ans2 == 'B':
        return strength, v2_meta

    # 其他組合：偶發錯誤，不硬貼迷思
    v2_meta['V2_uncertain'] = True
    return strength, v2_meta


# ──────────────────────────────────────────
# LCI 計算
# ──────────────────────────────────────────
def _calc_lci(results: list) -> dict:
    """
    LCI = 100 * (0.6 * low_conf_ratio + 0.4 * (1 - (avg_conf - 1) / 4))
    Hesitant Twin 標記：
      Rule H1：LCI >= 70
      Rule H2：avg_conf <= 2.6 且 low_conf_ratio >= 0.50
    """
    confs = [r['confidence'] for r in results]
    n     = len(confs)
    if n == 0:
        return {}

    avg_conf       = sum(confs) / n
    low_conf_ratio = sum(1 for c in confs if c <= 2) / n
    lci            = 100 * (0.6 * low_conf_ratio + 0.4 * (1 - (avg_conf - 1) / 4))
    lci            = round(min(100.0, max(0.0, lci)), 2)

    hesitant = (lci >= 70) or (avg_conf <= 2.6 and low_conf_ratio >= 0.50)

    # 副標籤
    acc               = sum(1 for r in results if r['is_correct']) / n
    high_conf_wrong   = sum(1 for r in results
                            if not r['is_correct'] and r['confidence'] >= HIGH_CONF_THRESHOLD)
    hesitant_subtype  = None
    if hesitant:
        if acc >= 0.75 and high_conf_wrong == 0:
            if avg_conf <= 2.2 and low_conf_ratio >= 0.75:
                hesitant_subtype = 'LC_GUESS'
            else:
                hesitant_subtype = 'LC_KNOWS'

    hesitation_level    = round(lci / 100, 3)
    intuition_intrusion = round(max(0.0, min(1.0, (lci - 50) / 50)), 3)

    return {
        'LCI_score':           lci,
        'avg_conf':            round(avg_conf, 2),
        'low_conf_ratio':      round(low_conf_ratio, 2),
        'twin_tag_hesitant':   hesitant,
        'hesitant_subtype':    hesitant_subtype,
        'hesitation_level':    hesitation_level,
        'intuition_intrusion': intuition_intrusion,
    }


# ──────────────────────────────────────────
# 訪談候選判定
# ──────────────────────────────────────────
def _interview_candidates(strength: dict, results: list, v2_meta: dict) -> list:
    """
    候選條件（任一成立）：
    1. strength[code] >= 0.7
    2. 有「高把握度錯」觸發該 code
    3. code 是 V2a 或 X1
    """
    # 建立「哪些 code 有高把握度錯」的集合
    high_conf_wrong_codes = set()
    for r in results:
        if not r['is_correct'] and r['confidence'] >= HIGH_CONF_THRESHOLD:
            code = r.get('mistake_code')
            if code:
                high_conf_wrong_codes.add(code)

    candidates = []
    for code in ALL_CODES:
        s = strength.get(code, 0)
        reasons = []
        if s >= INTERVIEW_MIN_STRENGTH:
            reasons.append(f'strength={s:.2f}')
        if code in high_conf_wrong_codes:
            reasons.append('high_conf_wrong')
        if code in ('V2a', 'X1') and s > 0:
            reasons.append(f'priority_code')
        if reasons:
            candidates.append({'code': code, 'strength': s, 'reasons': reasons})

    return candidates


# ──────────────────────────────────────────
# 主分析函數
# ──────────────────────────────────────────
def analyze(results: list, username: str, session_id: str, log_path: str) -> dict:
    """
    輸入：validity.py 每題回傳的 dict list，格式：
        [{'item_id', 'answer', 'is_correct', 'confidence', 'mistake_code'}, ...]
    輸出：完整分析 report dict，並寫入 log。
    """
    # 初始化
    strength = {code: 0.0 for code in ALL_CODES}

    # Step A：單題加分（非 V2）
    strength = _step_a(results, strength)

    # Step B：V2 pattern
    strength, v2_meta = _step_b(results, strength)

    # LCI
    lci_data = _calc_lci(results)

    # 訪談候選
    interview = _interview_candidates(strength, results, v2_meta)

    # 整體正確率
    acc = sum(1 for r in results if r['is_correct']) / len(results) if results else 0

    report = {
        'username':    username,
        'session_id':  session_id,
        'accuracy':    round(acc, 3),
        'strength':    {k: round(v, 3) for k, v in strength.items()},
        'v2_meta':     v2_meta,
        'lci':         lci_data,
        'interview_candidates': interview,
    }

    # 寫入 log
    if log_path:
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write('\n\n── 效度分析報告 ──\n')
                f.write(f'正確率：{acc:.1%}\n')
                f.write('迷思強度：\n')
                for code, val in strength.items():
                    if val > 0:
                        f.write(f'  {code}: {val:.2f}\n')
                f.write(f'V2 meta：{v2_meta}\n')
                f.write(f'LCI：{lci_data.get("LCI_score", "N/A")} | '
                        f'猶豫型孿生：{lci_data.get("twin_tag_hesitant", False)} | '
                        f'subtype：{lci_data.get("hesitant_subtype")}\n')
                if interview:
                    codes_str = ', '.join(c['code'] for c in interview)
                    f.write(f'訪談候選：{codes_str}\n')
                f.write('──────────────────\n')
        except Exception as e:
            print(f"[log 寫入失敗] {e}")

    print(f"[validity_analyze] 分析完成：acc={acc:.1%} | "
          f"interview={[c['code'] for c in interview]}")
    return report


if __name__ == '__main__':
    # 測試用：模擬一組作答結果
    test_results = [
        {'item_id': 'V1_GATE', 'answer': 'A', 'is_correct': False, 'confidence': 4, 'mistake_code': 'V1a'},
        {'item_id': 'V2_1',    'answer': 'B', 'is_correct': False, 'confidence': 3, 'mistake_code': 'V2a'},
        {'item_id': 'V2_2',    'answer': 'A', 'is_correct': False, 'confidence': 3, 'mistake_code': 'V2a'},
        {'item_id': 'V1_1',    'answer': 'B', 'is_correct': True,  'confidence': 2, 'mistake_code': None},
        {'item_id': 'VX_1',    'answer': 'A', 'is_correct': False, 'confidence': 5, 'mistake_code': 'X1'},
        {'item_id': 'V1_2',    'answer': 'B', 'is_correct': True,  'confidence': 2, 'mistake_code': None},
        {'item_id': 'V3_1',    'answer': 'A', 'is_correct': False, 'confidence': 2, 'mistake_code': 'V3a'},
        {'item_id': 'V3_2',    'answer': 'B', 'is_correct': True,  'confidence': 1, 'mistake_code': None},
    ]
    report = analyze(test_results, 'test_user', 'test_session', '')
    import json
    print(json.dumps(report, ensure_ascii=False, indent=2))