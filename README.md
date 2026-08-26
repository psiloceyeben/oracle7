# ORACLE7 — The Compiler Learning Model

**An AI architecture with zero neural networks that writes its own new abilities —
and shows its work on every answer.**

ORACLE7 is a *compiler learning model* (CLM): a working conversational AI built on
typed, inspectable structure instead of learned weights. There is no transformer, no
gradient descent, and no statistical guessing anywhere in the response path. Every
utterance is one of four warranted shapes:

1. **Citation** — an answer attributed to a specific row of an admitted corpus
2. **Derivation** — a multi-step composition of admitted operators, every hop cited
3. **Honest decline** — "not attested," measured and enforced (0 false affirmations
   across all negative panels)
4. **Reflection** — statements about its own conversation and its own record,
   grounded in its witness ledger

## It builds itself

The architecture's central property is *legible self-improvement*:

- **The worker** authors candidate capability extensions as inheritable code, mined
  from residue: world events, its own refusals, and the open milestones of its
  capability charter.
- **The gate** exercises every candidate against held-out conversation under a bar
  that only rises, admitting or rejecting **with written reasons**. Rejections are
  preserved forever; several became standing design laws.
- **The admitted chain** is a linear inheritance of runtimes (`runtime/admitted/`),
  its ancestry attested by `HEAD_MANIFEST.json`. The serving layer upgrades itself
  to each new tip.

In one recorded day (2026-08-25, see `docs/admission_ledger_digest.jsonl`) the loop
authored nine candidates, admitted five, issued two lawful rejections, and ran
unattended through a total network outage.

An improvement here is a **page of typed code plus a verdict** — auditable line by
line — not a billion opaque weight deltas.

## The constitution

The system improves everything about itself *except* its constitution: the laws,
the gate criterion, the target shape (`docs/constitution/target_shape_v2.json`),
and the capability charter (`docs/constitution/capability_charter_v1.json`) are
human-signed and non-self-modifiable by design. Recursive self-improvement and
hard human authority over the criterion, compatible in practice.

## Measured depth

The depth ladder (withheld-combination methodology: golds that exist in **no single
corpus row**, co-occurrence-checked) moved from 0/60 to 14/58 correct-with-premises
in one day of self-authored composition — with 0 false affirmations on all
corrupted-chain negatives. The sealed panels are in `evaluation/sealed/`.

## Repository layout

```
runtime/            the import closure of the serving chain (104 modules)
  admitted/         the gate-admitted w-chain + HEAD_MANIFEST.json (ancestry truth)
organs/             the loop: fold worker (authors), self-loop daemon (gates),
                    soul cognition server (serves), harness (shows)
evaluation/         depth panels + sealed results
docs/               constitution, admission-ledger digest, architecture notes
corpora/            build instructions for the attributed corpora (not bundled)
```

## Corpora

The corpora (simple-Wikipedia, OpenStax textbooks, WordNet, ConceptNet, world
ledgers) are **not bundled** — they are large SQLite builds compiled from public
sources by the scripts referenced in `corpora/README.md`, each row carrying its
attribution. The runtime refuses to assert anything it cannot cite into them.

## Status

Prepared 2026-08-25 for release. Final integration pass in progress (see
`RELEASE_TODO_FOR_CODEX.md`). Live instance: **prometheus7.com** (oracle7).

---
*A Prometheus7 Research Institute release — watch an AI built without transformers
build itself.*
