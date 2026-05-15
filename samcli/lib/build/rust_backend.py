"""
Optional bridge to the Rust build core.

This module is deliberately opt-in while the native extension packaging path is
being proven out. Set ``SAM_CLI_RUST_BUILD_CORE=1`` to allow call sites to use
the Rust backend when the extension module is importable.
"""

import os
from typing import Any, Dict, List, Optional

RUST_BUILD_CORE_ENV_VAR = "SAM_CLI_RUST_BUILD_CORE"
RUST_BUILD_CORE_SHADOW_ENV_VAR = "SAM_CLI_RUST_BUILD_CORE_SHADOW"

try:
    from samcli.lib.build import _sam_build_core as _native
except ImportError:  # pragma: no cover - depends on optional native module
    _native = None


def is_enabled() -> bool:
    """Return True when the optional Rust backend is available and requested."""
    return os.getenv(RUST_BUILD_CORE_ENV_VAR) == "1" and _native is not None


def is_shadow_enabled() -> bool:
    """Return True when Rust may be used only for comparison/telemetry."""
    return os.getenv(RUST_BUILD_CORE_SHADOW_ENV_VAR) == "1" and _native is not None


def sha256_dir_checksum(directory: str, ignore_list: Optional[List[str]] = None) -> Optional[str]:
    """Calculate a source tree SHA-256 checksum through Rust when enabled."""
    if not is_enabled():
        return None
    return str(_native.sha256_dir_checksum(directory, ignore_list or []))


def plan_build(
    runtime: Optional[str],
    use_container: bool,
    cache_exists: bool,
    previous_source_hash: str,
    current_source_hash: str,
    current_manifest_hash: Optional[str],
    previous_manifest_hash: str,
    dependencies_dir_exists: bool,
) -> Optional[Dict[str, Any]]:
    """Return a Rust-generated build plan when the backend is enabled."""
    if not is_enabled():
        return None
    return _plan_build(
        runtime,
        use_container,
        cache_exists,
        previous_source_hash,
        current_source_hash,
        current_manifest_hash,
        previous_manifest_hash,
        dependencies_dir_exists,
    )


def shadow_plan_build(
    runtime: Optional[str],
    use_container: bool,
    cache_exists: bool,
    previous_source_hash: str,
    current_source_hash: str,
    current_manifest_hash: Optional[str],
    previous_manifest_hash: str,
    dependencies_dir_exists: bool,
) -> Optional[Dict[str, Any]]:
    """Return a Rust-generated plan only for side-by-side validation."""
    if not is_shadow_enabled():
        return None
    return _plan_build(
        runtime,
        use_container,
        cache_exists,
        previous_source_hash,
        current_source_hash,
        current_manifest_hash,
        previous_manifest_hash,
        dependencies_dir_exists,
    )


def shadow_batch_plan_builds(inputs: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Return Rust-generated plans for multiple definitions in one shadow call."""
    if not is_shadow_enabled():
        return None
    return [dict(plan) for plan in _native.batch_plan_builds(inputs)]


def shadow_batch_plan_modes(inputs: List[tuple[str, Optional[str], bool]]) -> Optional[List[tuple[str, str]]]:
    """Return Rust-generated build modes in a compact batch representation."""
    if not is_shadow_enabled():
        return None
    return list(_native.batch_plan_modes(inputs))


def shadow_dedupe_function_specs(inputs: List[Dict[str, Any]]) -> Optional[List[List[str]]]:
    """Return deduped function groups from compact raw specs for shadow comparison."""
    if not is_shadow_enabled():
        return None
    return [list(group) for group in _native.dedupe_function_specs(inputs)]


def dedupe_function_specs(inputs: List[Dict[str, Any]]) -> Optional[List[List[str]]]:
    """Return deduped function groups when the Rust backend is enabled."""
    if not is_enabled():
        return None
    return [list(group) for group in _native.dedupe_function_specs(inputs)]


def shadow_dedupe_layer_specs(inputs: List[Dict[str, Any]]) -> Optional[List[List[str]]]:
    """Return deduped layer groups from compact raw specs for shadow comparison."""
    if not is_shadow_enabled():
        return None
    return [list(group) for group in _native.dedupe_layer_specs(inputs)]


def dedupe_layer_specs(inputs: List[Dict[str, Any]]) -> Optional[List[List[str]]]:
    """Return deduped layer groups when the Rust backend is enabled."""
    if not is_enabled():
        return None
    return [list(group) for group in _native.dedupe_layer_specs(inputs)]


def plan_graph_groups(
    function_inputs: List[tuple],
    layer_inputs: List[tuple],
) -> Optional[tuple[List[List[int]], List[List[int]]]]:
    """Return compact function/layer graph groups from one native call."""
    if not is_enabled():
        return None
    function_groups, layer_groups = _native.plan_graph_groups(function_inputs, layer_inputs)
    return [list(group) for group in function_groups], [list(group) for group in layer_groups]


def shadow_plan_graph_groups(
    function_inputs: List[tuple],
    layer_inputs: List[tuple],
) -> Optional[tuple[List[List[int]], List[List[int]]]]:
    """Return compact function/layer graph groups for shadow comparison."""
    if not is_shadow_enabled():
        return None
    function_groups, layer_groups = _native.plan_graph_groups(function_inputs, layer_inputs)
    return [list(group) for group in function_groups], [list(group) for group in layer_groups]


def write_hash_updates(
    path: str,
    function_updates: List[tuple[str, str, str]],
    layer_updates: List[tuple[str, str, str]],
) -> bool:
    """Persist build graph hash updates through Rust when enabled."""
    if not is_enabled():
        return False
    _native.write_hash_updates(path, function_updates, layer_updates)
    return True


def _plan_build(
    runtime: Optional[str],
    use_container: bool,
    cache_exists: bool,
    previous_source_hash: str,
    current_source_hash: str,
    current_manifest_hash: Optional[str],
    previous_manifest_hash: str,
    dependencies_dir_exists: bool,
) -> Dict[str, Any]:
    return dict(
        _native.plan_build(
            runtime,
            use_container,
            cache_exists,
            previous_source_hash,
            current_source_hash,
            current_manifest_hash,
            previous_manifest_hash,
            dependencies_dir_exists,
        )
    )


def remove_redundant_folders(base_dir: str, retained_uuids: List[str]) -> Optional[List[str]]:
    """Remove redundant folders through Rust when enabled."""
    if not is_enabled():
        return None
    return list(_native.remove_redundant_folders(base_dir, retained_uuids))
