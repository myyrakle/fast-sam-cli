"""
Compact row builders for the optional Rust build core boundary.

Keep the tuple layouts in one place so callers do not need to know the native
ABI details while the graph model is gradually moved across the boundary.
"""

import json
from typing import Dict, List, Sequence

from samcli.lib.samlib.resource_metadata_normalizer import SAM_IS_NORMALIZED, SAM_RESOURCE_ID_KEY


def json_repr(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def normalized_metadata(metadata: Dict | None) -> Dict:
    return {
        key: value for key, value in (metadata or {}).items() if key not in {SAM_RESOURCE_ID_KEY, SAM_IS_NORMALIZED}
    }


def current_function_rows(functions: List, function_env_vars: Dict[str, Dict]) -> List[tuple]:
    return [
        (
            function.runtime,
            function.codeuri,
            function.imageuri,
            function.packagetype,
            function.architecture,
            json_repr(normalized_metadata(function.metadata)),
            (function.metadata or {}).get("BuildMethod"),
            function.handler,
            json_repr(function_env_vars[function.full_path]),
        )
        for function in functions
    ]


def definition_function_rows(definitions: Sequence) -> List[tuple]:
    return [
        (
            definition.uuid,
            definition.source_hash,
            definition.manifest_hash,
            definition.runtime,
            definition.codeuri,
            definition.imageuri,
            definition.packagetype,
            definition.architecture,
            json_repr(definition.metadata),
            definition.metadata.get("BuildMethod"),
            definition.handler,
            json_repr(definition.env_vars),
        )
        for definition in definitions
    ]


def current_layer_rows(layers: List, layer_env_vars: Dict[str, Dict]) -> List[tuple]:
    return [
        (
            layer.full_path,
            layer.codeuri,
            layer.build_method,
            json_repr(layer.compatible_runtimes),
            layer.build_architecture,
            json_repr(layer_env_vars[layer.full_path]),
        )
        for layer in layers
    ]


def definition_layer_rows(definitions: Sequence) -> List[tuple]:
    return [
        (
            definition.uuid,
            definition.source_hash,
            definition.manifest_hash,
            definition.full_path,
            definition.codeuri,
            definition.build_method,
            json_repr(definition.compatible_runtimes),
            definition.architecture,
            json_repr(definition.env_vars),
        )
        for definition in definitions
    ]


def persisted_function_rows(definitions: Sequence) -> List[tuple]:
    return [
        (
            definition.uuid,
            definition.runtime,
            definition.codeuri,
            definition.packagetype,
            definition.architecture,
            definition.handler,
            definition.source_hash,
            definition.manifest_hash,
            [function.full_path for function in definition.functions],
            json_repr(definition.metadata),
            json_repr(definition.env_vars),
        )
        for definition in definitions
    ]


def persisted_layer_rows(definitions: Sequence) -> List[tuple]:
    return [
        (
            definition.uuid,
            definition.full_path,
            definition.codeuri,
            definition.build_method,
            definition.compatible_runtimes,
            definition.architecture,
            definition.source_hash,
            definition.manifest_hash,
            json_repr(definition.env_vars),
            definition.layer.full_path,
        )
        for definition in definitions
    ]
