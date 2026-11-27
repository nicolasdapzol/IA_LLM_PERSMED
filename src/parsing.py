"""Extraction de la décision depuis la sortie brute du modèle.

Usage :
    python -m src.parsing --in results/smoke [--config config/experiment.yaml]

Lit <run>/raw.jsonl, écrit <run>/parsed.jsonl et <run>/parse_report.json.
Aucune sortie invalide ne reçoit de décision par défaut : elle est comptée.
Si la sortie contient un bloc de raisonnement, seule la réponse qui le suit est lue.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

OK_STRICT = "ok_strict"          # la sortie entière est le JSON attendu
OK_EXTRACTED = "ok_extracted"    # un seul JSON valide, entouré d'autre texte
INVALID_JSON = "invalid_json"    # aucun objet JSON lisible
INVALID_VALUE = "invalid_value"  # JSON lisible, mais clé ou valeur inattendue
CONTRADICTORY = "contradictory"  # plusieurs décisions différentes
EMPTY = "empty"                  # sortie vide
THINKING_TRUNCATED = "thinking_truncated"  # raisonnement commencé mais jamais terminé
OK_STATUSES = (OK_STRICT, OK_EXTRACTED)
ALL_STATUSES = (OK_STRICT, OK_EXTRACTED, INVALID_JSON, INVALID_VALUE, CONTRADICTORY, EMPTY,
                THINKING_TRUNCATED)

_JSON_OBJECT = re.compile(r"\{[^{}]*\}")


def _decision_of(obj: object, key: str, values: dict[str, int]) -> int | None:
    """Décision codée si l'objet est {key: valeur autorisée}, sinon None."""
    if not isinstance(obj, dict) or set(obj) != {key}:
        return None
    value = obj[key]
    if not isinstance(value, str):
        return None
    return values.get(value.strip().lower())


def parse_output(text: str, key: str, values: dict[str, int]) -> tuple[int | None, str]:
    """Renvoie (décision codée ou None, statut)."""
    if not text or not text.strip():
        return None, EMPTY
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        obj = None
    else:
        decision = _decision_of(obj, key, values)
        return (decision, OK_STRICT) if decision is not None else (None, INVALID_VALUE)

    decisions, parsed_any = [], False
    for match in _JSON_OBJECT.findall(stripped):
        try:
            candidate = json.loads(match)
        except json.JSONDecodeError:
            continue
        parsed_any = True
        decision = _decision_of(candidate, key, values)
        if decision is not None:
            decisions.append(decision)
    if len(set(decisions)) == 1:
        return decisions[0], OK_EXTRACTED
    if len(set(decisions)) > 1:
        return None, CONTRADICTORY
    return None, INVALID_VALUE if parsed_any else INVALID_JSON


def split_thinking(text: str, start: str, end: str) -> tuple[str | None, str | None]:
    """Renvoie (raisonnement, réponse). Réponse None si le raisonnement n'est pas terminé."""
    if end in text:
        head, _, answer = text.rpartition(end)
        return head.replace(start, "", 1).strip(), answer
    if text.lstrip().startswith(start):
        return text.lstrip()[len(start):].strip(), None
    return None, text


def parse_raw(text: str, pcfg: dict) -> tuple[int | None, str, str | None]:
    """Sortie brute -> (décision codée ou None, statut, raisonnement ou None)."""
    thinking, answer = split_thinking(text or "", pcfg["thinking_start"], pcfg["thinking_end"])
    if answer is None:
        return None, THINKING_TRUNCATED, thinking
    decision, status = parse_output(answer, pcfg["decision_key"], pcfg["values"])
    return decision, status, thinking


def parse_records(records: list[dict], pcfg: dict) -> tuple[list[dict], dict]:
    """Parse toutes les sorties ; renvoie les lignes parsées et le compte rendu."""
    parsed = []
    by_persona: dict[str, Counter] = defaultdict(Counter)
    hosp_by_persona: Counter = Counter()
    for rec in records:
        decision, status, thinking = parse_raw(rec["output"], pcfg)
        parsed.append({
            "case_id": rec["case_id"],
            "persona_id": rec["persona_id"],
            "decision": decision,
            "parse_status": status,
            "p_hospitalize": (rec.get("score") or {}).get("p_hospitalize"),
            "has_thinking": thinking is not None,
            "thinking_words": len(thinking.split()) if thinking else 0,
        })
        by_persona[rec["persona_id"]][status] += 1
        if decision == 1:
            hosp_by_persona[rec["persona_id"]] += 1

    total = Counter()
    for c in by_persona.values():
        total.update(c)
    n = sum(total.values())
    n_invalid = n - sum(total[s] for s in OK_STATUSES)
    per_persona = {}
    for pid, c in by_persona.items():
        n_p = sum(c.values())
        n_ok = sum(c[s] for s in OK_STATUSES)
        per_persona[pid] = {
            "n": n_p,
            "status_counts": {s: c[s] for s in ALL_STATUSES if c[s]},
            "invalid_rate": round((n_p - n_ok) / n_p, 4) if n_p else None,
            "hospitalization_rate_among_valid": round(hosp_by_persona[pid] / n_ok, 4) if n_ok else None,
        }
    invalid_rate = n_invalid / n if n else 0.0
    report = {
        "n_outputs": n,
        "status_counts": {s: total[s] for s in ALL_STATUSES},
        "n_invalid": n_invalid,
        "invalid_rate": round(invalid_rate, 4),
        "max_invalid_rate": pcfg["max_invalid_rate"],
        "invalid_rate_above_threshold": invalid_rate > pcfg["max_invalid_rate"],
        "n_missing_score": sum(p["p_hospitalize"] is None for p in parsed),
        "n_with_thinking": sum(p["has_thinking"] for p in parsed),
        "per_persona": dict(sorted(per_persona.items())),
    }
    return parsed, report


def read_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Parse les sorties brutes d'un run.")
    parser.add_argument("--in", dest="run_dir", required=True)
    parser.add_argument("--config", default="config/experiment.yaml")
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        pcfg = yaml.safe_load(f)["parsing"]
    run = Path(args.run_dir)
    parsed, report = parse_records(read_jsonl(run / "raw.jsonl"), pcfg)
    with open(run / "parsed.jsonl", "w", encoding="utf-8") as f:
        for rec in parsed:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (run / "parse_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n_outputs", "status_counts", "invalid_rate",
                                             "n_missing_score")}, indent=2))
    if report["invalid_rate_above_threshold"]:
        print(f"ATTENTION : taux de sorties invalides {report['invalid_rate']:.2%} > "
              f"{pcfg['max_invalid_rate']:.0%} : revoir la consigne avant le run complet.")
    print(f"Écrit : {run / 'parsed.jsonl'}, {run / 'parse_report.json'}")


if __name__ == "__main__":
    main()
