IMPORTANCE_RULES = {
    "low": {"damage": 10, "exp": 10},
    "medium": {"damage": 20, "exp": 20},
    "high": {"damage": 50, "exp": 50},
}

IMPORTANCE_LABELS = {
    "low": "弱い(攻撃力10)",
    "medium": "ふつう(攻撃力20)",
    "high": "高い(攻撃力50)",
}


def get_damage_and_exp(importance):
    """重要度に応じてダメージとEXPを返す。"""
    key = str(importance).strip().lower() if importance is not None else ""
    if key not in IMPORTANCE_RULES:
        key = "medium"
    return IMPORTANCE_RULES[key]["damage"], IMPORTANCE_RULES[key]["exp"]


def get_progress_ratio(done_count, total_count):
    """達成率を0〜1の範囲で返す。"""
    if total_count in (None, 0):
        return 0.0
    done_count = max(0, done_count)
    total_count = max(0, total_count)
    if total_count == 0:
        return 0.0
    return min(1.0, done_count / total_count)
