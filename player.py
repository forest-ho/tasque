def get_level_from_exp(exp):
    """EXPからレベルを計算する。例: 150EXPならレベル2。"""
    safe_exp = max(0, int(exp or 0))
    return 1 + (safe_exp // 100)


def get_exp_needed_for_next_level(level):
    """次のレベルまでに必要なEXPを返す。"""
    safe_level = max(0, int(level or 0))
    return safe_level * 100


def add_exp_and_level(exp, gained_exp):
    """現在のEXPに加算し、レベルを計算する。"""
    safe_exp = max(0, int(exp or 0))
    safe_gained_exp = max(0, int(gained_exp or 0))
    new_exp = safe_exp + safe_gained_exp
    level = get_level_from_exp(new_exp)
    return new_exp, level
