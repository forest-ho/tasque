def get_level_from_exp(exp):
    """EXPからレベルを計算する。例: 150EXPならレベル2。"""
    return 1 + (exp // 100)


def get_exp_needed_for_next_level(level):
    """次のレベルまでに必要なEXPを返す。"""
    return level * 100


def add_exp_and_level(exp, gained_exp):
    """現在のEXPに加算し、レベルを計算する。"""
    new_exp = exp + gained_exp
    level = get_level_from_exp(new_exp)
    return new_exp, level
