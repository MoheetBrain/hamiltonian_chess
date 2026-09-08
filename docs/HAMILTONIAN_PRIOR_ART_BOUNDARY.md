# Hamiltonian Chess — Prior-Art / Novelty Boundary

**Author role:** prior-art / novelty auditor.
**Date:** 2026-09-08.
**Scope:** bounded literature audit against the reset mission — *open-ended automated search over
the design of machine-facing mathematical cognition languages, evaluated through verified
long-horizon mathematical capability.*
**Method:** web search + primary-source fetch, plus the project's own research notes
(`GOAL.md`, `docs/REPRESENTATION_LANDSCAPE.md`, `docs/LANGUAGE_GENOME.md`,
`docs/CONTENT_GENOME_V1.md`, `docs/CORPUS_STRATEGY.md`, `docs/FUTURE_ENVIRONMENT_FAMILIES.md`,
`docs/CANONICAL_VNEXT_GAP_REPORT.md`, `docs/TRAINING_LANGUAGE_V0.md`,
`docs/REASONING_OPERATION_DISCOVERY.md`, `docs/codex_audit/`).
**Nothing else in this repository was modified.** No experiment, artifact or spec was touched.

> **Citation discipline.** Every work below was seen in a search result or a fetched page.
> Items I could not confirm from a primary source are marked **UNVERIFIED** and must not be
> cited until checked. At most 15 words are quoted from any source, in quotation marks with
> attribution.

---

## 0. Executive verdict

## Verdict: `NOVEL_ONLY_IN_COMBINATION`

Every *component* of the proposed research object is already published, most of it in the last
three years, and two of the components are published **in exactly this domain with exactly this
metric**. Specifically:

1. **The payoff is already demonstrated.** Redesigning a proof language for machine consumption
   produces a large, kernel-verified gain: Minilang improves pass@1 on PISA "by up to 20/29
   percentage points" over Isar (Xu et al., OOPSLA 2026, authors' abstract). A follow-up puts a
   proving agent directly on that language's **abstract syntax tree** (AoA, 2026). The claim
   "machine-facing mathematical language design is consequential for verified capability" is
   **no longer open**.
2. **The information-parity hypothesis is already demonstrated.** Meaning-preserving format
   changes swing LLM accuracy by "up to 76 accuracy points" (Sclar et al., ICLR 2024), and
   permuting premises — which cannot change the task — costs over 30% (Chen et al., ICML 2024).
   `GOAL.md` §5's "foundational representation hypothesis" is, as stated, **already answered
   yes**.
3. **Automated search over representations that improves a downstream inference objective is
   already demonstrated**, in probabilistic programming: Gorinova, Moore & Hoffman search "over
   a continuous space of parameterisations" and beat "the best fixed parameterisation"
   (ICML 2020, authors' abstract).
4. **Automated search over how state is rendered to an LLM agent, scored by that agent's
   downstream task success, is already demonstrated.** UIFormer synthesises UI-transformation
   programs under a DSL with "LLM-based iterative refinement with correctness and efficiency
   rewards", achieving 48.7–55.8% token reduction "while maintaining or improving agent
   performance" across three navigation benchmarks and five LLMs (Ran et al., 2025, authors'
   abstract). **This is the project's inner-loop mechanism, in another domain, already
   published.**
5. **Meta-evolution over representations is already demonstrated**: Medvet et al. evolve
   candidate representations "expressed with an ad hoc language" for grammatical evolution
   (GPEM 2019, authors' abstract); and O'Neill & Ryan's *Grammatical Evolution by Grammatical
   Evolution* (EuroGP 2004) evolves the grammar itself.
6. **Growing an artifact under a proof kernel to improve verified math is already demonstrated**:
   LEGO-Prover (ICLR 2024) grows a verified Isabelle skill library (miniF2F-test 45.5% → 50.0%);
   DreamProver (2026) transplants DreamCoder's wake-sleep loop into theorem proving to evolve
   "a compact set of high-level, transferable lemmas" (authors' abstract).
7. **The canonical-content-plus-many-renderings architecture is twenty years old**: OMDoc/MMT's
   content-vs-presentation split, with a declarative notation language that renders one theory
   graph into many output formats.
8. **The outer-loop machinery is off-the-shelf, down to the combination**: NAS and its
   search-space/strategy/estimation taxonomy, MAP-Elites, POET, novelty search, successive
   halving/Hyperband, PBT, LLM-driven evolution under automated verifiers (FunSearch,
   AlphaEvolve, ELM, Voyager), evolutionary search over an agent's own state representation with
   fitness = agent performance (Whiteson & Stone, JMLR 2006) — and even **quality-diversity
   crossed with outer design search** has been published as a pairing (Schneider et al.,
   AutoML 2022).

**What survives.** No published work searches over the design of a *machine-facing mathematical
state-presentation language* — ontology, state topology, grammar, morphology, binding, action
granularity and reasoning workspace jointly — under **enforced information parity**, scored by
**verified long-horizon** mathematical capability. The nearest works sit on different sides of
the seam and none crosses it: Minilang has the domain, the object and the verified metric but
**one hand-designed point and no search**; UIFormer has the search over a *rendered observation*
scored by agent success but **compresses an existing representation, in UI navigation, with no
verifier and short episodes**; Gorinova et al. have the search and the "same content, different
expression" discipline but **a single hand-specified transform family, in statistics, scored by
sampler efficiency**; DreamCoder/LILO/DreamProver search a **primitive set** inside a fixed
formalism, and their solver never observes a state rendered through the searched artifact.
A hostile reviewer will compose the first three in one sentence — *"Minilang shows the language
matters, Gorinova and UIFormer show you can automate the search, this is the cross-product"* —
and Medvet et al. or GE² supplies the evolutionary mechanism if they want a fourth. That
composition is the argument the project must survive, and it can only be survived **by a result,
not by an architecture**.

Therefore: the research *object* is defensible, but only as a combination, and only if the
project (a) concedes items 1–8 explicitly and loudly, (b) locates its claim entirely in the
**search + parity + horizon** axes, and (c) produces the specific empirical result in §5. A
project that publishes the architecture without that result is `LARGELY_COVERED_BY_PRIOR_ART`.

**One fragility that decides the verdict.** If the implemented "language variation" turns out to
be dominated by changes to the *primitive/abstraction set*, the claim collapses into
DreamCoder / LILO / DreamProver outright. The genome must demonstrably vary grammar, morphology,
binding, state topology and action granularity **with the primitive set held constant** in at
least one pre-registered ablation. Without that ablation the verdict degrades to
`LARGELY_COVERED_BY_PRIOR_ART`.

**Verdicts I rejected, and why.**
`NOVEL_OBJECT_SUPPORTED` is not defensible: too many of the load-bearing premises are already
in print, including in the exact domain. `LARGELY_COVERED_BY_PRIOR_ART` is too harsh: nobody
has crossed representation-variation with reasoning-depth-variation, nobody has run a population
search over formal proof-state presentation, and nobody has enforced information parity across
a searched population.

---

## 1. Area-by-area boundary table

| # | Area | Strongest prior work | What it establishes | What it does **not** cover |
|---|---|---|---|---|
| 1 | Formal proof / tactic languages | **Xu, Wang, Wang, Li, Watt — "A Minimalist Proof Language for Neural Theorem Proving over Isabelle/HOL", PACMPL/OOPSLA 2026** ([arXiv:2507.18885](https://arxiv.org/abs/2507.18885), [DOI](https://dl.acm.org/doi/10.1145/3798275)) | A proof language redesigned *for machines* (10 operations, ATP delegation), with ~340K Isar proofs translated at ~85%, lifts pass@1 on PISA to 69.1% and pass@8 to 79.2% — "improving the pass@1 success rate…by up to 20/29 percentage points". **The payoff claim is settled.** | No search: one hand-designed language, no population, no variation over design axes, no ontology/topology/binding sweep. No length-stratified curve. Gain confounds language redesign with ATP delegation (whether an ablation separates them is **UNVERIFIED** — the PDF did not extract). |
| 1b | Proof agent state representation | **Xu, Ong Jun Leang, Wang, Li, Li, Ong, Watt — "Theorem-Proving Agent over Abstract Syntax Tree of Redesigned Language" (AoA)**, [arXiv:2607.16372](https://arxiv.org/abs/2607.16372) (17 Jul 2026) | An agent that reads/edits Minilang's **AST as JSON** rather than concrete syntax; states fused into the proof tree. 99.6% on MiniF2F, 89.2% on NTP4VC-Pearl, 2.3–4.7× lower API cost. Notes "harder proof goals can amplify AoA's advantage". | Hand-designed; no search over AST/ontology design. No explicit representation × proof-depth interaction term (difficulty-budget curves only). |
| 1c | Proof-state serialisation as an unexamined given | Polu & Sutskever, GPT-f ([arXiv:2009.03393](https://arxiv.org/abs/2009.03393)); Yang et al., **LeanDojo**, NeurIPS 2023 D&B ([arXiv:2306.15626](https://arxiv.org/abs/2306.15626)); Wenzel, [Isabelle/Isar framework](https://wwwbroy.in.tum.de/~wenzelm/papers/isar-framework.pdf) | Proof states are serialised and fed to models at scale; LeanDojo's ablations are on the **retriever**, not the rendering. Isar's stated design target is *human* readability. | **No published work treats proof-state presentation as a design space and searches it.** This is the clearest open seam found in this audit. |
| 1d | Evolution *inside* theorem proving | ProofEvolve, [arXiv:2608.26334](https://arxiv.org/abs/2608.26334) | LLM-proposed decompositions/repairs/recombinations evolve **proof DAGs** under the Lean kernel. | The language and representation are **fixed**; only proof objects evolve. Confirms "evolution + verifier" is standard machinery, not a contribution. |
| 2 | Mathematical interchange / semantic formats | **MMT** (Rabe, [system description](https://kwarc.info/people/frabe/Research/rabe_mmtsys_20.pdf)); **OMDoc** ([overview](https://en.wikipedia.org/wiki/OMDoc)); Kohlhase & Rabe, "Semantics of OpenMath and MathML3", *Math. in Computer Science* 2012 ([DOI](https://link.springer.com/article/10.1007/s11786-012-0113-x)); [OpenMath CDs](https://openmath.org/cdgroups/); Math-in-the-Middle, [arXiv:1603.06424](https://arxiv.org/abs/1603.06424) | The **content-vs-presentation split with a parameterised notation layer already exists** and predates this project by ~20 years. MMT has a declarative notation language that renders one theory graph into many output formats; OpenMath CDs are a standardised symbol ontology with roles (binder, application, attribution). | **Zero performance claims.** No objective function over notations, no search, no evaluation against any reasoner. Notations are chosen by hand for human/system output. |
| 3 | MiniLang / AoA "compact language for machine reasoning" | See rows 1 and 1b. Also **Beiser, Penz, Musliu — "Intermediate Languages Matter", [arXiv:2509.04083](https://arxiv.org/abs/2509.04083)** (KG-NeSy @ SEMANTiCS 2025) | Choice among four *formal target languages* measurably changes neurosymbolic reasoning across 3 datasets and 7 LLMs; framed as a previously overlooked factor. | Compares a handful of existing languages; no search, no design-space parameterisation, no depth stratification. |
| 4 | Symbolic-computation representations designed by humans for machines | Wolfram Language ([principles](https://www.wolfram.com/language/principles/)); SymPy `Basic`/`Expr` ([docs](https://docs.sympy.org/latest/tutorials/intro-tutorial/manipulation.html), maintainer [retrospective](https://oscarbenjamin.github.io/blog/czi/post1.html)); Bezanson, Edelman, Karpinski & Shah, "Julia: A Fresh Approach to Numerical Computing", *SIAM Review* 59(1), 2017 ([DOI](https://dl.acm.org/doi/10.1137/141000671)) | Documented, sometimes peer-reviewed, arguments that representation design determines machine capability — including a SymPy core maintainer describing automatic evaluation baked into `Basic`/`Expr` as "a fundamental design flaw". | Advocacy and engineering retrospective, not controlled study. No counterfactual, no search, no reasoning metric. **JAX/jaxpr: UNVERIFIED — no primary source obtained; do not cite.** |
| 5 | Probabilistic-programming DSL design | **Gorinova, Moore & Hoffman — "Automatic Reparameterisation of Probabilistic Programs", ICML 2020** ([PMLR v119](https://proceedings.mlr.press/v119/gorinova20a/gorinova20a.pdf), [arXiv:1906.03028](https://arxiv.org/abs/1906.03028)) | The other half of the pincer. "the performance of inference algorithms can be dramatically affected by the parameterisation used"; they automate the transforms and give "a novel variational formulation that searches over a continuous space of parameterisations", yielding samplers better than "the best fixed parameterisation". **Automated search over expressions of identical content, scored by downstream inference quality, beating the best hand design.** | Hand-specified, continuous, semantics-preserving transform family (non-centring and relatives) — not grammar, ontology, state topology, binding, morphology or action granularity. Not open-ended, no population, no agent, no verifier, no long-horizon task. Statistics, not mathematics. |
| 5b | Stan | Carpenter et al., "Stan: A Probabilistic Programming Language", *JSS* 76(1), 2017 ([JSS](https://www.jstatsoft.org/v076/i01)) | The canonical citation for the field whose folklore is "reparameterise or your sampler dies". | **UNVERIFIED** that this paper itself measures reparameterisation effects. Do not attribute the non-centred-parameterisation result to it without reading the PDF. |
| 6 | Emergent communication / language emergence in MARL | Foerster, Assael, de Freitas & Whiteson, NIPS 2016 ([proceedings](https://proceedings.neurips.cc/paper/2016/hash/c7635bfd99248a2cdef8249ef7bfbef4-Abstract.html)); Lazaridou, Peysakhovich & Baroni, ICLR 2017 ([dblp](https://dblp.org/rec/conf/iclr/LazaridouPB17.html)); **Kottur, Moura, Lee & Batra, "Natural Language Does Not Emerge 'Naturally' in Multi-Agent Dialog", EMNLP 2017** ([ACL Anthology](https://aclanthology.org/D17-1321/), best short paper); Lazaridou & Baroni survey ([arXiv:2006.02419](https://arxiv.org/abs/2006.02419)) | Populations of agents invent communication protocols under task reward; protocols are effective but "decidedly not interpretable or compositional" (Kottur et al.). **"Agents invent symbols" has been done since 2016 and its known failure mode is exactly degenerate, non-compositional codes.** | Toy referential/dialog games. No formal content, no verifier, no mathematics, no long-horizon capability, and — crucially — **no external ground truth**: the emergent code is scored by the agents' own coordination success. |
| 7 | Program synthesis, library learning, DSL learning | **Ellis, Wong, Nye, Sablé-Meyer, Morales, Hewitt, Cary, Solar-Lezama & Tenenbaum, DreamCoder, PLDI 2021** ([arXiv:2006.08381](https://arxiv.org/abs/2006.08381), [DOI](https://dl.acm.org/doi/10.1145/3453483.3454080)); LAPS, ICML 2021 ([arXiv:2106.11053](https://arxiv.org/abs/2106.11053)); Stitch, POPL 2023 ([arXiv:2211.16605](https://arxiv.org/abs/2211.16605)); babble, POPL 2023 ([arXiv:2212.04596](https://arxiv.org/abs/2212.04596)); **LILO, ICLR 2024** ([arXiv:2310.19791](https://arxiv.org/abs/2310.19791)); Lake, Salakhutdinov & Tenenbaum, *Science* 350(6266), 2015 ([DOI](https://www.science.org/doi/10.1126/science.aab3050)) | An automated wake-sleep loop grows a **domain vocabulary** and measurably improves downstream solving. DreamCoder markets itself in exactly the project's language — its abstract speaks of "powerful languages for thinking about problems" and of building expertise by "creating programming languages for expressing domain concepts". LILO adds LLM synthesis plus AutoDoc naming/documentation of abstractions. | **Decisive distinction, confirmed against the full text: DreamCoder searches the *library*, never the syntax.** The base formalism — "polymorphically typed λ-calculus expressions" — is invariant; the sleep phase adds named λ-abstractions to the primitive set and touches no grammar rule, notation, serialization or binding discipline. **The recognition model observes the task (I/O pairs, images), never a state rendered through the artifact under search.** Single monotone lineage hill-climbing a compression objective — no population, no diversity archive. No verifier-owned truth, no long-horizon proof. |
| 7b | Library learning under a proof kernel (verified math) | **LEGO-Prover, ICLR 2024 (Oral)** ([arXiv:2310.00656](https://arxiv.org/abs/2310.00656)); **DreamProver** ([arXiv:2604.26311](https://arxiv.org/abs/2604.26311), 2026); TroVE, ICML 2024 ([arXiv:2401.12869](https://arxiv.org/abs/2401.12869)) | **Growing an artifact under a proof kernel to raise verified math capability already exists.** LEGO-Prover grows a verified Isabelle skill library (miniF2F-test 45.5% → 50.0%, 20,000+ skills). DreamProver runs wake-sleep over theorem proving, evolving "a compact set of high-level, transferable lemmas". | The artifact is a **lemma/skill library inside fixed Isabelle or Lean syntax**. Zero language design: no ontology, grammar, binding, state topology, morphology or workspace variation. *(Whether DreamProver's fitness is kernel-owned is stated only implicitly in its abstract — see §7.)* |
| 7c | **Automated search over how state is rendered to an agent** | **Ran, Gong, Guo, Wu, Cao, Lu, Zhang, Zeng, Cao, Yao, Deng, Yang & Xie — "From User Interface to Agent Interface: Efficiency Optimization of UI Representations for LLM Agents" (UIFormer)**, [arXiv:2512.13438](https://arxiv.org/abs/2512.13438) (Dec 2025). Also: Value Driven Representation ([arXiv:2004.01223](https://arxiv.org/abs/2004.01223)) | **The sharpest mechanistic match found in this audit.** UIFormer "synthesizes UI transformation programs", restricts the program space with a DSL, and runs "LLM-based iterative refinement with correctness and efficiency rewards" — i.e. **automated search over the representation the agent observes, scored by the agent's downstream task success** (48.7–55.8% token reduction "while maintaining or improving agent performance", 3 benchmarks × 5 LLMs, deployed at WeChat). | It **transforms/compresses an existing representation** (a UI tree) rather than designing ontology, grammar, binding or state topology. Iterative refinement, not a population or open-ended search. UI navigation, not mathematics. **No verifier owns truth**; short episodes, no long-horizon axis; no information-parity constraint (token reduction is explicitly an objective, so information is deliberately *not* held constant). |
| 7d | Grammar-level and DSL-level meta-search | **O'Neill & Ryan, "Grammatical Evolution by Grammatical Evolution: The Evolution of Grammar and Genetic Code", EuroGP 2004, LNCS 3003:138–149** ([Springer](https://link.springer.com/chapter/10.1007/978-3-540-24650-3_13)); **Medvet, Bartoli, De Lorenzo & Tarlao, *GPEM* 20:37–65, 2019** ([DOI](https://link.springer.com/article/10.1007/s10710-018-9327-2)); **Shi et al., AutoDSL, ACL 2024** ([ACL](https://aclanthology.org/2024.acl-long.659/)); autoBOT, *Machine Learning* 2021 ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8550026/)); AutoML-Zero, ICML 2020 ([PMLR v119](https://proceedings.mlr.press/v119/real20a.html)) | **"Evolve the grammar, not just the solution" is ~22-year-old prior art.** Medvet et al. run meta-evolution whose individuals are candidate representations expressed in a purpose-built language. AutoDSL automates DSL constraint design from corpora to improve LLM procedural planning. autoBOT is literally described as evolution at the representation level. | GE² : the evolved grammar constrains the *generator's solution space*; nothing is rendered to an observing solver; toy symbolic regression. Medvet et al.: fitness is **intrinsic** representation properties (redundancy, uniformity of redundancy, locality), **not** downstream capability. AutoDSL: experimental protocols, corpus-statistical, no verifier, no math, no long-horizon metric. AutoML-Zero/autoBOT/GAVEL: evolve artifacts *expressed in* a fixed DSL. |
| 7e | LLM-driven evolution under a verifier | FunSearch, *Nature* 625:468–475, 2024 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/38096900/)); AlphaEvolve ([arXiv:2506.13131](https://arxiv.org/abs/2506.13131)); ELM ([arXiv:2206.08896](https://arxiv.org/abs/2206.08896)); Voyager ([arXiv:2305.16291](https://arxiv.org/abs/2305.16291)) | LLM-as-mutation-operator plus an automated evaluator, sometimes with MAP-Elites, is now commodity and has produced real mathematical results. Voyager's "ever-growing skill library of executable code" is the canonical example of the thing the project says it is *not*. | All evolve **artifacts inside an ordinary fixed language** (Python, JavaScript). The language is a constant in every one of them. |
| 7f | Evaluation threat to this whole literature | **Berlot-Attwell et al., "Library Learning Doesn't: The Curious Case of the Single-Use 'Library'", MATH-AI @ NeurIPS 2024** ([arXiv:2410.20274](https://arxiv.org/abs/2410.20274)) | Finds function reuse is extremely infrequent in LEGO-Prover and TroVE on miniF2F/MATH, and that **self-correction and self-consistency — not the learned artifact — drive the reported gains**. | Not about notation. **But it hands a reviewer a ready-made attack**: a compute-matched, sampling-matched control across language variants is not optional for this project. |
| 8 | Search methodology (NAS, QD, open-endedness) | **Whiteson & Stone, "Evolutionary Function Approximation for Reinforcement Learning", *JMLR* 7:877–917, 2006** ([JMLR](https://jmlr.org/papers/v7/whiteson06a.html)); Elsken, Metzen & Hutter, *JMLR* 20(55), 2019 ([JMLR](https://jmlr.org/papers/v20/18-598.html)); Zoph & Le, ICLR 2017 ([arXiv:1611.01578](https://arxiv.org/abs/1611.01578)); Jamieson & Talwalkar, AISTATS 2016 ([PMLR 51](https://proceedings.mlr.press/v51/jamieson16.html)); Li et al., Hyperband, *JMLR* 18(185) ([JMLR](https://jmlr.org/papers/v18/16-558.html)); Mouret & Clune, MAP-Elites ([arXiv:1504.04909](https://arxiv.org/abs/1504.04909)); Cully, Clune, Tarapore & Mouret, *Nature* 521:503–507, 2015 ([Nature](https://www.nature.com/articles/nature14422)); POET ([arXiv:1901.01753](https://arxiv.org/abs/1901.01753), [Enhanced POET, ICML 2020](https://proceedings.mlr.press/v119/wang20l.html)); Lehman & Stanley, *Evolutionary Computation* 19(2):189–223, 2011 ([MIT Press](https://direct.mit.edu/evco/article-abstract/19/2/189/1365/)); PBT ([arXiv:1711.09846](https://arxiv.org/abs/1711.09846)); **Schneider et al., "Quality Diversity for Neural Architecture Search"-style pairing, AutoML Conf 2022** ([arXiv:2208.00204](https://arxiv.org/abs/2208.00204)); AutoRL survey ([arXiv:2201.05000](https://arxiv.org/abs/2201.05000)) | **Evolutionary search over an agent's own state representation, with fitness = the agent's task performance, is twenty years old.** Elsken et al. even name the exact *search space / search strategy / performance-estimation* decomposition the project would use. **QD crossed with outer design search is itself already published**, so even the combination is not novel. | Non-symbolic representations (function approximators, tilings, architectures) for small RL or vision domains; no language, no grammar, no ontology, no verifier, no LLM. **The novelty cannot be the search algorithm, and the project must say so in its first paragraph.** *Cite MAP-Elites as an arXiv preprint (never peer-reviewed) and Stanley/Lehman's open-endedness essay as a position piece, not evidence.* |
| 9 | Prompt/representation format effects on LLM reasoning | **Sclar, Choi, Tsvetkov & Suhr, ICLR 2024** ([arXiv:2310.11324](https://arxiv.org/abs/2310.11324)); **Chen, Chi, Wang & Zhou, "Premise Order Matters in Reasoning with LLMs", ICML 2024** ([PMLR v235](https://proceedings.mlr.press/v235/chen24i.html), [arXiv:2402.08939](https://arxiv.org/abs/2402.08939)); He et al. ([arXiv:2411.10541](https://arxiv.org/abs/2411.10541)); Tam et al., EMNLP 2024 Industry ([ACL](https://aclanthology.org/2024.emnlp-industry.91/)) | Sclar: "meaning-preserving design choices" alone give "performance differences of up to 76 accuracy points" on LLaMA-2-13B, and FormatSpread is itself **an automated search over a format space**. Chen et al.: reordering premises — an information-preserving change — costs >30%. Tam et al.: format restriction degrades reasoning specifically. **`GOAL.md` §5's foundational hypothesis is already answered.** | Almost entirely **single-turn**: classification, QA, code translation, one-shot generation. No formal/verified setting, no proof state, no depth-stratified interaction. Sclar frames format as a **robustness bug**, not a design space — which a reviewer will turn against the project ("your effect is format noise"). He et al. report GPT-4 is *more robust*, which cuts against the thesis on the capability axis. |
| 9b | Reasoning workspace | Nye et al., Scratchpads ([arXiv:2112.00114](https://arxiv.org/abs/2112.00114)); Wei et al., CoT, NeurIPS 2022 ([arXiv:2201.11903](https://arxiv.org/abs/2201.11903)); Gao et al., PAL, ICML 2023 ([PMLR v202](https://proceedings.mlr.press/v202/gao23f.html)); Chen et al., PoT, TMLR 2023 ([arXiv:2211.12588](https://arxiv.org/abs/2211.12588)); Li, Liu, Zhou & Ma, ICLR 2024 ([arXiv:2402.12875](https://arxiv.org/abs/2402.12875)); Merrill & Sabharwal, ICLR 2024 ([arXiv:2310.07923](https://arxiv.org/abs/2310.07923)); Hao et al., Coconut ([arXiv:2412.06769](https://arxiv.org/abs/2412.06769)) | An external workspace is a first-class capability lever; code beats prose for math (PoT: ~12% over CoT); and **formally, expressive power is monotone increasing in the number of workspace steps**. Coconut shows the workspace need not even be discrete text. | All are **presence-vs-absence or one-design-vs-one-design**, never a searched population. The theoretical results settle the *steps* axis, so "more workspace helps at depth" is not claimable as a finding. |
| 9c | Automated search over task presentation | **Fernando, Banarse, Michalewski, Osindero & Rocktäschel, Promptbreeder, ICML 2024** ([arXiv:2309.16797](https://arxiv.org/abs/2309.16797), [PMLR v235](https://proceedings.mlr.press/v235/fernando24a.html)); **Khattab et al., DSPy, ICLR 2024** ([arXiv:2310.03714](https://arxiv.org/abs/2310.03714)); GEPA ([arXiv:2507.19457](https://arxiv.org/abs/2507.19457)) | Evolutionary and reflective search over *how a task is presented to an LLM*, with fitness = benchmark accuracy, beating hand-designed CoT/Plan-and-Solve. Self-referential mutation operators included. | Searches **English prompt strings and pipeline parameters**, not a formal language's ontology, grammar, binding or state topology. No verifier, no canonical substrate, no information-parity constraint, no long-horizon proof. |
| 10 | Tokenizer / representation co-design | Singh & Strouse ([arXiv:2402.14903](https://arxiv.org/abs/2402.14903)); Zheng et al. ([arXiv:2506.19004](https://arxiv.org/abs/2506.19004)); **McLeish et al., "Transformers Can Do Arithmetic with the Right Embeddings", NeurIPS 2024** ([arXiv:2405.17399](https://arxiv.org/abs/2405.17399)); Lee et al. ([arXiv:2307.03381](https://arxiv.org/abs/2307.03381)); ByT5, TACL 2022 ([ACL](https://aclanthology.org/2022.tacl-1.17/)); MEGABYTE ([arXiv:2305.07185](https://arxiv.org/abs/2305.07185)) | Representation change with **zero weight change** buys +33% on large-number arithmetic (Zheng et al.); Abacus embeddings generalise to 120-digit addition; reversing digit order changes not just accuracy but **sample efficiency** (Lee et al.: a phase transition between 1000–4000 samples). | Single-operation arithmetic; the "length" axis is **input width, not inference depth** — equivocating between them is the first thing a reviewer will catch. **No verified byte-vs-BPE math-reasoning head-to-head was found; treat that as an open gap, not an established result.** |

---

## 2. WHAT WOULD NOT BE NOVEL

The project must **not** make any of the following claims. Each is already in print, with a
citation that a reviewer will produce in one search.

1. **"We designed a machine-facing mathematical language / DSL."** — Minilang, OOPSLA 2026.
2. **"We present the proof state to the model as an AST rather than text."** — AoA, 2026.
3. **"Agents invent their own symbols / a private language."** — Foerster 2016, Lazaridou 2017;
   and Kottur et al. 2017 already established the failure mode.
4. **"Representation/format matters for LLM reasoning."** — Sclar et al., ICLR 2024 (76 points).
5. **"The same mathematical information, organised differently, changes AI reasoning."** —
   this is `GOAL.md` §5 verbatim, and it is **Chen et al., ICML 2024** (premise order, >30%).
   The project must stop treating this as its open question.
6. **"A canonical semantic core with multiple reversible renderings."** — OMDoc/MMT, ~2005.
   Re-deriving it is engineering, not contribution. Concede this to KWARC explicitly.
7. **"Learning a library/vocabulary of abstractions improves solving."** — DreamCoder, PLDI 2021;
   LAPS, ICML 2021; Stitch/babble, POPL 2023; LILO, ICLR 2024.
8. **"We grow a verified lemma/skill library under a proof kernel and prove more theorems."** —
   LEGO-Prover, ICLR 2024; DreamProver, 2026; TroVE, ICML 2024. And note that
   Berlot-Attwell et al. (2024) already argue those gains may come from self-correction and
   extra sampling rather than the artifact.
9. **"Automated search over how content is expressed improves downstream performance."** —
   Gorinova et al., ICML 2020.
10. **"We automatically search over how the state is rendered to the agent, scored by the
    agent's downstream success."** — UIFormer, 2025. This is the project's inner-loop mechanism
    and it must be cited proactively, not discovered by a reviewer.
11. **"Meta-evolution over candidate representations" / "we evolve the grammar."** —
    Medvet et al., GPEM 2019; O'Neill & Ryan, GE², EuroGP 2004.
12. **"Evolutionary search over the agent's own state representation, fitness = agent
    performance."** — Whiteson & Stone, JMLR 2006.
13. **"Evolving how the task is presented to an LLM improves reasoning."** — Promptbreeder,
    ICML 2024; DSPy, ICLR 2024; GEPA, 2025. FormatSpread (Sclar et al.) is *itself* an automated
    search over a format space.
14. **"We use a population / quality-diversity archive / successive halving / MAP-Elites /
    open-ended search"** — commodity — **and even "quality diversity applied to an outer design
    search"** — Schneider et al., AutoML 2022. The novelty can never be the search algorithm.
15. **"We use a formal kernel as ground truth and evolve under it."** — FunSearch, AlphaEvolve,
    ProofEvolve, DreamProver.
16. **"Compact encodings beat verbose JSON for LLMs."** — the format literature, repeatedly.
17. **"A reasoning workspace/scratchpad helps more on longer problems."** — Nye et al. 2021
    empirically, and Li et al. / Merrill & Sabharwal (ICLR 2024) *formally*.
18. **"Language advantage grows with reasoning horizon" — in its naive form.** See §5: under
    independent per-step errors this is arithmetic, and Sinha et al. (ICLR 2026) already state
    that "marginal gains in single-step accuracy can compound into exponential improvements"
    in executable task length.
19. **"Tokenization/notation affects mathematical ability."** — Singh & Strouse; McLeish et al.;
    Lee et al.
20. **"We built an inner reasoning MDP over verified trajectories where a verifier owns truth."**
    — that is the standard formulation of neural theorem proving (GPT-f, LeanDojo, HTPS).

---

## 3. THE NARROWEST DEFENSIBLE CLAIM

Phrased so that every clause is either frozen by protocol or measured, and so that a hostile
reviewer has nothing left to attack except the data:

> **Under a frozen canonical mathematical substrate, a frozen external verifier, a frozen task
> distribution, a frozen solver checkpoint, a matched compute and sampling budget, and enforced
> semantic and visible-information parity between candidates, an automated population search over
> the *design* of the machine-facing language in which proof states and actions are presented to
> the solver — varying ontology, state topology, grammar, morphology, binding, action granularity
> and reasoning workspace **with the primitive/abstraction set held constant** — discovers
> presentations that (i) are not Pareto-dominated by any of
> the N pre-registered hand-designed baselines, including the strongest published machine-facing
> proof language, and (ii) exhibit a **representation × horizon interaction that is not
> accounted for by independent per-step error compounding** — operationalised as a
> pre-registered change in the *ranking* of representations between short and long horizons, or
> a pre-registered widening of the *per-step* accuracy gap with depth — replicated across at
> least two structurally distinct solver families and at least three seeds.**

Notes on why each clause is load-bearing:

- *"enforced… information parity"* — this is what separates the claim from Minilang, whose gain
  is partly a change in what work is delegated to Sledgehammer, and from every prompt-format
  paper, which does not control information content at all. It is the project's single strongest
  methodological differentiator, and `GOAL.md` §13 already specifies it.
- *"population search over the design"* — separates from Minilang/AoA (one point) and Beiser et
  al. (four off-the-shelf languages).
- *"not Pareto-dominated by… the strongest published machine-facing proof language"* — the
  baseline **must** include a Minilang-class arm. Without it the result is unpublishable: the
  reviewer's first question is "did search beat the expert?"
- *"not accounted for by independent per-step error compounding"* — see §5. Without this clause
  the horizon claim is arithmetic.
- *"with the primitive/abstraction set held constant"* — separates from DreamCoder, LILO, LAPS,
  Stitch, LEGO-Prover, TroVE and DreamProver in one clause. Without it the project is library
  learning with extra steps.
- *"matched compute and sampling budget"* — answers Berlot-Attwell et al. (2024), who showed that
  gains in this literature can come from self-correction and extra sampling rather than the
  artifact.
- *"at least two structurally distinct solver families"* — `GOAL.md` §16's `RSTAR_0_1` bar,
  and the answer to "this is model-specific format noise".

**What the project may additionally claim, honestly, even on a null result:** a **negative**
result is publishable here precisely because the positive result is assumed by the field.
"An open-ended search over N language-design axes, under information parity, on verified Lean
states, fails to beat strong generic representations for solver family F at budget B" is a real
contribution given Minilang's headline — it bounds where language design pays.

---

## 4. NEAREST COMPETITOR

**Xu, Wang, Wang, Li & Watt, "A Minimalist Proof Language for Neural Theorem Proving over
Isabelle/HOL", PACMPL / OOPSLA 2026 — [arXiv:2507.18885](https://arxiv.org/abs/2507.18885) —
together with its 2026 successor "Theorem-Proving Agent over Abstract Syntax Tree of Redesigned
Language" (AoA), [arXiv:2607.16372](https://arxiv.org/abs/2607.16372).**

This is the single closest work: same domain (mechanised mathematics), same object (the language
the machine reasons *in*), same ground truth (a proof kernel), same headline metric (verified
success rate). It already carries the sentence this project wanted to write — that the design of
a machine-facing mathematical language is a first-order determinant of verified capability — and
it carries it with double-digit gains. AoA then does the thing the owner explicitly flagged as
non-novel: it puts the agent on the **AST** of that language as its state representation.

**Exactly how a Hamiltonian Chess result would differ:**

| Axis | Minilang / AoA | Hamiltonian Chess (if it delivers) |
|---|---|---|
| How the language is obtained | Hand-designed by expert PL researchers from an informal-proof analysis | Discovered by an automated population search over a declared genome of design axes |
| Number of designs evaluated | 1 (plus the Isar baseline) | A population, with a quality-diversity archive over behavioural descriptors |
| Information control | Not controlled — Minilang delegates fine-grained steps to ATPs, so language redesign and automation delegation are entangled | **Semantic + visible-information parity enforced per `GOAL.md` §13**; only the organisation of identical information varies |
| Design axes varied | Operation set / granularity | Ontology, state topology, grammar, morphology, binding, action granularity, reasoning workspace — jointly |
| Reported dependence on horizon | None (aggregate pass@k; AoA reports difficulty-budget curves only, noting harder goals can amplify its advantage) | The **representation × horizon interaction term**, pre-registered, with a metric that is honest about compounding |
| Falsifiability | A positive result | Pre-registered stopping rules and explicitly allowed negative outcomes (`GOAL.md` §20) |

The competitor's weakness the project should exploit: **Minilang cannot tell you whether its gain
came from the language or from Sledgehammer**, and it evaluates one point. The project's
weakness the competitor exposes: **the project has never scored two representations against a
solver** (`docs/WHAT_WORKS_WHAT_DOESNT.md`: "No representation has ever been scored against a
Solver"), while Minilang has already shipped a verified 20–29 point result. Any framing that
implies the field has not noticed language design will be fatal.

### 4.1 Closest on *mechanism* (a different, equally dangerous competitor)

**Ran et al., "From User Interface to Agent Interface: Efficiency Optimization of UI
Representations for LLM Agents" (UIFormer) — [arXiv:2512.13438](https://arxiv.org/abs/2512.13438).**

Minilang is nearest on *object and metric*; UIFormer is nearest on *mechanism*. It is the only
verified work found that **automatically searches over how state is rendered to an LLM agent and
scores candidates by that agent's downstream task success**. A well-read reviewer will raise it,
so the project should cite it first rather than be caught by it. The differences to state
explicitly: UIFormer *compresses an existing* representation rather than designing an ontology,
grammar, binding discipline or state topology; it uses LLM iterative refinement, not a population
or open-ended search; token reduction is an explicit objective, so it deliberately **does not**
hold information constant — the exact opposite of `GOAL.md` §13; there is no verifier owning
truth; and its episodes are short UI navigations, not long-horizon proofs.

### 4.2 Closest on *marketing* — the one that will be confused with this project

**DreamCoder (Ellis et al., PLDI 2021).** Not because it does what the project does — a full-text
check confirms it does not — but because its abstract *says* it does: it speaks of building
expertise by "creating programming languages for expressing domain concepts". A reviewer skimming
the abstract will conclude the project is DreamCoder with a proof assistant attached, **and
DreamProver has already attached one**. The rebuttal must be technical and appear in the first
paragraph, not in related work: DreamCoder's λ-calculus formalism is invariant, its search is a
single-lineage compression hill-climb rather than a population, and its recognition model
observes the *task*, never a state rendered through the artifact under search.

**Runner-up competitors, ranked:** (3) Gorinova, Moore & Hoffman, ICML 2020 — automated search
over expressions of identical content; (4) Sclar et al., ICLR 2024 — the information-preserving
format effect *and* an automated format search; (5) LEGO-Prover / DreamProver — artifact growth
under a proof kernel for verified math; (6) Medvet et al., GPEM 2019 and O'Neill & Ryan, GE²,
EuroGP 2004 — meta-evolution over representations and grammars.

---

## 5. WHAT WOULD MAKE IT INDISPUTABLE — and an assessment of the horizon thesis

### 5.1 Is "language advantage grows with reasoning horizon" itself novel?

**Partially, and much less than the owner appears to believe.** Decompose it, because the three
sub-claims have very different status:

**(a) Representation shifts per-step accuracy — ESTABLISHED, not novel.**
Sclar et al. (76 points), Chen et al. (>30% from premise order), Tam et al., PoT/PAL (~12%),
Minilang (20–29 points, verified), plus the whole tokenizer literature.

**(b) A per-step edge compounds into a growing horizon advantage — ESTABLISHED, and partly a
tautology.**
Sinha, Arun, Goel, Staab & Geiping, "The Illusion of Diminishing Returns: Measuring Long Horizon
Execution in LLMs", [arXiv:2509.09677](https://arxiv.org/abs/2509.09677) (ICLR 2026), state that
"marginal gains in single-step accuracy can compound into exponential improvements" in the length
of tasks a model can complete. Under independent per-step errors this is just p^n versus q^n —
**arithmetic, not a finding.** A hostile reviewer will say so in the first paragraph of the
review.

Worse, **the claim is metric-dependent, and one common metric makes it false.** With per-step
accuracies p > q, the *absolute* end-to-end accuracy gap p^n − q^n is unimodal in n: it rises,
peaks, and then collapses to ~0 as both terms go to zero. "The gap widens with horizon" is true
for *horizon-at-fixed-success-rate* and for *log-odds*, and **false** for absolute accuracy
difference at large fixed n. If the project does not pre-register the metric, a reviewer will
choose the one whose curve goes down.

**(c) A directly measured representation × horizon interaction — NOT ESTABLISHED. This is the
seam.**
The literature is cleanly bipartite and nobody crosses it:
- Papers that vary **representation** hold depth roughly fixed: Sclar, Chen, He, Tam, PAL, PoT,
  Beiser, Minilang, and all of the tokenizer work.
- Papers that vary **depth** hold representation fixed: Dziri et al., *Faith and Fate*, NeurIPS
  2023 ([arXiv:2305.18654](https://arxiv.org/abs/2305.18654)); Ye, Xu, Li & Allen-Zhu, *Physics
  of Language Models 2.1*, ICLR 2025 ([arXiv:2407.20311](https://arxiv.org/abs/2407.20311));
  Sinha et al.

The closest partial support, all of which must be cited rather than ignored:
- **Nye et al. 2021** — workspace benefit shown across a ladder of increasing step count. But it
  is presence-vs-absence, not design-vs-design.
- **Li, Liu, Zhou & Ma (ICLR 2024)** and **Merrill & Sabharwal (ICLR 2024)** — *formally*,
  expressive power is monotone in workspace steps. This settles the workspace axis theoretically.
- **Tam et al. (EMNLP 2024 Industry)** — format restriction degrades **reasoning tasks
  specifically**: a task-type interaction, the nearest published cousin.
- **McLeish et al. (NeurIPS 2024)** — representation change unlocks 120-digit generalisation, but
  the length is *input width*, not *inference depth*.
- **Yang et al., "Can Structured Templates Facilitate LLMs in Tackling Harder Tasks?"**
  ([arXiv:2508.19069](https://arxiv.org/abs/2508.19069)) — structured solution templates help
  "especially on harder problems"; difficulty, not proof depth, and templates are hand-designed.
- **AoA (2026)** — "harder proof goals can amplify AoA's advantage", which is the *closest
  existing statement of the owner's thesis in the target domain*. It is a remark on a
  difficulty-budget curve, not a measured interaction term — but it means the project cannot
  claim to have been first to suspect it.

**Verdict on the horizon thesis:** as stated, it is **not novel and partly tautological**. As a
*measured interaction term under information parity in a verified setting, with a
pre-registered metric and an explicit compounding null model*, it is **unmeasured and
defensible** — and it is the strongest single card the project holds.

### 5.2 The specific results that would make the contribution indisputable

Ranked by how hard they are to dismiss. Any **one** of the first three would carry a paper.

1. **Rank reversal across horizon (strongest).** Representation A beats B at horizon 1–3 and B
   beats A at horizon ≥ H, under information parity, on kernel-verified states, replicated on
   two solver families. This **cannot** be explained by compounding: compounding preserves
   ordering. It would establish that "the best presentation" is horizon-relative — a genuinely
   new statement about machine mathematical cognition, and one that no cited work predicts.

2. **Super-compounding: the per-step gap itself widens with depth.** Fit the compounding null
   (per-step accuracy constant in depth, errors independent), show the residual is significant
   and positive for the discovered language. Sinha et al. already show per-step accuracy
   *degrades* with step count via self-conditioning on prior errors; a representation that
   externalises and re-reads state could plausibly *suppress* self-conditioning. Demonstrating
   that **a language-design choice attenuates self-conditioning** would be a mechanism result,
   not a benchmark result, and mechanism results are much harder to dismiss.

3. **Search beats the expert.** The discovered language Pareto-dominates a faithfully
   re-implemented Minilang-class baseline on a verified benchmark, under matched information and
   matched budget. This is the result that converts "an optimiser looking for a problem" into
   "automated design search outperforms expert design in formal mathematics" — the same rhetorical
   move AlphaEvolve/FunSearch made for algorithms.

4. **Transfer.** The discovered language helps a solver family that was **not** in the search
   loop, and ideally not in the same model lineage. This kills "you overfit the search to one
   checkpoint's tokenizer", which is otherwise the default explanation.

5. **Matched-learning curve, not just zero-shot ceiling.** `GOAL.md` §14's example-matched and
   token-matched regimes, reporting the **learning curve** as the causal object. Lee et al.'s
   arithmetic phase transition (sample efficiency, not just accuracy, is a function of
   representation) is the precedent that makes this measurable and interesting.

6. **An honest negative.** Pre-registered, budgeted, with allowed outcomes declared in advance
   (`GOAL.md` §20). Given that Minilang has already published the positive, a rigorous null on
   *information-parity* variation would itself be informative: it would localise Minilang's gain
   in **abstraction/automation-granularity** rather than in **presentation**, which is a real
   scientific claim about where language design pays.

### 5.3 Two controls that are not optional

7. **The primitive-set-held-constant ablation.** At least one pre-registered arm must vary
   grammar, morphology, binding, state topology and action granularity **while holding the
   primitive/abstraction set fixed**. Without it, the claim is indistinguishable from
   DreamCoder / LILO / DreamProver library learning, and that is the whole ballgame.
8. **A compute- and sampling-matched control across language variants.** Berlot-Attwell et al.
   (MATH-AI @ NeurIPS 2024) showed that reported gains in the verified-library literature can be
   attributed to self-correction and extra sampling rather than the learned artifact. If two
   language arms differ in tokens emitted, retries, or self-consistency samples, the reviewer's
   default explanation is compute, not language. `GOAL.md` §14's token/compute-matched regime
   already anticipates this; it must be executed, not deferred.

### 5.4 Three things that would destroy the contribution

- **Publishing the architecture instead of a result.** Canonical-state-plus-renderings is MMT;
  genome-plus-mutation is standard EC; verifier-in-the-loop is standard NTP. There is no paper in
  the architecture.
- **Measuring on tasks a surface heuristic solves.** The project's own audits already found
  `formal_expression_depth` solvable at 1.000 by bracket counting on **every** surface, and
  World-v0 `NEXT_ACTION` model-free solvable 676/676
  (`docs/WHAT_WORKS_WHAT_DOESNT.md`, `docs/FUTURE_ENVIRONMENT_FAMILIES.md`). A representation
  effect measured on a shortcut-solvable family is not a representation effect. The shortcut
  audit must read **the rendered surface**, not the canonical JSON — the current defect.
- **Comparing arms that are not actually different.** The same audit found that the three new
  Lean families "emit raw Lean pretty-printed strings", which *fixes R* and gives all eight arms
  byte-identical input, and that the Astra bridge arms share no ≥40-character span at 300/300.
  A searched population that does not vary what the solver reads is not a search.

---

## 6. Full citation list

Formal proof languages and provers
- Xu, Q., Wang, R., Wang, P., Li, H., Watt, C. *A Minimalist Proof Language for Neural Theorem Proving over Isabelle/HOL.* PACMPL / OOPSLA 2026. https://arxiv.org/abs/2507.18885 · https://dl.acm.org/doi/10.1145/3798275
- Xu, Q., Ong Jun Leang, J., Wang, R., Li, W., Li, H., Ong, L., Watt, C. *Theorem-Proving Agent over Abstract Syntax Tree of Redesigned Language.* arXiv:2607.16372, 2026. https://arxiv.org/abs/2607.16372
- Polu, S., Sutskever, I. *Generative Language Modeling for Automated Theorem Proving.* arXiv:2009.03393, 2020. https://arxiv.org/abs/2009.03393
- Yang, K. et al. *LeanDojo: Theorem Proving with Retrieval-Augmented Language Models.* NeurIPS 2023 Datasets & Benchmarks. https://arxiv.org/abs/2306.15626
- Wenzel, M. *Isabelle/Isar — a generic framework for human-readable proof documents.* https://wwwbroy.in.tum.de/~wenzelm/papers/isar-framework.pdf
- Beiser, A., Penz, ?., Musliu, N. *Intermediate Languages Matter: Formal Languages and LLMs affect Neurosymbolic Reasoning.* KG-NeSy @ SEMANTiCS 2025. arXiv:2509.04083. https://arxiv.org/abs/2509.04083 *(full author list not verified beyond search metadata)*
- Ye, W. et al. *ProofEvolve: Neuro-Symbolic Evolution for Formal Automated Theorem Proving.* arXiv:2608.26334, 2026. https://arxiv.org/abs/2608.26334

Mathematical interchange and knowledge representation
- Rabe, F. *MMT: The Meta Meta Tool (system description).* https://kwarc.info/people/frabe/Research/rabe_mmtsys_20.pdf
- Kohlhase, M. *OMDoc.* https://en.wikipedia.org/wiki/OMDoc
- Kohlhase, M., Rabe, F. *Semantics of OpenMath and MathML3.* Mathematics in Computer Science, 2012. https://link.springer.com/article/10.1007/s11786-012-0113-x
- OpenMath Content Dictionaries. https://openmath.org/cdgroups/
- Dehaye, P.-O., Kohlhase, M. et al. *Interoperability in the OpenDreamKit Project: The Math-in-the-Middle Approach.* arXiv:1603.06424, 2016. https://arxiv.org/abs/1603.06424

Symbolic computation and execution substrates
- Wolfram Language design principles. https://www.wolfram.com/language/principles/
- SymPy expression manipulation. https://docs.sympy.org/latest/tutorials/intro-tutorial/manipulation.html · maintainer retrospective https://oscarbenjamin.github.io/blog/czi/post1.html
- Bezanson, J., Edelman, A., Karpinski, S., Shah, V. *Julia: A Fresh Approach to Numerical Computing.* SIAM Review 59(1), 2017. https://dl.acm.org/doi/10.1137/141000671
- JAX / jaxpr — **UNVERIFIED**, no primary source obtained.

Probabilistic programming
- Gorinova, M. I., Moore, D., Hoffman, M. D. *Automatic Reparameterisation of Probabilistic Programs.* ICML 2020, PMLR v119. https://proceedings.mlr.press/v119/gorinova20a/gorinova20a.pdf · https://arxiv.org/abs/1906.03028
- Carpenter, B. et al. *Stan: A Probabilistic Programming Language.* JSS 76(1), 2017. https://www.jstatsoft.org/v076/i01 — *its own treatment of reparameterisation is* **UNVERIFIED**.

Emergent communication
- Foerster, J., Assael, Y., de Freitas, N., Whiteson, S. *Learning to Communicate with Deep Multi-Agent Reinforcement Learning.* NIPS 2016. https://proceedings.neurips.cc/paper/2016/hash/c7635bfd99248a2cdef8249ef7bfbef4-Abstract.html
- Lazaridou, A., Peysakhovich, A., Baroni, M. *Multi-Agent Cooperation and the Emergence of (Natural) Language.* ICLR 2017. https://dblp.org/rec/conf/iclr/LazaridouPB17.html
- Kottur, S., Moura, J., Lee, S., Batra, D. *Natural Language Does Not Emerge 'Naturally' in Multi-Agent Dialog.* EMNLP 2017. https://aclanthology.org/D17-1321/
- Lazaridou, A., Baroni, M. *Emergent Multi-Agent Communication in the Deep Learning Era.* arXiv:2006.02419. https://arxiv.org/abs/2006.02419

Program synthesis, library learning, representation meta-evolution
- Ellis, K., Wong, C., Nye, M., Sablé-Meyer, M., Morales, L., Hewitt, L., Cary, L., Solar-Lezama, A., Tenenbaum, J. B. *DreamCoder: Bootstrapping Inductive Program Synthesis with Wake-Sleep Library Learning.* PLDI 2021. https://arxiv.org/abs/2006.08381 · https://dl.acm.org/doi/10.1145/3453483.3454080
- Wong, C., Ellis, K., Tenenbaum, J. B., Andreas, J. *Leveraging Language to Learn Program Abstractions and Search Heuristics (LAPS).* ICML 2021. https://arxiv.org/abs/2106.11053
- Bowers, M., Olausson, T., Wong, C., Grand, G., Tenenbaum, J. B., Ellis, K., Solar-Lezama, A. *Top-Down Synthesis for Library Learning (Stitch).* POPL 2023. https://arxiv.org/abs/2211.16605
- Cao, D., Kunkel, R., Nandi, C., Willsey, M., Tatlock, Z., Polikarpova, N. *babble: Learning Better Abstractions with E-Graphs and Anti-Unification.* POPL 2023. https://arxiv.org/abs/2212.04596
- Grand, G., Wong, C., Bowers, M., Olausson, T., Liu, M., Tenenbaum, J. B., Andreas, J. *LILO: Learning Interpretable Libraries by Compressing and Documenting Code.* ICLR 2024. https://arxiv.org/abs/2310.19791
- Lake, B. M., Salakhutdinov, R., Tenenbaum, J. B. *Human-level concept learning through probabilistic program induction.* Science 350(6266):1332–1338, 2015. https://www.science.org/doi/10.1126/science.aab3050
- Dechter, E., Malmaud, J., Adams, R. P., Tenenbaum, J. B. *Bootstrap Learning via Modular Concept Discovery.* IJCAI 2013. https://www.ijcai.org/Proceedings/13/Papers/196.pdf
- Zhang, Y., Sun, J., Bi, H., Geng, C., Ma, W., Li, Z., Si, X. *DreamProver: Evolving Transferable Lemma Libraries via a Wake-Sleep Theorem-Proving Agent.* arXiv:2604.26311, 2026. https://arxiv.org/abs/2604.26311
- *LEGO-Prover: Neural Theorem Proving with Growing Libraries.* ICLR 2024 (Oral). https://arxiv.org/abs/2310.00656
- Wang, Z. et al. *TroVE: Inducing Verifiable and Efficient Toolboxes for Solving Programmatic Tasks.* ICML 2024. https://arxiv.org/abs/2401.12869
- Berlot-Attwell, I. et al. *Library Learning Doesn't: The Curious Case of the Single-Use "Library".* MATH-AI @ NeurIPS 2024. https://arxiv.org/abs/2410.20274
- O'Neill, M., Ryan, C. *Grammatical Evolution by Grammatical Evolution: The Evolution of Grammar and Genetic Code.* EuroGP 2004, LNCS 3003:138–149. https://link.springer.com/chapter/10.1007/978-3-540-24650-3_13 *(Springer page auth-blocked; metadata from search result — see §7)*
- Medvet, E., Bartoli, A., De Lorenzo, A., Tarlao, F. *Designing automatically a representation for grammatical evolution.* Genetic Programming and Evolvable Machines 20:37–65, 2019. https://link.springer.com/article/10.1007/s10710-018-9327-2
- Shi, Y.-Z., Hou, H., Bi, Z., Meng, F., Wei, X., Ruan, L., Wang, Q. *AutoDSL: Automated domain-specific language design for structural representation of procedures with constraints.* ACL 2024. https://aclanthology.org/2024.acl-long.659/ · https://arxiv.org/abs/2406.12324
- Škrlj, B. et al. *autoBOT: evolving neuro-symbolic representations for explainable low-resource text classification.* Machine Learning, 2021. https://pmc.ncbi.nlm.nih.gov/articles/PMC8550026/
- Real, E. et al. *AutoML-Zero: Evolving Machine Learning Algorithms From Scratch.* ICML 2020, PMLR v119. https://proceedings.mlr.press/v119/real20a.html
- Romera-Paredes, B., Barekatain, M. et al. *Mathematical discoveries from program search with large language models (FunSearch).* Nature 625(7995):468–475, 2024. https://pubmed.ncbi.nlm.nih.gov/38096900/
- *AlphaEvolve: A coding agent for scientific and algorithmic discovery.* arXiv:2506.13131, 2025. https://arxiv.org/abs/2506.13131 · https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- Lehman, J., Gordon, J., Jain, S., Ndousse, K., Yeh, C., Stanley, K. O. *Evolution Through Large Models (ELM).* arXiv:2206.08896. https://arxiv.org/abs/2206.08896
- Wang, G. et al. *Voyager: An Open-Ended Embodied Agent with Large Language Models.* arXiv:2305.16291. https://arxiv.org/abs/2305.16291

Search over the agent's observed representation
- Ran, D., Gong, Z., Guo, Y., Wu, M., Cao, Y., Lu, H., Zhang, H., Zeng, X., Cao, G., Yao, L., Deng, Y., Yang, W., Xie, T. *From User Interface to Agent Interface: Efficiency Optimization of UI Representations for LLM Agents (UIFormer).* arXiv:2512.13438, 2025. https://arxiv.org/abs/2512.13438
- *Value Driven Representation for Human-in-the-Loop Reinforcement Learning.* UMAP 2019. https://arxiv.org/abs/2004.01223

Search methodology
- Whiteson, S., Stone, P. *Evolutionary Function Approximation for Reinforcement Learning.* JMLR 7:877–917, 2006. https://jmlr.org/papers/v7/whiteson06a.html
- Whiteson, S., Taylor, M. E., Stone, P. *Adaptive Tile Coding for Value Function Approximation.* UT Austin tech report. https://www.cs.utexas.edu/~ai-lab/pubs/whitesontr07.pdf · *Evolutionary Tile Coding* (AAAI workshop). https://cdn.aaai.org/ocs/ws/ws0625/2068-8478-1-PB.pdf
- Zoph, B., Le, Q. V. *Neural Architecture Search with Reinforcement Learning.* ICLR 2017. https://arxiv.org/abs/1611.01578
- Elsken, T., Metzen, J. H., Hutter, F. *Neural Architecture Search: A Survey.* JMLR 20(55), 2019. https://jmlr.org/papers/v20/18-598.html
- Jamieson, K., Talwalkar, A. *Non-stochastic Best Arm Identification and Hyperparameter Optimization.* AISTATS 2016, PMLR 51:240–248. https://proceedings.mlr.press/v51/jamieson16.html
- Li, L., Jamieson, K., DeSalvo, G., Rostamizadeh, A., Talwalkar, A. *Hyperband.* JMLR 18(185). https://jmlr.org/papers/v18/16-558.html
- Mouret, J.-B., Clune, J. *Illuminating search spaces by mapping elites (MAP-Elites).* arXiv:1504.04909, 2015 — **arXiv preprint, never peer-reviewed**. https://arxiv.org/abs/1504.04909
- Cully, A., Clune, J., Tarapore, D., Mouret, J.-B. *Robots that can adapt like animals.* Nature 521:503–507, 2015. https://www.nature.com/articles/nature14422
- Wang, R., Lehman, J., Clune, J., Stanley, K. O. *POET.* arXiv:1901.01753 · *Enhanced POET*, ICML 2020, PMLR v119. https://arxiv.org/abs/1901.01753 · https://proceedings.mlr.press/v119/wang20l.html
- Lehman, J., Stanley, K. O. *Abandoning Objectives: Evolution Through the Search for Novelty Alone.* Evolutionary Computation 19(2):189–223, 2011. https://direct.mit.edu/evco/article-abstract/19/2/189/1365/
- Jaderberg, M. et al. *Population Based Training of Neural Networks.* arXiv:1711.09846. https://arxiv.org/abs/1711.09846
- Schneider, L., Pfisterer, F., Kent, P., Branke, J., Bischl, B., Thomas, J. *Tackling Neural Architecture Search With Quality Diversity Optimization.* AutoML Conf 2022. https://arxiv.org/abs/2208.00204
- *Automated Reinforcement Learning (AutoRL): An Overview.* arXiv:2201.05000. https://arxiv.org/abs/2201.05000

Prompt / representation format and reasoning
- Sclar, M., Choi, Y., Tsvetkov, Y., Suhr, A. *Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design.* ICLR 2024. https://arxiv.org/abs/2310.11324
- Chen, X., Chi, R. A., Wang, X., Zhou, D. *Premise Order Matters in Reasoning with Large Language Models.* ICML 2024, PMLR v235:6596–6620. https://proceedings.mlr.press/v235/chen24i.html · https://arxiv.org/abs/2402.08939
- He, J., Rungta, M., Koleczek, D., Sekhon, A., Wang, F., Hasan, S. *Does Prompt Formatting Have Any Impact on LLM Performance?* arXiv:2411.10541. https://arxiv.org/abs/2411.10541
- Tam, Z. R. et al. *Let Me Speak Freely? A Study on the Impact of Format Restrictions on Large Language Model Performance.* EMNLP 2024 Industry Track. https://aclanthology.org/2024.emnlp-industry.91/
- Nye, M. et al. *Show Your Work: Scratchpads for Intermediate Computation with Language Models.* arXiv:2112.00114, 2021. https://arxiv.org/abs/2112.00114
- Wei, J. et al. *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.* NeurIPS 2022. https://arxiv.org/abs/2201.11903
- Gao, L. et al. *PAL: Program-aided Language Models.* ICML 2023, PMLR v202. https://proceedings.mlr.press/v202/gao23f.html
- Chen, W., Ma, X., Wang, X., Cohen, W. *Program of Thoughts Prompting.* TMLR 2023. https://arxiv.org/abs/2211.12588
- Li, Z., Liu, H., Zhou, D., Ma, T. *Chain of Thought Empowers Transformers to Solve Inherently Serial Problems.* ICLR 2024. https://arxiv.org/abs/2402.12875
- Merrill, W., Sabharwal, A. *The Expressive Power of Transformers with Chain of Thought.* ICLR 2024. https://arxiv.org/abs/2310.07923
- Hao, S. et al. *Training Large Language Models to Reason in a Continuous Latent Space (Coconut).* arXiv:2412.06769. https://arxiv.org/abs/2412.06769
- Fernando, C., Banarse, D., Michalewski, H., Osindero, S., Rocktäschel, T. *Promptbreeder: Self-Referential Self-Improvement via Prompt Evolution.* ICML 2024. https://arxiv.org/abs/2309.16797 · https://proceedings.mlr.press/v235/fernando24a.html
- Khattab, O. et al. *DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines.* ICLR 2024. https://arxiv.org/abs/2310.03714
- *GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning.* arXiv:2507.19457. https://arxiv.org/abs/2507.19457

Reasoning depth, horizon and compounding
- Dziri, N. et al. *Faith and Fate: Limits of Transformers on Compositionality.* NeurIPS 2023. https://arxiv.org/abs/2305.18654
- Ye, T., Xu, Z., Li, Y., Allen-Zhu, Z. *Physics of Language Models: Part 2.1, Grade-School Math and the Hidden Reasoning Process.* ICLR 2025. https://arxiv.org/abs/2407.20311
- Sinha, A., Arun, A., Goel, S., Staab, S., Geiping, J. *The Illusion of Diminishing Returns: Measuring Long Horizon Execution in LLMs.* ICLR 2026. https://arxiv.org/abs/2509.09677
- Yang, Z. et al. *Can Structured Templates Facilitate LLMs in Tackling Harder Tasks? An Exploration of Scaling Laws by Difficulty.* arXiv:2508.19069. https://arxiv.org/abs/2508.19069

Tokenization and numeric representation
- Singh, A. K., Strouse, D. *Tokenization counts: the impact of tokenization on arithmetic in frontier LLMs.* arXiv:2402.14903. https://arxiv.org/abs/2402.14903
- Zheng, B. et al. *Broken Tokens? Your Language Model can Secretly Handle Non-Canonical Tokenizations.* arXiv:2506.19004. https://arxiv.org/abs/2506.19004
- McLeish, S. et al. *Transformers Can Do Arithmetic with the Right Embeddings.* NeurIPS 2024. https://arxiv.org/abs/2405.17399
- Lee, N. et al. *Teaching Arithmetic to Small Transformers.* arXiv:2307.03381. https://arxiv.org/abs/2307.03381 — *venue* **UNVERIFIED**.
- Xue, L. et al. *ByT5: Towards a Token-Free Future with Pre-trained Byte-to-Byte Models.* TACL 2022. https://aclanthology.org/2022.tacl-1.17/
- Yu, L. et al. *MEGABYTE: Predicting Million-byte Sequences with Multiscale Transformers.* arXiv:2305.07185. https://arxiv.org/abs/2305.07185

---

## 7. Items explicitly UNVERIFIED in this audit

Do not cite these until a primary source is read.

- Whether Minilang's evaluation contains an ablation separating language redesign from
  Sledgehammer/ATP delegation, and whether it varies any Minilang design axis. (The arXiv PDF
  did not extract to text in this session.) **This matters: it determines whether Minilang is an
  information-parity result or a confounded one.**
- JAX / jaxpr as a documented representation-design-affects-capability case.
- Whether Carpenter et al. (JSS 2017) itself measures reparameterisation effects; NumPyro/Pyro
  automatic-reparameterisation equivalents.
- Full author list and venue details for Beiser/Penz/Musliu (arXiv:2509.04083) and for the
  StructuredRAG line.
- Venue for Lee et al., *Teaching Arithmetic to Small Transformers*.
- A byte-level-vs-BPE head-to-head on mathematical *reasoning* (as opposed to arithmetic or
  robustness). None was found; treat as an open gap, not an established result.
- HTPS/Lample, Thor, PACT/Han, Lean Copilot, Magnushammer, miniF2F and ProofNet were **not**
  individually verified in this sweep; they are named here only as context.
- **DreamProver's fitness signal and whether a kernel owns its ground truth** — the abstract does
  not state it; only the lemma-library object and the benchmark direction were confirmed.
  Benchmark names and numbers were not obtained.
- **O'Neill & Ryan, GE², EuroGP 2004** — the Springer page was auth-blocked; title, authors,
  venue and pages come from search metadata only. The related, independently reachable
  "meta-Grammar Constant Creation with GE by GE" (GECCO 2005,
  https://ncra.ucd.ie/papers/constantsgecco2005.pdf) can substitute if a primary source is needed.
- Full author list for **LEGO-Prover** and for **TroVE**; exact venue string for
  Berlot-Attwell et al.
- **This audit's negative finding is bounded, not proof of absence.** No work was found that
  evolves the surface syntax, morphology or serialization of a language and measures downstream
  solver performance on verified mathematics — across roughly a dozen targeted queries in the
  DSL-learning, NAS-grammar, emergent-language, prompt-format and formal-math-agent literatures.
  Patents, non-English venues and unindexed 2026 preprints were not searched.
