#!/bin/zsh
# Replay LeanDojo-recorded tactic trajectories through the real Lean 4 elaborator.
# Read-only w.r.t. the mathlib checkout: `lake env` only sets LEAN_PATH.
MB=/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4
LEAN=/Users/moheet/.elan/bin/lean; LAKE=/Users/moheet/.elan/bin/lake
HERE=${0:A:h}; D=$HERE/probes; O=$HERE/probe_out; mkdir -p $O; rm -f $O/*.out $O/*.err
ok=0; bad=0; total=0
for f in $D/P_*.lean; do
  b=$(basename $f .lean); total=$((total+1))
  s=$(python3 -c 'import time;print(time.time())')
  env -C $MB $LAKE env $LEAN "$f" > $O/$b.out 2> $O/$b.err; rc=$?
  e=$(python3 -c 'import time;print(time.time())')
  errs=$(cat $O/$b.out $O/$b.err | grep -c 'error:')
  w=$(python3 -c "print(round($e-$s,2))")
  if [ "$errs" = "0" ] && [ "$rc" = "0" ]; then ok=$((ok+1)); st=PASS; else bad=$((bad+1)); st=FAIL; fi
  echo "$st $b rc=$rc errors=$errs wall=${w}s"
  echo "$b\t$rc\t$errs\t$w" >> $O/timings.tsv
done
echo "---- PASS=$ok FAIL=$bad TOTAL=$total ----"
