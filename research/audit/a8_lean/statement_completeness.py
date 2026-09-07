"""A8: are the admitted 'complete source headers' self-contained propositions?

Measures, over every candidate statement in the Astra bank, how many identifiers
occur free -- neither bound by the header's own binder groups nor resolvable to a
mathlib declaration.  Those are ambient `variable`/`section` bindings that
corpus.jsonl does not record, so the rendered statement is not a closed formula.

Read-only.  Reads corpus.jsonl (permitted) and the development bank only.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from arena.environments import premise_selection as ps

SOURCE = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4"
)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
KEYWORDS = {
    "theorem", "lemma", "def", "abbrev", "instance", "structure", "inductive", "class",
    "axiom", "opaque", "Type", "Prop", "Sort", "fun", "if", "then", "else", "let", "in",
    "match", "with", "do", "forall", "exists", "and", "or", "not", "by", "at", "from",
    "u", "v", "w", "u_1", "u_2", "u_3", "u_4",
}


def bound_names(header: str) -> set[str]:
    """Names bound by the header's own binder groups, before the top-level ':'."""
    out: set[str] = set()
    depth = 0
    start = None
    opener = ""
    i = 0
    # strip 'theorem NAME' prefix
    m = re.match(r"\s*(theorem|lemma)\s+([^\s({\[]+)", header)
    body = header[m.end():] if m else header
    if m:
        out.add(m.group(2).rsplit(".", 1)[-1])
    while i < len(body):
        ch = body[i]
        if ch in "([{":
            if depth == 0:
                start, opener = i, ch
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0 and start is not None:
                group = body[start + 1 : i]
                names = group.split(":", 1)[0]
                for tok in IDENT.findall(names):
                    out.add(tok)
                start = None
        elif ch == ":" and depth == 0:
            break
        i += 1
    return out


def main() -> None:
    decls, _ = ps.load_corpus(SOURCE / "corpus.jsonl")
    globals_full = set(decls)
    globals_short = {n.rsplit(".", 1)[-1] for n in decls}
    for n in list(decls):
        for part in n.split("."):
            globals_short.add(part)

    bank = [json.loads(line) for line in
            (Path("research/astra/artifacts/dev_bank.jsonl")).read_text().splitlines() if line.strip()]

    c: Counter[str] = Counter()
    free_hist: Counter[int] = Counter()
    examples: list[dict] = []
    for item in bank:
        item_free = 0
        for cand in item["candidate_premises"]:
            c["statements"] += 1
            header = cand["statement"]["text"]
            bound = bound_names(header)
            typ = header.split(":", 1)[-1] if ":" in header else header
            # the part after the top-level colon, approximated by the last top-level ':'
            free = set()
            for tok in IDENT.findall(typ):
                if tok in bound or tok in KEYWORDS:
                    continue
                if tok in globals_full or tok in globals_short:
                    continue
                free.add(tok)
            free_hist[len(free)] += 1
            if free:
                c["statements_with_unresolved_identifiers"] += 1
                item_free += 1
                if len(examples) < 8:
                    examples.append({"name": cand["name"], "free": sorted(free), "header": header[:180]})
        if item_free:
            c["items_with_at_least_one_incomplete_statement"] += 1
    c["items"] = len(bank)

    report = {
        "counters": dict(c),
        "free_identifier_histogram": dict(sorted(free_hist.items())),
        "rate_statements_incomplete": c["statements_with_unresolved_identifiers"] / c["statements"],
        "rate_items_affected": c["items_with_at_least_one_incomplete_statement"] / c["items"],
        "method": "identifier is 'free' when it is neither bound by the header's own binder "
                  "groups nor equal to any mathlib declaration name or name component; such "
                  "identifiers come from ambient `variable`/`section` declarations that "
                  "corpus.jsonl does not record",
        "caveat": "conservative: any identifier that coincides with a mathlib name component is "
                  "counted as resolved, so the true incompleteness rate is HIGHER than reported",
        "examples": examples,
    }
    Path("research/audit/a8_lean/out").mkdir(parents=True, exist_ok=True)
    Path("research/audit/a8_lean/out/statement_completeness.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
