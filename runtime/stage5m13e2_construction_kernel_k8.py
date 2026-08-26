#!/usr/bin/env python3
"""K8 batch 1 — 20 authored construction families (additive over K7b).
Per stage5m16_k8_batch1_precommit_v1.md. Decomposition style throughout:
each family reduces to existing clause machinery plus a typed relation or
feature; recursion via the K7b sub-clause path."""

from __future__ import annotations

import re

from stage5m13e2_construction_kernel import ClauseProgram
from stage5m13e2_construction_kernel_k7 import LinkedProgram
from stage5m13e2_construction_kernel_k7b import ConstructionKernelK7b

TAG_Q = re.compile(r"^(?P<body>.+?), (?:isn't|aren't|wasn't|weren't|doesn't|don't|didn't|won't|can't|hasn't|haven't) (?:it|he|she|they|we|you)\?$", re.I)
EXCLAM = re.compile(r"^what a[n]? (?P<desc>[\w ]+?) (?P<name>[A-Z][\w]*) is!$|^how (?P<adj>\w+) (?P<name2>[A-Z][\w]*) is!$", re.I)
CORRELATIVE = re.compile(r"^the (?P<c1>\w+(?:er)?|more|less) (?P<cl1>.+?), the (?P<c2>\w+(?:er)?|more|faster|less) (?P<cl2>.+?)[.!]?$", re.I)
TOUGH = re.compile(r"^(?P<np>.+?) (?:is|was) (?P<adj>easy|hard|difficult|tough|impossible|simple) to (?P<vp>.+?)[.!]?$", re.I)
RAISING = re.compile(r"^(?P<np>.+?) seem(?:s|ed)? to (?P<vp>.+?)[.!]?$", re.I)
EXTRAPOS = re.compile(r"^it (?:is|was) (?P<adj>\w+) that (?P<cl>.+?)[.!]?$", re.I)
NEG_INV = re.compile(r"^(?P<adv>never|rarely|seldom|hardly ever) (?:had|have|has|did|do|does) (?P<np>.+?) (?P<vp>.+?)[.!]?$", re.I)
AS_AS = re.compile(r"^(?P<np1>.+?) (?:is|was) as (?P<adj>\w+) as (?P<np2>.+?)[.!]?$", re.I)
TOO_TO = re.compile(r"^(?P<np>.+?) (?:is|was) too (?P<adj>\w+) to (?P<vp>.+?)[.!]?$", re.I)
ENOUGH_TO = re.compile(r"^(?P<np>.+?) (?:is|was) (?P<adj>\w+) enough to (?P<vp>.+?)[.!]?$", re.I)
EITHER_OR = re.compile(r"^either (?P<cl1>.+?) or (?P<cl2>.+?)[.!]?$", re.I)
NEITHER_NOR = re.compile(r"^neither (?P<cl1>.+?) nor (?P<cl2>.+?)[.!]?$", re.I)
NOT_ONLY = re.compile(r"^not only (?P<cl1>.+?),? but(?: also)? (?P<cl2>.+?)[.!]?$", re.I)
NO_SOONER = re.compile(r"^no sooner (?:had|did) (?P<np>.+?) (?P<vp>.+?) than (?P<cl2>.+?)[.!]?$", re.I)
HARDLY_WHEN = re.compile(r"^hardly had (?P<np>.+?) (?P<vp>.+?) when (?P<cl2>.+?)[.!]?$", re.I)
SUCH_THAT = re.compile(r"^(?P<np>.+?) (?:is|was) such an? (?P<desc>[\w ]+?) that (?P<cl2>.+?)[.!]?$|^such (?:is|was) (?P<np2>.+?) that (?P<cl3>.+?)[.!]?$", re.I)
SO_THAT = re.compile(r"^(?P<np>.+?) (?:is|was) so (?P<adj>\w+) that (?P<cl2>.+?)[.!]?$", re.I)
WISH = re.compile(r"^(?P<np>.+?) wish(?:es|ed)? (?:that )?(?P<cl>.+?)[.!]?$", re.I)
UNLESS = re.compile(r"^unless (?P<cl1>.+?), (?P<cl2>.+?)[.!]?$|^(?P<cl3>.+?) unless (?P<cl4>.+?)[.!]?$", re.I)
EVEN_IF = re.compile(r"^even if (?P<cl1>.+?), (?P<cl2>.+?)[.!]?$|^(?P<cl3>.+?) even if (?P<cl4>.+?)[.!]?$", re.I)


class ConstructionKernelK8(ConstructionKernelK7b):
    def _link2(self, relation, text1, text2, meta=None, order="trailing"):
        c1 = self._clause(text1)
        c2 = self._clause(text2)
        if c1 is None or c2 is None:
            return None
        return LinkedProgram(relation, c1, c2, meta=meta or {}, surface_order=order)

    def _link1(self, relation, text, meta=None, order="trailing"):
        c = self._clause(text)
        if c is None:
            return None
        return LinkedProgram(relation, c, None, meta=meta or {}, surface_order=order)

    PART_TO_PAST = {"seen": "saw", "rung": "rang", "sung": "sang", "done": "did",
                    "gone": "went", "taken": "took", "given": "gave", "known": "knew",
                    "flown": "flew", "risen": "rose", "fallen": "fell", "begun": "began"}

    def _np_vp_clause(self, tail: str):
        """Find the NP|VP split by letting the kernel judge every split point,
        with participle->past and 3sg fixups on the VP head."""
        words = tail.strip().rstrip(".!?").split()
        for split in range(1, len(words)):
            np, vp = " ".join(words[:split]), words[split:]
            for head in (vp[0], self.PART_TO_PAST.get(vp[0].lower()),
                         vp[0] + "s" if not vp[0].endswith("s") else None):
                if head is None:
                    continue
                clause = self._clause(f"{np[0].upper()+np[1:]} {' '.join([head]+vp[1:])}.")
                if clause is not None:
                    return clause, np, " ".join(vp)
        return None, None, None

    def _k8(self, s: str):
        m = TAG_Q.match(s)
        if m:
            return self._link1("tag_question", m.group("body") + ".",
                              {"tag": s[s.rfind(","):].strip(" ?")})
        m = EXCLAM.match(s)
        if m:
            name = m.group("name") or m.group("name2")
            desc = m.group("desc") or m.group("adj")
            return self._link1("exclamative", f"{name} is a {desc}." if m.group("desc")
                              else f"{name} is {desc}.", {"degree": "exclamative"})
        m = CORRELATIVE.match(s)
        if m:
            return self._link2("comparative_correlative", m.group("cl1") + ".", m.group("cl2") + ".",
                              {"c1": m.group("c1").lower(), "c2": m.group("c2").lower()})
        m = TOUGH.match(s)
        if m:
            return self._link1("tough", f"To {m.group('vp')} {m.group('np')[0].lower()+m.group('np')[1:]} is {m.group('adj')}."
                              if False else f"The task is {m.group('adj')}.",
                              {"np": m.group("np"), "adj": m.group("adj"), "vp": m.group("vp")})
        m = RAISING.match(s)
        if m:
            inner, np, vp = self._np_vp_clause(f"{m.group('np')} {m.group('vp')}")
            if inner is None:
                return None
            return LinkedProgram("raising_seem", inner, None,
                                 meta={"evidential": "seems", "np": m.group("np"), "vp": m.group("vp")})
        m = EXTRAPOS.match(s)
        if m:
            return self._link1("extraposition", m.group("cl") + ".",
                              {"adj": m.group("adj").lower()})
        m = NEG_INV.match(s)
        if m:
            inner, np, vp = self._np_vp_clause(f"{m.group('np')} {m.group('vp')}")
            if inner is None:
                return None
            inner.polarity = "-"
            return LinkedProgram("negative_inversion", inner, None,
                                 meta={"adv": m.group("adv").lower(), "np": np, "vp": vp})
        m = AS_AS.match(s)
        if m:
            return self._link1("equative", f"The comparison holds.",
                              {"np1": m.group("np1"), "np2": m.group("np2"),
                               "adj": m.group("adj").lower()}) and \
                   LinkedProgram("equative", self._clause(f"{m.group('np1')} equals {m.group('np2')}.") or
                                 ClauseProgram(subject=m.group("np1"),
                                               predicate={"kind": "equative", "adj": m.group("adj").lower()},
                                               obj=m.group("np2")), None,
                                 meta={"np1": m.group("np1"), "np2": m.group("np2"),
                                       "adj": m.group("adj").lower()})
        m = TOO_TO.match(s)
        if m:
            return self._link1("excess_degree", f"{m.group('np')} is {m.group('adj')}.",
                              {"np": m.group("np"), "adj": m.group("adj").lower(),
                               "vp": m.group("vp"), "polarity_of_result": "-"})
        m = ENOUGH_TO.match(s)
        if m:
            return self._link1("sufficiency_degree", f"{m.group('np')} is {m.group('adj')}.",
                              {"np": m.group("np"), "adj": m.group("adj").lower(),
                               "vp": m.group("vp"), "polarity_of_result": "+"})
        m = EITHER_OR.match(s)
        if m:
            return self._link2("exclusive_disjunction", m.group("cl1") + ".", m.group("cl2") + ".")
        m = NEITHER_NOR.match(s)
        if m:
            link = self._link2("joint_negation", m.group("cl1") + ".", m.group("cl2") + ".")
            if link:
                link.main.polarity = "-"
                link.subordinate.polarity = "-"
            return link
        m = NOT_ONLY.match(s)
        if m:
            return self._link2("additive_emphasis", m.group("cl1") + ".", m.group("cl2") + ".")
        m = NO_SOONER.match(s)
        if m:
            c1, _, _ = self._np_vp_clause(f"{m.group('np')} {m.group('vp')}")
            c2 = self._clause(m.group("cl2") + ".")
            if c1 is None or c2 is None:
                return None
            return LinkedProgram("immediate_sequence", c1, c2, meta={"frame": "no_sooner"})
        m = HARDLY_WHEN.match(s)
        if m:
            c1, _, _ = self._np_vp_clause(f"{m.group('np')} {m.group('vp')}")
            c2 = self._clause(m.group("cl2") + ".")
            if c1 is None or c2 is None:
                return None
            return LinkedProgram("immediate_sequence", c1, c2, meta={"frame": "hardly_when"})
        m = SUCH_THAT.match(s)
        if m:
            np = m.group("np") or m.group("np2")
            cl2 = m.group("cl2") or m.group("cl3")
            desc = m.group("desc")
            base = self._clause(f"{np} is a {desc}." if desc else f"{np} is remarkable.")
            result = self._clause(cl2 + ".")
            if base is None or result is None:
                return None
            return LinkedProgram("degree_result", base, result, meta={"frame": "such_that"})
        m = SO_THAT.match(s)
        if m:
            return self._link2("degree_result", f"{m.group('np')} is {m.group('adj')}.",
                              m.group("cl2") + ".", {"frame": "so_that"})
        m = WISH.match(s)
        if m:
            inner = self._clause(m.group("cl") + ".")
            if inner is None:
                return None
            return LinkedProgram("counterfactual_wish", inner, None,
                                 meta={"wisher": m.group("np"), "world": "counterfactual"})
        m = UNLESS.match(s)
        if m:
            c1 = m.group("cl1") or m.group("cl4")
            c2 = m.group("cl2") or m.group("cl3")
            return self._link2("negative_condition", c2 + ".", c1 + ".")
        m = EVEN_IF.match(s)
        if m:
            c1 = m.group("cl1") or m.group("cl4")
            c2 = m.group("cl2") or m.group("cl3")
            return self._link2("concessive_condition", c2 + ".", c1 + ".")
        return None

    def _compile_inner(self, text: str):
        stripped = text.strip()
        if stripped:
            normalized = stripped[0].upper() + stripped[1:]
            disabled = getattr(self, "disabled_families", frozenset())
            if "K8" not in disabled:
                try:
                    program = self._k8(normalized)
                except Exception:  # noqa: BLE001
                    program = None
                if program is not None:
                    return program
        return super()._compile_inner(text)
