# Language Genome

Each candidate owns a closed, machine-readable fourteen-gene vector plus stable candidate,
genome, and ancestry hashes.

| Gene | What varies |
|---|---|
| alphabet | ASCII, Unicode, or hybrid symbols |
| token policy | wordlike, symbolic, role-labelled, or compact tokens |
| morphology | none, role affixes, typed affixes, structural roles |
| grammar | labelled linear, prefix/postfix, S-expression, JSON AST, graph, symbolic, hybrid |
| composition | specialized forms, generic application, typed trees, hybrid |
| types | every use, declarations, inference, refinements |
| binders | named lexical, structural IDs, locally nameless, validated extensions |
| state | flat list, typed frame, DAG, graph |
| actions | free text, typed action, verb-target-arguments, rule form |
| obligations | inline, separate, action-attached, expression-attached |
| evidence | minimal, explicit state machine, proof DAG |
| serialization | line, tree, compact code, graph |
| redundancy | explicit, medium, compressed |
| error locality | delimiters, checksums, structural markers, none |

## Seed population

The eight equal-status seeds are Structured English, current-HML compatibility syntax,
S-expression, JSON AST, typed prefix, compact symbolic, graph triples, and a role-labelled
hybrid. The HML seed imports no legacy truth semantics and receives no privileged score.

Every seed implements the same strict `render(CanonicalState) -> str` and
`parse(str) -> CanonicalState` interface. The wire validator rejects unknown or missing fields,
duplicate identities, non-finite values, malformed graph references, and non-canonical payloads.

## Mutation governance

Mutations record their parent, operator, changed genes, hypothesis, expected benefit,
soundness risk, required evaluation tier, impact class, and affected test slice. Invalid gene
dependencies are rejected before evaluation. Candidate identity commits to genes and ancestry.

The Architect can propose deterministic legal neighbours. A proposed genome is not an
executable language until a renderer and parser implement the changed phenotype; such
candidates remain `GENOME_VALIDATED_RENDERER_PENDING` and cannot enter the league.
