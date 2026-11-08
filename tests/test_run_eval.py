from eval.run_eval import match, report, same_span


def test_same_span_overlap_is_case_insensitive():
    assert same_span("Lumora pay", "LUMORA PAY app")
    assert not same_span("", "x")


def test_match_is_one_to_one():
    errors = [{"exact_span": "LumoraPay", "type": "terminology", "rule_or_fact_id": "T01"}]
    findings = [{"span": "LumoraPay", "source_id": "T01"}, {"span": "LumoraPay", "source_id": "T01"}]
    assert len(match(findings, errors)) == 1


def test_report_numbers():
    r = dict(n=1, n_find=4, n_err=5, tp=3, cite_ok=2, clean_total=2, clean_flagged=1,
             wrong_cites={"G07": 1}, by_type={"claim": [1, 2]})
    out = report(r, "test")
    assert "Precision: 75.0%" in out and "Recall: 60.0%" in out and "Citation accuracy: 66.7%" in out
