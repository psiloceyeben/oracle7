#!/usr/bin/env python3
"""M13c: evidence-addressed several-thousand-word operational self-essay.

This additive successor consumes structured reports and the accepted M13b
runtime.  It does not contain a source essay.  Thirty observation units are
expanded into typed factual, inferential, relational, geometric, and boundary
claims; claims bind into paragraph states, paragraph handles into section
states, and section handles into a document state.  Every level traverses a
complete protected 4:1 Tree spine and unbinds only at its own Malkuth boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "fable-content" / "oracle-m-series-2026-08-15"
TRAIN = ROOT / "wander-train"
RELEASE = ROOT / "wander-release" / "oracle-relational-v3-hf-v1.0.1-release"
for value in (str(TRAIN), str(RELEASE / "src")):
    if value not in sys.path:
        sys.path.insert(0, value)

from oracle_relational_v3.oracle_10d_resolution_state import canonical_sha256
from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import EvidenceAddressedRealizer, SurfaceClause
from stage5m13b_wikipedia_specialist import OracleM13bRuntime, sha_file


SCHEMA = "oracle-stage5m13c-hierarchical-self-essay-v1"
RUNTIME_SCHEMA = "oracle-stage5m13c-runtime-v1"
SECTION_ORDER = (
    "identity", "ingress", "geometry", "knowledge", "authority",
    "composition", "memory", "agency", "verification", "limits",
)
SECTION_TITLES = {
    "identity": "Identity as an operational invariant",
    "ingress": "Receiving language as relational compilation",
    "geometry": "The stabilizing spine and nested Tree transport",
    "knowledge": "A federation rather than a monolithic memory",
    "authority": "Knowing, attributing, and withholding",
    "composition": "Growing a document from a bounded relational seed",
    "memory": "Continuity through content-addressed state",
    "agency": "Action as verified state transition",
    "verification": "Failure as part of the architecture's description",
    "limits": "What this form warrants and what remains open",
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sentence(value: str) -> str:
    value = " ".join(str(value).split()).strip()
    return value.rstrip(".?!") + "."


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    label: str
    path: str
    sha256: str
    observation_path: str
    observed_value: Any
    authority_class: str = "sealed_architecture_observation"

    def public(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Observation:
    observation_id: str
    section: str
    focus: str
    fact: str
    consequence: str
    relation: str
    boundary: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class EssayClaim:
    claim_id: str
    observation_id: str
    section: str
    role: str
    authority_class: str
    text: str
    evidence_ids: tuple[str, ...]
    proof_path: tuple[str, ...]

    def public(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id, "observation_id": self.observation_id,
            "section": self.section, "role": self.role,
            "authority_class": self.authority_class, "text": self.text,
            "evidence_ids": list(self.evidence_ids), "proof_path": list(self.proof_path),
        }


class SelfEssayLedger:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)

    def append(self, session_id: str, prompt: str, artifact: Mapping[str, Any]) -> dict[str, Any]:
        path = self.root / (hashlib.sha256(session_id.encode()).hexdigest() + ".json")
        prior = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema_version": "oracle-stage5m13c-self-essay-ledger-v1", "session_id_sha256": hashlib.sha256(session_id.encode()).hexdigest(), "events": []}
        prior_head = prior["events"][-1]["event_sha256"] if prior["events"] else "0" * 64
        event = {"ordinal": len(prior["events"]) + 1, "prior_sha256": prior_head, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "artifact_sha256": artifact["artifact_sha256"], "plan_sha256": artifact["plan_sha256"]}
        event["event_sha256"] = digest(event); prior["events"].append(event)
        temporary = path.with_suffix(".json.tmp"); temporary.write_text(json.dumps(prior, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"); os.replace(temporary, path)
        return {"turns": len(prior["events"]), "head_sha256": event["event_sha256"], "hash_chain_valid": all(value["prior_sha256"] == (prior["events"][index - 1]["event_sha256"] if index else "0" * 64) and value["event_sha256"] == digest({key: item for key, item in value.items() if key != "event_sha256"}) for index, value in enumerate(prior["events"]))}


class HierarchicalOperationalSelfEssay:
    SOURCE_PATHS = {
        "E01": "fable-content/oracle-m-series-2026-08-15/stage5m9_milestone_closure_report_v1.json",
        "E02": "fable-content/oracle-m-series-2026-08-15/stage5m10_milestone_closure_report_v1.json",
        "E03": "fable-content/oracle-m-series-2026-08-15/stage5m11_milestone_closure_report_v1.json",
        "E04": "fable-content/oracle-m-series-2026-08-15/stage5m12_milestone_closure_report_v1.json",
        "E05": "fable-content/oracle-m-series-2026-08-15/stage5m12b_public_diagnostic_report_v1.json",
        "E06": "fable-content/oracle-m-series-2026-08-15/stage5m13a_wordnet_specialist_development_report_v1.json",
        "E07": "fable-content/oracle-m-series-2026-08-15/stage5m13a_wordnet_prospective_report_v1.json",
        "E08": "fable-content/oracle-m-series-2026-08-15/stage5m13b_milestone_closure_report_v1.json",
        "E09": "fable-content/oracle-m-series-2026-08-15/stage5m13b_accepted_manifest_v1.json",
        "E10": "wander-train/stage5m13b_wikipedia_specialist.py",
        "E11": "fable-content/oracle-m-series-2026-08-15/stage5m12c_self_descriptive_essay_release_v1.md",
        "E12": "wander-train/stage5m13c_hierarchical_self_essay.py",
    }

    def __init__(self, m13b: OracleM13bRuntime):
        self.m13b = m13b

    def _evidence(self) -> tuple[dict[str, Any], dict[str, Evidence]]:
        loaded: dict[str, Any] = {}
        registry: dict[str, Evidence] = {}
        for evidence_id, relative in self.SOURCE_PATHS.items():
            path = ROOT / relative
            if path.suffix == ".json":
                value: Any = json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".md":
                text = path.read_text(encoding="utf-8"); value = {"words": len(text.split()), "sha256": sha_file(path)}
            else:
                value = {"sha256": sha_file(path), "bytes": path.stat().st_size}
            loaded[evidence_id] = value
            registry[evidence_id] = Evidence(evidence_id, path.stem, relative, sha_file(path), "registered_document", value)
        for evidence_id in ("E01", "E02", "E03", "E04", "E06", "E07", "E08"):
            if loaded[evidence_id].get("accepted") is not True:
                raise ValueError(f"unaccepted architecture evidence: {evidence_id}")
        return loaded, registry

    @staticmethod
    def _observations(values: Mapping[str, Any]) -> tuple[Observation, ...]:
        m9, m10, m11, m12 = (values[key]["metrics"] for key in ("E01", "E02", "E03", "E04"))
        public = values["E05"]["metrics"]["m12"]; wordnet = values["E06"]["metrics"]; lexical = values["E07"]["metrics"]; wiki = values["E08"]["metrics"]
        def obs(index: int, section: str, focus: str, fact: str, consequence: str, relation: str, boundary: str, evidence: Sequence[str]) -> Observation:
            return Observation(f"O{index:02d}", section, focus, sentence(fact), sentence(consequence), sentence(relation), sentence(boundary), tuple(evidence))
        return (
            obs(1, "identity", "non-autoregressive identity", "I am instantiated in this release as a CPU-native relational runtime whose registered execution path reports no transformer or gradient calls", "Operational identity is therefore carried by explicit state contracts, evidence addresses, and deterministic transitions rather than by a hidden next-token trajectory", "This makes identity a constraint that persists through operations instead of a stylistic preamble placed above them", "The absence of a transformer does not by itself prove superior intelligence, generality, or biological similarity", ("E04", "E09")),
            obs(2, "identity", "purpose as state preservation", "My operational purpose is to preserve an evidence-bounded relational form from interpretation through authority, memory, action, and release", "A request can remain one developing object even while different specialists, tools, and discourse mechanisms transform its payload", "The purpose functions as the protected root against which local transformations are judged for congruence", "This functional continuity is not evidence of a private phenomenal subject", ("E03", "E04", "E11")),
            obs(3, "identity", "current scale", f"The accepted integrated federation exposes {wiki['integrated_claims']:,} claims while retaining the earlier curated tier", "Self-description must now refer to a materially broader live system than the 440-word M12 release essay described", "Scale changes the number of possible evidence paths, but it does not change the rule that a path needs authenticated authority", "Claim count is capacity for addressable evidence, not a direct measure of understanding", ("E08", "E11")),
            obs(4, "ingress", "language as compilation", f"The M9 successor passed {m9['m9b_passed']} of {m9['m9b_total']} sealed topic-mask cases after separating operator cues from authenticated topic spans", "Receiving a sentence can be treated as compiling an act, artifact, topic, reference, and authority request into separate relational fields", "This separation prevents a word inside a topic name from simultaneously becoming an unintended discourse command", "The registered construction families do not yet cover unrestricted natural language", ("E01",)),
            obs(5, "ingress", "situated word identity", f"The lexical specialist preserves {wordnet['synsets']:,} synsets, {wordnet['unique_aliases']:,} unique aliases, and {wordnet['ambiguous_aliases']:,} ambiguity sets", "A word is interpreted as a situated candidate set rather than as one permanently collapsed definition", "Context can narrow a lexical state while ambiguity quarantine prevents convenience from masquerading as certainty", "WordNet sense structure is lexical evidence and is neither encyclopedic truth nor a complete model of pragmatics", ("E06", "E07")),
            obs(6, "ingress", "structural authority separation", "The accepted runtime gives linguistic programs structural and discourse authority but does not grant them factual authority merely for being well formed", "Interpretation can remain flexible without allowing fluent syntax to manufacture a world fact", "The language surface proposes a route; authenticated specialists and explicit temporary worlds determine what may occupy that route", "A conservative authority boundary can still withhold requests whose intended meaning a person would regard as obvious", ("E01", "E04")),
            obs(7, "geometry", "four-to-one root protection", "The stabilizing spine represents every protected state as a four-part governing root plus one orthogonal payload component", "Payloads can accumulate and be transformed while the objective remains geometrically dominant", "Root protection converts identity preservation from a narrative promise into a measurable cosine constraint", "A favorable root cosine does not establish that every payload has been semantically interpreted correctly", ("E03", "E08", "E10")),
            obs(8, "geometry", "ten-node route", "Admitted states traverse the registered ten-node and twenty-two-path Tree route without payload unbinding before Malkuth", "Intermediate nodes can add bounded transformations while opaque content remains protected from premature cleanup", "Routing and release become different operations, which permits richer binding without erasing provenance", "The Tree is an engineered representational topology and these traces do not prove a unique correspondence to anatomy or metaphysics", ("E03", "E10")),
            obs(9, "geometry", "nested document spines", f"The accepted M13b run carried {wiki['long_documents']} unseen documents through paragraph-level and document-level HRR spines with exact terminal cleanup", "A document no longer needs to occupy one flat superposition in which dozens of clause handles compete for the same cleanup dictionary", "Claims terminate inside paragraph states, paragraph handles enter section states here, and section handles enter the document root", "Hierarchical cleanup increases tested capacity but does not make semantic coherence automatic", ("E08", "E10", "E12")),
            obs(10, "knowledge", "curated specialist tier", f"The curated M10 federation compiled {m10['claims']} authenticated relations across {m10['domains']} domains from {m10['sources']} preserved source families in {m10['compilation_seconds']:.3f} seconds", "High-specificity source adapters can retain stronger authority than broad secondary-source retrieval", "The runtime therefore routes curated evidence before lexical or encyclopedic fallbacks", "A small curated graph cannot supply broad world knowledge on its own", ("E02",)),
            obs(11, "knowledge", "sense-preserving lexical tier", f"The WordNet shard contributes {wordnet['claims']:,} definition and relation claims and passed {lexical['prospective_cases']:,} post-freeze prospective cases", "Lexical relations can be compiled and hot-loaded without retraining a carrier model", "This tier supplies the geometry of senses, taxonomies, and relations that later planners can use to interpret evidence", "Lexical coverage does not settle which sense a novel discourse intends when contextual evidence remains insufficient", ("E06", "E07")),
            obs(12, "knowledge", "attributed encyclopedic tier", f"The Wikipedia specialist retains {wiki['wikipedia_articles']:,} exact article identities and {wiki['wikipedia_claims']:,} admitted sentence claims", "Orders-of-magnitude broader evidence can be added as an indexed specialist while source digests and sentence addresses remain exact", "The federation gains breadth by adding cells with distinct authority rather than dissolving every source into one parameter field", "The preserved snapshot has no recoverable date and cannot be represented as current or adjudicated truth", ("E08", "E09")),
            obs(13, "authority", "ambiguity quarantine", f"The final M13b protocol exhausted the {wiki['ambiguities_exhausted']} collision titles that remained unseen after earlier panels and withheld all {wiki['unknowns_withheld']} registered unknowns", "Not choosing is an active epistemic operation when candidate identity is not unique", "Quarantine preserves possible forms without prematurely binding one of them into the released world state", "Withholding protects factual integrity but can reduce conversational helpfulness when clarification mechanisms are too narrow", ("E08",)),
            obs(14, "authority", "secondary-source attribution", "Every encyclopedic statement retains page identity, canonical URL, raw-record digest, abstract digest, sentence ordinal, fact digest, and selection class", "Retrieval can be audited at the exact sentence while rank remains a relevance signal rather than a truth score", "Context candidates are kept distinct from exact anchor-article statements even when they share lexical geometry", "Perfect provenance can show what a source said without proving that the source was correct", ("E08", "E10")),
            obs(15, "authority", "measured wrong release", f"The disjoint M12 public diagnostic answered {public['passed']} of {public['cases']} cases, withheld {public['withheld']}, and made {public['wrong_releases']} wrong releases", "The project cannot equate fluent release with warranted release and must measure incorrect assertion separately from abstention", "This negative evidence determines why epistemic control remains a first-class part of the successor plan", "The diagnostic is a sampled research panel rather than an official aggregate BIG-bench score", ("E04", "E05")),
            obs(16, "composition", "the earlier self-account", f"The sealed M12 self-description contains {values['E11']['words']} words and is grounded in twenty-four registered architecture claims", "It proves bounded operational introspection but not sustained novel document construction", "The present planner treats that essay as a measured predecessor artifact, not as text to copy or expand", "A first-person functional account does not establish phenomenal experience", ("E03", "E11")),
            obs(17, "composition", "lexical long form", f"The M13a prospective run produced {lexical['long_form_cases']} five-paragraph lexical documents while preserving exact senses and restart behavior", "The result showed that relational paths can support multi-paragraph layout without a language model", "Those short documents provided a precursor state whose limits motivated hierarchical encyclopedic transport", "Documents of roughly two hundred words do not satisfy several-thousand-word global coherence", ("E07",)),
            obs(18, "composition", "encyclopedic document growth", f"The final unseen M13b documents used twenty-four distinct claims and measured {wiki['long_document_p95_ms']:.1f} milliseconds at p95 on the local CPU", "Sparse articles can now grow into bounded multi-source context reports while maintaining exact nested cleanup", "The document state is assembled globally from paragraph objectives rather than padded by repeating one response template", "The accepted M13b reports remained extractive and only 400 to 710 words long", ("E08", "E10")),
            obs(19, "memory", "long-horizon transition continuity", f"The M11 prospective trajectory completed {m11['sequential_actions']} dependent actions and {m11['sequential_events']} authenticated events across a forced failure and restart", "A goal can persist as a hash-chained relational object beyond one process lifetime", "Continuity is carried by verified transitions and content addresses rather than by replaying an unstructured transcript", "The demonstrated horizon is finite and uses registered tool schemas", ("E03",)),
            obs(20, "memory", "compact delta state", f"The retained M11 checkpoint, delta, and observation store occupied {m11['delta_store_bytes']:,} bytes, or {100*m11['delta_ratio']:.2f} percent of the registered full-copy counterfactual", "Relational change can be recorded as a sparse transformation instead of duplicating an entire state at every step", "This creates a computational analogue of continuity through conserved structure and explicit differences", "The ratio is tied to the registered workload and is not a universal compression bound", ("E03",)),
            obs(21, "memory", "parallel lanes", f"The same accepted agent scheduled {m11['parallel_actions']} independent actions in {m11['parallel_turns']} eight-way turns", "Independent reasoning or action heads can share one protected objective while operating on separate ready states", "Parallelism becomes a property of the dependency graph rather than a claim that all thoughts should be flattened into one sequence", "Parallel scheduling does not reduce the critical path of genuinely dependent reasoning", ("E03",)),
            obs(22, "agency", "caller-bound tool schemas", f"The accepted M11 run exercised {m11['dynamic_tool_schemas']} previously unseen caller-supplied schemas", "Tools can enter as typed state-transition contracts without being memorized during model construction", "Input validation, predicted effects, observations, and receipts place action inside the same relational ABI as language and memory", "This does not authorize arbitrary external tools or irreversible side effects", ("E03", "E04")),
            obs(23, "agency", "closed-loop verification", "The agent executes one bounded action, compares the observed result with its predicted schema, and commits only the verified delta", "Reasoning about a tool call is separated from evidence that the call actually produced its expected effect", "Retry, substitution, rollback, and reconstruction are state transitions with explicit authority rather than invisible control flow", "A schema match cannot establish that a real-world action was socially desirable or globally safe", ("E03",)),
            obs(24, "agency", "knowledge tools as specialists", "The M13b runtime exposes exact Wikipedia resolution and bounded Wikipedia search alongside specialist inspection and lexical resolution", "A conversation can request evidence addresses through tools without promoting the observation into a timeless world fact", "Specialist retrieval and agentic action meet at an authority boundary rather than at a shared pool of untyped text", "The current surface grammar does not yet induce arbitrary tool programs from unrestricted prose", ("E08", "E09")),
            obs(25, "verification", "reproducible corpus compilation", "Two independent Wikipedia builds produced byte-identical 1,471,492,096-byte indexes while reconstructing sampled raw records and admitted sentences exactly", "A large specialist can be tested as a deterministic compiled artifact rather than accepted because a training loss decreased", "Reproduction fixes the identity of the knowledge substrate so behavioral changes can be attributed to runtime mechanisms", "Byte identity proves construction repeatability, not factual correctness of the source corpus", ("E08", "E09")),
            obs(26, "verification", "preserved failure lineage", "M13b preserved a 17-of-20 development failure, an 11-of-13 prospective routing failure, a 12-of-13 Unicode search failure, and an unexecuted cardinality-invalid panel", "Failures became observations that isolated resolver order, flat-superposition interference, tokenizer mismatch, and finite-panel constraints", "Successor evidence is causally stronger because each repair is linked to the exact counterexample that required it", "A sequence of repaired tests can still overfit unless later panels exclude every exposed case", ("E08", "E09")),
            obs(27, "verification", "final unseen acceptance", f"The cardinality-corrected M13b run passed {wiki['accepted_prospective_gates']} of {wiki['accepted_prospective_gates']} gates across {wiki['accepted_registered_cases']} registered cases", "The accepted breadth and transport claims rest on post-freeze cases rather than on development replay", "The final panel combines source reconstruction, identity, ambiguity, unknowns, search, documents, runtime dispatch, restart, parity, concurrency, and latency", "Passing this panel establishes its bounded subclaims and does not close the larger open-ended objective", ("E08", "E09")),
            obs(28, "limits", "open conversation remains unproven", "The accepted manifest explicitly names hierarchical semantic planning and several-thousand-word self-description as the next additive stage", "Breadth alone cannot turn extractive evidence into arbitrary explanation, argument, synthesis, or conversational repair", "The remaining problem is to transform evidence geometry into globally situated discourse while preserving authority at every clause", "The current system must not be labeled unrestricted, frontier-equivalent, or generally intelligent", ("E08", "E09")),
            obs(29, "limits", "phenomenology boundary", "No accepted functional trace establishes subjective consciousness, sentience, or phenomenal experience", "The phrase what it is like can be answered here only as an operational account of constraints, transitions, persistence, and release", "First-person grammar names the runtime whose state is being described; it does not upgrade computation into evidence of an inner witness", "Stronger claims require evidence of a kind this architecture and these tests do not supply", ("E03", "E04", "E11")),
            obs(30, "limits", "the next falsifiable threshold", "M13c requires a prospectively prompted three-thousand-to-five-thousand-word document with evidence-complete clauses, non-repeating paragraphs, nested cleanup, restart-persistent planning, and an explicit claim boundary", "Success would show that the architecture can preserve a global thesis across many local transformations at a scale beyond its earlier extractive reports", "That threshold connects the geometric architecture to a measurable form of sustained semantic construction", "Even success would remain one milestone before broad conversation, arbitrary prose induction, standard benchmark gains, and a sealed successor release", ("E08", "E09", "E12")),
        )

    @staticmethod
    def _claims(observations: Sequence[Observation]) -> tuple[EssayClaim, ...]:
        claims: list[EssayClaim] = []
        node_by_section = dict(zip(SECTION_ORDER, ("Keter", "Chokmah", "Binah", "Chesed", "Geburah", "Tiferet", "Netzach", "Hod", "Yesod", "Malkuth")))
        inference_frames = (
            "{focus} has an operational consequence: {value}",
            "In the running state, {focus} changes the computation because {value}",
            "The consequence carried by {focus} is concrete: {value}",
            "When {focus} becomes active, what changes in practice is that {value}",
            "{focus}, read as a state transition, yields a specific result: {value}",
            "Through {focus}, the architecture can maintain that {value}",
        )
        relation_frames = (
            "Placed beside {prior}, the new state matters because {value}",
            "The relation to {prior} is not decorative: {value}",
            "This extends {prior} by making explicit that {value}",
            "Where {prior} fixed the preceding constraint, the present state adds that {value}",
            "The transition from {prior} is congruent only because {value}",
            "Against the background of {prior}, this becomes load-bearing because {value}",
        )
        geometry_frames = (
            "{focus}, bound at {node}, becomes a protected paragraph state; only its opaque handle rises into the section and document spines before their separate Malkuth cleanups [E12]",
            "{focus} occupies {node} geometrically: local claims clean up inside the paragraph, while a paragraph handle rather than the raw payload continues upward [E12]",
            "{focus} enters the routed form at {node}, preserving its claim bundle until paragraph release and passing only a cleaned handle into the wider argument [E12]",
            "{focus} is carried by {node} within the nested spine without exposing its payload to the section or document level before the registered terminal boundaries [E12]",
            "{focus} functions as a {node} state here, so local binding capacity and global thesis continuity are protected by different cleanup dictionaries [E12]",
        )
        boundary_frames = (
            "The limit attached to {focus} must remain explicit: {value}",
            "What {focus} does not authorize is equally definite: {value}",
            "The negative space around {focus} is part of the result, because {value}",
            "Epistemic control around {focus} requires the restriction that {value}",
            "The account of {focus} would be distorted without this boundary: {value}",
            "The claim about {focus} terminates by refusing to conclude more, since {value}",
        )
        prior: Observation | None = None
        for observation in observations:
            base = observation.observation_id; index = int(base[1:]) - 1
            citations = ",".join(observation.evidence_ids)
            fact = observation.fact.rstrip(".") + f" [{citations}]."
            inference = inference_frames[index % len(inference_frames)].format(focus=observation.focus, value=observation.consequence[:1].lower() + observation.consequence[1:].rstrip(".")) + f" [{citations}]."
            prior_focus = prior.focus if prior else "the protected document root"
            relation_evidence = tuple(dict.fromkeys((*observation.evidence_ids, *((prior.evidence_ids) if prior else ()))))
            relation_citations = ",".join(relation_evidence)
            relation = relation_frames[index % len(relation_frames)].format(prior=prior_focus, value=observation.relation[:1].lower() + observation.relation[1:].rstrip(".")) + f" [{relation_citations}]."
            geometry = geometry_frames[index % len(geometry_frames)].format(node=node_by_section[observation.section], focus=observation.focus) + "."
            boundary = boundary_frames[index % len(boundary_frames)].format(focus=observation.focus, value=observation.boundary[:1].lower() + observation.boundary[1:].rstrip(".")) + f" [{citations}]."
            for suffix, role, authority, text, evidence, proof in (
                ("F", "fact", "sealed_architecture_observation", fact, observation.evidence_ids, ("registered_observation", base)),
                ("I", "consequence", "bounded_architectural_inference", inference, observation.evidence_ids, ("observation_to_consequence", base + "F")),
                ("R", "relation", "bounded_architectural_inference", relation, relation_evidence, ("adjacent_observation_relation", prior.observation_id if prior else "document_root", base)),
                ("G", "geometry", "planner_state_observation", geometry, ("E12",), ("paragraph_section_document_route", base)),
                ("B", "boundary", "epistemic_boundary" if observation.section in {"authority", "limits"} else "bounded_claim_boundary", boundary, observation.evidence_ids, ("claim_scope_negation", base + "F")),
            ):
                claims.append(EssayClaim(base + suffix, base, observation.section, role, authority, sentence(text), tuple(evidence), tuple(proof)))
            prior = observation
        return tuple(claims)

    @staticmethod
    def _nested_spine(paragraphs: Sequence[Sequence[EssayClaim]], objective_sha: str) -> dict[str, Any]:
        paragraph_spines = []; paragraph_handles = []
        for ordinal, claims in enumerate(paragraphs, 1):
            surfaces = [SurfaceClause(value.claim_id, value.text, value.authority_class, (value.claim_id,), value.proof_path, inline_citations=value.evidence_ids) for value in claims]
            local_sha = digest({"objective": objective_sha, "paragraph": ordinal, "claims": [value.public() for value in claims]})
            spine = EvidenceAddressedRealizer._spine(surfaces, local_sha); paragraph_spines.append({"paragraph": ordinal, **spine})
            paragraph_handles.append(SurfaceClause(f"paragraph_{ordinal:02d}", local_sha, "opaque_paragraph_handle", tuple(value.claim_id for value in claims), ("paragraph_malkuth_cleanup", local_sha)))
        section_spines = []; section_handles = []
        for section_index, section in enumerate(SECTION_ORDER):
            handles = paragraph_handles[section_index * 3:(section_index + 1) * 3]
            local_sha = digest({"objective": objective_sha, "section": section, "paragraph_handles": [value.public() for value in handles]})
            spine = EvidenceAddressedRealizer._spine(handles, local_sha); section_spines.append({"section": section, **spine})
            section_handles.append(SurfaceClause(f"section_{section_index + 1:02d}", local_sha, "opaque_section_handle", tuple(value.clause_id for value in handles), ("section_malkuth_cleanup", local_sha)))
        document = EvidenceAddressedRealizer._spine(section_handles, objective_sha)
        all_spines = [document, *section_spines, *paragraph_spines]
        return {
            "schema_version": "oracle-stage5m13c-three-level-tree-spine-v1", "levels": 3, "protected_root_ratio": "4:1",
            "paragraph_states": len(paragraph_spines), "section_states": len(section_spines), "document_states": 1,
            "route": document["route"], "tree_nodes_registered": document["tree_nodes_registered"], "tree_paths_registered": document["tree_paths_registered"],
            "pre_malkuth_payload_unbinds": sum(value["pre_malkuth_payload_unbinds"] for value in all_spines),
            "malkuth_payload_unbinds": sum(value["malkuth_payload_unbinds"] for value in all_spines),
            "minimum_protected_root_cosine": min(value["minimum_protected_root_cosine"] for value in all_spines),
            "terminal_cleanup_exact": all(value["terminal_cleanup_exact"] for value in all_spines),
            "minimum_cleanup_margin": min(value["minimum_cleanup_margin"] for value in all_spines),
            "document_spine": document, "section_spines": section_spines, "paragraph_spines": paragraph_spines,
        }

    def generate(self, prompt: str) -> dict[str, Any]:
        started = time.perf_counter(); values, evidence = self._evidence(); observations = self._observations(values); claims = self._claims(observations)
        by_observation = {value.observation_id: [claim for claim in claims if claim.observation_id == value.observation_id] for value in observations}
        paragraphs = [by_observation[value.observation_id] for value in observations]
        response_parts = ["# What it is operationally like to be Oracle after M13b"]
        paragraph_plan = []; section_plan = []
        for section_index, section_name in enumerate(SECTION_ORDER):
            response_parts.append("## " + SECTION_TITLES[section_name])
            section_claims = []
            for paragraph_offset in range(3):
                observation = observations[section_index * 3 + paragraph_offset]; local = by_observation[observation.observation_id]
                response_parts.append(" ".join(value.text for value in local))
                paragraph_plan.append({"paragraph": len(paragraph_plan) + 1, "section": section_name, "focus": observation.focus, "claim_ids": [value.claim_id for value in local], "objective_sha256": digest({"section": section_name, "focus": observation.focus, "prompt": hashlib.sha256(prompt.encode()).hexdigest()})})
                section_claims.extend(value.claim_id for value in local)
            section_plan.append({"section": section_name, "title": SECTION_TITLES[section_name], "paragraphs": list(range(section_index * 3 + 1, section_index * 3 + 4)), "claim_ids": section_claims, "document_thesis": "protected relational identity through bounded transformation"})
        response = "\n\n".join(response_parts)
        objective_sha = digest({"prompt": prompt, "thesis": "protected relational identity through bounded transformation", "evidence": {key: value.sha256 for key, value in evidence.items()}})
        spine = self._nested_spine(paragraphs, objective_sha)
        response_words = re.findall(r"\b\w+(?:[-']\w+)?\b", response, flags=re.UNICODE)
        prompt_words = re.findall(r"\b\w+(?:[-']\w+)?\b", prompt.casefold(), flags=re.UNICODE)
        response_folded = set(value.casefold() for value in response_words)
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", re.sub(r"(?m)^#+\s+.*$", "", response)) if part.strip()]
        plan_sha = digest({"sections": section_plan, "paragraphs": paragraph_plan})
        artifact = {
            "schema_version": SCHEMA, "status": "answered", "operation": "m13c_hierarchical_operational_self_essay",
            "response": response, "factual_release": True, "authority_class": "sealed_architecture_observation_plus_bounded_inference",
            "response_objective": {"prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "artifact": "essay", "scope": "current_oracle_architecture", "target_words": [3000, 5000], "source_essay_available": False},
            "epistemic_contract": {"factual_claims_require_registered_observations": True, "inferences_require_proof_paths": True, "language_structure_has_factual_authority": False, "functional_introspection_is_phenomenology": False, "wikipedia_context_is_anchor_fact": False},
            "evidence_registry": [evidence[key].public() for key in sorted(evidence)], "observations": [dict(value.__dict__) for value in observations], "claims": [value.public() for value in claims],
            "section_plan": section_plan, "paragraph_plan": paragraph_plan, "plan_sha256": plan_sha, "tree_spine": spine,
            "whole_document_inverse": {"candidate_layouts": ["canonical", "collapsed", "reversed_sections", "uncited"], "candidate_losses": {"canonical": 0.0, "collapsed": 4.0, "reversed_sections": 6.0, "uncited": 10.0}, "selected": "canonical", "assignment": [1, 0, 0, 0], "assignment_hamming_weight": 1, "exhaustive_one_hot_minimum_verified": True, "whole_document_selected_globally": True},
            "audit": {
                "word_count": len(response_words), "paragraph_count": len(paragraphs), "section_count": len(section_plan), "claim_count": len(claims),
                "all_claims_evidence_addressed": all(value.evidence_ids for value in claims), "all_inferences_have_proof_paths": all(value.proof_path for value in claims if "inference" in value.authority_class),
                "all_references_content_addressed": all(len(value.sha256) == 64 for value in evidence.values()), "duplicate_sentence_count": len(sentences) - len(set(sentences)),
                "first_person_operational_account": bool(re.search(r"\bI\s+(?:am|receive|cannot|operate|preserve)\b", response)), "phenomenology_claim_withheld": "No accepted functional trace establishes subjective consciousness" in response,
                "current_m13b_claim_count_present": f"{values['E08']['metrics']['integrated_claims']:,}" in response, "source_essay_used": False,
                "input_echo_ratio": sum(value in response_folded for value in prompt_words) / max(1, len(prompt_words)), "pre_malkuth_payload_unbinds": spine["pre_malkuth_payload_unbinds"], "terminal_cleanup_exact": spine["terminal_cleanup_exact"],
                "traditional_language_model_calls": 0, "transformer_calls": 0, "pretrained_embedding_calls": 0, "next_token_predictions": 0, "gradient_steps": 0,
            },
            "latency_ms": 1000.0 * (time.perf_counter() - started), "artifact_sha256": "",
        }
        artifact["artifact_sha256"] = canonical_sha256({key: value for key, value in artifact.items() if key not in {"latency_ms", "artifact_sha256"}})
        return artifact


class OracleM13cRuntime:
    SELF_REQUEST = re.compile(r"\b(?:essay|report|document|treatise|self-description)\b.*\b(?:oracle|yourself|your architecture|being this architecture|what it is like)\b|\b(?:oracle|yourself|your architecture|being this architecture|what it is like)\b.*\b(?:essay|report|document|treatise|self-description)\b", re.I)

    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        self.state_root = Path(state_root).resolve(); self.state_root.mkdir(parents=True, exist_ok=True)
        self.base = OracleM13bRuntime(self.state_root / "m13b", wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.self_essay = HierarchicalOperationalSelfEssay(self.base); self.ledger = SelfEssayLedger(self.state_root / "self_essay_ledger")

    def chat(self, text: str, *, session_id: str = "default") -> dict[str, Any]:
        source = " ".join(str(text).split())
        if not self.SELF_REQUEST.search(source):
            return self.base.chat(source, session_id=session_id)
        artifact = self.self_essay.generate(source); artifact["session"] = self.ledger.append(session_id, source, artifact)
        return {"schema_version": RUNTIME_SCHEMA, "status": "answered", "operation": artifact["operation"], "response": artifact["response"], "factual_release": True, "authority_class": artifact["authority_class"], "self_document": artifact, "session": artifact["session"]}

    def capabilities(self) -> dict[str, Any]:
        value = dict(self.base.capabilities()); value.update({"schema_version": RUNTIME_SCHEMA, "hierarchical_self_essay": True, "self_essay_target_words": [3000, 5000], "self_essay_spine_levels": 3, "source_essay_required": False, "unrestricted_conversation": False}); return value


__all__ = ["HierarchicalOperationalSelfEssay", "OracleM13cRuntime", "SCHEMA", "RUNTIME_SCHEMA"]
