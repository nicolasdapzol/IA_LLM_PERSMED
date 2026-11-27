"""Tests de src/inference.py avec le modèle factice (sans GPU)."""
import copy
import json
from pathlib import Path

import pytest

from src import inference as I
from src import personas as P

ROOT = Path(__file__).resolve().parents[1]
BASE_CFG = P.load_yaml(ROOT / "config" / "experiment.yaml")
BASE_CFG["personas"]["file"] = str(ROOT / BASE_CFG["personas"]["file"])
PERSONAS, SPEC = P.load_personas(BASE_CFG)


def make_vignettes(tmp_path: Path, n_pos: int = 3, n_neg: int = 3) -> Path:
    rows = [{"case_id": f"c{i}", "label": int(i < n_pos), "vignette": f"Patient {i}.",
             "outcome_flags": {"ADMITHOS": int(i < n_pos)}, "fields": {}}
            for i in range(n_pos + n_neg)]
    # ordre mélangé, comme le vrai fichier
    rows = rows[::2] + rows[1::2]
    path = tmp_path / "vignettes.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def make_cfg(tmp_path: Path) -> dict:
    cfg = copy.deepcopy(BASE_CFG)
    cfg["inference"]["vignettes"] = str(make_vignettes(tmp_path))
    return cfg


def read(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_select_vignettes_balanced_and_in_file_order(tmp_path):
    v = I.load_vignettes(make_vignettes(tmp_path))
    chosen = I.select_vignettes(v, 4)
    assert sorted(x["label"] for x in chosen) == [0, 0, 1, 1]
    order = [x["case_id"] for x in v]
    assert [x["case_id"] for x in chosen] == sorted((x["case_id"] for x in chosen), key=order.index)
    with pytest.raises(ValueError):
        I.select_vignettes(v, 3)
    with pytest.raises(ValueError):
        I.select_vignettes(v, 10)


def test_jobs_vignette_major_and_no_outcome_in_prompt(tmp_path):
    v = I.load_vignettes(make_vignettes(tmp_path))
    assert set(v[0]) == {"case_id", "label", "vignette"}
    jobs = I.make_jobs(v[:2], PERSONAS, SPEC)
    assert len(jobs) == 2 * 24
    assert {j["case_id"] for j in jobs[:24]} == {v[0]["case_id"]}
    assert all("ADMITHOS" not in j["prompt"] and "label" not in j for j in jobs)
    assert all(j["prompt"].endswith(v[0]["vignette"]) for j in jobs[:24])


def test_select_personas():
    assert len(I.select_personas(PERSONAS, "all")) == 24
    assert [p.id for p in I.select_personas(PERSONAS, "N00,R01")] == ["N00", "R01"]
    with pytest.raises(ValueError):
        I.select_personas(PERSONAS, "X99")


def test_resume_after_crash_no_duplicates(tmp_path):
    cfg = make_cfg(tmp_path)
    jobs = I.make_jobs(I.load_vignettes(cfg["inference"]["vignettes"]), PERSONAS, SPEC)
    out = tmp_path / "run"
    out.mkdir()
    with pytest.raises(RuntimeError, match="Crash"):
        I.run_jobs(jobs, I.FakeBackend(cfg, fail_after=60), out, batch_size=24)
    assert len(read(out / I.RAW)) == 48          # deux lots complets écrits avant le crash
    session = I.run_jobs(jobs, I.FakeBackend(cfg), out, batch_size=24)
    rows = read(out / I.RAW)
    keys = [(r["case_id"], r["persona_id"]) for r in rows]
    assert len(keys) == len(set(keys)) == len(jobs)
    assert session["n_already_done"] == 48 and session["n_new_calls"] == len(jobs) - 48
    assert all(r["prompt"] for r in rows) and all("label" not in r for r in rows)


def test_partial_last_line_is_repaired(tmp_path):
    cfg = make_cfg(tmp_path)
    jobs = I.make_jobs(I.load_vignettes(cfg["inference"]["vignettes"])[:1], PERSONAS, SPEC)
    out = tmp_path / "run"
    out.mkdir()
    I.run_jobs(jobs[:10], I.FakeBackend(cfg), out, batch_size=24)
    with open(out / I.RAW, "a", encoding="utf-8") as f:
        f.write('{"case_id": "c0", "persona_id": "trunc')       # crash pendant l'écriture
    session = I.run_jobs(jobs, I.FakeBackend(cfg), out, batch_size=24)
    assert session["repaired_partial_lines"] == 1
    assert len(read(out / I.RAW)) == 24


def test_fingerprint_mismatch_blocks_resume(tmp_path):
    cfg = make_cfg(tmp_path)
    out = tmp_path / "run"
    out.mkdir()
    fp = I.fingerprint(cfg, "fake", ["c0"], ["N00"])
    I.check_or_write_run_config(out, fp, {})
    I.check_or_write_run_config(out, fp, {})                   # même run : accepté
    other = copy.deepcopy(cfg)
    other["generation"]["modes"][other["generation"]["mode"]]["max_new_tokens"] = 99
    with pytest.raises(RuntimeError, match="generation"):
        I.check_or_write_run_config(out, I.fingerprint(other, "fake", ["c0"], ["N00"]), {})
    switched = copy.deepcopy(cfg)
    switched["generation"]["mode"] = next(m for m in cfg["generation"]["modes"]
                                          if m != cfg["generation"]["mode"])
    with pytest.raises(RuntimeError, match="generation"):
        I.check_or_write_run_config(out, I.fingerprint(switched, "fake", ["c0"], ["N00"]), {})
    Path(cfg["inference"]["vignettes"]).write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="vignettes_sha256"):
        I.check_or_write_run_config(out, I.fingerprint(cfg, "fake", ["c0"], ["N00"]), {})


def test_main_end_to_end_with_fake_backend(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    cfg_path = tmp_path / "experiment.yaml"
    import yaml
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    out = tmp_path / "smoke"
    I.main(["--config", str(cfg_path), "--n", "4", "--out", str(out), "--backend", "fake"])
    assert len(read(out / I.RAW)) == 4 * 24
    report = json.loads((out / "parse_report.json").read_text())
    assert report["n_outputs"] == 96
    assert sum(report["status_counts"].values()) == 96
    timing = json.loads((out / I.TIMING).read_text())
    assert timing["full_run_estimate"]["n_full_calls"] == cfg["n_vignettes"] * 24
    # relancer : rien à refaire
    I.main(["--config", str(cfg_path), "--n", "4", "--out", str(out), "--backend", "fake"])
    assert len(read(out / I.RAW)) == 96


def test_resolve_generation_modes():
    cfg = copy.deepcopy(BASE_CFG)
    for mode in cfg["generation"]["modes"]:
        cfg["generation"]["mode"] = mode
        g = I.resolve_generation(cfg)
        assert g["mode"] == mode and {"prefill", "max_new_tokens", "batch_size"} <= set(g)
    cfg["generation"]["mode"] = "nope"
    with pytest.raises(ValueError):
        I.resolve_generation(cfg)
