"""Phase 8 preparation: representation-parity audit of the precondition ladder.

CPU-only, offline, ZERO model calls.  ``span_audit.py`` measures, for every founder surface and
every pair of surfaces, how much rendered text the arms share (E1-style span coverage, longest
common substring, difflib ratio), whether the identifier tokens on the page agree, how many
bytes separate a twin pair, and where on the page the truth-carrying block sits.  The output is
``artifacts/reports/precondition_parity_audit.json``.
"""
