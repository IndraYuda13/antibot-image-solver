from antibot_image_solver.normalize import canonical_forms, eval_simple_expr, normalize_letters, roman_to_int


def test_roman_to_int():
    assert roman_to_int("III") == 3
    assert roman_to_int("IV") == 4
    assert roman_to_int("X") == 10


def test_eval_simple_expr():
    assert eval_simple_expr("3+3") == "6"
    assert eval_simple_expr("2*4") == "8"
    assert eval_simple_expr("9-4") == "5"


def test_normalize_letters_repairs_common_ocr_confusion():
    assert normalize_letters("d0g") == "dog"
    assert normalize_letters("elephent") == "elephant"


def test_canonical_forms_include_words_and_digits():
    forms = canonical_forms("five")
    assert "five" in forms
    assert "5" in forms


def test_canonical_forms_include_expr_resolution():
    forms = canonical_forms("2+8")
    assert "10" in forms
