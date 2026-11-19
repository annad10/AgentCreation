import json
from collections import Counter
from pathlib import Path

DATA = json.loads((Path(__file__).parent.parent / "data" / "bocconi" / "courses.json").read_text(encoding="utf-8"))
COURSES = DATA["courses"]


def test_course_counts_match_source_department_totals():
    # Totals printed in the source PDFs' department headings, summed.
    counts = Counter(c["term"] for c in COURSES)
    assert counts == {"Fall 2026": 292, "Spring 2027": 265}


def test_every_course_has_complete_typed_fields():
    for c in COURSES:
        assert len(c["code"]) == 5 and c["code"].isdigit()
        assert c["level"] in {"Undergraduate", "Graduate", "Law School"}
        assert c["title"].strip() and c["department"]
        assert isinstance(c["credits"], int) and 1 <= c["credits"] <= 12
        assert isinstance(c["teaching_year"], int) and c["class_group"]


def test_source_glyph_losses_are_repaired():
    titles = " ".join(c["title"] for c in COURSES)
    assert "MA-EMENT" not in titles and "ALTERNA-E" not in titles
    assert "MANAGEMENT OF FASHION COMPANIES" in titles


def test_known_course_matches_source_pdf():
    c = next(c for c in COURSES if c["code"] == "20161")
    assert (c["title"], c["credits"], c["term"], c["department"]) == (
        "PERFORMANCE MEASUREMENT", 6, "Fall 2026", "Department of Accounting")
