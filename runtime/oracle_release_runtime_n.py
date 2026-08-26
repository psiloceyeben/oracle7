#!/usr/bin/env python3
"""Runtime N — runtime M with the K8 batch-1 grammar wired into the session
kernel (additive; the IR pipeline and all capability routes now parse through
the ~190-construction inventory)."""

from __future__ import annotations

from oracle_release_runtime_m import OracleReleaseRuntimeM
from stage5m13e2_construction_kernel_k8 import ConstructionKernelK8
from stage5m13e4_migration2 import IRPipeline2


class OracleReleaseRuntimeN(OracleReleaseRuntimeM):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kernel = ConstructionKernelK8(compositional=True)
        self.pipeline = IRPipeline2(self.kernel)
