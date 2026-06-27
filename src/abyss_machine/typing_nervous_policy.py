from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Mapping

from .path_policy import AbyssMachinePathPolicy, DEFAULT_PATH_POLICY


def _environment_snapshot(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    return dict(os.environ if environ is None else environ)


@dataclass(frozen=True)
class TypingNervousPolicy:
    """Path and service policy for the typed-intake and nervous-system organs."""

    path_policy: AbyssMachinePathPolicy = DEFAULT_PATH_POLICY
    environ: Mapping[str, str] = field(default_factory=_environment_snapshot)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "TypingNervousPolicy":
        source = _environment_snapshot(environ)
        return cls(
            path_policy=AbyssMachinePathPolicy.from_environment(environ=source),
            environ=source,
        )

    @classmethod
    def from_path_policy(
        cls,
        path_policy: AbyssMachinePathPolicy,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "TypingNervousPolicy":
        return cls(path_policy=path_policy, environ=_environment_snapshot(environ))

    def _env_path(self, name: str, default: str | Path) -> Path:
        return Path(self.environ.get(name, str(default)))

    def _env_text(self, name: str, default: str) -> str:
        return self.environ.get(name, default)

    @property
    def user_systemd_dir(self) -> Path:
        return self._env_path(
            "ABYSS_MACHINE_USER_SYSTEMD_DIR",
            self.path_policy.systemd_user_dir or self.path_policy.home / ".config/systemd/user",
        )

    @property
    def nervous_root(self) -> Path:
        return self._env_path("ABYSS_MACHINE_NERVOUS_ROOT", self.path_policy.state_path("nervous"))

    @property
    def typing_root(self) -> Path:
        return self._env_path("ABYSS_MACHINE_TYPING_ROOT", self.path_policy.state_path("typing"))

    def as_cli_constants(self) -> dict[str, Any]:
        path_policy = self.path_policy
        home = path_policy.home
        storage_root = path_policy.storage_root
        tmp_root = path_policy.tmp_root
        cache_root = path_policy.cache_root
        srv_root = path_policy.srv_root
        user_systemd_dir = self.user_systemd_dir

        nervous_root = self.nervous_root
        nervous_config_dir = self._env_path("ABYSS_MACHINE_NERVOUS_CONFIG_DIR", path_policy.etc_file("nervous"))
        nervous_capture_root = nervous_root / "capture"
        nervous_private_capture_root = self._env_path(
            "ABYSS_MACHINE_NERVOUS_CAPTURE_ROOT",
            storage_root / "nervous" / "captures",
        )
        nervous_retrieval_root = nervous_root / "retrieval"
        nervous_synthesis_root = nervous_root / "synthesis"
        nervous_evals_root = nervous_root / "evals"
        nervous_search_index_root = self._env_path(
            "ABYSS_MACHINE_NERVOUS_INDEX_ROOT",
            storage_root / "nervous" / "indexes",
        )
        nervous_search_index_db_path = self._env_path(
            "ABYSS_MACHINE_NERVOUS_INDEX_DB",
            nervous_search_index_root / "sqlite" / "nervous.db",
        )
        nervous_semantic_index_root = self._env_path(
            "ABYSS_MACHINE_NERVOUS_SEMANTIC_INDEX_ROOT",
            nervous_search_index_root / "semantic",
        )
        nervous_semantic_index_db_path = self._env_path(
            "ABYSS_MACHINE_NERVOUS_SEMANTIC_INDEX_DB",
            nervous_semantic_index_root / "semantic.db",
        )
        nervous_semantic_maintain_root = nervous_root / "indexes" / "semantic" / "maintain"
        nervous_brief_root = nervous_root / "brief"
        nervous_validate_root = nervous_root / "validate"
        nervous_passive_chronicle_service = "abyss-nervous-passive-chronicle.service"

        typing_root = self.typing_root
        typing_events_root = typing_root / "events"
        typing_capture_gate_root = typing_root / "capture-gate"
        typing_privacy_selftest_root = typing_root / "privacy-selftest"
        typing_coverage_root = typing_root / "coverage"
        typing_process_root = typing_root / "process"
        typing_nervous_refresh_root = typing_root / "nervous-refresh"
        typing_focused_snapshot_root = typing_root / "focused-snapshot"
        typing_atspi_text_events_root = typing_root / "atspi-text-events"
        typing_generic_gui_selftest_root = typing_root / "generic-gui-selftest"
        typing_validate_root = typing_root / "validate"
        typing_saved_text_root = typing_root / "saved-text"
        typing_zsh_hook_root = typing_root / "zsh-hook"
        typing_zsh_hook_status_root = typing_zsh_hook_root / "status"
        typing_zsh_hook_selftest_root = typing_zsh_hook_root / "selftest"
        typing_codex_hook_root = typing_root / "codex-hook"
        typing_codex_hook_events_root = typing_codex_hook_root / "events"
        typing_codex_hook_status_root = typing_codex_hook_root / "status"
        typing_codex_hook_selftest_root = typing_codex_hook_root / "selftest"
        typing_codex_session_tail_root = typing_root / "codex-session-tail"
        typing_editor_extension_root = typing_root / "editor-extension"
        typing_editor_extension_selftest_root = typing_editor_extension_root / "selftest"
        typing_editor_extension_callback_selftest_root = typing_editor_extension_root / "callback-selftest"
        typing_browser_extension_status_root = typing_root / "browser-extension"
        typing_browser_ai_transcript_root = typing_root / "browser-ai-transcript"
        typing_browser_ai_transcript_selftest_root = typing_browser_ai_transcript_root / "selftest"
        typing_browser_webextension_selftest_root = typing_root / "browser-webextension-selftest"
        typing_browser_atspi_selftest_root = typing_root / "browser-atspi-selftest"
        typing_browser_atspi_release_selftest_root = typing_root / "browser-atspi-release-selftest"
        typing_browser_context_selftest_root = typing_root / "browser-context-selftest"
        typing_focused_browser_selftest_root = typing_root / "focused-browser-selftest"
        typing_browser_privacy_selftest_root = typing_root / "browser-privacy-selftest"
        typing_end_to_end_root = typing_root / "end-to-end"
        typing_browser_native_host_name = "org.abyss_machine.typing_intake"
        typing_focused_snapshot_service = "abyss-machine-typing-focused-snapshot.service"
        typing_focused_snapshot_timer = "abyss-machine-typing-focused-snapshot.timer"
        typing_atspi_text_events_service = "abyss-machine-typing-atspi-text-events.service"
        typing_codex_session_tail_service = "abyss-machine-typing-codex-session-tail.service"
        typing_codex_session_tail_timer = "abyss-machine-typing-codex-session-tail.timer"
        typing_saved_text_scan_service = "abyss-machine-typing-saved-text-scan.service"
        typing_saved_text_scan_timer = "abyss-machine-typing-saved-text-scan.timer"
        typing_nervous_refresh_service = "abyss-machine-typing-nervous-refresh.service"
        typing_nervous_refresh_timer = "abyss-machine-typing-nervous-refresh.timer"

        return {
            "NERVOUS_ROOT": nervous_root,
            "NERVOUS_AGENTS_PATH": nervous_root / "AGENTS.md",
            "NERVOUS_INDEX_PATH": nervous_root / "index.json",
            "NERVOUS_LATEST_PATH": nervous_root / "latest.json",
            "NERVOUS_CONFIG_DIR": nervous_config_dir,
            "NERVOUS_POLICY_CONFIG_PATH": nervous_config_dir / "policy.json",
            "NERVOUS_SOURCES_CONFIG_PATH": nervous_config_dir / "sources.json",
            "NERVOUS_PRIVACY_CONFIG_PATH": nervous_config_dir / "privacy.json",
            "NERVOUS_POLICY_LATEST_PATH": nervous_root / "policy" / "latest.json",
            "NERVOUS_SOURCES_LATEST_PATH": nervous_root / "sources" / "latest.json",
            "NERVOUS_PRIVACY_LATEST_PATH": nervous_root / "privacy" / "latest.json",
            "NERVOUS_PRIVACY_STATE_PATH": nervous_root / "privacy" / "state.json",
            "NERVOUS_PRIVACY_AUDIT_ROOT": nervous_root / "privacy" / "audit",
            "NERVOUS_SOURCES_STATE_PATH": nervous_root / "sources" / "state.json",
            "NERVOUS_CHECKS_ROOT": nervous_root / "checks",
            "NERVOUS_CHECKS_LATEST_PATH": nervous_root / "checks" / "latest.json",
            "NERVOUS_EVENTS_ROOT": nervous_root / "events",
            "NERVOUS_EVENTS_LATEST_PATH": nervous_root / "events" / "latest.json",
            "NERVOUS_FACTS_ROOT": nervous_root / "facts",
            "NERVOUS_FACTS_LATEST_PATH": nervous_root / "facts" / "latest.json",
            "NERVOUS_CAPTURE_ROOT": nervous_capture_root,
            "NERVOUS_CAPTURE_LATEST_PATH": nervous_capture_root / "latest.json",
            "NERVOUS_PRIVATE_CAPTURE_ROOT": nervous_private_capture_root,
            "NERVOUS_SCREENSHOT_ROOT": nervous_private_capture_root / "screenshots",
            "NERVOUS_BROWSER_CONTENT_ROOT": nervous_private_capture_root / "browser-content",
            "NERVOUS_BROWSER_CONTENT_LATEST_PATH": nervous_capture_root / "browser-content" / "latest.json",
            "NERVOUS_WEB_PERFORMANCE_ROOT": nervous_root / "diagnostics" / "web-performance",
            "NERVOUS_WEB_PERFORMANCE_LATEST_PATH": nervous_root / "diagnostics" / "web-performance" / "latest.json",
            "NERVOUS_BROWSER_CONTENT_MAX_CHARS": 120_000,
            "NERVOUS_BROWSER_ATSPI_MAX_APPS": 4,
            "NERVOUS_BROWSER_ATSPI_MAX_DOCUMENTS_PER_APP": 24,
            "NERVOUS_BROWSER_ATSPI_SCAN_MAX_NODES": 10_000,
            "NERVOUS_BROWSER_ATSPI_TEXT_MAX_NODES": 8_000,
            "NERVOUS_BROWSER_ATSPI_MAX_CHILDREN": 220,
            "NERVOUS_BROWSER_BIDI_DEFAULT_URL": self._env_text(
                "ABYSS_MACHINE_FIREFOX_BIDI_URL",
                "ws://127.0.0.1:9222/session",
            ),
            "NERVOUS_BROWSER_TMP_ROOT": tmp_root / "nervous" / "browser-history",
            "NERVOUS_EPISODES_ROOT": nervous_root / "episodes",
            "NERVOUS_EPISODES_LATEST_PATH": nervous_root / "episodes" / "latest.json",
            "NERVOUS_RETRIEVAL_ROOT": nervous_retrieval_root,
            "NERVOUS_RETRIEVAL_LATEST_PATH": nervous_retrieval_root / "latest.json",
            "NERVOUS_RERANK_ROOT": nervous_retrieval_root / "rerank",
            "NERVOUS_RERANK_LATEST_PATH": nervous_retrieval_root / "rerank" / "latest.json",
            "NERVOUS_SYNTHESIS_ROOT": nervous_synthesis_root,
            "NERVOUS_SYNTHESIS_HOURLY_ROOT": nervous_synthesis_root / "hourly",
            "NERVOUS_SYNTHESIS_DAILY_ROOT": nervous_synthesis_root / "daily",
            "NERVOUS_SYNTHESIS_LATEST_PATH": nervous_synthesis_root / "latest.json",
            "NERVOUS_SYNTHESIS_VALIDATE_LATEST_PATH": nervous_synthesis_root / "validate" / "latest.json",
            "NERVOUS_EVALS_ROOT": nervous_evals_root,
            "NERVOUS_EVALS_LATEST_PATH": nervous_evals_root / "latest.json",
            "NERVOUS_EVALS_VALIDATE_LATEST_PATH": nervous_evals_root / "validate" / "latest.json",
            "NERVOUS_RETENTION_ROOT": nervous_root / "retention",
            "NERVOUS_RETENTION_LATEST_PATH": nervous_root / "retention" / "latest.json",
            "NERVOUS_RETENTION_VALIDATE_LATEST_PATH": nervous_root / "retention" / "validate" / "latest.json",
            "NERVOUS_QUALITY_ROOT": nervous_root / "quality",
            "NERVOUS_QUALITY_LATEST_PATH": nervous_root / "quality" / "latest.json",
            "NERVOUS_DESIGN_PATH": srv_root / "design" / "abyss-nervous-system-design.md",
            "NERVOUS_PASSIVE_CHRONICLE_SERVICE": nervous_passive_chronicle_service,
            "NERVOUS_PASSIVE_CHRONICLE_TIMER": "abyss-nervous-passive-chronicle.timer",
            "NERVOUS_BROWSER_CONTENT_CAPTURE_SERVICE": "abyss-nervous-browser-content-capture.service",
            "NERVOUS_BROWSER_CONTENT_CAPTURE_TIMER": "abyss-nervous-browser-content-capture.timer",
            "NERVOUS_INDEX_CONFIG_PATH": nervous_config_dir / "index.json",
            "NERVOUS_SEARCH_INDEX_ROOT": nervous_search_index_root,
            "NERVOUS_SEARCH_INDEX_DB_PATH": nervous_search_index_db_path,
            "NERVOUS_SEARCH_INDEX_SCHEMA_PATH": nervous_search_index_db_path.with_name("schema.sql"),
            "NERVOUS_SEARCH_INDEX_LATEST_PATH": nervous_root / "indexes" / "latest.json",
            "NERVOUS_SEARCH_INDEX_SERVICE": "abyss-nervous-index-build.service",
            "NERVOUS_SEARCH_INDEX_TIMER": "abyss-nervous-index-build.timer",
            "NERVOUS_DERIVED_REFRESH_SERVICE": "abyss-nervous-derived-refresh.service",
            "NERVOUS_PASSIVE_CHRONICLE_DERIVED_DROPIN_PATH": user_systemd_dir
            / f"{nervous_passive_chronicle_service}.d"
            / "50-derived-refresh.conf",
            "NERVOUS_SEMANTIC_INDEX_ROOT": nervous_semantic_index_root,
            "NERVOUS_SEMANTIC_INDEX_DB_PATH": nervous_semantic_index_db_path,
            "NERVOUS_SEMANTIC_INDEX_LATEST_PATH": nervous_root / "indexes" / "semantic" / "latest.json",
            "NERVOUS_SEMANTIC_MAINTAIN_ROOT": nervous_semantic_maintain_root,
            "NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH": nervous_semantic_maintain_root / "latest.json",
            "NERVOUS_SEMANTIC_EVAL_ROOT": nervous_evals_root / "semantic",
            "NERVOUS_SEMANTIC_EVAL_LATEST_PATH": nervous_evals_root / "semantic" / "latest.json",
            "NERVOUS_RERANK_EVAL_ROOT": nervous_evals_root / "rerank",
            "NERVOUS_RERANK_EVAL_LATEST_PATH": nervous_evals_root / "rerank" / "latest.json",
            "NERVOUS_SEMANTIC_MAINTAIN_SERVICE": "abyss-nervous-semantic-maintain.service",
            "NERVOUS_SEMANTIC_MAINTAIN_TIMER": "abyss-nervous-semantic-maintain.timer",
            "NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND": (
                "abyss-machine nervous semantic-maintain --dry-run --refresh-index-first --json"
            ),
            "NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND": (
                "abyss-machine nervous semantic-maintain --refresh-index-first --json"
            ),
            "NERVOUS_SEMANTIC_MAINTAIN_STATUS_COMMAND": "abyss-machine nervous semantic-status --json",
            "NERVOUS_QUALITY_AUDIT_COMMAND": "abyss-machine nervous quality-audit --json",
            "NERVOUS_QUALITY_AUDIT_REFRESH_COMMAND": "abyss-machine nervous quality-audit --refresh --json",
            "NERVOUS_QUALITY_AUDIT_REFRESH_INDEX_COMMAND": (
                "abyss-machine nervous quality-audit --refresh --refresh-index --json"
            ),
            "NERVOUS_BRIEF_ROOT": nervous_brief_root,
            "NERVOUS_BRIEF_LATEST_PATH": nervous_brief_root / "latest.json",
            "NERVOUS_VALIDATE_ROOT": nervous_validate_root,
            "NERVOUS_VALIDATE_LATEST_PATH": nervous_validate_root / "latest.json",
            "TYPING_ROOT": typing_root,
            "TYPING_AGENTS_PATH": typing_root / "AGENTS.md",
            "TYPING_POLICY_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_POLICY",
                path_policy.etc_file("typing-policy.json"),
            ),
            "TYPING_INDEX_PATH": typing_root / "index.json",
            "TYPING_EVENTS_ROOT": typing_events_root,
            "TYPING_EVENTS_LATEST_PATH": typing_events_root / "latest.json",
            "TYPING_CAPTURE_GATE_ROOT": typing_capture_gate_root,
            "TYPING_CAPTURE_GATE_LATEST_PATH": typing_capture_gate_root / "latest.json",
            "TYPING_PRIVACY_SELFTEST_ROOT": typing_privacy_selftest_root,
            "TYPING_PRIVACY_SELFTEST_LATEST_PATH": typing_privacy_selftest_root / "latest.json",
            "TYPING_COVERAGE_ROOT": typing_coverage_root,
            "TYPING_COVERAGE_LATEST_PATH": typing_coverage_root / "latest.json",
            "TYPING_PROCESS_ROOT": typing_process_root,
            "TYPING_PROCESS_LATEST_PATH": typing_process_root / "latest.json",
            "TYPING_NERVOUS_REFRESH_ROOT": typing_nervous_refresh_root,
            "TYPING_NERVOUS_REFRESH_LATEST_PATH": typing_nervous_refresh_root / "latest.json",
            "TYPING_FOCUSED_SNAPSHOT_ROOT": typing_focused_snapshot_root,
            "TYPING_FOCUSED_SNAPSHOT_LATEST_PATH": typing_focused_snapshot_root / "latest.json",
            "TYPING_ATSPI_TEXT_EVENTS_ROOT": typing_atspi_text_events_root,
            "TYPING_ATSPI_TEXT_EVENTS_LATEST_PATH": typing_atspi_text_events_root / "latest.json",
            "TYPING_GENERIC_GUI_SELFTEST_ROOT": typing_generic_gui_selftest_root,
            "TYPING_GENERIC_GUI_SELFTEST_LATEST_PATH": typing_generic_gui_selftest_root / "latest.json",
            "TYPING_VALIDATE_ROOT": typing_validate_root,
            "TYPING_VALIDATE_LATEST_PATH": typing_validate_root / "latest.json",
            "TYPING_SAVED_TEXT_ROOT": typing_saved_text_root,
            "TYPING_SAVED_TEXT_LATEST_PATH": typing_saved_text_root / "latest.json",
            "TYPING_SAVED_TEXT_STATE_PATH": typing_saved_text_root / "state.json",
            "TYPING_ZSH_HOOK_ROOT": typing_zsh_hook_root,
            "TYPING_ZSH_HOOK_STATUS_ROOT": typing_zsh_hook_status_root,
            "TYPING_ZSH_HOOK_STATUS_LATEST_PATH": typing_zsh_hook_status_root / "latest.json",
            "TYPING_ZSH_HOOK_SELFTEST_ROOT": typing_zsh_hook_selftest_root,
            "TYPING_ZSH_HOOK_SELFTEST_LATEST_PATH": typing_zsh_hook_selftest_root / "latest.json",
            "TYPING_ZSH_HOOK_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_ZSH_HOOK",
                home / ".config/zsh/abyss-typing.zsh",
            ),
            "TYPING_ZSHRC_PATH": self._env_path("ABYSS_MACHINE_ZSHRC", home / ".zshrc"),
            "TYPING_CODEX_HOOK_ROOT": typing_codex_hook_root,
            "TYPING_CODEX_HOOK_EVENTS_ROOT": typing_codex_hook_events_root,
            "TYPING_CODEX_HOOK_EVENTS_LATEST_PATH": typing_codex_hook_events_root / "latest.json",
            "TYPING_CODEX_HOOK_STATUS_ROOT": typing_codex_hook_status_root,
            "TYPING_CODEX_HOOK_STATUS_LATEST_PATH": typing_codex_hook_status_root / "latest.json",
            "TYPING_CODEX_HOOK_SELFTEST_ROOT": typing_codex_hook_selftest_root,
            "TYPING_CODEX_HOOK_SELFTEST_LATEST_PATH": typing_codex_hook_selftest_root / "latest.json",
            "TYPING_CODEX_SESSION_TAIL_ROOT": typing_codex_session_tail_root,
            "TYPING_CODEX_SESSION_TAIL_LATEST_PATH": typing_codex_session_tail_root / "latest.json",
            "TYPING_CODEX_SESSION_TAIL_STATE_PATH": typing_codex_session_tail_root / "state.json",
            "TYPING_CODEX_SESSIONS_ROOT": self._env_path(
                "ABYSS_MACHINE_CODEX_SESSIONS_ROOT",
                home / ".codex/sessions",
            ),
            "TYPING_EDITOR_EXTENSION_ROOT": typing_editor_extension_root,
            "TYPING_EDITOR_EXTENSION_LATEST_PATH": typing_editor_extension_root / "latest.json",
            "TYPING_EDITOR_EXTENSION_SELFTEST_ROOT": typing_editor_extension_selftest_root,
            "TYPING_EDITOR_EXTENSION_SELFTEST_LATEST_PATH": typing_editor_extension_selftest_root / "latest.json",
            "TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_ROOT": typing_editor_extension_callback_selftest_root,
            "TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_LATEST_PATH": (
                typing_editor_extension_callback_selftest_root / "latest.json"
            ),
            "TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_TMP_ROOT": self._env_path(
                "ABYSS_MACHINE_TYPING_EDITOR_CALLBACK_SELFTEST_TMP",
                tmp_root / "typing-editor-callback-selftest",
            ),
            "TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_FILE": self._env_path(
                "ABYSS_MACHINE_TYPING_EDITOR_CALLBACK_SELFTEST_FILE",
                home / "md/.abyss-machine/typing-editor-callback-selftest.txt",
            ),
            "TYPING_VSCODE_EXTENSION_ID": "abyss-machine.typing-intake",
            "TYPING_VSCODE_EXTENSION_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_VSCODE_EXTENSION",
                home / ".vscode/extensions/abyss-machine.typing-intake-0.1.0",
            ),
            "TYPING_BROWSER_EXTENSION_ROOT": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_EXTENSION",
                srv_root / "tools/typing/firefox-extension",
            ),
            "TYPING_BROWSER_EXTENSION_XPI_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_EXTENSION",
                srv_root / "tools/typing/firefox-extension",
            )
            / "abyss-machine-typing-intake.xpi",
            "TYPING_BROWSER_EXTENSION_ID": "abyss-machine-typing-intake@abyss.local",
            "TYPING_BROWSER_NATIVE_HOST_NAME": typing_browser_native_host_name,
            "TYPING_BROWSER_NATIVE_HOST_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_NATIVE_HOST",
                srv_root / "tools/typing/browser-native-host",
            ),
            "TYPING_BROWSER_NATIVE_HOST_USER_MANIFEST": home
            / ".mozilla/native-messaging-hosts"
            / f"{typing_browser_native_host_name}.json",
            "TYPING_BROWSER_EXTENSION_STATUS_ROOT": typing_browser_extension_status_root,
            "TYPING_BROWSER_EXTENSION_LATEST_PATH": typing_browser_extension_status_root / "latest.json",
            "TYPING_BROWSER_AI_TRANSCRIPT_ROOT": typing_browser_ai_transcript_root,
            "TYPING_BROWSER_AI_TRANSCRIPT_LATEST_PATH": typing_browser_ai_transcript_root / "latest.json",
            "TYPING_BROWSER_AI_TRANSCRIPT_SELFTEST_ROOT": typing_browser_ai_transcript_selftest_root,
            "TYPING_BROWSER_AI_TRANSCRIPT_SELFTEST_LATEST_PATH": (
                typing_browser_ai_transcript_selftest_root / "latest.json"
            ),
            "TYPING_BROWSER_WEBEXTENSION_SELFTEST_ROOT": typing_browser_webextension_selftest_root,
            "TYPING_BROWSER_WEBEXTENSION_SELFTEST_LATEST_PATH": (
                typing_browser_webextension_selftest_root / "latest.json"
            ),
            "TYPING_BROWSER_WEBEXTENSION_SELFTEST_TMP_ROOT": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_WEBEXTENSION_SELFTEST_TMP",
                tmp_root / "typing-browser-webextension-selftest",
            ),
            "TYPING_BROWSER_WEBEXTENSION_NPM_CACHE": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_WEBEXTENSION_NPM_CACHE",
                cache_root / "npm",
            ),
            "TYPING_BROWSER_ATSPI_SELFTEST_ROOT": typing_browser_atspi_selftest_root,
            "TYPING_BROWSER_ATSPI_SELFTEST_LATEST_PATH": typing_browser_atspi_selftest_root / "latest.json",
            "TYPING_BROWSER_ATSPI_RELEASE_SELFTEST_ROOT": typing_browser_atspi_release_selftest_root,
            "TYPING_BROWSER_ATSPI_RELEASE_SELFTEST_LATEST_PATH": (
                typing_browser_atspi_release_selftest_root / "latest.json"
            ),
            "TYPING_BROWSER_ATSPI_SELFTEST_TMP_ROOT": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_ATSPI_SELFTEST_TMP",
                tmp_root / "typing-browser-atspi-selftest",
            ),
            "TYPING_BROWSER_CONTEXT_SELFTEST_ROOT": typing_browser_context_selftest_root,
            "TYPING_BROWSER_CONTEXT_SELFTEST_LATEST_PATH": typing_browser_context_selftest_root / "latest.json",
            "TYPING_BROWSER_CONTEXT_SELFTEST_TMP_ROOT": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_CONTEXT_SELFTEST_TMP",
                tmp_root / "typing-browser-context-selftest",
            ),
            "TYPING_FOCUSED_BROWSER_SELFTEST_ROOT": typing_focused_browser_selftest_root,
            "TYPING_FOCUSED_BROWSER_SELFTEST_LATEST_PATH": typing_focused_browser_selftest_root / "latest.json",
            "TYPING_FOCUSED_BROWSER_SELFTEST_TMP_ROOT": self._env_path(
                "ABYSS_MACHINE_TYPING_FOCUSED_BROWSER_SELFTEST_TMP",
                tmp_root / "typing-focused-browser-selftest",
            ),
            "TYPING_BROWSER_PRIVACY_SELFTEST_ROOT": typing_browser_privacy_selftest_root,
            "TYPING_BROWSER_PRIVACY_SELFTEST_LATEST_PATH": typing_browser_privacy_selftest_root / "latest.json",
            "TYPING_BROWSER_PRIVACY_SELFTEST_TMP_ROOT": self._env_path(
                "ABYSS_MACHINE_TYPING_BROWSER_PRIVACY_SELFTEST_TMP",
                tmp_root / "typing-browser-privacy-selftest",
            ),
            "TYPING_END_TO_END_ROOT": typing_end_to_end_root,
            "TYPING_END_TO_END_LATEST_PATH": typing_end_to_end_root / "latest.json",
            "TYPING_FIREFOX_POLICIES_PATH": self._env_path(
                "ABYSS_MACHINE_FIREFOX_POLICIES",
                "/usr/lib64/firefox/distribution/policies.json",
            ),
            "TYPING_CODEX_HOOKS_PATH": self._env_path("ABYSS_MACHINE_CODEX_HOOKS", home / ".codex/hooks.json"),
            "TYPING_CODEX_CONFIG_PATH": self._env_path("ABYSS_MACHINE_CODEX_CONFIG", home / ".codex/config.toml"),
            "TYPING_USER_SYSTEMD_DIR": user_systemd_dir,
            "TYPING_FOCUSED_SNAPSHOT_SERVICE": typing_focused_snapshot_service,
            "TYPING_FOCUSED_SNAPSHOT_TIMER": typing_focused_snapshot_timer,
            "TYPING_FOCUSED_SNAPSHOT_SERVICE_PATH": user_systemd_dir / typing_focused_snapshot_service,
            "TYPING_FOCUSED_SNAPSHOT_TIMER_PATH": user_systemd_dir / typing_focused_snapshot_timer,
            "TYPING_FOCUSED_SNAPSHOT_TICK_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_FOCUSED_TICK",
                home / ".local/bin/abyss-machine-typing-focused-snapshot-tick",
            ),
            "TYPING_ATSPI_TEXT_EVENTS_SERVICE": typing_atspi_text_events_service,
            "TYPING_ATSPI_TEXT_EVENTS_SERVICE_PATH": user_systemd_dir / typing_atspi_text_events_service,
            "TYPING_CODEX_SESSION_TAIL_SERVICE": typing_codex_session_tail_service,
            "TYPING_CODEX_SESSION_TAIL_TIMER": typing_codex_session_tail_timer,
            "TYPING_CODEX_SESSION_TAIL_SERVICE_PATH": user_systemd_dir / typing_codex_session_tail_service,
            "TYPING_CODEX_SESSION_TAIL_TIMER_PATH": user_systemd_dir / typing_codex_session_tail_timer,
            "TYPING_SAVED_TEXT_SCAN_SERVICE": typing_saved_text_scan_service,
            "TYPING_SAVED_TEXT_SCAN_TIMER": typing_saved_text_scan_timer,
            "TYPING_SAVED_TEXT_SCAN_SERVICE_PATH": user_systemd_dir / typing_saved_text_scan_service,
            "TYPING_SAVED_TEXT_SCAN_TIMER_PATH": user_systemd_dir / typing_saved_text_scan_timer,
            "TYPING_SAVED_TEXT_SCAN_TICK_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_SAVED_TEXT_TICK",
                home / ".local/bin/abyss-machine-typing-saved-text-scan-tick",
            ),
            "TYPING_NERVOUS_REFRESH_SERVICE": typing_nervous_refresh_service,
            "TYPING_NERVOUS_REFRESH_TIMER": typing_nervous_refresh_timer,
            "TYPING_NERVOUS_REFRESH_SERVICE_PATH": user_systemd_dir / typing_nervous_refresh_service,
            "TYPING_NERVOUS_REFRESH_TIMER_PATH": user_systemd_dir / typing_nervous_refresh_timer,
            "TYPING_NERVOUS_REFRESH_TICK_PATH": self._env_path(
                "ABYSS_MACHINE_TYPING_NERVOUS_REFRESH_TICK",
                home / ".local/bin/abyss-machine-typing-nervous-refresh-tick",
            ),
        }


def _path_text(constants: Mapping[str, Any], key: str) -> str:
    return str(constants[key])


def _path_join(constants: Mapping[str, Any], key: str, *parts: str) -> str:
    return str(Path(constants[key]).joinpath(*parts))


def typing_paths_document(
    constants: Mapping[str, Any],
    *,
    generated_at: str,
    events_today_path: str | Path,
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
) -> dict[str, Any]:
    p = lambda key: _path_text(constants, key)
    t = lambda key: str(constants[key])
    return {
        "schema": f"{schema_prefix}_typing_paths_v1",
        "version": version,
        "generated_at": generated_at,
        "root": p("TYPING_ROOT"),
        "agent_entrypoint": p("TYPING_AGENTS_PATH"),
        "policy": p("TYPING_POLICY_PATH"),
        "index": p("TYPING_INDEX_PATH"),
        "events": {
            "root": p("TYPING_EVENTS_ROOT"),
            "latest": p("TYPING_EVENTS_LATEST_PATH"),
            "today": str(events_today_path),
            "daily_glob": _path_join(constants, "TYPING_EVENTS_ROOT", "YYYY", "MM", "YYYY-MM-DD.jsonl"),
        },
        "validate": {
            "root": p("TYPING_VALIDATE_ROOT"),
            "latest": p("TYPING_VALIDATE_LATEST_PATH"),
        },
        "capture_gate": {
            "root": p("TYPING_CAPTURE_GATE_ROOT"),
            "latest": p("TYPING_CAPTURE_GATE_LATEST_PATH"),
            "command": "abyss-machine typing capture-gate --source SOURCE --json",
        },
        "privacy_selftest": {
            "root": p("TYPING_PRIVACY_SELFTEST_ROOT"),
            "latest": p("TYPING_PRIVACY_SELFTEST_LATEST_PATH"),
            "command": "abyss-machine typing privacy-selftest --json",
            "status": "non-persisting regression probes for secret-like text, login URLs, messenger URLs, and denied paths",
        },
        "browser_privacy_selftest": {
            "root": p("TYPING_BROWSER_PRIVACY_SELFTEST_ROOT"),
            "latest": p("TYPING_BROWSER_PRIVACY_SELFTEST_LATEST_PATH"),
            "tmp_root": p("TYPING_BROWSER_PRIVACY_SELFTEST_TMP_ROOT"),
            "command": "abyss-machine typing browser-privacy-selftest --json",
            "status": "temporary Firefox loopback proof that browser login URL input stays metadata-only before text read",
        },
        "coverage": {
            "root": p("TYPING_COVERAGE_ROOT"),
            "latest": p("TYPING_COVERAGE_LATEST_PATH"),
            "command": "abyss-machine typing coverage --json",
        },
        "process": {
            "root": p("TYPING_PROCESS_ROOT"),
            "latest": p("TYPING_PROCESS_LATEST_PATH"),
            "command": "abyss-machine typing process --json",
            "status": "derived readmodel over recent committed-text events; does not widen capture",
        },
        "causal_awareness": {
            "root": p("TYPING_PROCESS_ROOT"),
            "latest": p("TYPING_PROCESS_LATEST_PATH"),
            "command": "abyss-machine typing causal-awareness --lines 240 --json",
            "status": "evidence-axis readmodel over process output; exposes known, guarded, partial, and missing causal context without extra text",
        },
        "nervous_refresh": {
            "root": p("TYPING_NERVOUS_REFRESH_ROOT"),
            "latest": p("TYPING_NERVOUS_REFRESH_LATEST_PATH"),
            "service": p("TYPING_NERVOUS_REFRESH_SERVICE_PATH"),
            "timer": p("TYPING_NERVOUS_REFRESH_TIMER_PATH"),
            "tick": p("TYPING_NERVOUS_REFRESH_TICK_PATH"),
            "interval": "180s",
            "command": "abyss-machine typing nervous-refresh --json",
            "status": "keeps typing process, nervous facts, and local FTS index fresh after new typed events without widening capture",
        },
        "focused_snapshot": {
            "adapter": "atspi_focused_text_snapshot",
            "root": p("TYPING_FOCUSED_SNAPSHOT_ROOT"),
            "latest": p("TYPING_FOCUSED_SNAPSHOT_LATEST_PATH"),
            "service": p("TYPING_FOCUSED_SNAPSHOT_SERVICE_PATH"),
            "timer": p("TYPING_FOCUSED_SNAPSHOT_TIMER_PATH"),
            "tick": p("TYPING_FOCUSED_SNAPSHOT_TICK_PATH"),
            "interval": "75s",
            "command": "abyss-machine typing focused-snapshot --json",
        },
        "atspi_text_events": {
            "adapter": "atspi_text_changed_event",
            "root": p("TYPING_ATSPI_TEXT_EVENTS_ROOT"),
            "latest": p("TYPING_ATSPI_TEXT_EVENTS_LATEST_PATH"),
            "service": p("TYPING_ATSPI_TEXT_EVENTS_SERVICE_PATH"),
            "command": "abyss-machine typing atspi-text-events --forever --json",
            "sample_command": "abyss-machine typing atspi-text-events --seconds 5 --json",
        },
        "generic_gui_selftest": {
            "adapter": "atspi_text_changed_event",
            "root": p("TYPING_GENERIC_GUI_SELFTEST_ROOT"),
            "latest": p("TYPING_GENERIC_GUI_SELFTEST_LATEST_PATH"),
            "command": "abyss-machine typing generic-gui-selftest --json",
            "status": "synthetic committed-text proof for generic editable AT-SPI text fields without a browser URL",
        },
        "saved_text_scan": {
            "adapter": "saved_text_snapshot",
            "latest": p("TYPING_SAVED_TEXT_LATEST_PATH"),
            "state": p("TYPING_SAVED_TEXT_STATE_PATH"),
            "service": p("TYPING_SAVED_TEXT_SCAN_SERVICE_PATH"),
            "timer": p("TYPING_SAVED_TEXT_SCAN_TIMER_PATH"),
            "tick": p("TYPING_SAVED_TEXT_SCAN_TICK_PATH"),
            "interval": "120s",
            "command": "abyss-machine typing saved-text-scan --json",
        },
        "zsh_hook": {
            "adapter": "zsh_preexec",
            "hook": p("TYPING_ZSH_HOOK_PATH"),
            "zshrc": p("TYPING_ZSHRC_PATH"),
            "root": p("TYPING_ZSH_HOOK_ROOT"),
            "status_latest": p("TYPING_ZSH_HOOK_STATUS_LATEST_PATH"),
            "selftest_latest": p("TYPING_ZSH_HOOK_SELFTEST_LATEST_PATH"),
            "status_command": "abyss-machine typing zsh-hook-status --json",
            "selftest_command": "abyss-machine typing zsh-hook-selftest --json",
        },
        "codex_hook": {
            "adapter": "codex_user_prompt_submit",
            "hooks_json": p("TYPING_CODEX_HOOKS_PATH"),
            "config": p("TYPING_CODEX_CONFIG_PATH"),
            "root": p("TYPING_CODEX_HOOK_ROOT"),
            "event_latest": p("TYPING_CODEX_HOOK_EVENTS_LATEST_PATH"),
            "status_latest": p("TYPING_CODEX_HOOK_STATUS_LATEST_PATH"),
            "selftest_latest": p("TYPING_CODEX_HOOK_SELFTEST_LATEST_PATH"),
            "hook_command": "abyss-machine typing codex-prompt-hook",
            "status_command": "abyss-machine typing codex-hook-status --json",
            "selftest_command": "abyss-machine typing codex-hook-selftest --json",
        },
        "codex_session_tail": {
            "adapter": "codex_session_jsonl_prompt_tail",
            "sessions_root": p("TYPING_CODEX_SESSIONS_ROOT"),
            "root": p("TYPING_CODEX_SESSION_TAIL_ROOT"),
            "latest": p("TYPING_CODEX_SESSION_TAIL_LATEST_PATH"),
            "state": p("TYPING_CODEX_SESSION_TAIL_STATE_PATH"),
            "service": p("TYPING_CODEX_SESSION_TAIL_SERVICE_PATH"),
            "timer": p("TYPING_CODEX_SESSION_TAIL_TIMER_PATH"),
            "interval": "1s",
            "command": "abyss-machine typing codex-session-tail --files 8 --json",
            "service_command": "abyss-machine typing codex-session-tail --files 8 --interval 1 --forever",
            "status": "near-live fallback over Codex raw JSONL user-message records; supports event_msg.user_message and response_item role=user input_text; includes recent active state files beyond newest mtimes; still passes typing capture-gate",
        },
        "editor_extension": {
            "adapter": "editor_extension_explicit",
            "id": t("TYPING_VSCODE_EXTENSION_ID"),
            "extension": p("TYPING_VSCODE_EXTENSION_PATH"),
            "latest": p("TYPING_EDITOR_EXTENSION_LATEST_PATH"),
            "selftest_latest": p("TYPING_EDITOR_EXTENSION_SELFTEST_LATEST_PATH"),
            "callback_selftest_latest": p("TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_LATEST_PATH"),
            "callback_selftest_tmp_root": p("TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_TMP_ROOT"),
            "callback_selftest_file": p("TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_FILE"),
            "selftest_command": "abyss-machine typing editor-extension-selftest --json",
            "callback_selftest_command": "abyss-machine typing editor-callback-selftest --json",
            "status": "activated by VS Code extension host when VS Code is running",
        },
        "browser_extension": {
            "adapter": "browser_extension_explicit",
            "id": t("TYPING_BROWSER_EXTENSION_ID"),
            "extension": p("TYPING_BROWSER_EXTENSION_ROOT"),
            "xpi": p("TYPING_BROWSER_EXTENSION_XPI_PATH"),
            "native_host": t("TYPING_BROWSER_NATIVE_HOST_NAME"),
            "native_host_wrapper": p("TYPING_BROWSER_NATIVE_HOST_PATH"),
            "native_host_manifest": p("TYPING_BROWSER_NATIVE_HOST_USER_MANIFEST"),
            "firefox_policies": p("TYPING_FIREFOX_POLICIES_PATH"),
            "latest": p("TYPING_BROWSER_EXTENSION_LATEST_PATH"),
            "status_command": "abyss-machine typing browser-extension-status --json",
            "selftest_command": "abyss-machine typing browser-extension-selftest --json",
        },
        "browser_ai_transcript": {
            "adapter": "browser_ai_transcript",
            "root": p("TYPING_BROWSER_AI_TRANSCRIPT_ROOT"),
            "latest": p("TYPING_BROWSER_AI_TRANSCRIPT_LATEST_PATH"),
            "selftest_latest": p("TYPING_BROWSER_AI_TRANSCRIPT_SELFTEST_LATEST_PATH"),
            "command": "abyss-machine typing browser-ai-transcript-selftest --json",
            "status": "explicit AI-chat message transcript route from Firefox content script; separate from typed browser input and AT-SPI page fallback",
        },
        "browser_webextension_selftest": {
            "adapter": "browser_extension_explicit",
            "root": p("TYPING_BROWSER_WEBEXTENSION_SELFTEST_ROOT"),
            "latest": p("TYPING_BROWSER_WEBEXTENSION_SELFTEST_LATEST_PATH"),
            "tmp_root": p("TYPING_BROWSER_WEBEXTENSION_SELFTEST_TMP_ROOT"),
            "npm_cache": p("TYPING_BROWSER_WEBEXTENSION_NPM_CACHE"),
            "command": "abyss-machine typing browser-webextension-selftest --json",
            "status": "temporary Firefox profile proof; does not mutate release profiles",
        },
        "browser_atspi_selftest": {
            "adapter": "atspi_text_changed_event",
            "root": p("TYPING_BROWSER_ATSPI_SELFTEST_ROOT"),
            "latest": p("TYPING_BROWSER_ATSPI_SELFTEST_LATEST_PATH"),
            "tmp_root": p("TYPING_BROWSER_ATSPI_SELFTEST_TMP_ROOT"),
            "command": "abyss-machine typing browser-atspi-selftest --json",
        },
        "browser_context_selftest": {
            "adapter": "browser_active_tab",
            "root": p("TYPING_BROWSER_CONTEXT_SELFTEST_ROOT"),
            "latest": p("TYPING_BROWSER_CONTEXT_SELFTEST_LATEST_PATH"),
            "tmp_root": p("TYPING_BROWSER_CONTEXT_SELFTEST_TMP_ROOT"),
            "command": "abyss-machine typing browser-context-selftest --json",
            "status": "temporary Firefox proof for browser-content capture and AT-SPI URL context inference",
        },
        "browser_atspi_release_selftest": {
            "adapter": "atspi_text_changed_event",
            "root": p("TYPING_BROWSER_ATSPI_RELEASE_SELFTEST_ROOT"),
            "latest": p("TYPING_BROWSER_ATSPI_RELEASE_SELFTEST_LATEST_PATH"),
            "tmp_root": p("TYPING_BROWSER_ATSPI_SELFTEST_TMP_ROOT"),
            "command": "abyss-machine typing browser-atspi-selftest --release-profile --json",
            "status": "Firefox release-profile safe loopback proof for AT-SPI browser fallback; separate from temporary-profile proof",
        },
        "focused_browser_selftest": {
            "adapter": "atspi_focused_text_snapshot",
            "root": p("TYPING_FOCUSED_BROWSER_SELFTEST_ROOT"),
            "latest": p("TYPING_FOCUSED_BROWSER_SELFTEST_LATEST_PATH"),
            "tmp_root": p("TYPING_FOCUSED_BROWSER_SELFTEST_TMP_ROOT"),
            "command": "abyss-machine typing focused-browser-selftest --json",
            "status": "temporary Firefox loopback proof for focused safe-browser fallback",
        },
        "end_to_end": {
            "root": p("TYPING_END_TO_END_ROOT"),
            "latest": p("TYPING_END_TO_END_LATEST_PATH"),
            "command": "abyss-machine typing end-to-end --json",
        },
        "commands": {
            "status": "abyss-machine typing status --json",
            "paths": "abyss-machine typing paths --json",
            "policy": "abyss-machine typing policy --json",
            "ingest": "printf %s TEXT | abyss-machine typing ingest --stdin --source SOURCE --json",
            "latest": "abyss-machine typing latest --json",
            "tail": "abyss-machine typing tail --lines 20 --json",
            "causal_context": "abyss-machine typing causal-context --lines 20 --json",
            "causal_awareness": "abyss-machine typing causal-awareness --lines 240 --json",
            "capture_gate": "abyss-machine typing capture-gate --source SOURCE --json",
            "privacy_selftest": "abyss-machine typing privacy-selftest --json",
            "coverage": "abyss-machine typing coverage --json",
            "process": "abyss-machine typing process --json",
            "nervous_refresh": "abyss-machine typing nervous-refresh --json",
            "focused_snapshot": "abyss-machine typing focused-snapshot --json",
            "atspi_text_events": "abyss-machine typing atspi-text-events --seconds 5 --json",
            "generic_gui_selftest": "abyss-machine typing generic-gui-selftest --json",
            "saved_text_scan": "abyss-machine typing saved-text-scan --json",
            "zsh_hook_status": "abyss-machine typing zsh-hook-status --json",
            "zsh_hook_selftest": "abyss-machine typing zsh-hook-selftest --json",
            "codex_prompt_hook": "abyss-machine typing codex-prompt-hook",
            "codex_hook_status": "abyss-machine typing codex-hook-status --json",
            "codex_hook_selftest": "abyss-machine typing codex-hook-selftest --json",
            "codex_session_tail": "abyss-machine typing codex-session-tail --json",
            "editor_extension_selftest": "abyss-machine typing editor-extension-selftest --json",
            "editor_callback_selftest": "abyss-machine typing editor-callback-selftest --json",
            "browser_extension_status": "abyss-machine typing browser-extension-status --json",
            "browser_extension_selftest": "abyss-machine typing browser-extension-selftest --json",
            "browser_ai_transcript_selftest": "abyss-machine typing browser-ai-transcript-selftest --json",
            "browser_webextension_selftest": "abyss-machine typing browser-webextension-selftest --json",
            "browser_atspi_selftest": "abyss-machine typing browser-atspi-selftest --json",
            "browser_atspi_release_selftest": "abyss-machine typing browser-atspi-selftest --release-profile --json",
            "browser_context_selftest": "abyss-machine typing browser-context-selftest --json",
            "focused_browser_selftest": "abyss-machine typing focused-browser-selftest --json",
            "browser_privacy_selftest": "abyss-machine typing browser-privacy-selftest --json",
            "end_to_end": "abyss-machine typing end-to-end --json",
            "redact_test": "abyss-machine typing redact-test --text TEXT --json",
            "validate": "abyss-machine typing validate --json",
        },
    }


def typing_index_document_from_paths(
    constants: Mapping[str, Any],
    paths_document: Mapping[str, Any],
    *,
    generated_at: str,
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
) -> dict[str, Any]:
    p = lambda key: _path_text(constants, key)
    return {
        "schema": f"{schema_prefix}_typing_index_v1",
        "version": version,
        "generated_at": generated_at,
        "paths": dict(paths_document),
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "committed_text_only": True,
            "raw_private_content": False,
            "automatic_action": False,
        },
        "commands": paths_document.get("commands", {}) if isinstance(paths_document.get("commands"), Mapping) else {},
        "causal_context": {
            "schema": f"{schema_prefix}_typing_causal_context_v1",
            "stores_text": False,
            "automatic_action": False,
            "intent_claim": False,
            "fields": ["input", "where", "recipient", "task", "policy"],
        },
        "capture_gate": {
            "schema": f"{schema_prefix}_typing_capture_gate_v1",
            "default_decision": "metadata_only",
            "offline_only": True,
            "network_access": False,
            "decisions": ["allow_text", "metadata_only", "skip", "needs_review"],
        },
        "privacy_selftest": {
            "schema": f"{schema_prefix}_typing_privacy_selftest_v1",
            "latest": p("TYPING_PRIVACY_SELFTEST_LATEST_PATH"),
            "writes_typing_events": False,
            "proves_secret_like_text_metadata_only": True,
            "automatic_action": False,
        },
        "browser_privacy_selftest": {
            "schema": f"{schema_prefix}_typing_browser_privacy_selftest_v1",
            "latest": p("TYPING_BROWSER_PRIVACY_SELFTEST_LATEST_PATH"),
            "runtime_loopback_firefox": True,
            "proves_login_url_metadata_only_before_text_read": True,
            "raw_keylogging": False,
        },
        "coverage": {
            "schema": f"{schema_prefix}_typing_coverage_v1",
            "latest": p("TYPING_COVERAGE_LATEST_PATH"),
            "tracks": ["adapters", "live_input_lanes", "saved_text_fallback", "capture_gate_decisions", "recipients", "projects", "coverage_gaps", "browser_input_recency"],
            "automatic_action": False,
        },
        "process": {
            "schema": f"{schema_prefix}_typing_process_v1",
            "latest": p("TYPING_PROCESS_LATEST_PATH"),
            "tracks": ["causal_lanes", "task_bindings", "recipients", "projects", "context_anchors", "quality_gaps"],
            "stores_extra_text": False,
            "widens_capture": False,
            "automatic_action": False,
        },
        "nervous_refresh": {
            "schema": f"{schema_prefix}_typing_nervous_refresh_v1",
            "latest": p("TYPING_NERVOUS_REFRESH_LATEST_PATH"),
            "service": constants["TYPING_NERVOUS_REFRESH_SERVICE"],
            "timer": constants["TYPING_NERVOUS_REFRESH_TIMER"],
            "keeps_process_facts_index_fresh": True,
            "resource_gated_index_work": True,
            "requires_privileged_access": False,
            "widens_capture": False,
            "automatic_action": False,
        },
        "focused_snapshot": {
            "adapter": "atspi_focused_text_snapshot",
            "latest": p("TYPING_FOCUSED_SNAPSHOT_LATEST_PATH"),
            "selftest": p("TYPING_FOCUSED_BROWSER_SELFTEST_LATEST_PATH"),
            "mode": "safe_text_routes",
            "text_capture_enabled": True,
            "requires_capture_gate_allow_text": True,
            "safe_text_routes": ["browser_safe_url", "generic_editable_text"],
            "primary_capture_by": "atspi_text_changed_event",
            "raw_keylogging": False,
        },
        "zsh_hook": {
            "adapter": "zsh_preexec",
            "status": p("TYPING_ZSH_HOOK_STATUS_LATEST_PATH"),
            "selftest": p("TYPING_ZSH_HOOK_SELFTEST_LATEST_PATH"),
            "committed_shell_commands_only": True,
            "raw_keylogging": False,
        },
        "editor_extension": {
            "adapter": "editor_extension_explicit",
            "status": p("TYPING_EDITOR_EXTENSION_LATEST_PATH"),
            "selftest": p("TYPING_EDITOR_EXTENSION_SELFTEST_LATEST_PATH"),
            "callback_selftest": p("TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_LATEST_PATH"),
            "committed_editor_changes_only": True,
            "live_vscode_callback_proof": True,
            "raw_keylogging": False,
        },
        "browser_extension": {
            "adapter": "browser_extension_explicit",
            "id": constants["TYPING_BROWSER_EXTENSION_ID"],
            "extension": p("TYPING_BROWSER_EXTENSION_ROOT"),
            "native_host": p("TYPING_BROWSER_NATIVE_HOST_USER_MANIFEST"),
            "status": p("TYPING_BROWSER_EXTENSION_LATEST_PATH"),
            "webextension_selftest": p("TYPING_BROWSER_WEBEXTENSION_SELFTEST_LATEST_PATH"),
            "committed_page_text_only": True,
            "requires_safe_url": True,
            "raw_keylogging": False,
        },
        "browser_atspi_fallback": {
            "adapter": "atspi_text_changed_event",
            "selftest": p("TYPING_BROWSER_ATSPI_SELFTEST_LATEST_PATH"),
            "context_selftest": p("TYPING_BROWSER_CONTEXT_SELFTEST_LATEST_PATH"),
            "requires_safe_browser_url": True,
            "context_inference": "recent_browser_content_atspi_path",
            "recency_reported_in_coverage": True,
            "raw_keylogging": False,
        },
        "generic_gui_committed_text": {
            "adapter": "atspi_text_changed_event",
            "selftest": p("TYPING_GENERIC_GUI_SELFTEST_LATEST_PATH"),
            "requires_editable_text_role": True,
            "requires_capture_gate_allow_text": True,
            "rejects_sensitive_state": True,
            "rejects_browser_without_safe_url": True,
            "raw_keylogging": False,
        },
        "saved_text_fallback": {
            "adapter": "saved_text_snapshot",
            "selection_filter": "low_signal_artifact_path_tokens",
            "secret_deny_filter": "deny_path_tokens",
            "reported_separately_from_live_input": True,
            "raw_keylogging": False,
        },
        "focused_browser_fallback": {
            "adapter": "atspi_focused_text_snapshot",
            "selftest": p("TYPING_FOCUSED_BROWSER_SELFTEST_LATEST_PATH"),
            "privacy_selftest": p("TYPING_BROWSER_PRIVACY_SELFTEST_LATEST_PATH"),
            "requires_safe_browser_url": True,
            "loopback_probe_only": True,
            "reads_focused_accessibility_text_only_after_gate": True,
            "raw_keylogging": False,
        },
        "end_to_end": {
            "schema": f"{schema_prefix}_typing_end_to_end_v1",
            "latest": p("TYPING_END_TO_END_LATEST_PATH"),
            "runs_safe_adapter_selftests": True,
            "refreshes_nervous_snapshot_index": True,
            "requires_privileged_access": False,
            "widens_capture": False,
        },
    }


DEFAULT_TYPING_NERVOUS_POLICY = TypingNervousPolicy.from_path_policy(DEFAULT_PATH_POLICY)
