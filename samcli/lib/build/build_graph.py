"""
Holds classes and utility methods related to build graph
"""

import copy
import json
import logging
import os
import threading
from abc import abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple, cast
from uuid import uuid4

import tomlkit
from tomlkit.toml_document import TOMLDocument

from samcli.commands._utils.experimental import ExperimentalFlag, is_experimental_enabled
from samcli.lib.build.exceptions import InvalidBuildGraphException
from samcli.lib.build.rust_backend import read_build_graph as rust_read_build_graph
from samcli.lib.build.rust_backend import read_runtime_build_graph as rust_read_runtime_build_graph
from samcli.lib.build.rust_backend import compare_definition_hashes as rust_compare_definition_hashes
from samcli.lib.build.rust_backend import create_runtime_definition_record
from samcli.lib.build.rust_backend import create_runtime_function_record, create_runtime_layer_record
from samcli.lib.build.rust_backend import write_build_graph as rust_write_build_graph
from samcli.lib.build.rust_backend import write_build_graph_compact as rust_write_build_graph_compact
from samcli.lib.build.rust_backend import write_hash_updates as rust_write_hash_updates
from samcli.lib.build.rust_compact import (
    definition_function_rows,
    definition_layer_rows,
    json_repr,
    persisted_function_rows,
    persisted_layer_rows,
)
from samcli.lib.providers.provider import Function, LayerVersion
from samcli.lib.samlib.resource_metadata_normalizer import (
    SAM_IS_NORMALIZED,
    SAM_RESOURCE_ID_KEY,
)
from samcli.lib.utils.architecture import X86_64
from samcli.lib.utils.packagetype import ZIP

LOG = logging.getLogger(__name__)

DEFAULT_BUILD_GRAPH_FILE_NAME = "build.toml"

DEFAULT_DEPENDENCIES_DIR = os.path.join(".aws-sam", "deps")

# filed names for the toml table
PACKAGETYPE_FIELD = "packagetype"
CODE_URI_FIELD = "codeuri"
RUNTIME_FIELD = "runtime"
METADATA_FIELD = "metadata"
FUNCTIONS_FIELD = "functions"
SOURCE_HASH_FIELD = "source_hash"
MANIFEST_HASH_FIELD = "manifest_hash"
ENV_VARS_FIELD = "env_vars"
LAYER_NAME_FIELD = "layer_name"
BUILD_METHOD_FIELD = "build_method"
COMPATIBLE_RUNTIMES_FIELD = "compatible_runtimes"
LAYER_FIELD = "layer"
ARCHITECTURE_FIELD = "architecture"
HANDLER_FIELD = "handler"
SHARED_CODEURI_SUFFIX = "Shared"

# Compiled runtimes that we need to compare handlers for
COMPILED_RUNTIMES = ["go1.x"]


def _function_build_definition_to_toml_table(
    function_build_definition: "FunctionBuildDefinition",
) -> tomlkit.api.Table:
    """
    Converts given function_build_definition into toml table representation

    Parameters
    ----------
    function_build_definition: FunctionBuildDefinition
        FunctionBuildDefinition which will be converted into toml table

    Returns
    -------
    tomlkit.api.Table
        toml table of FunctionBuildDefinition
    """
    toml_table = tomlkit.table()
    if function_build_definition.packagetype == ZIP:
        toml_table[CODE_URI_FIELD] = function_build_definition.codeuri
        toml_table[RUNTIME_FIELD] = function_build_definition.runtime
        toml_table[ARCHITECTURE_FIELD] = function_build_definition.architecture
        toml_table[HANDLER_FIELD] = function_build_definition.handler
        if function_build_definition.source_hash:
            toml_table[SOURCE_HASH_FIELD] = function_build_definition.source_hash
        toml_table[MANIFEST_HASH_FIELD] = function_build_definition.manifest_hash
    toml_table[PACKAGETYPE_FIELD] = function_build_definition.packagetype
    toml_table[FUNCTIONS_FIELD] = [f.full_path for f in function_build_definition.functions]

    if function_build_definition.metadata:
        toml_table[METADATA_FIELD] = function_build_definition.metadata
    if function_build_definition.env_vars:
        toml_table[ENV_VARS_FIELD] = function_build_definition.env_vars

    return toml_table


def _toml_table_to_function_build_definition(uuid: str, toml_table: tomlkit.api.Table) -> "FunctionBuildDefinition":
    """
    Converts given toml table into FunctionBuildDefinition instance

    Parameters
    ----------
    uuid: str
        key of the function toml_table instance
    toml_table: tomlkit.api.Table
        function build definition as toml table

    Returns
    -------
    FunctionBuildDefinition
        FunctionBuildDefinition of given toml table
    """
    function_build_definition = FunctionBuildDefinition(
        toml_table.get(RUNTIME_FIELD),
        toml_table.get(CODE_URI_FIELD),
        None,
        toml_table.get(PACKAGETYPE_FIELD, ZIP),
        toml_table.get(ARCHITECTURE_FIELD, X86_64),
        dict(toml_table.get(METADATA_FIELD, {})),
        toml_table.get(HANDLER_FIELD, ""),
        toml_table.get(SOURCE_HASH_FIELD, ""),
        toml_table.get(MANIFEST_HASH_FIELD, ""),
        dict(toml_table.get(ENV_VARS_FIELD, {})),
    )
    function_build_definition.uuid = uuid
    return function_build_definition


def _layer_build_definition_to_toml_table(layer_build_definition: "LayerBuildDefinition") -> tomlkit.api.Table:
    """
    Converts given layer_build_definition into toml table representation

    Parameters
    ----------
    layer_build_definition: LayerBuildDefinition
        LayerBuildDefinition which will be converted into toml table

    Returns
    -------
    tomlkit.api.Table
        toml table of LayerBuildDefinition
    """
    toml_table = tomlkit.table()
    toml_table[LAYER_NAME_FIELD] = layer_build_definition.full_path
    toml_table[CODE_URI_FIELD] = layer_build_definition.codeuri
    toml_table[BUILD_METHOD_FIELD] = layer_build_definition.build_method
    toml_table[COMPATIBLE_RUNTIMES_FIELD] = layer_build_definition.compatible_runtimes
    toml_table[ARCHITECTURE_FIELD] = layer_build_definition.architecture
    if layer_build_definition.source_hash:
        toml_table[SOURCE_HASH_FIELD] = layer_build_definition.source_hash
    toml_table[MANIFEST_HASH_FIELD] = layer_build_definition.manifest_hash
    if layer_build_definition.env_vars:
        toml_table[ENV_VARS_FIELD] = layer_build_definition.env_vars
    toml_table[LAYER_FIELD] = layer_build_definition.layer.full_path

    return toml_table


def _toml_table_to_layer_build_definition(uuid: str, toml_table: tomlkit.api.Table) -> "LayerBuildDefinition":
    """
    Converts given toml table into LayerBuildDefinition instance

    Parameters
    ----------
    uuid: str
        key of the toml_table instance
    toml_table:  tomlkit.api.Table
        layer build definition as toml table

    Returns
    -------
    LayerBuildDefinition
        LayerBuildDefinition of given toml table
    """
    layer_build_definition = LayerBuildDefinition(
        toml_table.get(LAYER_NAME_FIELD, ""),
        toml_table.get(CODE_URI_FIELD),
        toml_table.get(BUILD_METHOD_FIELD),
        toml_table.get(COMPATIBLE_RUNTIMES_FIELD),
        toml_table.get(ARCHITECTURE_FIELD, X86_64),
        toml_table.get(SOURCE_HASH_FIELD, ""),
        toml_table.get(MANIFEST_HASH_FIELD, ""),
        dict(toml_table.get(ENV_VARS_FIELD, {})),
    )
    layer_build_definition.uuid = uuid
    return layer_build_definition


class BuildHashingInformation(NamedTuple):
    """
    Holds hashing information for the source folder and the manifest file
    """

    source_hash: str
    manifest_hash: str


class BuildGraph:
    """
    Contains list of build definitions, with ability to read and write them into build.toml file
    """

    # private lock for build.toml reads and writes
    __toml_lock = threading.Lock()

    # global table build definitions key
    FUNCTION_BUILD_DEFINITIONS = "function_build_definitions"
    LAYER_BUILD_DEFINITIONS = "layer_build_definitions"

    def __init__(self, build_dir: str) -> None:
        # put build.toml file inside .aws-sam folder
        self._filepath = Path(build_dir).parent.joinpath(DEFAULT_BUILD_GRAPH_FILE_NAME)
        self._function_build_definitions: List["FunctionBuildDefinition"] = []
        self._layer_build_definitions: List["LayerBuildDefinition"] = []
        self._runtime_state = None
        self._atomic_read()

    def get_function_build_definitions(self) -> Tuple["FunctionBuildDefinition", ...]:
        return tuple(self._function_build_definitions)

    def get_layer_build_definitions(self) -> Tuple["LayerBuildDefinition", ...]:
        return tuple(self._layer_build_definitions)

    def definition_function_rows(self) -> List[tuple]:
        if self._runtime_state is not None:
            return list(self._runtime_state.definition_function_rows())
        return definition_function_rows(self._function_build_definitions)

    def definition_layer_rows(self) -> List[tuple]:
        if self._runtime_state is not None:
            return list(self._runtime_state.definition_layer_rows())
        return definition_layer_rows(self._layer_build_definitions)

    def persisted_function_rows(self) -> List[tuple]:
        if self._runtime_state is not None:
            return list(
                self._runtime_state.persisted_function_rows(
                    [
                        [function.full_path for function in definition.functions]
                        for definition in self._function_build_definitions
                    ]
                )
            )
        return persisted_function_rows(self._function_build_definitions)

    def persisted_layer_rows(self) -> List[tuple]:
        if self._runtime_state is not None:
            return list(
                self._runtime_state.persisted_layer_rows(
                    [definition.layer.full_path for definition in self._layer_build_definitions]
                )
            )
        return persisted_layer_rows(self._layer_build_definitions)

    def get_function_build_definition_with_full_path(
        self, function_full_path: str
    ) -> Optional["FunctionBuildDefinition"]:
        """
        Returns FunctionBuildDefinition instance of given function logical id.

        Parameters
        ----------
        function_full_path : str
            Function full path that will be searched in the function build definitions

        Returns
        -------
        Optional[FunctionBuildDefinition]
            If a function build definition found returns it, otherwise returns None

        """
        for function_build_definition in self._function_build_definitions:
            for build_definition_function in function_build_definition.functions:
                if build_definition_function.full_path == function_full_path:
                    return function_build_definition
        return None

    def put_function_build_definition(
        self, function_build_definition: "FunctionBuildDefinition", function: Function
    ) -> None:
        """
        Puts the newly read function build definition into existing build graph.
        If graph already contains a function build definition which is same as the newly passed one, then it will add
        the function to the existing one, discarding the new one

        If graph doesn't contain such unique function build definition, it will be added to the current build graph

        Parameters
        ----------
        function_build_definition: FunctionBuildDefinition
            function build definition which is newly read from template.yaml file
        function: Function
            function details for this function build definition
        """
        if function_build_definition in self._function_build_definitions:
            previous_build_definition = self._function_build_definitions[
                self._function_build_definitions.index(function_build_definition)
            ]
            LOG.debug(
                "Same function build definition found, adding function (Previous: %s, Current: %s, Function: %s)",
                previous_build_definition,
                function_build_definition,
                function,
            )
            previous_build_definition.add_function(function)
        else:
            LOG.debug(
                "Unique function build definition found, adding as new (Function Build Definition: %s, Function: %s)",
                function_build_definition,
                function,
            )
            function_build_definition.add_function(function)
            self._function_build_definitions.append(function_build_definition)
            self._runtime_state = None

    def put_pre_deduped_function_build_definition(
        self, function_build_definition: "FunctionBuildDefinition", functions: List[Function]
    ) -> None:
        """
        Append a function build definition whose equivalence grouping was already
        computed by a trusted caller.

        This avoids repeating the quadratic Python-side dedupe scan after the
        optional Rust backend has already produced unique function groups.
        """
        for function in functions:
            function_build_definition.add_function(function)
        self._function_build_definitions.append(function_build_definition)
        self._runtime_state = None

    def put_layer_build_definition(self, layer_build_definition: "LayerBuildDefinition", layer: LayerVersion) -> None:
        """
        Puts the newly read layer build definition into existing build graph.
        If graph already contains a layer build definition which is same as the newly passed one, then it will add
        the layer to the existing one, discarding the new one

        If graph doesn't contain such unique layer build definition, it will be added to the current build graph

        Parameters
        ----------
        layer_build_definition: LayerBuildDefinition
            layer build definition which is newly read from template.yaml file
        layer: Layer
            layer details for this layer build definition
        """
        if layer_build_definition in self._layer_build_definitions:
            previous_build_definition = self._layer_build_definitions[
                self._layer_build_definitions.index(layer_build_definition)
            ]
            LOG.debug(
                "Same Layer build definition found, adding layer (Previous: %s, Current: %s, Layer: %s)",
                previous_build_definition,
                layer_build_definition,
                layer,
            )
            previous_build_definition.layer = layer
        else:
            LOG.debug(
                "Unique Layer build definition found, adding as new (Layer Build Definition: %s, Layer: %s)",
                layer_build_definition,
                layer,
            )
            layer_build_definition.layer = layer
            self._layer_build_definitions.append(layer_build_definition)
            self._runtime_state = None

    def put_pre_deduped_layer_build_definition(
        self, layer_build_definition: "LayerBuildDefinition", layer: LayerVersion
    ) -> None:
        """
        Append a layer build definition whose equivalence grouping was already
        computed by a trusted caller.
        """
        layer_build_definition.layer = layer
        self._layer_build_definitions.append(layer_build_definition)
        self._runtime_state = None

    def populate_from_runtime_graph_plan(
        self, runtime_graph_plan: Any, functions: List[Function], layers: List[LayerVersion]
    ) -> None:
        """
        Replace the current Python facade lists from a Rust-owned graph plan.

        The native plan already reconciled the current template resources with
        persisted build state, so the Python graph only needs to attach provider
        objects to the native runtime records.
        """
        function_build_definitions = []
        for group, runtime_record in zip(runtime_graph_plan.function_groups(), runtime_graph_plan.function_records()):
            function_build_definition = FunctionBuildDefinition.from_runtime_record(runtime_record)
            for index in group:
                function_build_definition.add_function(functions[index])
            function_build_definitions.append(function_build_definition)

        layer_build_definitions = []
        for group, runtime_record in zip(runtime_graph_plan.layer_groups(), runtime_graph_plan.layer_records()):
            layer_build_definition = LayerBuildDefinition.from_runtime_record(runtime_record)
            layer_build_definition.layer = layers[group[-1]]
            layer_build_definitions.append(layer_build_definition)

        self._function_build_definitions = function_build_definitions
        self._layer_build_definitions = layer_build_definitions
        self._runtime_state = runtime_graph_plan.into_state()

    def clean_redundant_definitions_and_update(self, persist: bool) -> None:
        """
        Removes build definitions which doesn't have any function in it, which means these build definitions
        are no longer used, and they can be deleted

        If persist parameter is given True, build graph is written to .aws-sam/build.toml file
        """
        previous_counts = (len(self._function_build_definitions), len(self._layer_build_definitions))
        self._function_build_definitions[:] = [
            fbd for fbd in self._function_build_definitions if len(fbd.functions) > 0
        ]
        self._layer_build_definitions[:] = [bd for bd in self._layer_build_definitions if bd.layer]
        if previous_counts != (len(self._function_build_definitions), len(self._layer_build_definitions)):
            self._runtime_state = None
        if persist:
            self._atomic_write()

    def update_definition_hash(self) -> None:
        """
        Updates the build.toml file with the newest source_hash values of the partial build's definitions

        This operation is atomic, that no other thread accesses build.toml
        during the process of reading and modifying the hash value
        """
        with BuildGraph.__toml_lock:
            # Rust-native graphs already have an owned runtime state. In that case
            # we can compare against the persisted runtime state directly instead
            # of round-tripping the whole Python graph through deepcopy -> _read()
            # -> restore just to update hashes.
            if self._runtime_state is not None:
                persisted_runtime_graph = rust_read_runtime_build_graph(str(self._filepath))
                if persisted_runtime_graph is not None:
                    persisted_runtime_state = persisted_runtime_graph.into_state()
                    rust_hash_changes = rust_compare_definition_hashes(
                        self.definition_function_rows(),
                        list(persisted_runtime_state.definition_function_rows()),
                        self.definition_layer_rows(),
                        list(persisted_runtime_state.definition_layer_rows()),
                    )
                    if rust_hash_changes is not None:
                        function_content = {
                            uuid: BuildHashingInformation(source_hash, manifest_hash)
                            for uuid, source_hash, manifest_hash in rust_hash_changes[0]
                        }
                        layer_content = {
                            uuid: BuildHashingInformation(source_hash, manifest_hash)
                            for uuid, source_hash, manifest_hash in rust_hash_changes[1]
                        }
                        if function_content or layer_content:
                            self._write_source_hash(function_content, layer_content)
                        return

            stored_function_definitions = copy.deepcopy(self._function_build_definitions)
            stored_layer_definitions = copy.deepcopy(self._layer_build_definitions)
            self._read()

            rust_hash_changes = rust_compare_definition_hashes(
                definition_function_rows(stored_function_definitions),
                self.definition_function_rows(),
                definition_layer_rows(stored_layer_definitions),
                self.definition_layer_rows(),
            )
            if rust_hash_changes is not None:
                function_content = {
                    uuid: BuildHashingInformation(source_hash, manifest_hash)
                    for uuid, source_hash, manifest_hash in rust_hash_changes[0]
                }
                layer_content = {
                    uuid: BuildHashingInformation(source_hash, manifest_hash)
                    for uuid, source_hash, manifest_hash in rust_hash_changes[1]
                }
            else:
                function_content = BuildGraph._compare_hash_changes(
                    stored_function_definitions, self._function_build_definitions
                )
                layer_content = BuildGraph._compare_hash_changes(
                    stored_layer_definitions, self._layer_build_definitions
                )

            if function_content or layer_content:
                self._write_source_hash(function_content, layer_content)

            self._function_build_definitions = stored_function_definitions
            self._layer_build_definitions = stored_layer_definitions

    @staticmethod
    def _compare_hash_changes(
        input_list: Sequence["AbstractBuildDefinition"], compared_list: Sequence["AbstractBuildDefinition"]
    ) -> Dict[str, BuildHashingInformation]:
        """
        Helper to compare the function and layer definition changes in hash value

        Returns a dictionary that has uuid as key, updated hash value as value
        """
        content = {}
        for compared_def in compared_list:
            for stored_def in input_list:
                if stored_def == compared_def:
                    old_hash = compared_def.source_hash
                    updated_hash = stored_def.source_hash
                    old_manifest_hash = compared_def.manifest_hash
                    updated_manifest_hash = stored_def.manifest_hash
                    uuid = stored_def.uuid
                    if old_hash != updated_hash or old_manifest_hash != updated_manifest_hash:
                        content[uuid] = BuildHashingInformation(updated_hash, updated_manifest_hash)
                    compared_def.download_dependencies = old_manifest_hash != updated_manifest_hash
        return content

    def _write_source_hash(
        self, function_content: Dict[str, BuildHashingInformation], layer_content: Dict[str, BuildHashingInformation]
    ) -> None:
        """
        Helper to write source_hash values to build.toml file
        """
        if rust_write_hash_updates(
            str(self._filepath),
            [
                (uuid, hashing_info.source_hash, hashing_info.manifest_hash)
                for uuid, hashing_info in function_content.items()
            ],
            [
                (uuid, hashing_info.source_hash, hashing_info.manifest_hash)
                for uuid, hashing_info in layer_content.items()
            ],
        ):
            return

        if not self._filepath.exists():
            open(self._filepath, "a+").close()  # pylint: disable=consider-using-with

        txt = self._filepath.read_text()
        # .loads() returns a TOMLDocument,
        # and it behaves like a standard dictionary according to https://github.com/sdispater/tomlkit.
        # in tomlkit 0.7.2, the types are broken (tomlkit#128, #130, #134) so here we convert it to Dict.
        document = cast(Dict[str, Dict[str, Any]], tomlkit.loads(txt))

        for function_uuid, hashing_info in function_content.items():
            if function_uuid in document.get(BuildGraph.FUNCTION_BUILD_DEFINITIONS, {}):
                function_build_definition = document[BuildGraph.FUNCTION_BUILD_DEFINITIONS][function_uuid]
                function_build_definition[SOURCE_HASH_FIELD] = hashing_info.source_hash
                function_build_definition[MANIFEST_HASH_FIELD] = hashing_info.manifest_hash
                LOG.info(
                    "Updated source_hash and manifest_hash field in build.toml for function with UUID %s", function_uuid
                )

        for layer_uuid, hashing_info in layer_content.items():
            if layer_uuid in document.get(BuildGraph.LAYER_BUILD_DEFINITIONS, {}):
                layer_build_definition = document[BuildGraph.LAYER_BUILD_DEFINITIONS][layer_uuid]
                layer_build_definition[SOURCE_HASH_FIELD] = hashing_info.source_hash
                layer_build_definition[MANIFEST_HASH_FIELD] = hashing_info.manifest_hash
                LOG.info("Updated source_hash and manifest_hash field in build.toml for layer with UUID %s", layer_uuid)

        self._filepath.write_text(tomlkit.dumps(cast(TOMLDocument, document)))

    def _read(self) -> None:
        """
        Reads build.toml file into array of build definition
        Each build definition will have empty function list, which will be populated from the current template.yaml file
        """
        LOG.debug("Instantiating build definitions")
        self._function_build_definitions = []
        self._layer_build_definitions = []
        self._runtime_state = None
        rust_runtime_graph = rust_read_runtime_build_graph(str(self._filepath))
        if rust_runtime_graph is not None:
            self._function_build_definitions = [
                FunctionBuildDefinition.from_runtime_record(record) for record in rust_runtime_graph.function_records()
            ]
            self._layer_build_definitions = [
                LayerBuildDefinition.from_runtime_record(record) for record in rust_runtime_graph.layer_records()
            ]
            self._runtime_state = rust_runtime_graph.into_state()
            return

        rust_document = rust_read_build_graph(str(self._filepath))
        if rust_document is not None:
            for definition in rust_document["function_build_definitions"]:
                function_build_definition = FunctionBuildDefinition(
                    definition.get(RUNTIME_FIELD),
                    definition.get(CODE_URI_FIELD),
                    None,
                    definition.get(PACKAGETYPE_FIELD, ZIP),
                    definition.get(ARCHITECTURE_FIELD, X86_64),
                    definition.get(METADATA_FIELD, {}),
                    definition.get(HANDLER_FIELD, ""),
                    definition.get(SOURCE_HASH_FIELD, ""),
                    definition.get(MANIFEST_HASH_FIELD, ""),
                    definition.get(ENV_VARS_FIELD, {}),
                )
                function_build_definition.uuid = definition["uuid"]
                self._function_build_definitions.append(function_build_definition)

            for definition in rust_document["layer_build_definitions"]:
                layer_build_definition = LayerBuildDefinition(
                    definition.get(LAYER_NAME_FIELD, ""),
                    definition.get(CODE_URI_FIELD),
                    definition.get(BUILD_METHOD_FIELD),
                    definition.get(COMPATIBLE_RUNTIMES_FIELD),
                    definition.get(ARCHITECTURE_FIELD, X86_64),
                    definition.get(SOURCE_HASH_FIELD, ""),
                    definition.get(MANIFEST_HASH_FIELD, ""),
                    definition.get(ENV_VARS_FIELD, {}),
                )
                layer_build_definition.uuid = definition["uuid"]
                self._layer_build_definitions.append(layer_build_definition)
            return

        document = {}
        try:
            txt = self._filepath.read_text()
            # .loads() returns a TOMLDocument,
            # and it behaves like a standard dictionary according to https://github.com/sdispater/tomlkit.
            # in tomlkit 0.7.2, the types are broken (tomlkit#128, #130, #134) so here we convert it to Dict.
            document = cast(Dict, tomlkit.loads(txt))
        except OSError:
            LOG.debug("No previous build graph found, generating new one")
        function_build_definitions_table = document.get(BuildGraph.FUNCTION_BUILD_DEFINITIONS, {})
        for function_build_definition_key in function_build_definitions_table:
            function_build_definition = _toml_table_to_function_build_definition(
                function_build_definition_key, function_build_definitions_table[function_build_definition_key]
            )
            self._function_build_definitions.append(function_build_definition)

        layer_build_definitions_table = document.get(BuildGraph.LAYER_BUILD_DEFINITIONS, {})
        for layer_build_definition_key in layer_build_definitions_table:
            layer_build_definition = _toml_table_to_layer_build_definition(
                layer_build_definition_key, layer_build_definitions_table[layer_build_definition_key]
            )
            self._layer_build_definitions.append(layer_build_definition)

    def _atomic_read(self) -> None:
        """
        Performs the _read() method with a global lock acquired
        It makes sure no other thread accesses build.toml when a read is happening
        """

        with BuildGraph.__toml_lock:
            self._read()

    def _write(self) -> None:
        """
        Writes build definition details into build.toml file, which would be used by the next build.
        build.toml file will contain the same information as build graph,
        function details will only be preserved as function names
        layer details will only be preserved as layer names
        """
        if rust_write_build_graph_compact(
            str(self._filepath),
            self.persisted_function_rows(),
            self.persisted_layer_rows(),
        ):
            return

        # convert build definition list into toml table
        function_build_definitions_table = tomlkit.table()
        for function_build_definition in self._function_build_definitions:
            build_definition_as_table = _function_build_definition_to_toml_table(function_build_definition)
            function_build_definitions_table.add(function_build_definition.uuid, build_definition_as_table)

        layer_build_definitions_table = tomlkit.table()
        for layer_build_definition in self._layer_build_definitions:
            build_definition_as_table = _layer_build_definition_to_toml_table(layer_build_definition)
            layer_build_definitions_table.add(layer_build_definition.uuid, build_definition_as_table)

        # create toml document and add build definitions
        document = tomlkit.document()
        document.add(tomlkit.comment("This file is auto generated by SAM CLI build command"))
        # we need to cast `Table` to `Item` because of tomlkit#135.
        document.add(BuildGraph.FUNCTION_BUILD_DEFINITIONS, cast(tomlkit.items.Item, function_build_definitions_table))
        document.add(BuildGraph.LAYER_BUILD_DEFINITIONS, cast(tomlkit.items.Item, layer_build_definitions_table))

        if not self._filepath.exists():
            open(self._filepath, "a+").close()  # pylint: disable=consider-using-with

        self._filepath.write_text(tomlkit.dumps(document))

    def _atomic_write(self) -> None:
        """
        Performs the _write() method with a global lock acquired
        It makes sure no other thread accesses build.toml when a write is happening
        """

        with BuildGraph.__toml_lock:
            self._write()


class AbstractBuildDefinition:
    """
    Abstract class for build definition
    Build definition holds information about each unique build
    """

    def __init__(
        self, source_hash: str, manifest_hash: str, env_vars: Optional[Dict] = None, architecture: str = X86_64
    ) -> None:
        self._uuid = str(uuid4())
        self._source_hash = source_hash
        self._manifest_hash = manifest_hash
        self._runtime_record = create_runtime_definition_record(self._uuid, source_hash, manifest_hash)
        self._env_vars = env_vars if env_vars else {}
        self._env_vars_cache_json = None
        self._env_vars_cache = None
        self._architecture = architecture
        # following properties are used during build time and they don't serialize into build.toml file
        self.download_dependencies: bool = True

    @property
    def dependencies_dir(self) -> str:
        return str(os.path.join(DEFAULT_DEPENDENCIES_DIR, self.uuid))

    @property
    def uuid(self) -> str:
        return self._runtime_record.uuid if self._runtime_record is not None else self._uuid

    @uuid.setter
    def uuid(self, value: str) -> None:
        if self._runtime_record is not None:
            self._runtime_record.uuid = value
        self._uuid = value

    @property
    def source_hash(self) -> str:
        return self._runtime_record.source_hash if self._runtime_record is not None else self._source_hash

    @source_hash.setter
    def source_hash(self, value: str) -> None:
        if self._runtime_record is not None:
            self._runtime_record.source_hash = value
        self._source_hash = value

    @property
    def manifest_hash(self) -> str:
        return self._runtime_record.manifest_hash if self._runtime_record is not None else self._manifest_hash

    @manifest_hash.setter
    def manifest_hash(self, value: str) -> None:
        if self._runtime_record is not None:
            self._runtime_record.manifest_hash = value
        self._manifest_hash = value

    @property
    def env_vars(self) -> Dict:
        if self._runtime_record is not None and hasattr(self._runtime_record, "env_vars_json"):
            env_vars_json = self._runtime_record.env_vars_json
            if self._env_vars_cache_json != env_vars_json:
                self._env_vars_cache_json = env_vars_json
                self._env_vars_cache = json.loads(env_vars_json)
            return deepcopy(self._env_vars_cache)
        return deepcopy(self._env_vars)

    @property
    def architecture(self) -> str:
        if self._runtime_record is not None and hasattr(self._runtime_record, "architecture"):
            return self._runtime_record.architecture
        return self._architecture

    @abstractmethod
    def get_resource_full_paths(self) -> str:
        """Returns string representation of resources' full path information for this build definition"""


class LayerBuildDefinition(AbstractBuildDefinition):
    """
    LayerBuildDefinition holds information about each unique layer build
    """

    def __init__(
        self,
        full_path: str,
        codeuri: Optional[str],
        build_method: Optional[str],
        compatible_runtimes: Optional[List[str]],
        architecture: str,
        source_hash: str = "",
        manifest_hash: str = "",
        env_vars: Optional[Dict] = None,
    ):
        super().__init__(source_hash, manifest_hash, env_vars, architecture)
        self._full_path = full_path
        self._codeuri = codeuri
        self._build_method = build_method
        self._compatible_runtimes = compatible_runtimes
        runtime_record = create_runtime_layer_record(
            self.uuid,
            self.source_hash,
            self.manifest_hash,
            full_path,
            codeuri,
            build_method,
            compatible_runtimes,
            architecture,
            self._env_vars,
        )
        if self._runtime_record is not None and type(self._runtime_record).__name__ != "RuntimeDefinitionRecord":
            pass
        elif runtime_record is not None:
            self._runtime_record = runtime_record
        elif type(self._runtime_record).__name__ == "RuntimeDefinitionRecord":
            self._runtime_record = None
        # Note(xinhol): In our code, we assume "layer" is never None. We should refactor
        # this and move "layer" out of LayerBuildDefinition to take advantage of type check.
        self.layer: LayerVersion = None  # type: ignore

    @classmethod
    def from_runtime_record(cls, runtime_record: Any) -> "LayerBuildDefinition":
        """Create the thin Python facade around a Rust-owned runtime record."""
        build_definition = cls.__new__(cls)
        build_definition._runtime_record = runtime_record
        build_definition._uuid = runtime_record.uuid or str(uuid4())
        if not runtime_record.uuid:
            runtime_record.uuid = build_definition._uuid
        build_definition._source_hash = runtime_record.source_hash
        build_definition._manifest_hash = runtime_record.manifest_hash
        build_definition._env_vars = {}
        build_definition._env_vars_cache_json = None
        build_definition._env_vars_cache = None
        build_definition._architecture = runtime_record.architecture
        build_definition.download_dependencies = True
        build_definition._full_path = runtime_record.full_path
        build_definition._codeuri = runtime_record.codeuri
        build_definition._build_method = runtime_record.build_method
        build_definition._compatible_runtimes = runtime_record.compatible_runtimes
        build_definition.layer = None  # type: ignore
        return build_definition

    @property
    def full_path(self) -> str:
        return self._runtime_record.full_path if self._runtime_record is not None else self._full_path

    @property
    def codeuri(self) -> Optional[str]:
        return self._runtime_record.codeuri if self._runtime_record is not None else self._codeuri

    @property
    def build_method(self) -> Optional[str]:
        return self._runtime_record.build_method if self._runtime_record is not None else self._build_method

    @property
    def compatible_runtimes(self) -> Optional[List[str]]:
        return (
            self._runtime_record.compatible_runtimes if self._runtime_record is not None else self._compatible_runtimes
        )

    def get_resource_full_paths(self) -> str:
        if not self.layer:
            LOG.debug("LayerBuildDefinition with uuid (%s) doesn't have a layer assigned to it", self.uuid)
            return ""
        return self.layer.full_path

    def __str__(self) -> str:
        return (
            f"LayerBuildDefinition({self.full_path}, {self.codeuri}, {self.source_hash}, {self.uuid}, "
            f"{self.build_method}, {self.compatible_runtimes}, {self.architecture}, {self.env_vars})"
        )

    def __eq__(self, other: Any) -> bool:
        """
        Checks equality of the layer build definition

        Parameters
        ----------
        other: Any
            other layer build definition to compare

        Returns
        -------
        bool
            True if both layer build definitions has same following properties, False otherwise
        """
        if not isinstance(other, LayerBuildDefinition):
            return False

        if self._runtime_record is not None and other._runtime_record is not None:
            try:
                return self._runtime_record.equivalent_for_build(other._runtime_record)
            except TypeError:
                # Mixed legacy/runtime-record graphs can appear during default-on
                # rollout; fall back to the established Python equality rules.
                pass

        return (
            self.full_path == other.full_path
            and self.codeuri == other.codeuri
            and self.build_method == other.build_method
            and self.compatible_runtimes == other.compatible_runtimes
            and self.env_vars == other.env_vars
            and self.architecture == other.architecture
        )


class FunctionBuildDefinition(AbstractBuildDefinition):
    """
    FunctionBuildDefinition holds information about each unique function build
    """

    def __init__(
        self,
        runtime: Optional[str],
        codeuri: Optional[str],
        imageuri: Optional[str],
        packagetype: str,
        architecture: str,
        metadata: Optional[Dict],
        handler: Optional[str],
        source_hash: str = "",
        manifest_hash: str = "",
        env_vars: Optional[Dict] = None,
    ) -> None:
        super().__init__(source_hash, manifest_hash, env_vars, architecture)
        # Skip SAM Added metadata properties
        metadata_copied = deepcopy(metadata) if metadata else {}
        metadata_copied.pop(SAM_RESOURCE_ID_KEY, "")
        metadata_copied.pop(SAM_IS_NORMALIZED, "")

        self._runtime = runtime
        self._codeuri = codeuri
        self._imageuri = imageuri
        self._packagetype = packagetype
        self._handler = handler
        runtime_record = create_runtime_function_record(
            self.uuid,
            self.source_hash,
            self.manifest_hash,
            runtime,
            codeuri,
            imageuri,
            packagetype,
            architecture,
            handler,
            metadata_copied,
            self._env_vars,
        )
        if self._runtime_record is not None and type(self._runtime_record).__name__ != "RuntimeDefinitionRecord":
            pass
        elif runtime_record is not None:
            self._runtime_record = runtime_record
        elif type(self._runtime_record).__name__ == "RuntimeDefinitionRecord":
            self._runtime_record = None

        self._metadata = metadata_copied
        self._metadata_cache_json = None
        self._metadata_cache = None

        self.functions: List[Function] = []

    @classmethod
    def from_runtime_record(cls, runtime_record: Any) -> "FunctionBuildDefinition":
        """Create the thin Python facade around a Rust-owned runtime record."""
        build_definition = cls.__new__(cls)
        build_definition._runtime_record = runtime_record
        build_definition._uuid = runtime_record.uuid or str(uuid4())
        if not runtime_record.uuid:
            runtime_record.uuid = build_definition._uuid
        build_definition._source_hash = runtime_record.source_hash
        build_definition._manifest_hash = runtime_record.manifest_hash
        build_definition._env_vars = {}
        build_definition._env_vars_cache_json = None
        build_definition._env_vars_cache = None
        build_definition._architecture = runtime_record.architecture
        build_definition.download_dependencies = True
        build_definition._runtime = runtime_record.runtime
        build_definition._codeuri = runtime_record.codeuri
        build_definition._imageuri = runtime_record.imageuri
        build_definition._packagetype = runtime_record.packagetype
        build_definition._handler = runtime_record.handler
        build_definition._metadata = {}
        build_definition._metadata_cache_json = None
        build_definition._metadata_cache = None
        build_definition.functions = []
        return build_definition

    @property
    def runtime(self) -> Optional[str]:
        return self._runtime_record.runtime if self._runtime_record is not None else self._runtime

    @property
    def codeuri(self) -> Optional[str]:
        return self._runtime_record.codeuri if self._runtime_record is not None else self._codeuri

    @property
    def imageuri(self) -> Optional[str]:
        return self._runtime_record.imageuri if self._runtime_record is not None else self._imageuri

    @property
    def packagetype(self) -> str:
        return self._runtime_record.packagetype if self._runtime_record is not None else self._packagetype

    @property
    def handler(self) -> Optional[str]:
        return self._runtime_record.handler if self._runtime_record is not None else self._handler

    @property
    def metadata(self) -> Dict:
        if self._runtime_record is not None and hasattr(self._runtime_record, "metadata_json"):
            metadata_json = self._runtime_record.metadata_json
            if self._metadata_cache_json != metadata_json:
                self._metadata_cache_json = metadata_json
                self._metadata_cache = json.loads(metadata_json)
            return self._metadata_cache
        return self._metadata

    def add_function(self, function: Function) -> None:
        self.functions.append(function)

    def get_function_name(self) -> str:
        self._validate_functions()
        return self.functions[0].name

    def get_handler_name(self) -> Optional[str]:
        self._validate_functions()
        return self.functions[0].handler

    def get_full_path(self) -> str:
        """
        Return the build identifier of the first function
        """
        self._validate_functions()
        return self.functions[0].full_path

    def get_build_dir(self, artifact_root_dir: str) -> str:
        """
        Return the directory path relative to root build directory
        """
        self._validate_functions()
        build_dir = self.functions[0].get_build_dir(artifact_root_dir)
        if is_experimental_enabled(ExperimentalFlag.BuildPerformance) and len(self.functions) > 1:
            # If there are multiple functions with the same build definition,
            # just put them into one single shared artifacts directory.
            build_dir = f"{build_dir}-{SHARED_CODEURI_SUFFIX}"
        return build_dir

    def get_resource_full_paths(self) -> str:
        """Returns list of functions' full path information as a list of str"""
        return ", ".join([function.full_path for function in self.functions])

    def _validate_functions(self) -> None:
        if not self.functions:
            raise InvalidBuildGraphException("Build definition doesn't have any function definition to build")

    def __str__(self) -> str:
        metadata = self.metadata.copy()
        if "DockerBuildArgs" in metadata:
            del metadata["DockerBuildArgs"]

        return (
            "BuildDefinition("
            f"{self.runtime}, {self.codeuri}, {self.packagetype}, {self.source_hash}, "
            f"{self.uuid}, {metadata}, {self.env_vars}, {self.architecture}, "
            f"{[f.functionname for f in self.functions]})"
        )

    def __eq__(self, other: Any) -> bool:
        """
        Checks equality of the function build definition

        Parameters
        ----------
        other: Any
            other function build definition to compare

        Returns
        -------
        bool
            True if both function build definitions has same following properties, False otherwise
        """
        if not isinstance(other, FunctionBuildDefinition):
            return False

        if self._runtime_record is not None and other._runtime_record is not None:
            try:
                return self._runtime_record.equivalent_for_build(
                    other._runtime_record,
                    self.metadata.get("BuildMethod") if self.metadata else None,
                )
            except TypeError:
                # Mixed legacy/runtime-record graphs can appear during default-on
                # rollout; fall back to the established Python equality rules.
                pass

        # each build with custom Makefile definition should be handled separately
        if self.metadata and self.metadata.get("BuildMethod", None) == "makefile":
            return False

        if self.metadata and self.metadata.get("BuildMethod", None) == "esbuild":
            # For esbuild, we need to check if handlers within the same CodeUri are the same
            # if they are different, it should create a separate build definition
            if self.handler != other.handler:
                return False

        if self.runtime in COMPILED_RUNTIMES:
            # For compiled languages, we need to check if handlers within the same CodeUri are the same
            # if they are different, it should create a separate build definition
            if self.handler != other.handler:
                return False

        return (
            self.runtime == other.runtime
            and self.codeuri == other.codeuri
            and self.imageuri == other.imageuri
            and self.packagetype == other.packagetype
            and self.metadata == other.metadata
            and self.env_vars == other.env_vars
            and self.architecture == other.architecture
        )
