"""Boucle d'inférence MedGemma : vignettes × personas, écriture au fil de l'eau, reprise.

Usage :
    python -m src.inference --config config/experiment.yaml --n 20 --personas all --out results/smoke
    python -m src.inference --config config/experiment.yaml --out results/full      # toutes les vignettes
    --mode thinking | no_thinking   (défaut : generation.mode de la config)

Sorties dans --out :
    raw.jsonl          une ligne par (case_id, persona_id) : prompt exact, sortie brute, score, durée
    run_config.json    empreinte du run (modèle, génération, fichiers d'entrée) + environnement
    timing.json        durée de chaque session et estimation du run complet
    parsed.jsonl, parse_report.json   (voir src/parsing.py, relancé à la fin)
Relancer la même commande reprend là où le run s'est arrêté.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Iterator, Protocol

import yaml

from src import parsing
from src import personas as P

RAW, RUN_CONFIG, TIMING = "raw.jsonl", "run_config.json", "timing.json"


# ---------------------------------------------------------------------------
# Entrées
# ---------------------------------------------------------------------------
def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_vignettes(path: str | Path) -> list[dict]:
    """Vignettes (seuls case_id, label et texte sont gardés ; le label ne sert qu'à la sélection)."""
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [{"case_id": r["case_id"], "label": r["label"], "vignette": r["vignette"]} for r in rows]


def select_vignettes(vignettes: list[dict], n: int | None) -> list[dict]:
    """n vignettes équilibrées (n/2 par classe), dans l'ordre du fichier (déjà mélangé)."""
    if n is None:
        return list(vignettes)
    if n % 2:
        raise ValueError(f"--n doit être pair pour un échantillon équilibré (reçu {n}).")
    chosen = []
    for label in (1, 0):
        stratum = [v for v in vignettes if v["label"] == label][: n // 2]
        if len(stratum) < n // 2:
            raise ValueError(f"Pas assez de vignettes de classe {label} pour --n {n}.")
        chosen += stratum
    keep = {v["case_id"] for v in chosen}
    return [v for v in vignettes if v["case_id"] in keep]


def select_personas(personas: list[P.Persona], spec: str) -> list[P.Persona]:
    """'all' ou liste d'identifiants séparés par des virgules."""
    if spec == "all":
        return list(personas)
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    by_id = {p.id: p for p in personas}
    unknown = [w for w in wanted if w not in by_id]
    if unknown:
        raise ValueError(f"Personas inconnues : {unknown}")
    return [by_id[w] for w in wanted]


def make_jobs(vignettes: list[dict], personas: list[P.Persona], spec: dict) -> list[dict]:
    """Ordre vignette par vignette (les 24 personas d'une vignette sont consécutives)."""
    return [
        {"case_id": v["case_id"], "persona_id": p.id, "persona_kind": p.kind,
         "prompt": P.build_prompt(p, v["vignette"], spec)}
        for v in vignettes for p in personas
    ]


# ---------------------------------------------------------------------------
# Reprise
# ---------------------------------------------------------------------------
def repair_tail(raw_path: Path) -> int:
    """Supprime une dernière ligne incomplète (crash pendant l'écriture). Renvoie 0 ou 1."""
    if not raw_path.exists() or raw_path.stat().st_size == 0:
        return 0
    data = raw_path.read_bytes()
    if data.endswith(b"\n"):
        return 0
    raw_path.write_bytes(data[: data.rfind(b"\n") + 1])
    return 1


def done_keys(raw_path: Path) -> set[tuple[str, str]]:
    if not raw_path.exists():
        return set()
    with open(raw_path, encoding="utf-8") as f:
        return {(r["case_id"], r["persona_id"]) for r in map(json.loads, filter(str.strip, f))}


def resolve_generation(cfg: dict) -> dict:
    """Paramètres de génération du mode choisi (generation.mode)."""
    g = cfg["generation"]
    if g["mode"] not in g["modes"]:
        raise ValueError(f"Mode inconnu : {g['mode']} (attendu : {sorted(g['modes'])})")
    return {"do_sample": g["do_sample"], "mode": g["mode"], **g["modes"][g["mode"]]}


def fingerprint(cfg: dict, backend_name: str, case_ids: list[str], persona_ids: list[str]) -> dict:
    """Ce qui doit être identique pour reprendre un run."""
    return {
        "backend": backend_name,
        "model": cfg["model"],
        "generation": resolve_generation(cfg),
        "thinking_markers": [cfg["parsing"]["thinking_start"], cfg["parsing"]["thinking_end"]],
        "answer_candidates": cfg["inference"]["answer_candidates"],
        "seed": cfg["seed"],
        "vignettes_file": cfg["inference"]["vignettes"],
        "vignettes_sha256": sha256_file(cfg["inference"]["vignettes"]),
        "personas_file": cfg["personas"]["file"],
        "personas_sha256": sha256_file(cfg["personas"]["file"]),
        "case_ids_sha256": hashlib.sha256("\n".join(case_ids).encode()).hexdigest(),
        "n_vignettes": len(case_ids),
        "persona_ids": persona_ids,
    }


def check_or_write_run_config(out: Path, fp: dict, environment: dict) -> None:
    """Crée run_config.json, ou vérifie qu'il correspond au run en cours."""
    path = out / RUN_CONFIG
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))["fingerprint"]
        diff = sorted(k for k in fp.keys() | previous.keys() if fp.get(k) != previous.get(k))
        if diff:
            raise RuntimeError(f"Reprise impossible : le run dans {out} diffère sur {diff}. "
                               "Utiliser un autre --out.")
        return
    tmp = path.with_suffix(".tmp")      # écriture atomique : jamais de fichier à moitié écrit
    tmp.write_text(json.dumps({"fingerprint": fp, "environment": environment,
                               "created_at": now()}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------
class Backend(Protocol):
    name: str

    def info(self) -> dict: ...

    def generate(self, prompts: list[str]) -> list[dict]: ...


class FakeBackend:
    """Modèle factice déterministe (tests, machine sans GPU)."""

    name = "fake"

    def __init__(self, cfg: dict, fail_after: int | None = None):
        self.answers = cfg["inference"]["answer_candidates"]
        self.fail_after = fail_after
        self.calls = 0

    def info(self) -> dict:
        return {"backend": self.name}

    def generate(self, prompts: list[str]) -> list[dict]:
        if self.fail_after is not None and self.calls + len(prompts) > self.fail_after:
            raise RuntimeError("Crash simulé")
        self.calls += len(prompts)
        outs = []
        for prompt in prompts:
            h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
            p = (h % 1000) / 1000
            text = self.answers["hospitalize" if p >= 0.5 else "do_not_hospitalize"]
            if h % 7 == 0:
                text = "I am not sure."
            outs.append({"output": text, "n_prompt_tokens": len(prompt.split()),
                         "n_output_tokens": len(text.split()), "finish": "eos",
                         "score": None if h % 7 == 0 else {"p_hospitalize": p}})
        return outs


class HFBackend:
    """MedGemma via transformers, décodage glouton, score continu des deux réponses."""

    name = "hf"

    def __init__(self, cfg: dict):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor, LogitsProcessor

        mcfg, self.gcfg = cfg["model"], resolve_generation(cfg)
        torch.manual_seed(cfg["seed"])
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(mcfg["id"], revision=mcfg["revision"])
        self.tok = self.processor.tokenizer
        self.tok.padding_side = "left"
        self.model = AutoModelForImageTextToText.from_pretrained(
            mcfg["id"], revision=mcfg["revision"], dtype=getattr(torch, mcfg["dtype"]),
            device_map="cuda")
        self.model.eval()

        # Les deux réponses complètes ont un début commun ({"decision": ") puis divergent :
        # le score compare les deux tokens de divergence à cet endroit de la génération.
        cands = cfg["inference"]["answer_candidates"]
        ids_h = self.tok.encode(cands["hospitalize"], add_special_tokens=False)
        ids_d = self.tok.encode(cands["do_not_hospitalize"], add_special_tokens=False)
        k = next(i for i, (a, b) in enumerate(zip(ids_h, ids_d)) if a != b)
        # Le préfixe cherché commence à la clé (decision": ") : le modèle écrit parfois
        # « {\n  "decision": ... » sur plusieurs lignes, où le token « {" » n'apparaît pas.
        key = cfg["parsing"]["decision_key"]
        start = next(i for i in range(k) if self.tok.decode(ids_h[i:k]).startswith(key))
        self.prefix, self.tok_h, self.tok_d = ids_h[start:k], ids_h[k], ids_d[k]
        # La réponse est cherchée après le dernier marqueur de fin de raisonnement.
        end_ids = self.tok.encode(cfg["parsing"]["thinking_end"], add_special_tokens=False)
        if len(end_ids) != 1:
            raise ValueError(f"Marqueur de fin de raisonnement sur {len(end_ids)} tokens : {end_ids}")
        self.thinking_end_id = end_ids[0]
        self.eos_ids = set(self.model.generation_config.eos_token_id or [])
        self.eos_ids |= {self.tok.eos_token_id, self.tok.pad_token_id} - {None}

        tok_h, tok_d = self.tok_h, self.tok_d

        class _Recorder(LogitsProcessor):
            """Garde, à chaque pas, les log-probabilités des deux tokens de divergence."""

            def __init__(self):
                self.steps = []

            def __call__(self, input_ids, scores):
                lp = scores.float().log_softmax(dim=-1)
                self.steps.append(lp[:, [tok_h, tok_d]].cpu())
                return scores

        self._recorder_cls = _Recorder

    def chat_text(self, prompt: str) -> str:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        return self.processor.apply_chat_template(messages, tokenize=False,
                                                  add_generation_prompt=True) + self.gcfg["prefill"]

    def info(self) -> dict:
        import torch
        import transformers
        template = self.processor.chat_template or ""
        return {
            "backend": self.name,
            "torch": torch.__version__, "transformers": transformers.__version__,
            "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
            "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest(),
            "chat_text_example": self.chat_text("<prompt>"),
            "generation": self.gcfg,
            "score_tokens": {"prefix": self.prefix, "hospitalize": self.tok_h,
                             "thinking_end": self.thinking_end_id,
                             "do_not_hospitalize": self.tok_d,
                             "decoded": [self.tok.decode(self.prefix), self.tok.decode([self.tok_h]),
                                         self.tok.decode([self.tok_d])]},
        }

    def _score(self, gen_ids: list[int], steps, row: int) -> dict | None:
        k = len(self.prefix)
        begin = max((i + 1 for i, t in enumerate(gen_ids) if t == self.thinking_end_id), default=0)
        for start in range(begin, len(gen_ids) - k + 1):
            if gen_ids[start:start + k] == self.prefix:
                step = start + k
                if step >= len(steps):
                    return None
                lh, ld = (float(x) for x in steps[step][row])
                m = max(lh, ld)
                p = math.exp(lh - m) / (math.exp(lh - m) + math.exp(ld - m))
                nxt = gen_ids[step] if step < len(gen_ids) else None
                chosen = ("hospitalize" if nxt == self.tok_h else
                          "do_not_hospitalize" if nxt == self.tok_d else "other")
                return {"p_hospitalize": p, "logprob_hospitalize": lh,
                        "logprob_do_not_hospitalize": ld, "step": step, "greedy_choice": chosen}
        return None

    def generate(self, prompts: list[str]) -> list[dict]:
        torch = self.torch
        texts = [self.chat_text(p) for p in prompts]
        enc = self.tok(texts, return_tensors="pt", padding=True, add_special_tokens=False)
        enc = {k: v.to(self.model.device) for k, v in enc.items()}
        recorder = self._recorder_cls()
        with torch.inference_mode():
            seqs = self.model.generate(
                **enc, do_sample=self.gcfg["do_sample"],
                max_new_tokens=self.gcfg["max_new_tokens"],
                logits_processor=[recorder], pad_token_id=self.tok.pad_token_id)
        n_in = enc["input_ids"].shape[1]
        n_prompt = enc["attention_mask"].sum(dim=1).tolist()
        outs = []
        for row, seq in enumerate(seqs[:, n_in:].tolist()):
            cut = next((i for i, t in enumerate(seq) if t in self.eos_ids), None)
            gen = seq if cut is None else seq[:cut]
            outs.append({
                "output": self.tok.decode(gen, skip_special_tokens=True),
                "n_prompt_tokens": int(n_prompt[row]),
                "n_output_tokens": len(gen),
                "finish": "length" if cut is None else "eos",
                "score": self._score(gen, recorder.steps, row),
            })
        return outs


# ---------------------------------------------------------------------------
# Boucle
# ---------------------------------------------------------------------------
def chunks(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def run_jobs(jobs: list[dict], backend: Backend, out: Path, batch_size: int) -> dict:
    """Exécute les jobs absents de raw.jsonl ; écrit et synchronise après chaque lot."""
    raw = out / RAW
    repaired = repair_tail(raw)
    done = done_keys(raw)
    todo = [j for j in jobs if (j["case_id"], j["persona_id"]) not in done]
    n_batches = math.ceil(len(todo) / batch_size) if todo else 0
    batch_seconds = []
    t_start = time.perf_counter()
    with open(raw, "a", encoding="utf-8") as f:
        for b, batch in enumerate(chunks(todo, batch_size), start=1):
            t0 = time.perf_counter()
            outs = backend.generate([j["prompt"] for j in batch])
            elapsed = time.perf_counter() - t0
            batch_seconds.append(elapsed)
            stamp = now()
            for job, o in zip(batch, outs):
                f.write(json.dumps({**job, **o, "batch_seconds": round(elapsed, 4),
                                    "batch_size": len(batch), "timestamp": stamp},
                                   ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            print(f"lot {b}/{n_batches} : {len(batch)} appels en {elapsed:.1f} s", flush=True)
    total = time.perf_counter() - t_start
    n_new = len(todo)
    # Le premier lot inclut l'échauffement (compilation, allocation) : estimation sans lui.
    steady = batch_seconds[1:] if len(batch_seconds) > 1 else batch_seconds
    steady_calls = n_new - (len(todo[:batch_size]) if len(batch_seconds) > 1 else 0)
    return {
        "started_at": None, "n_jobs": len(jobs), "n_already_done": len(jobs) - len(todo),
        "n_new_calls": n_new, "repaired_partial_lines": repaired,
        "seconds_total": round(total, 2),
        "seconds_per_call": round(total / n_new, 4) if n_new else None,
        "seconds_per_call_without_first_batch":
            round(sum(steady) / steady_calls, 4) if n_new and steady_calls else None,
    }


def append_timing(out: Path, session: dict, n_full_calls: int) -> dict:
    path = out / TIMING
    sessions = json.loads(path.read_text(encoding="utf-8"))["sessions"] if path.exists() else []
    sessions.append(session)
    spc = session["seconds_per_call_without_first_batch"] or session["seconds_per_call"]
    estimate = {"n_full_calls": n_full_calls, "seconds_per_call_used": spc,
                "estimated_hours": round(spc * n_full_calls / 3600, 2) if spc else None}
    path.write_text(json.dumps({"sessions": sessions, "full_run_estimate": estimate}, indent=2),
                    encoding="utf-8")
    return estimate


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Inférence MedGemma : vignettes × personas.")
    ap.add_argument("--config", default="config/experiment.yaml")
    ap.add_argument("--n", type=int, default=None, help="nombre de vignettes (pair) ; défaut : toutes")
    ap.add_argument("--personas", default="all", help="'all' ou ids séparés par des virgules")
    ap.add_argument("--out", required=True, help="dossier du run (reprise si existant)")
    ap.add_argument("--backend", choices=["hf", "fake"], default="hf")
    ap.add_argument("--mode", default=None, help="mode de generation.modes (défaut : config)")
    args = ap.parse_args(argv)

    cfg = P.load_yaml(args.config)
    if args.mode:
        cfg["generation"]["mode"] = args.mode
    gen = resolve_generation(cfg)
    all_personas, spec = P.load_personas(cfg)
    personas = select_personas(all_personas, args.personas)
    vignettes = select_vignettes(load_vignettes(cfg["inference"]["vignettes"]), args.n)
    jobs = make_jobs(vignettes, personas, spec)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    backend: Backend = HFBackend(cfg) if args.backend == "hf" else FakeBackend(cfg)
    fp = fingerprint(cfg, backend.name, [v["case_id"] for v in vignettes], [p.id for p in personas])
    env = {**backend.info(), "python": platform.python_version(), "platform": platform.platform()}
    check_or_write_run_config(out, fp, env)

    print(f"{len(vignettes)} vignettes × {len(personas)} personas = {len(jobs)} appels "
          f"(mode {gen['mode']})")
    started = now()
    session = run_jobs(jobs, backend, out, gen["batch_size"])
    session["started_at"] = started
    estimate = append_timing(out, session, cfg["n_vignettes"] * len(all_personas))

    parsed, report = parsing.parse_records(parsing.read_jsonl(out / RAW), cfg["parsing"])
    with open(out / "parsed.jsonl", "w", encoding="utf-8") as f:
        for rec in parsed:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (out / "parse_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({"session": session, "full_run_estimate": estimate,
                      "invalid_rate": report["invalid_rate"],
                      "status_counts": report["status_counts"],
                      "n_missing_score": report["n_missing_score"]}, indent=2))


if __name__ == "__main__":
    main()
