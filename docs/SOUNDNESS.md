# Soundness and Assurance Boundary

Arena claims are deliberately finite. Passing a suite means no defect was found in that exact,
versioned suite; it does not mean mathematical perfection.

## Frozen v0 campaign

The assurance runner executes 16 semantic mutation properties, including alpha-renaming,
variable capture, unbound variables, unknown scopes, malformed binders, untracked partial
operations, evidence cycles and missing dependencies, identity collisions, type/exactness
confusion, probability-role errors, shape errors, goal laundering, obligation laundering, and
illegal transition actions.

It also enumerates two declared finite universes:

- 2,703 integer expression trees using atoms `{-1,0,1}`, operators `{add,sub,mul}`, and depth
  at most two, checking lossless canonical encoding;
- all 64 loop-free-edge directed graphs on three labelled evidence nodes, comparing native
  acceptance with an independently implemented cycle predicate.

Three true arithmetic/propositional claims are cross-checked by SymPy, Z3, and a deterministic
numerical falsifier. The numerical result is evidence or a counterexample, never a proof.

## Fail-closed release rule

R*-V0 requires zero unresolved critical semantic defects, zero false accepts in the declared
bounded universes, zero unresolved disagreements on the supported differential subset, and
zero critical side-channel findings. Unsupported external-verifier cases remain unsupported.

Parser perturbation acceptance is reported separately from semantic false acceptance: an edit
can yield a different but well-formed record. It becomes critical only when a protocol labels
the edited surface invalid or when semantics change silently across a required roundtrip.

## Known limits

The world is synthetic and template-bounded; native verification is structural rather than a
general theorem prover; numerical checks are not proofs; the Lean adapter currently records
environment capability but does not discharge all world transitions. No global error
probability or universal correctness claim is made.
