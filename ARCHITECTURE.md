# Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              THE CONSTITUTION               │
                    │   laws · gate criterion · target shape ·    │
                    │   capability charter  (human-granted)     │
                    └──────────────────┬──────────────────────────┘
                                       │ binds
        ┌──────────────────────────────┼───────────────────────────────┐
        │                              │                               │
┌───────▼────────┐   authors   ┌───────▼────────┐   admits    ┌────────▼────────┐
│   THE WORKER   │────────────►│    THE GATE    │────────────►│  ADMITTED CHAIN │
│ fold families  │  candidates │ held-out panels│  + reasons  │ w1 → … → tip →  │
│ from residue   │◄────────────│ bar only rises │  (ledgered) │ HEAD_MANIFEST   │
└───────▲────────┘   rejects   └────────────────┘             └────────┬────────┘
        │            (preserved, become laws)                          │ serves
        │                                                     ┌────────▼────────┐
        │  residue: refusals, charter gaps,                   │  SERVING LAYER  │
        │  world events, epoch consolidations                 │ soul cognition  │
        │                                                     │ server + harness│
┌───────┴────────────────────────────┐                        └────────┬────────┘
│            THE WORLD               │◄──────────────────────────────-─┘
│  autonomous agents living on the   │        the chain IS their cognition
│  chain; every act ledgered         │
└────────────────────────────────────┘
```

## Design principles

1. **Warrant-total.** No response path exists that can emit an unwarranted
   assertion. Citation, derivation, marked inference, and decline are different
   *output states of the machine*, not stylistic labels. Honesty is physics here,
   not policy.
2. **Legibility over scale.** Knowledge lives in typed, inspectable structure:
   corpus rows with attribution, relations with operators, readings with roles.
   A capability is a page of code; an improvement is a diff plus a verdict; a
   failure is a ledger entry with reasons. Nothing important is a tensor.
3. **Governed autonomy.** The gate's bar rises on its own with every admission
   and never lowers; the standing laws were distilled from the gate's own
   verdicts. Discretionary instruments (the re-baseline flag, the media
   kill-switch) vest in the human, and each expansion of the system's autonomy
   is granted per capability, recorded, and revocable.
4. **Situated experience as curriculum.** The world's ledger is the model's
   sensory record. Episodic memory is re-consolidated from it on a cadence;
   refusals and world questions become the residue the worker mines; declared
   gaps become typed potentials the loop pursues.
5. **Failure is retained.** Rejected candidates are preserved immutably with
   their reasons. Repeated rejections crystallize into standing design law.
   The system's history of being wrong is part of its architecture.

## The runtime chain (`runtime/`)

The serving model is a **linear inheritance chain** of Python runtimes. The base
lineage (`oracle_release_runtime_b.py` … `_ao.py`) was built milestone by
milestone, each letter a sealed release; the `w`-chain on top is **authored by
the system itself** and admitted by the gate. `HEAD_MANIFEST.json` is the single
source of ancestry truth. Every consumer — daemon, worker, servers — resolves
the tip there; the daemon rebuilds it on every admission. Orphaned admissions
(admitted but superseded off the spine) are enumerated in the manifest rather
than silently forgotten.

Selected members and what they carry:

- `stage5m13a_wordnet_specialist` / `m13b_wikipedia_specialist` — attributed
  corpus access (kind relations, summaries): the citation substrate
- `stage5m13e2_construction_kernel*` (k1–k8) — the productive compiler line:
  withheld-combination competence proven in sealed panels (55/55, with ablation
  controls)
- `stage5m13e4_*` — the logical IR and combinator layer (operator products,
  beta-instantiation, round-trip realization)
- `stage5m13e8_*` — document, paragraph, and relevance-gated composition
- `stage5m17_release_arbiter_v1–v3` — typed dispatch and arbitration
- `stage5m21/m22` — transitive and relational reasoners (composition machinery)
- The `w`-chain (self-authored, gate-admitted): regeneration (`w4`), episodic
  world-memory epochs (`w6/w18/w21`), self-improvement narration from the
  ledgers (`w10/w19/w22`), grounded continuation (`w12`), typed potentials
  (`w15/w20`), conversation reflection (`w16`), the live made-of extraction
  rule (`w23`, corpus-queried at answer time), and the two-hop composer (`w24`,
  premise-cited derivations)

## Anatomy of a single turn

1. **Intake.** The surface is read into typed candidates: speech act, referents,
   operation, polarity, modality, discourse state. Weak or tied evidence yields
   a clarification state instead of a guess.
2. **Dispatch.** The arbitrated route selects an operator: a citation route, a
   relation operator, a composer, a memory recall, a reflection, or a register
   (greeting, meta). New capability obeys the fallback law: it may only occupy
   the space of declines, never override an existing answer.
3. **Warrant assembly.** The selected route gathers its evidence: corpus rows
   with claim ids, premise chains for derivations, witness entries for
   reflection. If the warrant cannot be completed, the turn becomes an honest
   decline that names what is missing.
4. **Witness.** Exactly one witness entry is recorded for the turn: the reading,
   the operator, grounded versus introduced terms, carried continuity,
   citations, cost, and any residual obligation. The witness is what reflection
   reads; its fidelity is protected by a transactional recorder (a correctness
   release in this line's history exists precisely because reflection on a
   distorted witness is worse than none).
5. **Response.** Text plus structured metadata: status, path, provenance,
   affordances (grounded doors the conversation could take next), and the
   runtime head identity that produced it.

## The organs (`organs/`)

- **`oracle_fold_worker_v8.py`** — the authoring organ. Fold families: region
  folds (episodic consolidation on six-hour epochs), meta folds (potentials,
  self-improvement narration, reflection, open conversation), depth folds (live
  extraction rules, composition). One candidate in flight at a time; authoring
  pausable by flag; the probe head is the manifest tip on the served corpus.
- **`oracle_self_loop_v1.py`** — observe / measure / criticise / **gate**.
  Regression probes against the manifest tip; a held-out metric floor that only
  rises; strict-gain requirement for new families (re-consolidation epochs are
  lawful at no-regression); crash-proof exercise; a human-flagged re-baseline
  path for correctness releases whose truthful instruments deflate a defective
  baseline. Admissions copy into `admitted/` and rebuild the manifest.
- **`soul_cognition_server_v1.py`** — serves the chain tip to the world's agents
  and typed clients; world-evidence routes answer from the world ledgers; the
  decline discipline is preserved under load.
- **`oracle_space_app_v20.py`** — the human harness and public contract: the
  witness pane, the live loop band, world panels, deterministic art realization,
  verify-by-hash on sealed artifacts, and the public chat contract (response +
  witness metadata + affordances + head identity).

## Laws distilled from verdicts (selection)

- **One-in-flight** — never author while a candidate awaits judgment.
- **Rule-folds-over-caches** — admit the extraction rule that queries the live
  corpus; never freeze a pair list and call it knowledge.
- **Fallback-over-intercept** — new capability may only fill declines (learned
  from a rejection: an intercepting route degraded answers the chain already
  gave well).
- **Replay is stale-by-construction** — caching responses inside a
  self-improving chain degrades held-out truth (three habit-fold rejections).
- **Depth needs decline discipline** — corrupted premise chains must be refused;
  composition without false-answer discipline is not depth.
- **Read the reasons** — a rejection's grounds are what the ledger says they
  are; never infer them.
- **The bar rises, never falls** — every admission resets the floor to its own
  measured truth.

## Evaluation (`evaluation/`)

`stage_d1_depth_panel_v1.py` implements the withheld-combination depth panel:
two-hop chains whose golds co-occur in **no** corpus row, programmatic golds,
corrupted-chain negatives, premise-citation scoring, and a sealed report. The
methodology descends from the sealed productive-compiler panels (55/55 with
withheld combinations and ablation controls). Sealed results live in
`evaluation/sealed/`; the baseline record of shallowness is kept deliberately,
because a depth claim begins there.

## Security model

- The public conversational surface is a single POST route, rate-limited at two
  edges, body-capped, session ids validated and bounded.
- Loop-state and world-feed snapshots reach the public site as static JSON
  pushed on a timer from allowlisted, IP-restricted routes; visitors add no load
  to the research machine and can mutate nothing.
- The public site carries no visitor-writable state. Verification surfaces are
  read-only; sealed artifacts are immutable and hash-checkable.
- Autonomy grants (self-publication of media) check a human-owned kill-switch
  before every act and seal provenance on every published item.
- The corpora and ledgers stay on the research machines; this repository ships
  structure, mechanism, and sealed evidence.
