"""
Optional bridge to the Rust build core.

The rollout policy is intentionally centralized here so the Rust backend can be
default-on while keeping explicit opt-out and shadow-mode escape hatches.
"""

import json
import os
from typing import Any, Dict, List, Optional

RUST_BUILD_CORE_ENV_VAR = "SAM_CLI_RUST_BUILD_CORE"
RUST_BUILD_CORE_SHADOW_ENV_VAR = "SAM_CLI_RUST_BUILD_CORE_SHADOW"
RUST_BUILD_CORE_DEFAULT_ENABLED = True

try:
    from samcli.lib.build import _sam_build_core as _native
except ImportError:  # pragma: no cover - depends on optional native module
    _native = None


def _env_flag(name: str) -> Optional[bool]:
    value = os.getenv(name)
    if value is None:
        return None
    return value == "1"


def _call_optional_native(native_fn, *args):
    """
    Call a rollout-only native boundary and fall back when inputs are not yet
    compatible with the typed Rust ABI.

    This keeps default-on rollout safe for legacy/test-only provider shapes
    while the Python fallback remains available.
    """
    try:
        return native_fn(*args)
    except (TypeError, ValueError):
        return None


def is_enabled() -> bool:
    """Return True when the native backend should be used for active execution."""
    if _native is None:
        return False
    explicit = _env_flag(RUST_BUILD_CORE_ENV_VAR)
    if explicit is not None:
        return explicit
    if _env_flag(RUST_BUILD_CORE_SHADOW_ENV_VAR) is True:
        return False
    return RUST_BUILD_CORE_DEFAULT_ENABLED


def is_shadow_enabled() -> bool:
    """Return True when Rust may be used only for comparison/telemetry."""
    if _native is None or is_enabled():
        return False
    return _env_flag(RUST_BUILD_CORE_SHADOW_ENV_VAR) is True


def backend_mode() -> str:
    """Return the selected rollout mode for diagnostics and future promotion."""
    if is_enabled():
        return "active"
    if is_shadow_enabled():
        return "shadow"
    return "python"


def sha256_dir_checksum(directory: str, ignore_list: Optional[List[str]] = None) -> Optional[str]:
    """Calculate a source tree SHA-256 checksum through Rust when enabled."""
    if not is_enabled():
        return None
    try:
        return str(_native.sha256_dir_checksum(os.fspath(directory), ignore_list or []))
    except (OSError, TypeError):
        return None


def create_runtime_definition_record(uuid: str, source_hash: str, manifest_hash: str) -> Optional[Any]:
    """Create a Rust-owned mutable persisted-state record when enabled."""
    if not is_enabled():
        return None
    try:
        return _native.RuntimeDefinitionRecord(uuid, source_hash, manifest_hash)
    except TypeError:
        return None


def create_runtime_function_record(
    uuid: str,
    source_hash: str,
    manifest_hash: str,
    runtime: Optional[str],
    codeuri: Optional[str],
    imageuri: Optional[str],
    packagetype: str,
    architecture: str,
    handler: Optional[str],
    metadata: Any,
    env_vars: Any,
) -> Optional[Any]:
    """Create a Rust-owned function runtime record when enabled."""
    if not is_enabled():
        return None
    try:
        metadata_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
        env_vars_json = json.dumps(env_vars, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    try:
        return _native.RuntimeFunctionRecord(
            uuid,
            source_hash,
            manifest_hash,
            runtime,
            codeuri,
            imageuri,
            packagetype,
            architecture,
            handler,
            metadata_json,
            env_vars_json,
        )
    except TypeError:
        return None


def create_runtime_layer_record(
    uuid: str,
    source_hash: str,
    manifest_hash: str,
    full_path: str,
    codeuri: Optional[str],
    build_method: Optional[str],
    compatible_runtimes: Optional[List[str]],
    architecture: str,
    env_vars: Any,
) -> Optional[Any]:
    """Create a Rust-owned layer runtime record when enabled."""
    if not is_enabled():
        return None
    try:
        env_vars_json = json.dumps(env_vars, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    try:
        return _native.RuntimeLayerRecord(
            uuid,
            source_hash,
            manifest_hash,
            full_path,
            codeuri,
            build_method,
            compatible_runtimes,
            architecture,
            env_vars_json,
        )
    except TypeError:
        return None


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


def plan_graph_groups_from_resources(
    functions: List[Any],
    function_env_vars: Dict[str, Dict],
    layers: List[Any],
    layer_env_vars: Dict[str, Dict],
) -> Optional[tuple[List[List[int]], List[List[int]]]]:
    """Return native graph groups directly from current provider resources."""
    if not is_enabled():
        return None
    native_fn = getattr(_native, "plan_graph_groups_from_resources", None)
    if native_fn is None:
        return None
    result = _call_optional_native(
        native_fn,
        functions, function_env_vars, layers, layer_env_vars
    )
    if result is None:
        return None
    function_groups, layer_groups = result
    return [list(group) for group in function_groups], [list(group) for group in layer_groups]


def current_graph_rows(
    functions: List[Any],
    function_env_vars: Dict[str, Dict],
    layers: List[Any],
    layer_env_vars: Dict[str, Dict],
) -> Optional[tuple[List[tuple], List[tuple]]]:
    """Build compact current-resource graph rows through Rust when enabled."""
    if not is_enabled():
        return None
    native_fn = getattr(_native, "current_graph_rows", None)
    if native_fn is None:
        return None
    result = _call_optional_native(native_fn, functions, function_env_vars, layers, layer_env_vars)
    if result is None:
        return None
    function_rows, layer_rows = result
    return list(function_rows), list(layer_rows)


def shadow_current_graph_rows(
    functions: List[Any],
    function_env_vars: Dict[str, Dict],
    layers: List[Any],
    layer_env_vars: Dict[str, Dict],
) -> Optional[tuple[List[tuple], List[tuple]]]:
    """Build compact current-resource graph rows through Rust for shadow validation."""
    if not is_shadow_enabled():
        return None
    native_fn = getattr(_native, "current_graph_rows", None)
    if native_fn is None:
        return None
    result = _call_optional_native(native_fn, functions, function_env_vars, layers, layer_env_vars)
    if result is None:
        return None
    function_rows, layer_rows = result
    return list(function_rows), list(layer_rows)


def shadow_plan_graph_groups_from_resources(
    functions: List[Any],
    function_env_vars: Dict[str, Dict],
    layers: List[Any],
    layer_env_vars: Dict[str, Dict],
) -> Optional[tuple[List[List[int]], List[List[int]]]]:
    """Return native graph groups from resources for shadow validation."""
    if not is_shadow_enabled():
        return None
    native_fn = getattr(_native, "plan_graph_groups_from_resources", None)
    if native_fn is None:
        return None
    result = _call_optional_native(
        native_fn,
        functions, function_env_vars, layers, layer_env_vars
    )
    if result is None:
        return None
    function_groups, layer_groups = result
    return [list(group) for group in function_groups], [list(group) for group in layer_groups]


def reconcile_graph_groups(
    function_inputs: List[tuple],
    layer_inputs: List[tuple],
    existing_function_inputs: List[tuple],
    existing_layer_inputs: List[tuple],
) -> Optional[tuple[List[tuple[List[int], Optional[str], str, str]], List[tuple[List[int], Optional[str], str, str]]]]:
    """Group current resources and retain matching persisted definition identity."""
    if not is_enabled():
        return None
    function_groups, layer_groups = _native.reconcile_graph_groups(
        function_inputs,
        layer_inputs,
        existing_function_inputs,
        existing_layer_inputs,
    )
    return (
        [
            (list(indexes), uuid, source_hash, manifest_hash)
            for indexes, uuid, source_hash, manifest_hash in function_groups
        ],
        [
            (list(indexes), uuid, source_hash, manifest_hash)
            for indexes, uuid, source_hash, manifest_hash in layer_groups
        ],
    )


def reconcile_graph_groups_from_resources(
    functions: List[Any],
    function_env_vars: Dict[str, Dict],
    layers: List[Any],
    layer_env_vars: Dict[str, Dict],
    existing_function_inputs: List[tuple],
    existing_layer_inputs: List[tuple],
) -> Optional[tuple[List[tuple[List[int], Optional[str], str, str]], List[tuple[List[int], Optional[str], str, str]]]]:
    """Reconcile current provider resources while retaining persisted identity."""
    if not is_enabled():
        return None
    native_fn = getattr(_native, "reconcile_graph_groups_from_resources", None)
    if native_fn is None:
        return None
    result = _call_optional_native(
        native_fn,
        functions,
        function_env_vars,
        layers,
        layer_env_vars,
        existing_function_inputs,
        existing_layer_inputs,
    )
    if result is None:
        return None
    function_groups, layer_groups = result
    return (
        [
            (list(indexes), uuid, source_hash, manifest_hash)
            for indexes, uuid, source_hash, manifest_hash in function_groups
        ],
        [
            (list(indexes), uuid, source_hash, manifest_hash)
            for indexes, uuid, source_hash, manifest_hash in layer_groups
        ],
    )


def reconcile_graph_plan(
    function_inputs: List[tuple],
    layer_inputs: List[tuple],
    existing_function_inputs: List[tuple],
    existing_layer_inputs: List[tuple],
) -> Optional[Any]:
    """Build a native graph materialization plan and retain matching persisted identity."""
    if not is_enabled():
        return None
    return _native.reconcile_graph_plan(
        function_inputs,
        layer_inputs,
        existing_function_inputs,
        existing_layer_inputs,
    )


def reconcile_graph_plan_from_resources(
    functions: List[Any],
    function_env_vars: Dict[str, Dict],
    layers: List[Any],
    layer_env_vars: Dict[str, Dict],
    existing_function_inputs: List[tuple],
    existing_layer_inputs: List[tuple],
) -> Optional[Any]:
    """Build a native graph plan directly from current provider resources."""
    if not is_enabled():
        return None
    native_fn = getattr(_native, "reconcile_graph_plan_from_resources", None)
    if native_fn is None:
        return None
    return _call_optional_native(
        native_fn,
        functions,
        function_env_vars,
        layers,
        layer_env_vars,
        existing_function_inputs,
        existing_layer_inputs,
    )


def runtime_graph_plan_from_resource_groups(
    functions: List[Any],
    function_env_vars: Dict[str, Dict],
    layers: List[Any],
    layer_env_vars: Dict[str, Dict],
    function_groups: List[tuple],
    layer_groups: List[tuple],
) -> Optional[Any]:
    """Materialize runtime records from already-reconciled resource groups."""
    if not is_enabled():
        return None
    native_fn = getattr(_native, "runtime_graph_plan_from_resource_groups", None)
    if native_fn is None:
        return None
    return _call_optional_native(
        native_fn,
        functions,
        function_env_vars,
        layers,
        layer_env_vars,
        function_groups,
        layer_groups,
    )


def compare_definition_hashes(
    updated_function_inputs: List[tuple],
    existing_function_inputs: List[tuple],
    updated_layer_inputs: List[tuple],
    existing_layer_inputs: List[tuple],
) -> Optional[tuple[List[tuple[str, str, str]], List[tuple[str, str, str]]]]:
    """Return changed source/manifest hashes for equivalent runtime definitions."""
    if not is_enabled():
        return None
    function_updates, layer_updates = _native.compare_definition_hashes(
        updated_function_inputs,
        existing_function_inputs,
        updated_layer_inputs,
        existing_layer_inputs,
    )
    return list(function_updates), list(layer_updates)


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


def read_build_graph(path: str) -> Optional[Dict[str, Any]]:
    """Read persisted build graph data through Rust when enabled."""
    if not is_enabled():
        return None
    try:
        return json.loads(_native.read_build_graph(path))
    except OSError:
        # Preserve the legacy Python reader's more permissive behavior for
        # historical or malformed build.toml files that do not fit Rust's
        # typed persisted graph model.
        return None


def read_runtime_build_graph(path: str) -> Optional[Any]:
    """Read persisted build graph records through Rust when enabled."""
    if not is_enabled():
        return None
    try:
        return _native.read_runtime_build_graph(path)
    except OSError:
        # Keep the same fallback behavior as the JSON bridge for historical or
        # malformed build.toml files the typed Rust graph cannot deserialize.
        return None


def write_build_graph(path: str, graph: Dict[str, Any]) -> bool:
    """Persist the full build graph through Rust when enabled."""
    if not is_enabled():
        return False
    _native.write_build_graph(path, json.dumps(graph, separators=(",", ":")))
    return True


def write_build_graph_compact(path: str, function_rows: List[tuple], layer_rows: List[tuple]) -> bool:
    """Persist the full build graph through the compact Rust writer when enabled."""
    if not is_enabled():
        return False
    try:
        _native.write_build_graph_compact(path, function_rows, layer_rows)
        return True
    except TypeError:
        return False


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
    try:
        return list(_native.remove_redundant_folders(os.fspath(base_dir), retained_uuids))
    except (OSError, TypeError):
        return None
