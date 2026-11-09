from app.guide.session import build_input


def test_build_input_no_note_when_no_interruption():
    assert build_input("what are your hours?", None) == "what are your hours?"
    assert build_input("what are your hours?", "") == "what are your hours?"


def test_build_input_folds_note_when_interrupted():
    partial = "Our hours are Monday through Saturday, six a.m. to nine p.m., and on Sundays we"
    result = build_input("what did you say?", partial)
    assert result.endswith("what did you say?")
    assert partial[-20:] in result
    assert result.startswith("[Note:")


def test_build_input_truncates_long_partial():
    partial = "x" * 500
    result = build_input("go on", partial)
    assert "x" * 500 not in result
    assert "x" * 150 in result
