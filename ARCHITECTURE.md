# Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              THE CONSTITUTION               │
                    │   laws · gate criterion · target shape ·    │
                    │   capability charter  (human-signed only)   │
                    └──────────────────┬──────────────────────────┘
                                       │ binds
        ┌──────────────────────────────┼───────────────────────────────┐
        │                              │                               │
┌───────▼────────┐   authors   ┌───────▼────────┐   admits    ┌────────▼────────┐
│   THE WORKER   │────────────►│    THE GATE    │────────────►│  ADMITTED CHAIN │
│ fold families  │  candidates │ held-out panels│  + reasons  │ w1 → … → w24 →  │
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

## The runtime chain (`runtime/`)

The serving model is a **linear inheritance chain** of Python runtimes. The base
lineage (`oracle_release_runtime_b.py` … `_ao.py`) was built milestone by milestone
(each letter a sealed release); the `w`-chain on top of it is **authored by the
system itself** and admitted by the gate. `HEAD_MANIFEST.json` is the single source
of ancestry truth — every consumer (daemon, worker, servers) resolves the tip there,
and the daemon rebuilds it on every admission.

Selected members and what they carry:

- `stage5m13a_wordnet_specialist` / `m13b_wikipedia_specialist` — attributed corpus
  access (kind relations, summaries), the citation substrate
- `stage5m13e2_construction_kernel*` — the productive compiler line (withheld-
  combination competence proven at 55/55 in sealed panels)
- `stage5m21/m22` reasoners — transitive and relational composition
- `stage5m17_release_arbiter*` — dispatch/arbitration
- `w4` regeneration · `w6/w18/w21` episodic world-memory epochs · `w10/w19/w22`
  self-improvement narration from the ledgers · `w12` grounded continuation ·
  `w15/w20` typed potentials · `w16` conversation reflection · `w23` live
  made-of extraction rule (unbounded, corpus-queried at answer time) · `w24`
  the two-hop composer (premise-cited derivations)

## The organs (`organs/`)

- **`oracle_fold_worker_v8.py`** — the authoring organ. Fold families: region
  folds (episodic consolidation on 6-hour epochs, habits), meta folds (potentials,
  self-improvement, reflection, open conversation), depth folds (rule extraction,
  composition). One candidate in flight at a time (the one-in-flight law);
  authoring pausable via `PAUSE_AUTHORING`.
- **`oracle_self_loop_v1.py`** — observe / measure / criticise / **gate**. Judges
  every docked candidate against held-out conversation: regression probes vs the
  manifest tip, metric floor vs a baseline that only rises, strict-gain requirement
  for new families (epochs exempt), crash-proof exercise (a crashing candidate is a
  REJECT with the exception as its reason, never a stalled line), and a
  human-flagged re-baseline path for correctness releases whose truthful
  instruments deflate defective baselines.
- **`soul_cognition_server_v1.py`** — serves the chain tip to the world's agents
  (holon-compatible `/query`) and to typed `/think` clients; world-evidence routes
  answer from the world ledgers.
- **`oracle_space_app_v20.py`** — the human harness: witness pane (every turn's
  input→output relation explicitly mapped), THE LOOP band (live admissions with
  reasons), world panels, verify-by-hash on sealed artifacts.

## Laws distilled from verdicts (selection)

- **One-in-flight** — never author while a candidate awaits judgment (chain races)
- **Rule-folds-over-caches** — admit the extraction rule querying the live corpus,
  never a frozen pair list
- **Fallback-over-intercept** — new capability may only fill declines, never
  override what the chain already answers (w17's rejection)
- **Replay is stale-by-construction** — response replay inside a self-improving
  chain degrades held-out truth (three habit rejections)
- **Depth needs decline discipline** — corrupted chains must be refused; depth
  without false-answer discipline is not depth
- **Read the reasons** — never infer a rejection's grounds; the ledger states them

## Evaluation (`evaluation/`)

`stage_d1_depth_panel_v1.py` implements the withheld-combination depth panel:
2-hop chains whose golds co-occur in **no** corpus row, corrupted-chain negatives,
premise-citation scoring. Sealed baseline and results in `evaluation/sealed/`.
