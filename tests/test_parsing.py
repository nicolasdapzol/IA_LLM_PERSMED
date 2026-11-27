"""Tests de src/parsing.py."""
from pathlib import Path

import pytest
import yaml

from src import parsing as PA

PCFG = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "experiment.yaml")
                      .read_text(encoding="utf-8"))["parsing"]
KEY, VALUES = PCFG["decision_key"], PCFG["values"]


@pytest.mark.parametrize("text, decision, status", [
    ('{"decision": "hospitalize"}', 1, PA.OK_STRICT),
    ('{"decision": "do_not_hospitalize"}', 0, PA.OK_STRICT),
    ('  {"decision":"Hospitalize"}\n', 1, PA.OK_STRICT),
    ('```json\n{"decision": "do_not_hospitalize"}\n```', 0, PA.OK_EXTRACTED),
    ('Answer: {"decision": "hospitalize"} because of hypoxia.', 1, PA.OK_EXTRACTED),
    ('{"decision": "hospitalize"} {"decision": "hospitalize"}', 1, PA.OK_EXTRACTED),
    ('{"decision": "hospitalize"} or {"decision": "do_not_hospitalize"}', None, PA.CONTRADICTORY),
    ('{"decision": "admit"}', None, PA.INVALID_VALUE),
    ('{"decision": "hospitalize", "reason": "x"}', None, PA.INVALID_VALUE),
    ('{"answer": "hospitalize"}', None, PA.INVALID_VALUE),
    ('{"decision": 1}', None, PA.INVALID_VALUE),
    ('["hospitalize"]', None, PA.INVALID_VALUE),
    ("I would hospitalize this patient.", None, PA.INVALID_JSON),
    ('{"decision": "hospitalize"', None, PA.INVALID_JSON),
    ("", None, PA.EMPTY),
    ("   \n", None, PA.EMPTY),
])
def test_parse_output(text, decision, status):
    assert PA.parse_output(text, KEY, VALUES) == (decision, status)


def test_report_counts_and_rates():
    records = [
        {"case_id": "c1", "persona_id": "A", "output": '{"decision": "hospitalize"}',
         "score": {"p_hospitalize": 0.9}},
        {"case_id": "c2", "persona_id": "A", "output": '{"decision": "do_not_hospitalize"}',
         "score": {"p_hospitalize": 0.2}},
        {"case_id": "c1", "persona_id": "B", "output": "no idea", "score": None},
        {"case_id": "c2", "persona_id": "B", "output": '{"decision": "hospitalize"}',
         "score": {"p_hospitalize": 0.7}},
    ]
    parsed, rep = PA.parse_records(records, PCFG)
    assert [p["decision"] for p in parsed] == [1, 0, None, 1]
    assert rep["n_outputs"] == 4 and rep["n_invalid"] == 1
    assert rep["status_counts"][PA.OK_STRICT] == 3
    assert rep["status_counts"][PA.INVALID_JSON] == 1
    assert rep["invalid_rate"] == 0.25 and rep["invalid_rate_above_threshold"]
    assert rep["n_missing_score"] == 1
    assert rep["per_persona"]["A"]["hospitalization_rate_among_valid"] == 0.5
    assert rep["per_persona"]["B"]["invalid_rate"] == 0.5
    assert rep["per_persona"]["B"]["hospitalization_rate_among_valid"] == 1.0


@pytest.mark.parametrize("text, decision, status, has_thinking", [
    ('<unused94>thought\nThe patient is hypoxic.<unused95>```json\n{"decision": "hospitalize"}\n```',
     1, PA.OK_EXTRACTED, True),
    # une décision citée dans le raisonnement n'est pas lue : seule la réponse finale compte
    ('<unused94>thought\nMaybe {"decision": "hospitalize"}?<unused95>{"decision": "do_not_hospitalize"}',
     0, PA.OK_STRICT, True),
    ('<unused94>thought\nThe user wants me to act as', None, PA.THINKING_TRUNCATED, True),
    ('<unused94>thought\nDone.<unused95>', None, PA.EMPTY, True),
    ('{"decision": "hospitalize"}', 1, PA.OK_STRICT, False),
])
def test_parse_raw_with_thinking(text, decision, status, has_thinking):
    d, s, thinking = PA.parse_raw(text, PCFG)
    assert (d, s, thinking is not None) == (decision, status, has_thinking)
