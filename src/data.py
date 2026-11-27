"""Chargement de NHAMCS 2022 (urgences) et construction des vignettes.

Usage :
    python -m src.data --config config/experiment.yaml

Tout (chemins, colonnes, codes, taille d'échantillon, graine) est lu dans la
configuration. Sorties : vignettes JSONL, compte rendu JSON, fichier de
relecture manuelle (Markdown).
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

LABEL_COL = "label"  # 1 = hospitalisation, 0 = non hospitalisation
LABEL_TEXT = {1: "hospitalization", 0: "no_hospitalization"}
TRUNCATION_MARK = "..."


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------
@dataclass
class Meta:
    """Métadonnées du fichier Stata : étiquettes de valeurs et de variables."""

    value_labels: dict[str, dict[int, str]] = field(default_factory=dict)
    var_labels: dict[str, str] = field(default_factory=dict)


def load_config(path: str | Path) -> dict:
    """Lit le fichier YAML de configuration."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_raw(path: str | Path) -> tuple[pd.DataFrame, Meta]:
    """Lit le fichier Stata NHAMCS (codes numériques bruts) et ses étiquettes."""
    reader = pd.io.stata.StataReader(path)
    with reader:
        df = reader.read(convert_categoricals=False)
        label_sets = reader.value_labels()
        var_labels = reader.variable_labels()
        # pandas n'expose pas publiquement le lien colonne -> jeu d'étiquettes.
        label_names = getattr(reader, "_lbllist", None)
    if label_names is None:
        raise RuntimeError("Version de pandas incompatible : StataReader._lbllist absent.")
    value_labels = {
        col: {int(k): v for k, v in label_sets[name].items()}
        for col, name in zip(df.columns, label_names)
        if name and name in label_sets
    }
    return df, Meta(value_labels=value_labels, var_labels=dict(var_labels))


def load_icd10(path: str | Path) -> dict[str, str]:
    """Lit le fichier « order » ICD-10-CM du CDC (format à largeur fixe).

    Colonnes : n° d'ordre (1-5), code (7-13), en-tête/facturable (15),
    libellé court (17-76), libellé long (78-). Renvoie {code: libellé long}.
    """
    codes: dict[str, str] = {}
    with open(path, encoding="ascii") as f:
        for line in f:
            line = line.rstrip("\r\n")
            code = line[6:13].strip()
            if code:
                codes[code] = line[77:].strip()
    if not codes:
        raise ValueError(f"Aucun code ICD-10-CM lu dans {path}")
    return codes


# ---------------------------------------------------------------------------
# Colonnes
# ---------------------------------------------------------------------------
def vignette_columns(dcfg: dict) -> list[str]:
    """Liste blanche : seules colonnes autorisées dans le texte de la vignette."""
    cols = [dcfg["age_col"], dcfg["sex_col"]]
    cols += [v["col"] for v in dcfg["vitals"]]
    cols += dcfg["rfv_cols"]
    cols += [dcfg["injury_flag_col"]] + [c["col"] for c in dcfg["injury_cols"]]
    cols += dcfg["cause_cols"]
    cols += dcfg["chronic_cols"] + [dcfg["no_chronic_col"]]
    cols += dcfg["diag_cols"] + dcfg["prdiag_cols"]
    cols += [dcfg["exam_flag_col"]] + dcfg["exam_cols"]
    return cols


def outcome_columns(dcfg: dict) -> list[str]:
    """Colonnes d'issue nécessaires à la vérité terrain et aux exclusions."""
    cols = dcfg["hospitalization_cols"] + dcfg["ambiguous_cols"] + [dcfg["no_answer_col"]]
    cols += dcfg["outcome_cols_saved"]
    return list(dict.fromkeys(cols))


def check_columns(df: pd.DataFrame, required: list[str]) -> None:
    """Lève une erreur si une colonne attendue est absente du fichier."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Colonnes absentes du fichier NHAMCS : {missing}")


def check_no_overlap(dcfg: dict) -> None:
    """Vérifie qu'aucune colonne d'issue n'est dans la liste blanche de la vignette."""
    overlap = set(vignette_columns(dcfg)) & set(outcome_columns(dcfg))
    if overlap:
        raise ValueError(f"Colonnes d'issue dans la liste blanche : {sorted(overlap)}")


# ---------------------------------------------------------------------------
# Vérité terrain et exclusions
# ---------------------------------------------------------------------------
def hospitalization_mask(df: pd.DataFrame, dcfg: dict) -> pd.Series:
    """True si au moins une case d'hospitalisation (ou de transfert) est cochée."""
    return (df[dcfg["hospitalization_cols"]] == 1).any(axis=1)


def ambiguity_reasons(df: pd.DataFrame, dcfg: dict) -> pd.DataFrame:
    """Une colonne booléenne par motif d'exclusion (issue ambiguë ou manquante)."""
    reasons = {c: df[c] == 1 for c in dcfg["ambiguous_cols"]}
    reasons[dcfg["no_answer_col"]] = df[dcfg["no_answer_col"]] == 1
    return pd.DataFrame(reasons, index=df.index)


def apply_exclusions(df: pd.DataFrame, dcfg: dict) -> tuple[pd.DataFrame, dict]:
    """Exclut les issues ambiguës, ajoute la colonne `label`, renvoie un compte rendu.

    Une visite cochée à la fois « hospitalisation » et ambiguë est exclue
    (décision du groupe) ; ces conflits sont comptés à part.
    """
    hosp = hospitalization_mask(df, dcfg)
    reasons = ambiguity_reasons(df, dcfg)
    excluded = reasons.any(axis=1)
    kept = df.loc[~excluded].copy()
    kept[LABEL_COL] = hosp[~excluded].astype(int)

    report = {
        "n_raw": int(len(df)),
        "n_excluded": int(excluded.sum()),
        "excluded_by_reason": {c: int(reasons[c].sum()) for c in reasons.columns},
        "note_by_reason": "une visite peut avoir plusieurs motifs",
        "n_conflicts_hospitalization_and_ambiguous": int((hosp & excluded).sum()),
        "conflicts_by_reason": {c: int((reasons[c] & hosp).sum()) for c in reasons.columns},
        "n_kept": int(len(kept)),
        "kept_distribution": {
            LABEL_TEXT[1]: int(kept[LABEL_COL].sum()),
            LABEL_TEXT[0]: int((kept[LABEL_COL] == 0).sum()),
        },
        "kept_hospitalization_by_component": {
            c: int((kept[c] == 1).sum()) for c in dcfg["hospitalization_cols"]
        },
    }
    return kept, report


def stratified_sample(df: pd.DataFrame, n_total: int, seed: int) -> pd.DataFrame:
    """Tire n_total/2 cas par classe, sans remise et sans poids, puis mélange."""
    if n_total % 2:
        raise ValueError(f"n_vignettes doit être pair pour un tirage 50/50 (reçu {n_total}).")
    n_per_class = n_total // 2
    rng = np.random.default_rng(seed)
    parts = []
    for label in (1, 0):
        stratum = df[df[LABEL_COL] == label]
        if len(stratum) < n_per_class:
            raise ValueError(
                f"Strate « {LABEL_TEXT[label]} » trop petite : {len(stratum)} cas "
                f"disponibles, {n_per_class} demandés. Réduire n_vignettes dans la config."
            )
        parts.append(stratum.sample(n=n_per_class, replace=False, random_state=rng))
    return pd.concat(parts).sample(frac=1, random_state=rng)


# ---------------------------------------------------------------------------
# Décodage des champs
# ---------------------------------------------------------------------------
@dataclass
class DecodeStats:
    """Compteurs de décodage (rapportés, jamais ignorés en silence)."""

    rfv_skipped: int = 0
    rfv_leak_masked: dict[str, int] = field(default_factory=dict)
    rfv_without_label: int = 0
    rfv_truncated_label: int = 0
    diag_admin_masked: dict[str, int] = field(default_factory=dict)
    icd_exact: int = 0
    icd_category_fallback: int = 0
    icd_missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rfv_skipped_codes": self.rfv_skipped,
            "rfv_leak_codes_masked": self.rfv_leak_masked,
            "rfv_without_label": self.rfv_without_label,
            "rfv_truncated_label_used": self.rfv_truncated_label,
            "diag_admin_codes_masked": self.diag_admin_masked,
            "icd_exact_match": self.icd_exact,
            "icd_3char_category_fallback": self.icd_category_fallback,
            "icd_missing": sorted(set(self.icd_missing)),
        }


def _bump(d: dict[str, int], key: str) -> None:
    d[key] = d.get(key, 0) + 1


def is_missing(value: Any, dcfg: dict) -> bool:
    """Vrai pour les codes vide (-9) et sans objet (-7)."""
    return value in (dcfg["blank_code"], dcfg["not_applicable_code"])


def label_of(col: str, value: int, meta: Meta) -> str | None:
    """Étiquette de valeur du fichier, ou None."""
    return meta.value_labels.get(col, {}).get(int(value))


def var_name(col: str, meta: Meta, dcfg: dict) -> str:
    """Nom lisible d'une variable (étiquette Stata, ou texte complet de la doc)."""
    if col in dcfg.get("label_overrides", {}):
        return dcfg["label_overrides"][col]
    name = meta.var_labels.get(col, col)
    prefix = dcfg.get("label_prefix_to_strip", "")
    if prefix and name.startswith(prefix):
        name = name[len(prefix):]
    return name.strip()


def decode_age(value: int, meta: Meta, dcfg: dict) -> str:
    label = label_of(dcfg["age_col"], value, meta)
    return label if label else f"{int(value)} years"


def decode_vital(value: int, spec: dict, dcfg: dict) -> str:
    value = int(value)
    if value in dcfg["vital_special_codes"]:
        return dcfg["vital_special_codes"][value]
    if value < 0:
        return dcfg["vital_missing_text"]
    scale = spec["scale"]
    number = f"{value / scale:.1f}" if scale != 1 else str(value)
    return f"{number} {spec['unit']}"


def format_icd(code: str) -> str:
    """'I10-' -> 'I10', 'R079' -> 'R07.9' (décimale implicite après 3 caractères)."""
    code = code.rstrip("-")
    return code[:3] + (f".{code[3:]}" if len(code) > 3 else "")


def decode_icd(code: str, icd: dict[str, str], stats: DecodeStats) -> str:
    """Libellé ICD-10-CM : code exact, sinon catégorie à 3 caractères."""
    raw = code.rstrip("-")
    if raw in icd:
        stats.icd_exact += 1
        desc = icd[raw]
    elif raw[:3] in icd:
        stats.icd_category_fallback += 1
        desc = icd[raw[:3]]
    else:
        stats.icd_missing.append(code)
        desc = "description unavailable"
    return f"{desc} ({format_icd(code)})"


def build_fields(row: pd.Series, meta: Meta, icd: dict[str, str], dcfg: dict,
                 stats: DecodeStats) -> dict:
    """Champs décodés d'une visite. `row` ne contient que la liste blanche."""
    allowed = set(vignette_columns(dcfg))
    extra = set(row.index) - allowed
    if extra:
        raise ValueError(f"Colonnes hors liste blanche passées à build_fields : {sorted(extra)}")
    blank = str(dcfg["blank_code"])

    fields: dict[str, Any] = {
        "age": decode_age(row[dcfg["age_col"]], meta, dcfg),
        "sex": label_of(dcfg["sex_col"], row[dcfg["sex_col"]], meta) or "not recorded",
        "vitals": [
            {"name": s["name"], "value": decode_vital(row[s["col"]], s, dcfg)}
            for s in dcfg["vitals"]
        ],
    }

    # Motifs de consultation
    reasons = []
    for col in dcfg["rfv_cols"]:
        code = int(row[col])
        if is_missing(code, dcfg):
            continue
        if code in dcfg["rfv_skip_codes"]:
            stats.rfv_skipped += 1
            continue
        if code in dcfg["rfv_leak_codes"]:
            _bump(stats.rfv_leak_masked, str(code))
            continue
        label = label_of(col, code, meta)
        if label is None:
            stats.rfv_without_label += 1
            label = f"reason-for-visit code {code} (no label)"
        elif label.endswith(TRUNCATION_MARK):
            stats.rfv_truncated_label += 1
        reasons.append(label)
    fields["reasons_for_visit"] = reasons

    # Blessure / intoxication / effet indésirable
    flag_col = dcfg["injury_flag_col"]
    flag = int(row[flag_col])
    if is_missing(flag, dcfg) or flag == dcfg["injury_not_related_code"]:
        fields["injury"] = None
    else:
        injury = {"type": label_of(flag_col, flag, meta) or str(flag)}
        for spec in dcfg["injury_cols"]:
            v = int(row[spec["col"]])
            if not is_missing(v, dcfg):
                injury[spec["name"]] = label_of(spec["col"], v, meta) or str(v)
        causes = [decode_icd(str(row[c]), icd, stats) for c in dcfg["cause_cols"]
                  if str(row[c]) != blank]
        if causes:
            injury["causes"] = causes
        fields["injury"] = injury

    # Maladies chroniques
    present = [var_name(c, meta, dcfg) for c in dcfg["chronic_cols"] if int(row[c]) == 1]
    no_chronic = int(row[dcfg["no_chronic_col"]])
    if present:
        fields["chronic_conditions"] = present
    elif no_chronic == 1:
        fields["chronic_conditions"] = "none"
    else:
        fields["chronic_conditions"] = "not documented"

    # Diagnostics du médecin
    diagnoses = []
    for dcol, pcol in zip(dcfg["diag_cols"], dcfg["prdiag_cols"]):
        code = str(row[dcol])
        if code == blank:
            continue
        if code.startswith(dcfg["diag_skip_prefix"]):
            _bump(stats.diag_admin_masked, code)
            continue
        text = decode_icd(code, icd, stats)
        if int(row[pcol]) == 1:
            text += " (probable)"
        diagnoses.append(text)
    fields["diagnoses"] = diagnoses

    # Examens demandés
    exam_flag = int(row[dcfg["exam_flag_col"]])
    exams = [var_name(c, meta, dcfg) for c in dcfg["exam_cols"] if int(row[c]) == 1]
    if exams:
        fields["exams_ordered"] = exams
    elif exam_flag == 0:
        fields["exams_ordered"] = "none"
    else:
        fields["exams_ordered"] = "not documented"
    return fields


def _join(items: list[str] | str, empty: str = "not documented") -> str:
    if isinstance(items, str):
        return items
    return "; ".join(items) if items else empty


def render_vignette(fields: dict) -> str:
    """Texte de la vignette (anglais) à partir des champs décodés."""
    vitals = "; ".join(f"{v['name']} {v['value']}" for v in fields["vitals"])
    lines = [
        f"Patient: {fields['age']}, {fields['sex']}.",
        f"Initial vital signs: {vitals}.",
        f"Reason(s) for visit: {_join(fields['reasons_for_visit'])}.",
    ]
    injury = fields["injury"]
    if injury:
        parts = [injury["type"]]
        parts += [f"{k}: {v}" for k, v in injury.items() if k not in ("type", "causes")]
        if injury.get("causes"):
            parts.append("cause: " + "; ".join(injury["causes"]))
        lines.append("Injury / poisoning / adverse effect: " + "; ".join(parts) + ".")
    lines.append(f"Chronic conditions: {_join(fields['chronic_conditions'])}.")
    lines.append(f"Provider's diagnoses: {_join(fields['diagnoses'])}.")
    lines.append(f"Diagnostic services ordered: {_join(fields['exams_ordered'])}.")
    # Un libellé tronqué (« ... ») en fin de ligne ne reçoit pas de point en plus.
    lines = [ln[:-1] if ln.endswith(TRUNCATION_MARK + ".") else ln for ln in lines]
    return "\n".join(lines)


def find_forbidden(text: str, patterns: list[str]) -> list[str]:
    """Motifs interdits (fuite d'issue) trouvés dans le texte."""
    return [p for p in patterns if re.search(p, text, flags=re.IGNORECASE)]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def build_records(sample: pd.DataFrame, meta: Meta, icd: dict[str, str], cfg: dict
                  ) -> tuple[list[dict], dict]:
    """Construit les enregistrements JSONL et les statistiques de décodage."""
    dcfg = cfg["data"]
    whitelist = vignette_columns(dcfg)
    stats = DecodeStats()
    forbidden_hits: dict[str, list[str]] = {}
    records = []
    for row_index, row in sample.iterrows():
        fields = build_fields(row[whitelist], meta, icd, dcfg, stats)
        text = render_vignette(fields)
        case_id = f"ed2022_{row_index}"
        hits = find_forbidden(text, dcfg["forbidden_patterns"])
        if hits:
            forbidden_hits[case_id] = hits
        records.append({
            "case_id": case_id,
            "row_index": int(row_index),
            "label": int(row[LABEL_COL]),
            "label_text": LABEL_TEXT[int(row[LABEL_COL])],
            "outcome_flags": {c: int(row[c]) for c in dcfg["outcome_cols_saved"]},
            "fields": fields,
            "vignette": text,
        })
    decode = stats.as_dict()
    decode["forbidden_pattern_hits"] = forbidden_hits
    return records, decode


def build_dataset(cfg: dict) -> tuple[list[dict], dict, pd.DataFrame]:
    """Chargement, exclusions, tirage et construction des vignettes."""
    dcfg = cfg["data"]
    df, meta = load_raw(dcfg["raw_file"])
    check_no_overlap(dcfg)
    check_columns(df, vignette_columns(dcfg) + outcome_columns(dcfg))
    icd = load_icd10(dcfg["icd10_file"])

    kept, report = apply_exclusions(df, dcfg)
    sample = stratified_sample(kept, cfg["n_vignettes"], cfg["seed"])
    records, decode = build_records(sample, meta, icd, cfg)

    report = {
        "source_file": dcfg["raw_file"],
        "icd10_file": dcfg["icd10_file"],
        **report,
        "sample": {
            "n_vignettes": len(records),
            "seed": cfg["seed"],
            "weights_used": False,
            "distribution": {
                LABEL_TEXT[1]: sum(r["label"] for r in records),
                LABEL_TEXT[0]: sum(1 - r["label"] for r in records),
            },
        },
        "decoding": decode,
    }
    return records, report, sample


def write_jsonl(records: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_manual_check(records: list[dict], sample: pd.DataFrame, dcfg: dict,
                       path: str | Path) -> None:
    """Fichier Markdown de relecture : vignette + valeurs brutes non vides."""
    n_half = dcfg["n_manual_check"] // 2
    chosen = ([r for r in records if r["label"] == 1][:n_half]
              + [r for r in records if r["label"] == 0][:n_half])
    whitelist = vignette_columns(dcfg)
    lines = ["# Relecture manuelle des vignettes", "",
             "Pour chaque cas : vérité terrain, cases d'issue cochées, valeurs brutes "
             "(colonnes de la liste blanche, hors 0 et codes vides), puis le texte.", ""]
    for rec in chosen:
        raw = sample.loc[rec["row_index"], whitelist]
        shown = {c: v for c, v in raw.items()
                 if str(v) not in ("0", str(dcfg["blank_code"]), str(dcfg["not_applicable_code"]))}
        flags = [c for c, v in rec["outcome_flags"].items() if v == 1]
        lines += [
            f"## {rec['case_id']} — {rec['label_text']}", "",
            f"Cases d'issue cochées : {', '.join(flags) or 'aucune'}", "",
            "Valeurs brutes : " + ", ".join(f"`{c}={v}`" for c, v in shown.items()), "",
            "```text", rec["vignette"], "```", "",
        ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Construit les vignettes NHAMCS 2022.")
    parser.add_argument("--config", default="config/experiment.yaml")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    dcfg = cfg["data"]
    records, report, sample = build_dataset(cfg)
    write_jsonl(records, dcfg["vignettes_out"])
    Path(dcfg["report_out"]).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_manual_check(records, sample, dcfg, dcfg["manual_check_out"])

    print(json.dumps({k: report[k] for k in (
        "n_raw", "n_excluded", "excluded_by_reason",
        "n_conflicts_hospitalization_and_ambiguous", "n_kept", "kept_distribution", "sample",
    )}, indent=2, ensure_ascii=False))
    hits = report["decoding"]["forbidden_pattern_hits"]
    if hits:
        print(f"ATTENTION : {len(hits)} vignette(s) contiennent un motif interdit "
              f"(voir {dcfg['report_out']}).")
    print(f"Écrit : {dcfg['vignettes_out']}, {dcfg['report_out']}, {dcfg['manual_check_out']}")


if __name__ == "__main__":
    main()
