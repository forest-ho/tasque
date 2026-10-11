from player import add_exp_and_level, get_exp_needed_for_next_level, get_level_from_exp
from quest import get_damage_and_exp, get_progress_ratio


def test_level_from_exp_handles_negative_and_string_inputs():
    assert get_level_from_exp(-10) == 1
    assert get_level_from_exp("250") == 3
    assert get_level_from_exp(None) == 1


def test_add_exp_and_level_clamps_non_negative_inputs():
    assert add_exp_and_level(-50, -10) == (0, 1)
    assert add_exp_and_level(50, 80) == (130, 2)


def test_exp_needed_for_next_level_is_non_negative():
    assert get_exp_needed_for_next_level(0) == 0
    assert get_exp_needed_for_next_level(4) == 400


def test_damage_and_exp_defaults_unknown_importance():
    assert get_damage_and_exp("high") == (50, 50)
    assert get_damage_and_exp("unknown") == (20, 20)
    assert get_damage_and_exp(None) == (20, 20)


def test_progress_ratio_handles_zero_and_overflow_cases():
    assert get_progress_ratio(0, 0) == 0.0
    assert get_progress_ratio(3, 10) == 0.3
    assert get_progress_ratio(20, 10) == 1.0
    assert get_progress_ratio(-1, 10) == 0.0
