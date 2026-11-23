"""Keep pre-split module paths importable after organs moved out of core.

`import abyss_machine.<old_module>` returns the module object that now lives
under `abyss_machine.organs.<organ>`, so external importers and monkeypatches
keep working. New code should import the organ path directly.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys

MOVED_MODULES = {
    "nervous_brief": "abyss_machine.organs.nervous.nervous_brief",
    "nervous_events": "abyss_machine.organs.nervous.nervous_events",
    "nervous_events_adapters": "abyss_machine.organs.nervous.nervous_events_adapters",
    "nervous_index": "abyss_machine.organs.nervous.nervous_index",
    "nervous_index_adapters": "abyss_machine.organs.nervous.nervous_index_adapters",
    "nervous_quality": "abyss_machine.organs.nervous.nervous_quality",
    "nervous_quality_adapters": "abyss_machine.organs.nervous.nervous_quality_adapters",
    "nervous_recall": "abyss_machine.organs.nervous.nervous_recall",
    "nervous_rerank": "abyss_machine.organs.nervous.nervous_rerank",
    "nervous_rerank_adapters": "abyss_machine.organs.nervous.nervous_rerank_adapters",
    "nervous_retention": "abyss_machine.organs.nervous.nervous_retention",
    "nervous_retention_adapters": "abyss_machine.organs.nervous.nervous_retention_adapters",
    "nervous_retrieval_adapters": "abyss_machine.organs.nervous.nervous_retrieval_adapters",
    "nervous_semantic": "abyss_machine.organs.nervous.nervous_semantic",
    "nervous_semantic_adapters": "abyss_machine.organs.nervous.nervous_semantic_adapters",
    "nervous_status_adapters": "abyss_machine.organs.nervous.nervous_status_adapters",
    "nervous_synthesis": "abyss_machine.organs.nervous.nervous_synthesis",
    "nervous_synthesis_adapters": "abyss_machine.organs.nervous.nervous_synthesis_adapters",
    "dictation_contracts": "abyss_machine.organs.dictation.dictation_contracts",
    "dictation_docs_adapters": "abyss_machine.organs.dictation.dictation_docs_adapters",
    "dictation_execution_adapters": "abyss_machine.organs.dictation.dictation_execution_adapters",
    "dictation_lock_adapters": "abyss_machine.organs.dictation.dictation_lock_adapters",
    "dictation_notifications_adapters": "abyss_machine.organs.dictation.dictation_notifications_adapters",
    "dictation_postprocess_adapters": "abyss_machine.organs.dictation.dictation_postprocess_adapters",
    "dictation_profile_adapters": "abyss_machine.organs.dictation.dictation_profile_adapters",
    "dictation_replacements_adapters": "abyss_machine.organs.dictation.dictation_replacements_adapters",
    "dictation_runtime_adapters": "abyss_machine.organs.dictation.dictation_runtime_adapters",
    "dictation_status_adapters": "abyss_machine.organs.dictation.dictation_status_adapters",
    "dictation_validation_adapters": "abyss_machine.organs.dictation.dictation_validation_adapters",
    "ai_runtime_adapters": "abyss_machine.organs.ai.ai_runtime_adapters",
    "ai_runtime_contracts": "abyss_machine.organs.ai.ai_runtime_contracts",
    "ai_tts_adapters": "abyss_machine.organs.ai.ai_tts_adapters",
    "ai_tts_contracts": "abyss_machine.organs.ai.ai_tts_contracts",
    "artifact_bundles": "abyss_machine.organs.artifacts.artifact_bundles",
    "artifact_subject_retention": "abyss_machine.organs.artifacts.artifact_subject_retention",
    "kag_artifacts": "abyss_machine.organs.artifacts.kag_artifacts",
}


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target: str) -> None:
        self.target = target

    def create_module(self, spec):  # noqa: ANN001
        module = importlib.import_module(self.target)
        # read without forcing a lazily bound organ module to execute
        self.real_spec = object.__getattribute__(module, "__spec__")
        return module

    def exec_module(self, module) -> None:  # noqa: ANN001
        # module_from_spec() stamped the alias spec onto the shared module;
        # keep its real spec so relative imports resolve inside the organ
        object.__setattr__(module, "__spec__", self.real_spec)


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001
        if not fullname.startswith("abyss_machine."):
            return None
        real = MOVED_MODULES.get(fullname.split(".", 1)[1])
        if real is None:
            return None
        return importlib.machinery.ModuleSpec(fullname, _AliasLoader(real))


def install() -> None:
    if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
        sys.meta_path.append(_AliasFinder())
