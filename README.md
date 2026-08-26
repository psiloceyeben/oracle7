# ORACLE7 — The Compiler Learning Model

**An AI architecture with zero neural networks that writes its own new abilities —
and shows its work on every answer.**

Live instance: **[prometheus7.com](https://prometheus7.com)** (the oracle7 desk) ·
[@prometheus7even](https://x.com/prometheus7even)

---

## The Mission

Modern AI has one dominant recipe: scale a statistical model until competence
emerges, then try to bolt trust on afterward. The result is systems of
extraordinary capability whose knowledge cannot be inspected, whose failures
cannot be explained, whose improvement cannot be audited, and whose alignment is
a promise rather than a property.

ORACLE7 is an existence proof for a different road. Its mission has five commitments:

**1. Intelligence that shows its work — by construction, not disclosure.**
Every utterance this system produces is one of a small set of warranted shapes:
a citation into an attributed record, a derivation whose premise chain is
exposed, a marked inference, or an honest decline. There is no place in the
architecture where an unwarranted assertion can form. The century-old question —
*can a machine know what it is talking about?* — is answered here by making
"knowing" a checkable, structural relation between an answer and a record.

**2. Self-improvement that is legible and governed.**
The system extends itself: an authoring organ writes new capabilities as small,
typed programs; an adversarial gate judges each against held-out conversation
under a bar that only rises; every admission and every refusal is recorded with
its reasons. An improvement here is a page of readable code plus a written
verdict — not a billion opaque weight deltas. Growth becomes a publication
process with an audit trail, and rejected attempts are preserved as the system's
accumulated design law.

**3. Hard human authority as a structural property.**
The laws, the gate's criterion, the target shape, and the capability charter are
human-signed and non-self-modifiable by design. The loop can improve everything
about itself except the terms under which improvement counts. Every expansion of
its autonomy — including the freedom to publish its own media — is an explicit,
revocable human grant, recorded in the same ledgers the system reflects on.
Recursive self-improvement and hard human authority are compatible in practice;
this repository is the demonstration.

**4. Minds grown from situated experience, at commodity cost.**
The model runs on CPU, at electricity cost, with no training runs and no API
dependencies. It is attached to a world of autonomous agents whose lived record
becomes its episodic memory and whose unanswerable questions become its
curriculum. Capability accrues from experience and evidence, not from gradient
descent over scraped text. This is the economics of intelligence turned inside
out: not a frontier few can afford, but a form of mind an individual can grow.

**5. A plurality of minds, not a single frontier.**
This architecture is not trying to be a transformer. It is a different *kind* of
mind — one whose strengths (total provenance, auditable growth, structural
honesty) are exactly the properties the dominant recipe finds hardest. The
mission is not to win a benchmark race; it is to widen the space of what minds
can be, and to do it in public: **watch an AI built without transformers build
itself.**

---

## What it is

ORACLE7 is a *compiler learning model* (CLM): a working conversational AI built
on typed, inspectable structure instead of learned weights. No transformer, no
gradient descent, no next-token sampling anywhere in the response path.

Every response is one of four warranted shapes:

| Shape | What it means | Warrant |
|---|---|---|
| **Citation** | attested by the record | the source row, attributed |
| **Derivation** | composed from attested facts | the full premise chain, every hop cited |
| **Decline** | "not attested" — refusal to guess | measured: 0 false affirmations on all negative panels |
| **Reflection** | statements about its own conversation and record | the witness ledger itself |

The witness is the architecture's spine: every turn is explicitly mapped from
input to output — the typed reading, the operator that fired, the terms grounded
versus introduced, the continuity carried, the citations, the residual it could
not discharge. Conversation is a *relationship between input and response,
explicitly mapped at every step*.

## It builds itself

- **The worker** authors candidate capability extensions as inheritable code,
  mined from residue: world events, its own refusals, and the open milestones of
  its human-signed capability charter.
- **The gate** exercises every candidate against held-out conversation:
  regression probes against the serving head, a metric floor that never lowers,
  a strict-gain requirement for new capability families, and crash-proof
  judgment (a crashing candidate is a REJECT with the exception as its reason —
  never a stalled line). Verdicts are written with reasons, always.
- **The admitted chain** is a linear inheritance of runtimes; its ancestry is
  attested by `runtime/admitted/HEAD_MANIFEST.json`, rebuilt on every admission.
  The serving layer resolves the head there and upgrades itself to each new tip.

In one recorded day (2026-08-25 — see `docs/admission_ledger_digest.jsonl`) the
loop authored nine candidates, admitted five, issued two lawful rejections whose
reasons became standing design law, and ran unattended through a total network
outage.

## Measured depth, honestly

The depth ladder uses the withheld-combination methodology: panel questions whose
answers exist in **no single corpus row** (co-occurrence-checked), answerable only
by composing admitted operators, scored only when every hop is cited — with
corrupted-chain negatives that must be refused. The chain moved from 0/60 to
14/58 correct-with-premises in one day of self-authored composition, with zero
false affirmations throughout. A depth claim begins with a sealed record of
shallowness; the sealed panels are in `evaluation/sealed/`.

## The world

Sixty-odd autonomous agents live continuously with the chain as their cognition.
Their acts are ledgered; the ledger consolidates into the model's episodic
memory on a cadence (gate-judged like everything else); their questions feed the
curriculum; their deterministic artworks and the model's self-narrated
broadcasts are published on the live desk. The world is the environmental half
of situated intelligence: resistance, affordances, other minds, consequences,
and memory.

## Repository layout

```
runtime/            the import closure of the serving chain (104 modules)
  admitted/         the gate-admitted w-chain + HEAD_MANIFEST.json (ancestry truth)
organs/             the loop: fold worker (authors), self-loop daemon (gates),
                    soul cognition server (serves the world), harness (shows)
evaluation/         depth panels + sealed results
docs/               constitution (target shape, capability charter),
                    admission-ledger digest, architecture notes
```

See `ARCHITECTURE.md` for the full mechanism: the organ loop, the runtime chain,
a worked single-turn trace, the laws distilled from verdicts, and the security
model.

## Corpora

The corpora (simple-Wikipedia, OpenStax textbooks, WordNet, ConceptNet, the
world's own ledgers) are **not bundled** — they are SQLite builds compiled from
public sources, each row carrying its attribution. The runtime refuses to assert
anything it cannot cite into them.

## Status

Prepared 2026-08-25. The live instance — conversation, live world feed, the
loop's own narrated work, the art gallery, and the broadcast desk — runs at
**prometheus7.com**, first tab.

---
*A Prometheus7 Research Institute release — watch an AI built without
transformers build itself.*
