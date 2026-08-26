#!/usr/bin/env python3
"""Sense-preserving WordNet specialist and Oracle M13 hot-load runtime."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
RELEASE_SRC = ROOT / "wander-release" / "oracle-relational-v3-hf-v1.0.1-release" / "src"
if str(RELEASE_SRC) not in sys.path:
    sys.path.insert(0, str(RELEASE_SRC))

from oracle_relational_v3.oracle_10d_resolution_state import canonical_sha256
from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import (
    EvidenceAddressedRealizer,
    RealizationRequest,
    SurfaceClause,
)
from oracle_relational_v3.stage5m11a_schema_native_long_horizon_agent import SchemaTool, SchemaToolRegistry
from oracle_relational_v3.stage5m12a_portable_successor_runtime import DEFAULT_DATA_ROOT, build_default_tool_registry
from oracle_relational_v3.stage5m12d_zero_argument_tool_successor import OracleRuntime as M12OracleRuntime


SCHEMA = "oracle-stage5m13a-wordnet-specialist-v3"
INDEX_SCHEMA = "oracle-stage5m13a-wordnet-sqlite-v3"
RUNTIME_SCHEMA = "oracle-stage5m13a-broad-lexical-runtime-v3"
SESSION_SCHEMA = "oracle-stage5m13a-lexical-session-v1"

INVERSE = {
    "subclass_of": "has_subtype",
    "instance_of": "has_instance",
    "has_part": "part_of",
    "has_member": "member_of",
    "made_of": "substance_of",
    "entails": "entailed_by",
    "causes": "caused_by",
    "similar_to": "similar_to",
    "related_to": "related_to",
    "has_attribute": "attribute_of",
    "verb_group_with": "verb_group_with",
    "topic_domain": "domain_of",
    "region_domain": "regional_domain_of",
    "usage_domain": "usage_domain_of",
}

PREDICATE_PRIORITY = {
    "defined_as": 0,
    "subclass_of": 1,
    "instance_of": 1,
    "has_subtype": 2,
    "has_instance": 2,
    "similar_to": 3,
    "related_to": 3,
    "has_attribute": 4,
    "has_part": 4,
    "has_member": 4,
    "made_of": 4,
    "entails": 5,
    "causes": 5,
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_alias(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold().replace("_", " ")
    return " ".join(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).split())


def validate_build(root: Path | str, *, deep: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != "compiled":
        raise ValueError("unsupported_wordnet_specialist")
    if digest(manifest["semantic_identity"]) != manifest.get("semantic_identity_sha256"):
        raise ValueError("wordnet_specialist_identity_changed")
    for relative, expected in manifest["files"].items():
        path = root / relative
        if not path.is_file() or sha_file(path) != expected:
            raise ValueError(f"wordnet_specialist_artifact_changed:{relative}")
    inventory = json.loads((root / "corpus_inventory.json").read_text(encoding="utf-8"))
    inventory_body = {key: value for key, value in inventory.items() if key != "semantic_identity_sha256"}
    if digest(inventory_body) != inventory.get("semantic_identity_sha256"):
        raise ValueError("wordnet_corpus_inventory_changed")
    if inventory.get("evaluation_data_read") or inventory.get("evaluation_inputs"):
        raise ValueError("evaluation_data_must_not_enter_specialist")
    uri = (root / "wordnet_specialist.sqlite3").as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    metadata = {key: json.loads(value) for key, value in connection.execute("SELECT key,value FROM metadata")}
    if metadata.get("index_schema") != INDEX_SCHEMA or metadata != manifest["metrics"]:
        raise ValueError("wordnet_index_metadata_changed")
    if deep:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("wordnet_index_integrity_failed")
        observed = {
            "synsets": connection.execute("SELECT COUNT(*) FROM synset").fetchone()[0],
            "definition_claims": connection.execute("SELECT COUNT(*) FROM synset").fetchone()[0],
            "relation_claims": connection.execute("SELECT COUNT(*) FROM relation").fetchone()[0],
            "alias_rows": connection.execute("SELECT COUNT(*) FROM alias").fetchone()[0],
        }
        for key, value in observed.items():
            if value != metadata[key]:
                raise ValueError(f"wordnet_index_count_changed:{key}")
        dangling = connection.execute(
            "SELECT COUNT(*) FROM relation r LEFT JOIN synset s ON r.subject_id=s.synset_id "
            "LEFT JOIN synset o ON r.object_id=o.synset_id WHERE s.synset_id IS NULL OR o.synset_id IS NULL"
        ).fetchone()[0]
        if dangling:
            raise ValueError("wordnet_index_has_dangling_relations")
    connection.close()
    return manifest


@dataclass(frozen=True)
class LexicalClaim:
    claim_id: str
    subject_id: str
    subject_surface: str
    predicate: str
    object_kind: str
    object_value: str
    object_surface: str
    authority_class: str
    proof_path: tuple[str, ...]

    def public(self) -> dict[str, Any]:
        value = dict(self.__dict__)
        value["proof_path"] = list(self.proof_path)
        return value


class WordNetSpecialist:
    def __init__(self, build_root: Path | str, *, deep_validate: bool = False):
        self.root = Path(build_root).resolve()
        self.manifest = validate_build(self.root, deep=deep_validate)
        uri = (self.root / "wordnet_specialist.sqlite3").as_uri() + "?mode=ro&immutable=1"
        self.connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.source = self.manifest["source"]

    def close(self) -> None:
        self.connection.close()

    def _entity(self, identity: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT synset_id,pos,offset,canonical_label,definition,lexname,definition_claim_id "
            "FROM synset WHERE synset_id=?", (identity,)
        ).fetchone()

    @staticmethod
    def _candidate(value: sqlite3.Row) -> dict[str, Any]:
        result = {
            "entity_id": value["synset_id"],
            "pos": value["pos"],
            "canonical_label": value["canonical_label"],
            "definition": value["definition"],
            "lexname": value["lexname"],
        }
        if "tag_count" in value.keys():
            result["tag_count"] = int(value["tag_count"])
        return result

    def resolve(self, query: str, *, pos: str | None = None, allow_dominant: bool = True) -> dict[str, Any]:
        source = " ".join(str(query).split())
        if re.fullmatch(r"wordnet:[nvars]:\d{8}", source.casefold()):
            value = self._entity(source.casefold())
            return ({"status": "resolved", "method": "exact_synset_id", **self._candidate(value)}
                    if value else {"status": "unresolved", "method": "unknown_synset_id", "query": source})
        normalized = normalize_alias(source)
        if not normalized:
            return {"status": "unresolved", "method": "empty_alias", "query": source}
        parameters: list[Any] = [normalized]
        constraint = ""
        if pos:
            constraint = " AND s.pos=?"
            parameters.append(pos)
        rows = self.connection.execute(
            "SELECT s.synset_id,s.pos,s.offset,s.canonical_label,s.definition,s.lexname,s.definition_claim_id,a.tag_count "
            "FROM alias a JOIN synset s ON a.synset_id=s.synset_id WHERE a.normalized_alias=?" + constraint +
            " ORDER BY a.tag_count DESC,s.pos,s.offset", parameters,
        ).fetchall()
        if len(rows) == 1:
            return {"status": "resolved", "method": "unique_exact_alias" if pos is None else "unique_contextual_pos_alias", "query": source, **self._candidate(rows[0])}
        if rows:
            first = int(rows[0]["tag_count"]); second = int(rows[1]["tag_count"])
            if allow_dominant and first >= 3 and (second == 0 or first >= 2 * second):
                return {
                    "status": "resolved", "method": "dominant_wordnet_tagged_sense", "query": source,
                    "dominance_rule": "top_tag_count_at_least_3_and_at_least_twice_runner_up",
                    "alternative_count": len(rows) - 1, **self._candidate(rows[0]),
                }
            return {
                "status": "ambiguous", "method": "exact_alias_collision", "query": source,
                "candidate_count": len(rows), "candidates": [self._candidate(value) for value in rows],
            }
        return {"status": "unresolved", "method": "no_exact_authenticated_alias", "query": source}

    def aliases(self, entity_id: str) -> list[str]:
        return [value[0] for value in self.connection.execute(
            "SELECT alias_surface FROM alias WHERE synset_id=? ORDER BY normalized_alias,alias_surface", (entity_id,)
        )]

    def _definition(self, entity: sqlite3.Row) -> LexicalClaim:
        return LexicalClaim(
            entity["definition_claim_id"], entity["synset_id"], entity["canonical_label"], "defined_as",
            "literal", entity["definition"], entity["definition"], "authenticated_fact",
            ("wordnet_synset_definition", entity["synset_id"], self.source["sha256"]),
        )

    def _edge(self, row: sqlite3.Row, *, inverse: bool) -> LexicalClaim:
        if inverse:
            subject_id = row["object_id"]
            subject_surface = row["object_label"]
            predicate = INVERSE[row["predicate"]]
            object_id = row["subject_id"]
            object_surface = row["subject_label"]
            identity = "inverse_" + row["claim_id"]
            authority = "derived_relation"
            proof = ("inverse_of_authenticated_relation", row["claim_id"], row["subject_id"], row["predicate"], row["object_id"])
        else:
            subject_id = row["subject_id"]
            subject_surface = row["subject_label"]
            predicate = row["predicate"]
            object_id = row["object_id"]
            object_surface = row["object_label"]
            identity = row["claim_id"]
            authority = "authenticated_fact"
            proof = ("wordnet_synset_relation", row["claim_id"], self.source["sha256"])
        return LexicalClaim(identity, subject_id, subject_surface, predicate, "entity", object_id, object_surface, authority, proof)

    def claims(self, entity_id: str, *, limit: int = 24, depth: int = 1) -> list[LexicalClaim]:
        root = self._entity(entity_id)
        if root is None:
            return []
        selected: list[LexicalClaim] = []
        seen_claims: set[str] = set()
        seen_entities = {entity_id}
        frontier = [(entity_id, 0)]
        while frontier and len(selected) < limit:
            current, level = frontier.pop(0)
            entity = self._entity(current)
            if entity is None:
                continue
            definition = self._definition(entity)
            if definition.claim_id not in seen_claims:
                selected.append(definition); seen_claims.add(definition.claim_id)
            outgoing = self.connection.execute(
                "SELECT r.subject_id,r.predicate,r.object_id,r.claim_id,ss.canonical_label AS subject_label," 
                "os.canonical_label AS object_label FROM relation r JOIN synset ss ON ss.synset_id=r.subject_id "
                "JOIN synset os ON os.synset_id=r.object_id WHERE r.subject_id=?", (current,)
            ).fetchall()
            incoming = self.connection.execute(
                "SELECT r.subject_id,r.predicate,r.object_id,r.claim_id,ss.canonical_label AS subject_label," 
                "os.canonical_label AS object_label FROM relation r JOIN synset ss ON ss.synset_id=r.subject_id "
                "JOIN synset os ON os.synset_id=r.object_id WHERE r.object_id=?", (current,)
            ).fetchall()
            candidates = [self._edge(value, inverse=False) for value in outgoing]
            candidates.extend(self._edge(value, inverse=True) for value in incoming)
            candidates.sort(key=lambda value: (PREDICATE_PRIORITY.get(value.predicate, 20), value.predicate, value.object_surface.casefold(), value.claim_id))
            for claim in candidates:
                if claim.claim_id in seen_claims:
                    continue
                selected.append(claim); seen_claims.add(claim.claim_id)
                if level < depth and claim.object_kind == "entity" and claim.object_value not in seen_entities:
                    seen_entities.add(claim.object_value); frontier.append((claim.object_value, level + 1))
                if len(selected) >= limit:
                    break
        return selected[:limit]

    @staticmethod
    def _sentence(claim: LexicalClaim, citation: str) -> str:
        subject = claim.subject_surface[:1].upper() + claim.subject_surface[1:]
        obj = claim.object_surface
        templates = {
            "defined_as": "{s} is defined as {o}",
            "subclass_of": "{s} is a kind of {o}",
            "instance_of": "{s} is an instance of {o}",
            "has_subtype": "{s} includes the subtype {o}",
            "has_instance": "{s} includes the instance {o}",
            "has_part": "{s} has {o} as a part",
            "part_of": "{s} is part of {o}",
            "has_member": "{s} has {o} as a member",
            "member_of": "{s} is a member of {o}",
            "made_of": "{s} is made of {o}",
            "substance_of": "{s} is a substance of {o}",
            "entails": "{s} entails {o}",
            "entailed_by": "{s} is entailed by {o}",
            "causes": "{s} causes {o}",
            "caused_by": "{s} is caused by {o}",
            "similar_to": "{s} is similar to {o}",
            "related_to": "{s} is lexically related to {o}",
            "has_attribute": "{s} has the attribute {o}",
            "attribute_of": "{s} is an attribute of {o}",
            "verb_group_with": "{s} belongs to a verb group with {o}",
            "topic_domain": "{s} belongs to the topic domain {o}",
            "domain_of": "{s} is the topic domain of {o}",
            "region_domain": "{s} belongs to the region domain {o}",
            "regional_domain_of": "{s} is the region domain of {o}",
            "usage_domain": "{s} belongs to the usage domain {o}",
            "usage_domain_of": "{s} is the usage domain of {o}",
        }
        return templates.get(claim.predicate, "{s} {p} {o}").format(s=subject, p=claim.predicate.replace("_", " "), o=obj).rstrip(". ") + f" [{citation}]."

    def realize(self, entity_id: str, *, artifact: str = "paragraph", paragraphs: int = 3) -> dict[str, Any]:
        started = time.perf_counter()
        limits = {"sentence": 1, "paragraph": 7, "essay": 18, "paper": 24}
        if artifact not in limits:
            raise ValueError("unsupported lexical artifact")
        root = self._entity(entity_id)
        if root is None:
            return {"schema_version": RUNTIME_SCHEMA, "status": "withheld", "reason": "unknown_synset", "response": "I need an exact authenticated lexical sense before I can answer.", "factual_release": False}
        claims = self.claims(entity_id, limit=limits[artifact], depth=2 if artifact in {"essay", "paper"} else 1)
        references: list[dict[str, Any]] = []
        clauses: list[SurfaceClause] = []
        if artifact != "sentence":
            clauses.append(SurfaceClause(
                "synthesis_intro", f"This account follows the authenticated lexical graph for {root['canonical_label']} ({entity_id}).",
                "inferred", tuple(value.claim_id for value in claims), ("select_exact_synset", entity_id),
            ))
        for index, claim in enumerate(claims, 1):
            citation = f"W{index}"
            references.append({
                "citation_id": citation, "claim_id": claim.claim_id, "source_record_id": claim.subject_id,
                "source_document_id": "princeton_wordnet_3_0", "source_document_sha256": self.source["sha256"],
                "source_url": self.source["data_access_url"], "license": self.source["license_name"],
                "proof_path": list(claim.proof_path),
            })
            clauses.append(SurfaceClause(
                f"claim_{index:02d}", self._sentence(claim, citation), claim.authority_class,
                (claim.claim_id,), claim.proof_path, inline_citations=(citation,),
            ))
        if artifact != "sentence":
            clauses.append(SurfaceClause(
                "synthesis_boundary",
                "The account is bounded to this recorded lexical graph; it does not convert lexical relations into unstored encyclopedic facts.",
                "inferred", tuple(value.claim_id for value in claims), ("bounded_wordnet_graph_closure", entity_id),
            ))
        request = RealizationRequest("wordnet", (entity_id,), artifact, "explain", max(3, min(6, paragraphs)))
        groups = EvidenceAddressedRealizer._partition(clauses, request)
        response, inverse = EvidenceAddressedRealizer._layout(groups, request)
        if artifact == "paper":
            response = "## Sense-addressed lexical analysis\n\n" + response + "\n\n## Source\n\nPrinceton WordNet 3.0, archive SHA-256 `" + self.source["sha256"] + "`."
        spine = EvidenceAddressedRealizer._spine(clauses, canonical_sha256({"entity_id": entity_id, "artifact": artifact, "paragraphs": paragraphs}))
        value = {
            "schema_version": RUNTIME_SCHEMA, "status": "answered", "reason": "exact_sense_graph_realized",
            "response": response, "factual_release": bool(claims), "entity": self._candidate(root),
            "claims": [claim.public() for claim in claims], "clauses": [clause.public() for clause in clauses],
            "references": references, "paragraph_plan": [[clause.clause_id for clause in group] for group in groups],
            "tree_spine": spine, "whole_answer_inverse": inverse,
            "audit": {
                "sense_identity_preserved": True, "all_released_claims_evidence_addressed": all(value.proof_path for value in claims),
                "all_derived_relations_have_proof_paths": all(value.proof_path for value in claims if value.authority_class == "derived_relation"),
                "pre_malkuth_payload_unbinds": spine["pre_malkuth_payload_unbinds"],
                "terminal_cleanup_exact": spine["terminal_cleanup_exact"],
                "traditional_language_model_calls": 0, "transformer_calls": 0,
                "pretrained_embedding_calls": 0, "next_token_predictions": 0, "gradient_steps": 0,
            },
            "latency_ms": 1000.0 * (time.perf_counter() - started),
        }
        value["artifact_sha256"] = canonical_sha256({key: item for key, item in value.items() if key not in {"latency_ms", "artifact_sha256"}})
        return value


class LexicalSessionStore:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.root / (hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json")

    def load(self, session_id: str) -> dict[str, Any]:
        path = self._path(session_id)
        if not path.exists():
            return {"schema_version": SESSION_SCHEMA, "turns": [], "last": None}
        value = json.loads(path.read_text(encoding="utf-8")); prior = "0" * 64
        for ordinal, turn in enumerate(value["turns"]):
            body = {key: item for key, item in turn.items() if key != "turn_sha256"}
            if turn["ordinal"] != ordinal or turn["previous_sha256"] != prior or digest(body) != turn["turn_sha256"]:
                raise ValueError("lexical_session_chain_changed")
            prior = turn["turn_sha256"]
        return value

    def append(self, session_id: str, text: str, result: Mapping[str, Any], state: Mapping[str, Any] | None) -> dict[str, Any]:
        value = self.load(session_id); prior = value["turns"][-1]["turn_sha256"] if value["turns"] else "0" * 64
        body = {
            "ordinal": len(value["turns"]), "previous_sha256": prior,
            "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "result_sha256": canonical_sha256({key: item for key, item in result.items() if key not in {"latency_ms", "session"}}),
            "state": dict(state) if state else None,
        }
        turn = {**body, "turn_sha256": digest(body)}; value["turns"].append(turn)
        if state:
            value["last"] = dict(state)
        path = self._path(session_id); temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
        return {"turns": len(value["turns"]), "head_sha256": turn["turn_sha256"], "hash_chain_valid": True}


class WordNetConversation:
    DOCUMENT = re.compile(r"^\s*(?:please\s+)?(?:write|compose|draft|produce|create|give\s+me)\s+(?:a\s+|an\s+)?(?:(?P<count>[3-6])[-\s]+paragraph\s+)?(?P<artifact>essay|paper|paragraph|sentence)\s+(?:about|on|explaining|concerning)\s+(?P<topic>.+?)\s*[?.!]*$", re.I)
    QUESTION = re.compile(r"^\s*(?:(?:what|who)\s+(?:is|are)|tell\s+me\s+about|describe|explain)\s+(?P<topic>.+?)\s*[?.!]*$", re.I)
    COMPARE = re.compile(r"^\s*compare\s+(?P<left>.+?)\s+(?:with|to|versus|vs\.?|and)\s+(?P<right>.+?)\s*[?.!]*$", re.I)
    MORE = re.compile(r"^\s*(?:tell\s+me\s+more|go\s+on|continue|expand(?:\s+that)?|say\s+more)\s*[?.!]*$", re.I)

    def __init__(self, specialist: WordNetSpecialist, state_root: Path | str):
        self.specialist = specialist
        self.sessions = LexicalSessionStore(Path(state_root) / "wordnet_sessions")

    @staticmethod
    def _clean_topic(value: str) -> str:
        value = re.sub(r"^(?:the|a|an)\s+", "", value.strip(), flags=re.I)
        return re.sub(r"\s+(?:briefly|please|in detail)$", "", value, flags=re.I).strip(" .?!")

    def _resolve_or_return(self, topic: str) -> tuple[str | None, dict[str, Any] | None]:
        cleaned = self._clean_topic(topic)
        # Definition, exposition, and document constructions put the topic in a
        # nominal slot.  Prefer noun senses without erasing other POS records;
        # fall back to the complete alias set only when no noun address exists.
        resolved = self.specialist.resolve(cleaned, pos="n")
        if resolved["status"] == "unresolved":
            resolved = self.specialist.resolve(cleaned)
        if resolved["status"] == "resolved":
            return str(resolved["entity_id"]), None
        if resolved["status"] == "ambiguous":
            choices = "; ".join(f"{value['entity_id']} — {value['definition']}" for value in resolved["candidates"][:8])
            return None, {
                "schema_version": RUNTIME_SCHEMA, "status": "clarification", "operation": "wordnet_sense_clarification",
                "response": f"That exact word has {resolved['candidate_count']} authenticated senses. Specify a synset identifier or intended sense: {choices}",
                "factual_release": False, "resolution": resolved,
            }
        return None, {
            "schema_version": RUNTIME_SCHEMA, "status": "unresolved", "operation": "wordnet_topic_unresolved",
            "response": "I found no exact authenticated WordNet topic address for that wording.",
            "factual_release": False, "resolution": resolved,
        }

    def chat(self, text: str, *, session_id: str = "default") -> dict[str, Any]:
        started = time.perf_counter(); source = " ".join(str(text).split()); prior = self.sessions.load(session_id).get("last")
        artifact = "paragraph"; paragraphs = 3; topics: list[str] = []
        match = self.DOCUMENT.match(source)
        if match:
            artifact = match.group("artifact").casefold(); paragraphs = int(match.group("count") or 3); topics = [match.group("topic")]
        elif (match := self.COMPARE.match(source)):
            topics = [match.group("left"), match.group("right")]
        elif (match := self.QUESTION.match(source)):
            artifact = "sentence" if source.casefold().startswith(("what is", "what are", "who is", "who are")) else "paragraph"
            topics = [match.group("topic")]
        elif self.MORE.match(source) and prior:
            artifact = "essay"; topics = list(prior["entity_ids"])
        elif re.fullmatch(r"wordnet:[nvars]:\d{8}", source.casefold()):
            topics = [source]
        else:
            result = {"schema_version": RUNTIME_SCHEMA, "status": "unresolved", "operation": "wordnet_act_unresolved", "response": "No lexical discourse act was compiled.", "factual_release": False}
            result["latency_ms"] = 1000.0 * (time.perf_counter() - started)
            return result

        resolved_ids: list[str] = []
        for topic in topics:
            if topic.startswith("wordnet:") and self.specialist._entity(topic) is not None:
                resolved_ids.append(topic); continue
            identity, failure = self._resolve_or_return(topic)
            if failure:
                failure["latency_ms"] = 1000.0 * (time.perf_counter() - started)
                failure["session"] = self.sessions.append(session_id, source, failure, None)
                return failure
            resolved_ids.append(str(identity))

        if len(resolved_ids) == 1:
            result = self.specialist.realize(resolved_ids[0], artifact=artifact, paragraphs=paragraphs)
            result["operation"] = "wordnet_relational_realization"
        else:
            components = [self.specialist.realize(value, artifact="paragraph", paragraphs=1) for value in resolved_ids]
            if any(value["status"] != "answered" for value in components):
                result = {"schema_version": RUNTIME_SCHEMA, "status": "withheld", "operation": "wordnet_comparison_withheld", "response": "Both lexical senses were not realizable.", "factual_release": False, "components": components}
            else:
                labels = [value["entity"]["canonical_label"] for value in components]
                response = f"Regarding {labels[0]}: {components[0]['response']}\n\nRegarding {labels[1]}: {components[1]['response']}\n\nThe comparison juxtaposes two exact authenticated sense graphs; it does not assert an unstored difference."
                result = {"schema_version": RUNTIME_SCHEMA, "status": "answered", "operation": "wordnet_sense_comparison", "response": response, "factual_release": True, "components": components, "audit": {"exact_sense_addresses": True, "unstored_difference_asserted": False}}
        state = {"entity_ids": resolved_ids, "artifact": artifact}
        result["latency_ms"] = 1000.0 * (time.perf_counter() - started)
        result["session"] = self.sessions.append(session_id, source, result, state)
        return result


class OracleM13aRuntime:
    """M12 v1.0.1 plus a hot-loaded full, sense-addressed lexical specialist."""

    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, **m12_options: Any):
        self.state_root = Path(state_root).resolve(); self.state_root.mkdir(parents=True, exist_ok=True)
        self.wordnet = WordNetSpecialist(wordnet_build)
        if "tool_registry" not in m12_options:
            data_root = Path(m12_options.get("data_root") or DEFAULT_DATA_ROOT).resolve()
            m12_options["tool_registry"] = self._integrated_tool_registry(data_root / "m10")
        self.base = M12OracleRuntime(self.state_root / "m12", **m12_options)
        self.lexical = WordNetConversation(self.wordnet, self.state_root / "lexical")

    def _integrated_tool_registry(self, m10_build: Path) -> SchemaToolRegistry:
        parent = build_default_tool_registry(m10_build)
        registry = SchemaToolRegistry()
        wordnet_claims = int(self.wordnet.manifest["metrics"]["claims"])
        base_claims = int(json.loads((m10_build / "compilation_manifest.json").read_text(encoding="utf-8"))["claims"])

        for name in sorted(parent.tools):
            tool = parent.tools[name]
            if name == "inspect_oracle":
                executor = lambda _value, total=base_claims + wordnet_claims: {
                    "version": "1.1.0-m13a-dev", "domains": 13, "claims": total,
                    "maximum_actions": 512, "maximum_parallel": 8,
                }
                tool = replace(tool, executor_id="oracle.m13.inspect.v1", executor=executor)
            elif name == "list_specialists":
                parent_executor = tool.executor
                def list_specialists(value: Mapping[str, Any], executor=parent_executor, count=wordnet_claims) -> dict[str, Any]:
                    result = dict(executor(value)); domains = list(result["domains"])
                    domains.append({"domain": "wordnet", "claims": count, "expert_id": "generalist_wordnet_3_0"})
                    return {"domains": domains, "total_claims": int(result["total_claims"]) + count}
                tool = replace(tool, executor_id="oracle.m13.specialists.v1", executor=list_specialists)
            registry.register(tool)

        def resolve_wordnet(arguments: Mapping[str, Any]) -> dict[str, Any]:
            value = self.wordnet.resolve(str(arguments["query"]), pos=arguments.get("pos"))
            return {
                "status": str(value["status"]), "method": str(value["method"]),
                "entity_id": str(value.get("entity_id", "")),
                "candidate_count": int(value.get("candidate_count", 0)),
                "candidates": list(value.get("candidates", ())),
            }

        registry.register(SchemaTool(
            "resolve_wordnet", "Resolve an exact lemma or synset identifier against the sense-preserving WordNet specialist.",
            {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 256}, "pos": {"type": "string", "enum": ["n", "v", "a", "s", "r"]}}, "required": ["query"], "additionalProperties": False},
            {"type": "object", "properties": {"status": {"type": "string"}, "method": {"type": "string"}, "entity_id": {"type": "string"}, "candidate_count": {"type": "integer"}, "candidates": {"type": "array", "items": {"type": "object"}}}, "required": ["status", "method", "entity_id", "candidate_count", "candidates"], "additionalProperties": False},
            "read_only", "oracle.m13.wordnet-resolution.v1", resolve_wordnet, ("resolve lexical sense", "find wordnet sense"),
        ))
        return registry

    def chat(self, text: str, *, session_id: str = "default") -> dict[str, Any]:
        source = " ".join(str(text).split())
        if re.match(r"^(?:call|use)\b", source, re.I) or (re.search(r"\b(?:essay|document|account|treatise|report)\b", source, re.I) and re.search(r"\b(?:oracle|yourself|your architecture|what it is like|being this architecture)\b", source, re.I)):
            return self.base.chat(source, session_id=session_id)
        lexical = self.lexical.chat(source, session_id=session_id)
        if lexical.get("status") in {"answered", "clarification"}:
            lexical["schema_version"] = RUNTIME_SCHEMA
            lexical["hot_loaded_specialist"] = "wordnet_3_0"
            return lexical
        value = dict(self.base.chat(source, session_id=session_id))
        value["m13_lexical_attempt"] = {key: item for key, item in lexical.items() if key not in {"latency_ms", "session"}}
        return value

    def capabilities(self) -> dict[str, Any]:
        value = dict(self.base.capabilities())
        value.update({
            "schema_version": RUNTIME_SCHEMA,
            "wordnet_synsets": int(self.wordnet.manifest["metrics"]["synsets"]),
            "wordnet_claims": int(self.wordnet.manifest["metrics"]["claims"]),
            "wordnet_unique_aliases": int(self.wordnet.manifest["metrics"]["unique_aliases"]),
            "sense_ambiguity_quarantine": True,
            "hot_loaded_without_carrier_parameter_update": True,
            "unrestricted_conversation": False,
        })
        return value


__all__ = [
    "LexicalClaim", "LexicalSessionStore", "OracleM13aRuntime", "WordNetConversation",
    "WordNetSpecialist", "validate_build", "RUNTIME_SCHEMA", "SCHEMA",
]
