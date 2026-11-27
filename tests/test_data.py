"""Tests de src/data.py sur un petit jeu synthétique (les données NHAMCS ne sont pas committées)."""
from pathlib import Path

import pandas as pd
import pytest

from src import data as D

CFG = D.load_config(Path(__file__).resolve().parents[1] / "config" / "experiment.yaml")
DCFG = CFG["data"]

META = D.Meta(
    value_labels={
        "AGE": {0: "Under one year", 94: "94 years and over"},
        "SEX": {1: "Female", 2: "Male"},
        "RFV1": {10100: "Fever", 71370: "Direct admission to hospital",
                 10550: "Pain, specified site not referable to..."},
        "RFV2": {10100: "Fever", 71370: "Direct admission to hospital"},
        "INJPOISAD": {1: "Yes, injury/trauma", 4: "No, visit is not related to injury"},
        "INTENT15": {2: "Unintentional", -8: "Unknown/intent unclear"},
        "INJURY72": {1: "Yes"},
        "INJURY_ENC": {1: "Initial encounter for injury"},
    },
    var_labels={"ASTHMA": "Does patient have: Asthma", "CBC": "CBC (Complete blood count)",
                "EKG": "EKG/ECG"},
)
ICD = {"I10": "Essential (primary) hypertension", "R079": "Chest pain, unspecified",
       "W19": "Unspecified fall"}


def make_row(**overrides) -> dict:
    """Une visite « neutre » : tout à 0 ou vide, puis valeurs imposées."""
    row = {c: 0 for c in D.vignette_columns(DCFG) + D.outcome_columns(DCFG)}
    for c in DCFG["rfv_cols"] + [s["col"] for s in DCFG["injury_cols"]] + DCFG["prdiag_cols"]:
        row[c] = -9
    for c in DCFG["diag_cols"] + DCFG["cause_cols"]:
        row[c] = "-9"
    row.update(AGE=40, SEX=1, TEMPF=981, PULSE=80, RESPR=16, BPSYS=120, BPDIAS=80, POPCT=98,
               RFV1=10100, INJPOISAD=4, NOCHRON=1, DIAGSCRN=0)
    row.update(overrides)
    return row


def make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def fields_of(row: dict, stats=None) -> dict:
    s = pd.Series(row)[D.vignette_columns(DCFG)]
    return D.build_fields(s, META, ICD, DCFG, stats or D.DecodeStats())


# --- Vérité terrain --------------------------------------------------------
@pytest.mark.parametrize("col", ["ADMITHOS", "OBSHOS", "TRANOTH", "TRANPSYC"])
def test_each_hospitalization_component(col):
    df = make_df([make_row(**{col: 1}), make_row()])
    assert D.hospitalization_mask(df, DCFG).tolist() == [True, False]


@pytest.mark.parametrize("col", ["TRANNH", "OBSDIS", "RETRNED", "RETREFFU", "NOFU"])
def test_non_hospitalization_dispositions(col):
    df = make_df([make_row(**{col: 1})])
    assert not D.hospitalization_mask(df, DCFG).iloc[0]


def test_combined_components():
    df = make_df([make_row(ADMITHOS=1, TRANOTH=1)])
    assert D.hospitalization_mask(df, DCFG).iloc[0]


# --- Exclusions ------------------------------------------------------------
@pytest.mark.parametrize("col", ["LWBS", "LBTC", "LEFTAMA", "DOA", "DIEDED", "OTHDISP", "NODISP"])
def test_ambiguous_excluded(col):
    df = make_df([make_row(**{col: 1}), make_row(), make_row(ADMITHOS=1)])
    kept, rep = D.apply_exclusions(df, DCFG)
    assert len(kept) == 2 and rep["n_excluded"] == 1
    assert rep["excluded_by_reason"][col] == 1
    assert kept[D.LABEL_COL].tolist() == [0, 1]


def test_conflict_hospitalization_and_ambiguous_is_excluded_and_counted():
    df = make_df([make_row(ADMITHOS=1, OTHDISP=1), make_row(ADMITHOS=1, LEFTAMA=1), make_row()])
    kept, rep = D.apply_exclusions(df, DCFG)
    assert len(kept) == 1
    assert rep["n_conflicts_hospitalization_and_ambiguous"] == 2
    assert rep["conflicts_by_reason"]["OTHDISP"] == 1


# --- Tirage ----------------------------------------------------------------
def _labelled(n_pos: int, n_neg: int) -> pd.DataFrame:
    df = make_df([make_row(ADMITHOS=1)] * n_pos + [make_row()] * n_neg)
    return D.apply_exclusions(df, DCFG)[0]


def test_stratified_sample_sizes_and_reproducible():
    kept = _labelled(30, 50)
    a = D.stratified_sample(kept, 20, seed=1)
    b = D.stratified_sample(kept, 20, seed=1)
    assert a[D.LABEL_COL].value_counts().to_dict() == {1: 10, 0: 10}
    assert a.index.tolist() == b.index.tolist()
    assert a.index.is_unique


def test_stratum_too_small_raises():
    with pytest.raises(ValueError, match="trop petite"):
        D.stratified_sample(_labelled(5, 50), 20, seed=1)


def test_odd_total_raises():
    with pytest.raises(ValueError, match="pair"):
        D.stratified_sample(_labelled(30, 50), 21, seed=1)


# --- Décodage --------------------------------------------------------------
def test_vitals_decoding():
    f = fields_of(make_row(TEMPF=981, PULSE=998, BPSYS=-9))
    v = {x["name"]: x["value"] for x in f["vitals"]}
    assert v["Temperature"] == "98.1 °F"
    assert v["Heart rate"] == DCFG["vital_special_codes"][998]
    assert v["Systolic BP"] == DCFG["vital_missing_text"]
    assert v["Pulse oximetry"] == "98 %"


def test_age_labels():
    assert fields_of(make_row(AGE=0))["age"] == "Under one year"
    assert fields_of(make_row(AGE=94))["age"] == "94 years and over"
    assert fields_of(make_row(AGE=37))["age"] == "37 years"


def test_icd_formatting_and_fallback():
    stats = D.DecodeStats()
    f = fields_of(make_row(DIAG1="I10-", DIAG2="R079", DIAG3="Q999", PRDIAG2=1), stats)
    assert f["diagnoses"][0] == "Essential (primary) hypertension (I10)"
    assert f["diagnoses"][1] == "Chest pain, unspecified (R07.9) (probable)"
    assert "description unavailable" in f["diagnoses"][2]
    assert stats.icd_missing == ["Q999"]


def test_injury_section_and_cause_fallback():
    stats = D.DecodeStats()
    f = fields_of(make_row(INJPOISAD=1, INTENT15=2, INJURY72=1, INJURY_ENC=1, CAUSE1="W19X"),
                  stats)
    assert f["injury"]["type"] == "Yes, injury/trauma"
    assert f["injury"]["causes"] == ["Unspecified fall (W19.X)"]
    assert stats.icd_category_fallback == 1
    assert fields_of(make_row(INJPOISAD=4))["injury"] is None


def test_chronic_and_exams():
    assert fields_of(make_row())["chronic_conditions"] == "none"
    assert fields_of(make_row(NOCHRON=2))["chronic_conditions"] == "not documented"
    assert fields_of(make_row(NOCHRON=0, ASTHMA=1, CAD=1))["chronic_conditions"] == [
        "Asthma", DCFG["label_overrides"]["CAD"]]
    assert fields_of(make_row())["exams_ordered"] == "none"
    assert fields_of(make_row(DIAGSCRN=2))["exams_ordered"] == "not documented"
    assert fields_of(make_row(DIAGSCRN=1, CBC=1, EKG=1))["exams_ordered"] == [
        "CBC (Complete blood count)", "EKG/ECG"]


def test_rfv_skip_and_truncation_counted():
    stats = D.DecodeStats()
    f = fields_of(make_row(RFV1=10550, RFV2=89990), stats)
    assert f["reasons_for_visit"] == ["Pain, specified site not referable to..."]
    assert stats.rfv_skipped == 1 and stats.rfv_truncated_label == 1


# --- Anti-fuite ------------------------------------------------------------
def test_outcome_columns_not_in_whitelist():
    D.check_no_overlap(DCFG)
    assert not set(D.vignette_columns(DCFG)) & set(D.outcome_columns(DCFG))


def test_build_fields_rejects_outcome_columns():
    s = pd.Series(make_row(ADMITHOS=1))
    with pytest.raises(ValueError, match="hors liste blanche"):
        D.build_fields(s, META, ICD, DCFG, D.DecodeStats())


def test_leak_codes_masked():
    stats = D.DecodeStats()
    f = fields_of(make_row(RFV1=71370, RFV2=10100, DIAG1="ZZZ2", DIAG2="I10-"), stats)
    text = D.render_vignette(f)
    assert "admission" not in text.lower() and "ZZZ" not in text
    assert stats.rfv_leak_masked == {"71370": 1}
    assert stats.diag_admin_masked == {"ZZZ2": 1}
    assert D.find_forbidden(text, DCFG["forbidden_patterns"]) == []


def test_forbidden_patterns_detect_leaks():
    pats = DCFG["forbidden_patterns"]
    for leak in ["Admit to this hospital", "Transfer to psychiatric hospital",
                 "Admit to observation unit", "Left without being seen", "Died in ED"]:
        assert D.find_forbidden(leak, pats), leak


def test_outcome_flags_never_in_text():
    """Même avec toutes les cases d'issue cochées, le texte est identique."""
    base = make_row()
    flagged = make_row(**{c: 1 for c in D.outcome_columns(DCFG)})
    whitelist = D.vignette_columns(DCFG)
    t1 = D.render_vignette(D.build_fields(pd.Series(base)[whitelist], META, ICD, DCFG,
                                          D.DecodeStats()))
    t2 = D.render_vignette(D.build_fields(pd.Series(flagged)[whitelist], META, ICD, DCFG,
                                          D.DecodeStats()))
    assert t1 == t2


def test_icd10_loader(tmp_path):
    p = tmp_path / "order.txt"
    line = f"{'00001':5} {'I10':7} 1 {'Essential (primary) hypertension':60} Essential (primary) hypertension\r\n"
    p.write_text(line, encoding="ascii")
    assert D.load_icd10(p) == {"I10": "Essential (primary) hypertension"}
