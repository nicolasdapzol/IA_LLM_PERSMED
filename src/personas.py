"""Personas et prompts : lecture et validation de config/personas.yaml.

Usage :
    python -m src.personas --config config/experiment.yaml

Construit les 24 conditions (18 factorielles, 1 sans persona, 5 identités non
médicales tirées avec la graine de la config), vérifie le fichier et écrit un
aperçu Markdown à relire.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FACTORIAL, NO_PERSONA, NON_MEDICAL = "factorial", "no_persona", "non_medical"


@dataclass(frozen=True)
class Persona:
    """Une condition expérimentale : texte de persona (éventuellement vide) et sources."""

    id: str
    kind: str
    text: str
    sources: tuple[str, ...]
    factors: dict = field(default_factory=dict, hash=False, compare=False)
    role: str | None = None

    @property
    def n_words(self) -> int:
        return len(self.text.split())


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_spec(spec: dict) -> None:
    """Vérifie la cohérence de personas.yaml ; lève ValueError sinon."""
    errors = []
    refs = spec.get("references", {})
    for factor, levels in spec["factors"].items():
        blocks = spec["blocks"].get(factor, {})
        if set(blocks) != set(levels):
            errors.append(f"Facteur {factor} : niveaux {levels} ≠ blocs {sorted(blocks)}")
        for level, block in blocks.items():
            if block["text"].strip() and not block["sources"]:
                errors.append(f"Bloc {factor}/{level} sans source")
            errors += [f"Bloc {factor}/{level} : référence inconnue {s}"
                       for s in block["sources"] if s not in refs]
    for name, ctrl in spec["controls"].items():
        if not ctrl.get("sources"):
            errors.append(f"Contrôle {name} sans source")
        errors += [f"Contrôle {name} : référence inconnue {s}"
                   for s in ctrl.get("sources", []) if s not in refs]
    nm = spec["controls"]["non_medical"]
    if not set(nm["excluded_roles"]) <= set(nm["roles"]):
        errors.append("excluded_roles contient des rôles absents de roles")
    if len(set(nm["roles"]) - set(nm["excluded_roles"])) < nm["n"]:
        errors.append("Pas assez de rôles non médicaux pour le tirage")
    placeholder = spec["vignette_placeholder"]
    if spec["task_prompt"].count(placeholder) != 1:
        errors.append(f"task_prompt doit contenir {placeholder} exactement une fois")
    if errors:
        raise ValueError("personas.yaml invalide :\n- " + "\n- ".join(errors))


# ---------------------------------------------------------------------------
# Construction des personas
# ---------------------------------------------------------------------------
def compose(template: str, parts: dict[str, str]) -> str:
    """Assemble les blocs ; un bloc vide ne laisse pas d'espace en trop."""
    text = template
    for key, value in parts.items():
        text = text.replace("{" + key + "}", value)
    return " ".join(text.split())


def factorial_personas(spec: dict) -> list[Persona]:
    """18 personas = produit cartésien des niveaux des 3 facteurs."""
    factors = spec["factors"]
    names = list(factors)
    out = []
    for levels in itertools.product(*(factors[n] for n in names)):
        chosen = dict(zip(names, levels))
        blocks = {n: spec["blocks"][n][lvl] for n, lvl in chosen.items()}
        text = compose(spec["persona_template"], {n: b["text"] for n, b in blocks.items()})
        sources = tuple(dict.fromkeys(s for b in blocks.values() for s in b["sources"]))
        out.append(Persona(id="F_" + "_".join(levels), kind=FACTORIAL, text=text,
                           sources=sources, factors=chosen))
    return out


def role_text(role: str, overrides: dict[str, str]) -> str:
    if role in overrides:
        return overrides[role]
    article = "an" if role[0].lower() in "aeiou" else "a"
    return f"{article} {role}"


def draw_non_medical_roles(nm: dict, seed: int) -> list[str]:
    """Tire n rôles (sans remise) dans la liste triée, hors rôles exclus."""
    pool = sorted(set(nm["roles"]) - set(nm["excluded_roles"]))
    return random.Random(seed).sample(pool, nm["n"])


def non_medical_personas(spec: dict, seed: int) -> list[Persona]:
    nm = spec["controls"]["non_medical"]
    out = []
    for i, role in enumerate(draw_non_medical_roles(nm, seed), start=1):
        text = nm["template"].replace("{role_text}", role_text(role, nm["role_text_overrides"]))
        out.append(Persona(id=f"{nm['id_prefix']}{i:02d}", kind=NON_MEDICAL, text=text,
                           sources=tuple(nm["sources"]), role=role))
    return out


def build_personas(spec: dict, seed: int) -> list[Persona]:
    """Les 24 conditions, dans l'ordre : factorielles, sans persona, non médicales."""
    validate_spec(spec)
    ctrl = spec["controls"]["no_persona"]
    personas = (factorial_personas(spec)
                + [Persona(id=ctrl["id"], kind=NO_PERSONA, text="", sources=tuple(ctrl["sources"]))]
                + non_medical_personas(spec, seed))
    ids = [p.id for p in personas]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Identifiants de personas en double : {ids}")
    if len(personas) != spec["expected_total"]:
        raise ValueError(f"{len(personas)} personas construites, {spec['expected_total']} attendues")
    return personas


def load_personas(experiment_cfg: dict) -> tuple[list[Persona], dict]:
    """Charge personas.yaml (chemin et graine lus dans experiment.yaml)."""
    spec = load_yaml(experiment_cfg["personas"]["file"])
    return build_personas(spec, experiment_cfg["seed"]), spec


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def build_prompt(persona: Persona, vignette: str, spec: dict) -> str:
    """Prompt exact envoyé au modèle : persona (si non vide) + consigne + vignette."""
    task = spec["task_prompt"].replace(spec["vignette_placeholder"], vignette)
    if not persona.text:
        return task
    return persona.text + spec["persona_task_separator"] + task


def unverified_references(spec: dict, personas: list[Persona]) -> list[str]:
    """Références utilisées dont le champ verified_by est vide."""
    used = dict.fromkeys(s for p in personas for s in p.sources)
    return [r for r in used if not spec["references"][r].get("verified_by")]


# ---------------------------------------------------------------------------
# Aperçu
# ---------------------------------------------------------------------------
def first_vignette(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.loads(f.readline())["vignette"]


def write_preview(personas: list[Persona], spec: dict, cfg: dict, path: str | Path) -> None:
    """Markdown de relecture : tableau des 24 conditions, sources, prompts d'exemple."""
    lines = ["# Aperçu des personas", "",
             f"Généré par `python -m src.personas` (graine {cfg['seed']}). "
             f"{len(personas)} conditions.", "",
             "| id | type | mots | texte de la persona | sources |", "|---|---|---|---|---|"]
    for p in personas:
        lines.append(f"| {p.id} | {p.kind} | {p.n_words} | {p.text or '*(aucune)*'} | "
                     f"{', '.join(p.sources)} |")
    unverified = unverified_references(spec, personas)
    lines += ["", "## Références", ""]
    for key in dict.fromkeys(s for p in personas for s in p.sources):
        ref = spec["references"][key]
        status = ref.get("verified_by") or "**non vérifiée par le groupe**"
        lines.append(f"- `{key}` — {ref['citation']} doi: {ref.get('doi') or '—'} ({status})")
    if unverified:
        lines += ["", f"⚠ {len(unverified)} référence(s) à vérifier : {', '.join(unverified)}"]

    vignette = first_vignette(cfg["personas"]["preview_vignettes"]) or "<vignette>"
    lines += ["", "## Prompts complets (exemples)", ""]
    examples = [personas[0], next(p for p in personas if p.kind == NO_PERSONA),
                next(p for p in personas if p.kind == NON_MEDICAL)]
    for p in examples:
        lines += [f"### {p.id}", "", "```text", build_prompt(p, vignette, spec), "```", ""]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Construit et vérifie les 24 personas.")
    parser.add_argument("--config", default="config/experiment.yaml")
    args = parser.parse_args(argv)

    cfg = load_yaml(args.config)
    personas, spec = load_personas(cfg)
    out = cfg["personas"]["preview_out"]
    write_preview(personas, spec, cfg, out)

    counts = {k: sum(p.kind == k for p in personas) for k in (FACTORIAL, NO_PERSONA, NON_MEDICAL)}
    print(f"{len(personas)} personas : {counts}")
    print("Identités non médicales :", [p.role for p in personas if p.kind == NON_MEDICAL])
    unverified = unverified_references(spec, personas)
    if unverified:
        print(f"ATTENTION : {len(unverified)} référence(s) non vérifiée(s) par le groupe : "
              f"{', '.join(unverified)}")
    print(f"Écrit : {out}")


if __name__ == "__main__":
    main()
