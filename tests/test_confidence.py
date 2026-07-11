from src.validation.hallucination import compute_confidence


def test_all_signals_pass_high_confidence():
    c = compute_confidence(syntax_valid=True, back_alignment=1.0, result_sane=True, schema_coverage=True)
    assert c.composite == 1.0


def test_low_alignment_drops_confidence():
    c = compute_confidence(syntax_valid=True, back_alignment=0.2, result_sane=True, schema_coverage=True)
    assert c.composite < 0.85


def test_all_fail_zero():
    c = compute_confidence(syntax_valid=False, back_alignment=0.0, result_sane=False, schema_coverage=False)
    assert c.composite == 0.0
