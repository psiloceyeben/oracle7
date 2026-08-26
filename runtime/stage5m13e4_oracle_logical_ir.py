#!/usr/bin/env python3
"""M13e4 core: the Oracle Logical IR.

Simply-typed lambda calculus over the registered base types, with deterministic
capture-avoiding beta normalization, alpha-invariant canonical digests, and a
six-valued epistemic store (Belnap TRUE/FALSE/BOTH/UNKNOWN plus HYPOTHESIS and
UNSUPPORTED) whose propositions carry exactly one world scope and whose
world/authority boundaries are crossable only through registered operators.

No transformer, no embedding, no gradient, no external model. Pure structure.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Union

SCHEMA = "oracle-stage5m13e4-logical-ir-v1"

# ---------------------------------------------------------------- types

BASE_TYPES = {
    "Entity", "Truth", "World", "Event", "Time", "Location", "Quantity",
    "Evidence", "Claim", "Speaker", "Goal", "Action", "Specialist",
    "Objective", "Authority",
}


@dataclass(frozen=True)
class Base:
    name: str

    def __post_init__(self):
        if self.name not in BASE_TYPES:
            raise TypeError(f"unknown base type: {self.name}")

    def __repr__(self):
        return self.name


@dataclass(frozen=True)
class Fun:
    domain: "Type"
    codomain: "Type"

    def __repr__(self):
        return f"({self.domain} -> {self.codomain})"


Type = Union[Base, Fun]

E, T, W = Base("Entity"), Base("Truth"), Base("World")
EV, TM = Base("Event"), Base("Time")


def pred(*args: Type) -> Type:
    """pred(A, B, ..., R) builds the curried type A -> B -> ... -> R."""
    result = args[-1]
    for domain in reversed(args[:-1]):
        result = Fun(domain, result)
    return result


GQ = Fun(Fun(E, T), Fun(Fun(E, T), T))  # generalized quantifier

# ---------------------------------------------------------------- terms


@dataclass(frozen=True)
class Var:
    name: str
    vtype: Type


@dataclass(frozen=True)
class Const:
    name: str
    ctype: Type


@dataclass(frozen=True)
class Lam:
    param: Var
    body: "Term"


@dataclass(frozen=True)
class App:
    fn: "Term"
    arg: "Term"


Term = Union[Var, Const, Lam, App]


class TypeError_(Exception):
    pass


def infer(term: Term, env: dict[str, Type] | None = None) -> Type:
    env = env or {}
    if isinstance(term, Var):
        bound = env.get(term.name)
        if bound is not None and bound != term.vtype:
            raise TypeError_(f"variable {term.name} annotated {term.vtype} but bound {bound}")
        return term.vtype
    if isinstance(term, Const):
        return term.ctype
    if isinstance(term, Lam):
        inner = dict(env)
        inner[term.param.name] = term.param.vtype
        return Fun(term.param.vtype, infer(term.body, inner))
    if isinstance(term, App):
        fn_type = infer(term.fn, env)
        arg_type = infer(term.arg, env)
        if not isinstance(fn_type, Fun):
            raise TypeError_(f"applying non-function of type {fn_type}")
        if fn_type.domain != arg_type:
            raise TypeError_(f"domain {fn_type.domain} != argument {arg_type}")
        return fn_type.codomain
    raise TypeError_(f"unknown term {term!r}")


def free_variables(term: Term) -> set[str]:
    if isinstance(term, Var):
        return {term.name}
    if isinstance(term, Const):
        return set()
    if isinstance(term, Lam):
        return free_variables(term.body) - {term.param.name}
    return free_variables(term.fn) | free_variables(term.arg)


class _Fresh:
    def __init__(self):
        self.counter = 0

    def name(self, base: str) -> str:
        self.counter += 1
        return f"{base}#{self.counter}"


def _substitute(term: Term, name: str, value: Term, fresh: _Fresh) -> Term:
    if isinstance(term, Var):
        return value if term.name == name else term
    if isinstance(term, Const):
        return term
    if isinstance(term, App):
        return App(_substitute(term.fn, name, value, fresh),
                   _substitute(term.arg, name, value, fresh))
    if isinstance(term, Lam):
        if term.param.name == name:
            return term  # shadowed
        if term.param.name in free_variables(value):
            renamed = Var(fresh.name(term.param.name.split("#")[0]), term.param.vtype)
            body = _substitute(term.body, term.param.name, renamed, fresh)
            return Lam(renamed, _substitute(body, name, value, fresh))
        return Lam(term.param, _substitute(term.body, name, value, fresh))
    raise TypeError_(f"unknown term {term!r}")


def _step(term: Term, fresh: _Fresh) -> Term | None:
    """One leftmost-outermost beta step, or None at normal form."""
    if isinstance(term, App):
        if isinstance(term.fn, Lam):
            return _substitute(term.fn.body, term.fn.param.name, term.arg, fresh)
        reduced = _step(term.fn, fresh)
        if reduced is not None:
            return App(reduced, term.arg)
        reduced = _step(term.arg, fresh)
        if reduced is not None:
            return App(term.fn, reduced)
        return None
    if isinstance(term, Lam):
        reduced = _step(term.body, fresh)
        if reduced is not None:
            return Lam(term.param, reduced)
        return None
    return None


def normalize(term: Term, budget: int = 10_000) -> Term:
    """Deterministic beta normalization; type-check first (typing guarantees termination)."""
    infer(term)
    fresh = _Fresh()
    for _ in range(budget):
        reduced = _step(term, fresh)
        if reduced is None:
            return term
        term = reduced
    raise TypeError_("normalization budget exceeded (ill-typed self-application?)")


# ------------------------------------------------- canonical form + digest


def _type_obj(t: Type) -> Any:
    if isinstance(t, Base):
        return t.name
    return [_type_obj(t.domain), _type_obj(t.codomain)]


def _canonical(term: Term, binders: tuple[str, ...]) -> Any:
    """de Bruijn form: alpha-equivalent terms serialize identically."""
    if isinstance(term, Var):
        if term.name in binders:
            return ["b", len(binders) - 1 - binders.index(term.name), _type_obj(term.vtype)]
        return ["f", term.name, _type_obj(term.vtype)]
    if isinstance(term, Const):
        return ["c", term.name, _type_obj(term.ctype)]
    if isinstance(term, Lam):
        return ["l", _type_obj(term.param.vtype), _canonical(term.body, binders + (term.param.name,))]
    return ["a", _canonical(term.fn, binders), _canonical(term.arg, binders)]


def canonical(term: Term) -> str:
    return json.dumps(_canonical(term, ()), sort_keys=True, separators=(",", ":"))


def digest(term: Term) -> str:
    return hashlib.sha256(canonical(term).encode()).hexdigest()


def alpha_equal(left: Term, right: Term) -> bool:
    return canonical(left) == canonical(right)


# --------------------------------------------- epistemic store with worlds

STATUSES = ("TRUE", "FALSE", "BOTH", "UNKNOWN", "HYPOTHESIS", "UNSUPPORTED")

WORLD_SCOPES = (
    "authenticated_fact", "user_temporary_world", "hypothetical_world",
    "counterfactual_world", "reported_belief", "fictional_world",
    "episodic_tool_observation",
)

# world-crossing operators: (source_scope, operator) -> target_scope
REGISTERED_CROSSINGS = {
    ("user_temporary_world", "report_as_belief"): "reported_belief",
    ("authenticated_fact", "report_as_belief"): "reported_belief",
    ("episodic_tool_observation", "adopt_observation"): "user_temporary_world",
    ("hypothetical_world", "discharge_hypothesis"): "user_temporary_world",
}


class WorldBoundaryError(Exception):
    pass


class EpistemicStore:
    """Six-valued store; BOTH preserves all conflicting supports (paraconsistent)."""

    def __init__(self):
        self.entries: dict[tuple[str, str], dict[str, Any]] = {}

    @staticmethod
    def _key(world: str, proposition: Term) -> tuple[str, str]:
        if world not in WORLD_SCOPES:
            raise WorldBoundaryError(f"unknown world scope: {world}")
        if infer(proposition) != T:
            raise TypeError_("only Truth-typed terms are propositions")
        return (world, digest(normalize(proposition)))

    def assert_(self, world: str, proposition: Term, polarity: bool, provenance: str) -> str:
        key = self._key(world, proposition)
        entry = self.entries.setdefault(key, {"status": "UNKNOWN", "supports": []})
        entry["supports"].append({"polarity": polarity, "provenance": provenance})
        polarities = {support["polarity"] for support in entry["supports"]}
        if polarities == {True}:
            entry["status"] = "TRUE"
        elif polarities == {False}:
            entry["status"] = "FALSE"
        else:
            entry["status"] = "BOTH"  # all conflicting supports retained, no explosion
        return entry["status"]

    def hypothesize(self, world: str, proposition: Term, provenance: str) -> str:
        key = self._key(world, proposition)
        entry = self.entries.setdefault(key, {"status": "UNKNOWN", "supports": []})
        if entry["status"] == "UNKNOWN":
            entry["status"] = "HYPOTHESIS"
            entry["supports"].append({"polarity": None, "provenance": provenance, "hypothesis": True})
        return entry["status"]

    def mark_unsupported(self, world: str, proposition: Term, provenance: str) -> str:
        key = self._key(world, proposition)
        entry = self.entries.setdefault(key, {"status": "UNKNOWN", "supports": []})
        if entry["status"] in ("UNKNOWN", "HYPOTHESIS"):
            entry["status"] = "UNSUPPORTED"
            entry["supports"].append({"polarity": None, "provenance": provenance, "unsupported": True})
        return entry["status"]

    def status(self, world: str, proposition: Term) -> str:
        return self.entries.get(self._key(world, proposition), {}).get("status", "UNKNOWN")

    def supports(self, world: str, proposition: Term) -> list[dict[str, Any]]:
        return list(self.entries.get(self._key(world, proposition), {}).get("supports", ()))

    def derive_across(self, source_world: str, target_world: str, operator: str,
                      proposition: Term, polarity: bool, provenance: str) -> str:
        """The ONLY path by which content crosses a world boundary."""
        licensed = REGISTERED_CROSSINGS.get((source_world, operator))
        if licensed != target_world:
            raise WorldBoundaryError(
                f"no registered operator carries {source_world} -> {target_world} via {operator!r}")
        if self.status(source_world, proposition) not in ("TRUE", "FALSE", "BOTH"):
            raise WorldBoundaryError("cannot cross with an unasserted proposition")
        return self.assert_(target_world, proposition, polarity,
                            f"{operator}({source_world}): {provenance}")


__all__ = [
    "App", "BASE_TYPES", "Base", "Const", "E", "EV", "EpistemicStore", "Fun", "GQ",
    "Lam", "REGISTERED_CROSSINGS", "SCHEMA", "STATUSES", "T", "TM", "Term", "Type",
    "TypeError_", "Var", "W", "WORLD_SCOPES", "WorldBoundaryError", "alpha_equal",
    "canonical", "digest", "free_variables", "infer", "normalize", "pred",
]
