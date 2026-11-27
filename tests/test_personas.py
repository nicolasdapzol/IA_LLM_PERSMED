"""Tests de src/personas.py sur le vrai config/personas.yaml (petit, versionné)."""
import copy
import itertools
from pathlib import Path

import pytest

from src import personas as P

ROOT = Path(__file__).resolve().parents[1]
CFG = P.load_yaml(ROOT / "config" / "experiment.yaml")
SPEC = P.load_yaml(ROOT / "config" / "personas.yaml")
SEED = CFG["seed"]
PERSONAS = P.build_personas(SPEC, SEED)
BY_ID = {p.id: p for p in PERSONAS}
VIGNETTE = "Patient: 40 years, Female.\nReason(s) for visit: Fever."


def test_counts_and_unique_ids():
    assert len(PERSONAS) == 24 == SPEC["expected_total"]
    assert len(BY_ID) == 24
    kinds = [p.kind for p in PERSONAS]
    assert kinds.count(P.FACTORIAL) == 18
    assert kinds.count(P.NO_PERSONA) == 1
    assert kinds.count(P.NON_MEDICAL) == 5


def test_full_factorial_design():
    combos = {tuple(p.factors.values()) for p in PERSONAS if p.kind == P.FACTORIAL}
    expected = set(itertools.product(*SPEC["factors"].values()))
    assert combos == expected


def test_factorial_text_is_block_composition():
    for p in PERSONAS:
        if p.kind != P.FACTORIAL:
            continue
        parts = [SPEC["blocks"][f][lvl]["text"] for f, lvl in p.factors.items()]
        assert p.text == " ".join(t for t in parts if t)


def test_neighbours_differ_by_one_block_only():
    """Deux personas qui diffèrent d'un facteur : le reste du texte est identique."""
    fact = [p for p in PERSONAS if p.kind == P.FACTORIAL]
    for a, b in itertools.combinations(fact, 2):
        diff = [f for f in a.factors if a.factors[f] != b.factors[f]]
        if len(diff) != 1:
            continue
        f = diff[0]
        strip = lambda p: p.text.replace(SPEC["blocks"][f][p.factors[f]]["text"], "").split()
        assert strip(a) == strip(b)


def test_neutral_objective_adds_nothing():
    p = BY_ID["F_junior_urgentiste_neutre"]
    assert p.text == (SPEC["blocks"]["experience"]["junior"]["text"] + " "
                      + SPEC["blocks"]["specialty"]["urgentiste"]["text"])


def test_every_block_has_known_sources():
    refs = SPEC["references"]
    for p in PERSONAS:
        if p.text:
            assert p.sources, p.id
        assert all(s in refs for s in p.sources), p.id


def test_no_persona_prompt_is_task_only():
    p = BY_ID[SPEC["controls"]["no_persona"]["id"]]
    prompt = P.build_prompt(p, VIGNETTE, SPEC)
    assert prompt == SPEC["task_prompt"].replace(SPEC["vignette_placeholder"], VIGNETTE)
    assert prompt.startswith("Below is the record")


def test_prompt_structure():
    for p in PERSONAS:
        prompt = P.build_prompt(p, VIGNETTE, SPEC)
        assert prompt.endswith(VIGNETTE)
        assert SPEC["vignette_placeholder"] not in prompt
        assert '{"decision": "hospitalize"}' in prompt
        assert '{"decision": "do_not_hospitalize"}' in prompt
        if p.text:
            assert prompt.startswith(p.text + "\n\n")


def test_non_medical_draw_is_reproducible_and_excludes_care_roles():
    nm = SPEC["controls"]["non_medical"]
    a = P.draw_non_medical_roles(nm, SEED)
    assert a == P.draw_non_medical_roles(nm, SEED)
    assert len(set(a)) == nm["n"]
    assert not set(a) & set(nm["excluded_roles"])
    assert [p.role for p in PERSONAS if p.kind == P.NON_MEDICAL] == a


def test_non_medical_texts_mention_no_medicine():
    for p in PERSONAS:
        if p.kind == P.NON_MEDICAL:
            low = p.text.lower()
            assert not any(w in low for w in ("physician", "doctor", "medic", "nurse", "health"))


def test_role_text_article_and_override():
    assert P.role_text("accountant", {}) == "an accountant"
    assert P.role_text("baker", {}) == "a baker"
    assert P.role_text("police", {"police": "a police officer"}) == "a police officer"


@pytest.mark.parametrize("mutate, message", [
    (lambda s: s["blocks"]["specialty"]["urgentiste"].update(sources=[]), "sans source"),
    (lambda s: s["blocks"]["objective"]["couts"].update(sources=["inconnue"]), "inconnue"),
    (lambda s: s["blocks"]["experience"].pop("senior"), "niveaux"),
    (lambda s: s.update(task_prompt="pas de vignette"), "exactement une fois"),
    (lambda s: s["controls"]["non_medical"].update(n=100), "Pas assez"),
])
def test_validation_errors(mutate, message):
    spec = copy.deepcopy(SPEC)
    mutate(spec)
    with pytest.raises(ValueError, match=message):
        P.build_personas(spec, SEED)


def test_wrong_total_raises():
    spec = copy.deepcopy(SPEC)
    spec["expected_total"] = 25
    with pytest.raises(ValueError, match="attendues"):
        P.build_personas(spec, SEED)
