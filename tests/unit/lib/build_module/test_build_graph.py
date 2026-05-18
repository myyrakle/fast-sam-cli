import copy
import os.path
from unittest import TestCase
from unittest.mock import patch, Mock
from uuid import uuid4
from pathlib import Path

import tomlkit
from samcli.lib.utils.architecture import X86_64, ARM64
from parameterized import parameterized
from typing import Dict, cast

from samcli.lib.build.build_graph import (
    FunctionBuildDefinition,
    _function_build_definition_to_toml_table,
    _layer_build_definition_to_toml_table,
    CODE_URI_FIELD,
    RUNTIME_FIELD,
    PACKAGETYPE_FIELD,
    METADATA_FIELD,
    FUNCTIONS_FIELD,
    SOURCE_HASH_FIELD,
    ENV_VARS_FIELD,
    LAYER_NAME_FIELD,
    BUILD_METHOD_FIELD,
    COMPATIBLE_RUNTIMES_FIELD,
    LAYER_FIELD,
    ARCHITECTURE_FIELD,
    _toml_table_to_function_build_definition,
    _toml_table_to_layer_build_definition,
    BuildGraph,
    InvalidBuildGraphException,
    LayerBuildDefinition,
    MANIFEST_HASH_FIELD,
    BuildHashingInformation,
    HANDLER_FIELD,
)
from samcli.lib.providers.provider import Function, LayerVersion, FunctionBuildInfo
from samcli.lib.utils import osutils
from samcli.lib.utils.packagetype import ZIP


def generate_function(
    function_id="name",
    name="name",
    function_name="function_name",
    runtime="runtime",
    memory="memory",
    timeout="timeout",
    handler="handler",
    imageuri="imageuri",
    packagetype=ZIP,
    imageconfig="imageconfig",
    codeuri="codeuri",
    environment="environment",
    rolearn="rolearn",
    layers="layers",
    events="events",
    codesign_config_arn="codesign_config_arn",
    metadata=None,
    inlinecode=None,
    architectures=[X86_64],
    stack_path="",
    function_build_info=FunctionBuildInfo.BuildableZip,
):
    if metadata is None:
        metadata = {}

    return Function(
        function_id,
        name,
        function_name,
        runtime,
        memory,
        timeout,
        handler,
        imageuri,
        packagetype,
        imageconfig,
        codeuri,
        environment,
        rolearn,
        layers,
        events,
        metadata,
        inlinecode,
        codesign_config_arn,
        architectures,
        stack_path,
        function_build_info,
    )


def generate_layer(
    arn="arn:aws:lambda:region:account-id:layer:layer-name:1",
    codeuri="codeuri",
    compatible_runtimes=None,
    metadata=None,
    stack_path="",
):
    if compatible_runtimes is None:
        compatible_runtimes = ["runtime"]
    if metadata is None:
        metadata = {}

    return LayerVersion(arn, codeuri, compatible_runtimes, metadata, stack_path)


class TestConversionFunctions(TestCase):
    def test_function_build_definition_to_toml_table(self):
        build_definition = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            X86_64,
            {"key": "value"},
            "source_hash",
            "manifest_hash",
            env_vars={"env_vars": "value1"},
        )
        build_definition.add_function(generate_function())

        toml_table = _function_build_definition_to_toml_table(build_definition)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[PACKAGETYPE_FIELD], build_definition.packagetype)
        self.assertEqual(toml_table[RUNTIME_FIELD], build_definition.runtime)
        self.assertEqual(toml_table[METADATA_FIELD], build_definition.metadata)
        self.assertEqual(toml_table[FUNCTIONS_FIELD], [f.name for f in build_definition.functions])
        self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ENV_VARS_FIELD], build_definition.env_vars)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_layer_build_definition_to_toml_table(self):
        build_definition = LayerBuildDefinition(
            "name",
            "codeuri",
            "method",
            ["runtime"],
            ARM64,
            "source_hash",
            "manifest_hash",
            env_vars={"env_vars": "value"},
        )
        build_definition.layer = generate_function()

        toml_table = _layer_build_definition_to_toml_table(build_definition)

        self.assertEqual(toml_table[LAYER_NAME_FIELD], build_definition.full_path)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[BUILD_METHOD_FIELD], build_definition.build_method)
        self.assertEqual(toml_table[COMPATIBLE_RUNTIMES_FIELD], build_definition.compatible_runtimes)
        self.assertEqual(toml_table[LAYER_FIELD], build_definition.layer.name)
        self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ENV_VARS_FIELD], build_definition.env_vars)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_toml_table_to_function_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[RUNTIME_FIELD] = "runtime"
        toml_table[PACKAGETYPE_FIELD] = ZIP
        toml_table[METADATA_FIELD] = {"key": "value"}
        toml_table[FUNCTIONS_FIELD] = ["function1"]
        toml_table[SOURCE_HASH_FIELD] = "source_hash"
        toml_table[MANIFEST_HASH_FIELD] = "manifest_hash"
        toml_table[ENV_VARS_FIELD] = {"env_vars": "value"}
        toml_table[ARCHITECTURE_FIELD] = X86_64
        uuid = str(uuid4())

        build_definition = _toml_table_to_function_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.packagetype, toml_table[PACKAGETYPE_FIELD])
        self.assertEqual(build_definition.runtime, toml_table[RUNTIME_FIELD])
        self.assertEqual(build_definition.metadata, toml_table[METADATA_FIELD])
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.functions, [])
        self.assertEqual(build_definition.source_hash, toml_table[SOURCE_HASH_FIELD])
        self.assertEqual(build_definition.manifest_hash, toml_table[MANIFEST_HASH_FIELD])
        self.assertEqual(build_definition.env_vars, toml_table[ENV_VARS_FIELD])
        self.assertEqual(build_definition.architecture, toml_table[ARCHITECTURE_FIELD])

    def test_toml_table_to_layer_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[LAYER_NAME_FIELD] = "name"
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[BUILD_METHOD_FIELD] = "method"
        toml_table[COMPATIBLE_RUNTIMES_FIELD] = "runtime"
        toml_table[COMPATIBLE_RUNTIMES_FIELD] = "layer1"
        toml_table[SOURCE_HASH_FIELD] = "source_hash"
        toml_table[MANIFEST_HASH_FIELD] = "manifest_hash"
        toml_table[ENV_VARS_FIELD] = {"env_vars": "value"}
        toml_table[ARCHITECTURE_FIELD] = ARM64
        uuid = str(uuid4())

        build_definition = _toml_table_to_layer_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.full_path, toml_table[LAYER_NAME_FIELD])
        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.build_method, toml_table[BUILD_METHOD_FIELD])
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.compatible_runtimes, toml_table[COMPATIBLE_RUNTIMES_FIELD])
        self.assertEqual(build_definition.layer, None)
        self.assertEqual(build_definition.source_hash, toml_table[SOURCE_HASH_FIELD])
        self.assertEqual(build_definition.manifest_hash, toml_table[MANIFEST_HASH_FIELD])
        self.assertEqual(build_definition.env_vars, toml_table[ENV_VARS_FIELD])
        self.assertEqual(build_definition.architecture, toml_table[ARCHITECTURE_FIELD])

    def test_minimal_function_build_definition_to_toml_table(self):
        build_definition = FunctionBuildDefinition("runtime", "codeuri", None, ZIP, X86_64, {"key": "value"}, "handler")
        build_definition.add_function(generate_function())

        toml_table = _function_build_definition_to_toml_table(build_definition)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[PACKAGETYPE_FIELD], build_definition.packagetype)
        self.assertEqual(toml_table[RUNTIME_FIELD], build_definition.runtime)
        self.assertEqual(toml_table[METADATA_FIELD], build_definition.metadata)
        self.assertEqual(toml_table[HANDLER_FIELD], build_definition.handler)
        self.assertEqual(toml_table[FUNCTIONS_FIELD], [f.name for f in build_definition.functions])
        if build_definition.source_hash:
            self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_minimal_layer_build_definition_to_toml_table(self):
        build_definition = LayerBuildDefinition("name", "codeuri", "method", "runtime", ARM64)
        build_definition.layer = generate_function()

        toml_table = _layer_build_definition_to_toml_table(build_definition)

        self.assertEqual(toml_table[LAYER_NAME_FIELD], build_definition.full_path)
        self.assertEqual(toml_table[CODE_URI_FIELD], build_definition.codeuri)
        self.assertEqual(toml_table[BUILD_METHOD_FIELD], build_definition.build_method)
        self.assertEqual(toml_table[COMPATIBLE_RUNTIMES_FIELD], build_definition.compatible_runtimes)
        self.assertEqual(toml_table[LAYER_FIELD], build_definition.layer.name)
        if build_definition.source_hash:
            self.assertEqual(toml_table[SOURCE_HASH_FIELD], build_definition.source_hash)
        self.assertEqual(toml_table[MANIFEST_HASH_FIELD], build_definition.manifest_hash)
        self.assertEqual(toml_table[ARCHITECTURE_FIELD], build_definition.architecture)

    def test_minimal_toml_table_to_function_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[RUNTIME_FIELD] = "runtime"
        toml_table[FUNCTIONS_FIELD] = ["function1"]
        uuid = str(uuid4())

        build_definition = _toml_table_to_function_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.packagetype, ZIP)
        self.assertEqual(build_definition.runtime, toml_table[RUNTIME_FIELD])
        self.assertEqual(build_definition.metadata, {})
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.functions, [])
        self.assertEqual(build_definition.source_hash, "")
        self.assertEqual(build_definition.manifest_hash, "")
        self.assertEqual(build_definition.env_vars, {})
        self.assertEqual(build_definition.architecture, X86_64)

    def test_minimal_toml_table_to_layer_build_definition(self):
        toml_table = tomlkit.table()
        toml_table[LAYER_NAME_FIELD] = "name"
        toml_table[CODE_URI_FIELD] = "codeuri"
        toml_table[BUILD_METHOD_FIELD] = "method"
        toml_table[COMPATIBLE_RUNTIMES_FIELD] = "runtime"
        uuid = str(uuid4())

        build_definition = _toml_table_to_layer_build_definition(uuid, toml_table)

        self.assertEqual(build_definition.full_path, toml_table[LAYER_NAME_FIELD])
        self.assertEqual(build_definition.codeuri, toml_table[CODE_URI_FIELD])
        self.assertEqual(build_definition.build_method, toml_table[BUILD_METHOD_FIELD])
        self.assertEqual(build_definition.uuid, uuid)
        self.assertEqual(build_definition.compatible_runtimes, toml_table[COMPATIBLE_RUNTIMES_FIELD])
        self.assertEqual(build_definition.layer, None)
        self.assertEqual(build_definition.source_hash, "")
        self.assertEqual(build_definition.manifest_hash, "")
        self.assertEqual(build_definition.env_vars, {})
        self.assertEqual(build_definition.architecture, X86_64)


class TestBuildGraph(TestCase):
    CODEURI = "hello_world_python/"
    LAYER_CODEURI = "sum_layer/"
    LAYER_NAME = "SumLayer"
    ZIP = ZIP
    RUNTIME = "python3.8"
    LAYER_RUNTIME = "nodejs20.x"
    METADATA = {"Test": "hello", "Test2": "world"}
    UUID = "3c1c254e-cd4b-4d94-8c74-7ab870b36063"
    LAYER_UUID = "7dnc257e-cd4b-4d94-8c74-7ab870b3abc3"
    SOURCE_HASH = "cae49aa393d669e850bd49869905099d"
    MANIFEST_HASH = "rty87gh393d669e850bd49869905099e"
    ENV_VARS = {"env_vars": "value"}
    ARCHITECTURE_FIELD = ARM64
    LAYER_ARCHITECTURE = X86_64
    HANDLER = "app.handler"

    BUILD_GRAPH_CONTENTS = f"""
    [function_build_definitions]
    [function_build_definitions.{UUID}]
    codeuri = "{CODEURI}"
    runtime = "{RUNTIME}"
    source_hash = "{SOURCE_HASH}"
    manifest_hash = "{MANIFEST_HASH}"
    packagetype = "{ZIP}"
    architecture = "{ARCHITECTURE_FIELD}"
    handler = "{HANDLER}"
    functions = ["HelloWorldPython", "HelloWorld2Python"]
    [function_build_definitions.{UUID}.metadata]
    Test = "{METADATA['Test']}"
    Test2 = "{METADATA['Test2']}"
    [function_build_definitions.{UUID}.env_vars]
    env_vars = "{ENV_VARS['env_vars']}"

    [layer_build_definitions]
    [layer_build_definitions.{LAYER_UUID}]
    layer_name = "{LAYER_NAME}"
    codeuri = "{LAYER_CODEURI}"
    build_method = "{LAYER_RUNTIME}"
    compatible_runtimes = ["{LAYER_RUNTIME}"]
    architecture = "{LAYER_ARCHITECTURE}"
    source_hash = "{SOURCE_HASH}"
    manifest_hash = "{MANIFEST_HASH}"
    layer = "SumLayer"
    [layer_build_definitions.{LAYER_UUID}.env_vars]
    env_vars = "{ENV_VARS['env_vars']}"
    """

    def test_should_instantiate_first_time(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)
            build_graph1 = BuildGraph(str(build_dir.resolve()))
            build_graph1.clean_redundant_definitions_and_update(True)

            build_graph2 = BuildGraph(str(build_dir.resolve()))

            self.assertEqual(
                build_graph1.get_function_build_definitions(), build_graph2.get_function_build_definitions()
            )
            self.assertEqual(build_graph1.get_layer_build_definitions(), build_graph2.get_layer_build_definitions())

    def test_should_instantiate_first_time_and_update(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            # create a build graph and persist it
            build_graph1 = BuildGraph(str(build_dir))
            function_build_definition1 = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                None,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            function1 = generate_function(
                runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=TestBuildGraph.METADATA
            )
            build_graph1.put_function_build_definition(function_build_definition1, function1)
            layer_build_definition1 = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            layer1 = generate_layer(
                compatible_runtimes=[TestBuildGraph.RUNTIME],
                codeuri=TestBuildGraph.LAYER_CODEURI,
                metadata=TestBuildGraph.METADATA,
            )
            build_graph1.put_layer_build_definition(layer_build_definition1, layer1)

            build_graph1.clean_redundant_definitions_and_update(True)

            # read previously persisted graph and compare
            build_graph2 = BuildGraph(str(build_dir))
            self.assertEqual(
                len(build_graph1.get_function_build_definitions()), len(build_graph2.get_function_build_definitions())
            )
            self.assertEqual(
                len(build_graph1.get_layer_build_definitions()), len(build_graph2.get_layer_build_definitions())
            )
            self.assertEqual(
                list(build_graph1.get_function_build_definitions())[0],
                list(build_graph2.get_function_build_definitions())[0],
            )
            self.assertEqual(
                list(build_graph1.get_layer_build_definitions())[0],
                list(build_graph2.get_layer_build_definitions())[0],
            )

    def test_should_read_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))
            for function_build_definition in build_graph.get_function_build_definitions():
                self.assertEqual(function_build_definition.codeuri, TestBuildGraph.CODEURI)
                self.assertEqual(function_build_definition.runtime, TestBuildGraph.RUNTIME)
                self.assertEqual(function_build_definition.packagetype, TestBuildGraph.ZIP)
                self.assertEqual(function_build_definition.architecture, TestBuildGraph.ARCHITECTURE_FIELD)
                self.assertEqual(function_build_definition.metadata, TestBuildGraph.METADATA)
                self.assertEqual(function_build_definition.source_hash, TestBuildGraph.SOURCE_HASH)
                self.assertEqual(function_build_definition.manifest_hash, TestBuildGraph.MANIFEST_HASH)
                self.assertEqual(function_build_definition.env_vars, TestBuildGraph.ENV_VARS)

            for layer_build_definition in build_graph.get_layer_build_definitions():
                self.assertEqual(layer_build_definition.full_path, TestBuildGraph.LAYER_NAME)
                self.assertEqual(layer_build_definition.codeuri, TestBuildGraph.LAYER_CODEURI)
                self.assertEqual(layer_build_definition.build_method, TestBuildGraph.LAYER_RUNTIME)
                self.assertEqual(layer_build_definition.source_hash, TestBuildGraph.SOURCE_HASH)
                self.assertEqual(layer_build_definition.manifest_hash, TestBuildGraph.MANIFEST_HASH)
                self.assertEqual(layer_build_definition.compatible_runtimes, [TestBuildGraph.LAYER_RUNTIME])
                self.assertEqual(layer_build_definition.env_vars, TestBuildGraph.ENV_VARS)

    @patch("samcli.lib.build.build_graph.rust_read_runtime_build_graph")
    def test_should_read_existing_build_graph_from_runtime_records(self, rust_read_runtime_build_graph):
        function_record = Mock(
            uuid="fn-uuid",
            source_hash="source",
            manifest_hash="manifest",
            runtime="python3.12",
            codeuri="src",
            imageuri=None,
            packagetype="Zip",
            architecture=X86_64,
            handler="app.handler",
            metadata_json='{"BuildMethod":"esbuild"}',
            env_vars_json='{"A":"1"}',
        )
        layer_record = Mock(
            uuid="layer-uuid",
            source_hash="source",
            manifest_hash="manifest",
            full_path="Layer",
            codeuri="layer",
            build_method="python3.12",
            compatible_runtimes=["python3.12"],
            architecture=X86_64,
            env_vars_json='{"L":"1"}',
        )
        rust_runtime_graph = Mock()
        rust_runtime_graph.function_records.return_value = [function_record]
        rust_runtime_graph.layer_records.return_value = [layer_record]
        rust_runtime_graph.into_state.return_value = "persisted-state"
        rust_read_runtime_build_graph.return_value = rust_runtime_graph

        build_graph = BuildGraph("build_dir")

        function_definition = build_graph.get_function_build_definitions()[0]
        layer_definition = build_graph.get_layer_build_definitions()[0]
        self.assertEqual(function_definition.uuid, "fn-uuid")
        self.assertEqual(function_definition.metadata, {"BuildMethod": "esbuild"})
        self.assertEqual(layer_definition.uuid, "layer-uuid")
        self.assertEqual(layer_definition.env_vars, {"L": "1"})
        self.assertEqual(build_graph._runtime_state, "persisted-state")

    def test_functions_should_be_added_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_definition1 = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                None,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            function1 = generate_function(
                runtime=TestBuildGraph.RUNTIME,
                codeuri=TestBuildGraph.CODEURI,
                metadata=TestBuildGraph.METADATA,
            )
            build_graph.put_function_build_definition(build_definition1, function1)

            build_definitions = build_graph.get_function_build_definitions()
            self.assertEqual(len(build_definitions), 1)
            self.assertEqual(len(build_definitions[0].functions), 1)
            self.assertEqual(build_definitions[0].functions[0], function1)
            self.assertEqual(build_definitions[0].uuid, TestBuildGraph.UUID)

            build_definition2 = FunctionBuildDefinition(
                "another_runtime",
                "another_codeuri",
                None,
                TestBuildGraph.ZIP,
                ARM64,
                None,
                "app.handler",
                "another_source_hash",
                "another_manifest_hash",
                {"env_vars": "value2"},
            )
            function2 = generate_function(name="another_function")
            build_graph.put_function_build_definition(build_definition2, function2)

            build_definitions = build_graph.get_function_build_definitions()
            self.assertEqual(len(build_definitions), 2)
            self.assertEqual(len(build_definitions[1].functions), 1)
            self.assertEqual(build_definitions[1].functions[0], function2)

    def test_layers_should_be_added_existing_build_graph(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_definition1 = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.LAYER_ARCHITECTURE,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            layer1 = generate_layer(
                compatible_runtimes=[TestBuildGraph.RUNTIME],
                codeuri=TestBuildGraph.LAYER_CODEURI,
                metadata=TestBuildGraph.METADATA,
            )
            build_graph.put_layer_build_definition(build_definition1, layer1)

            build_definitions = build_graph.get_layer_build_definitions()
            self.assertEqual(len(build_definitions), 1)
            self.assertEqual(build_definitions[0].layer, layer1)
            self.assertEqual(build_definitions[0].uuid, TestBuildGraph.LAYER_UUID)

            build_definition2 = LayerBuildDefinition(
                "another_layername",
                "another_codeuri",
                "another_runtime",
                ["another_runtime"],
                "another_source_hash",
                "another_manifest_hash",
                {"env_vars": "value2"},
            )
            layer2 = generate_layer(arn="arn:aws:lambda:region:account-id:layer:another-layer-name:1")
            build_graph.put_layer_build_definition(build_definition2, layer2)

            build_definitions = build_graph.get_layer_build_definitions()
            self.assertEqual(len(build_definitions), 2)
            self.assertEqual(build_definitions[1].layer, layer2)

    @patch.dict("os.environ", {"SAM_CLI_RUST_BUILD_CORE": "0"})
    @patch("samcli.lib.build.build_graph.BuildGraph._write_source_hash")
    @patch("samcli.lib.build.build_graph.BuildGraph._compare_hash_changes")
    def test_update_definition_hash_should_succeed(self, compare_hash_mock, write_hash_mock):
        compare_hash_mock.return_value = {"mock": "hash"}
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            current_function_build_definitions = build_graph.get_function_build_definitions()
            current_layer_build_definitions = build_graph.get_layer_build_definitions()

            build_graph.update_definition_hash()

            write_hash_mock.assert_called_with({"mock": "hash"}, {"mock": "hash"})
            self.assertEqual(current_function_build_definitions, build_graph.get_function_build_definitions())
            self.assertEqual(current_layer_build_definitions, build_graph.get_layer_build_definitions())

    @patch("samcli.lib.build.build_graph.BuildGraph._write_source_hash")
    @patch("samcli.lib.build.build_graph.rust_compare_definition_hashes")
    @patch("samcli.lib.build.build_graph.rust_read_runtime_build_graph")
    def test_update_definition_hash_uses_runtime_states_without_reloading_python_graph(
        self,
        read_runtime_build_graph_mock,
        compare_definition_hashes_mock,
        write_hash_mock,
    ):
        build_graph = BuildGraph("build_dir")
        current_runtime_state = Mock()
        current_runtime_state.definition_function_rows.return_value = [("current-function-row",)]
        current_runtime_state.definition_layer_rows.return_value = [("current-layer-row",)]
        build_graph._runtime_state = current_runtime_state

        persisted_runtime_state = Mock()
        persisted_runtime_state.definition_function_rows.return_value = [("persisted-function-row",)]
        persisted_runtime_state.definition_layer_rows.return_value = [("persisted-layer-row",)]
        persisted_runtime_graph = Mock()
        persisted_runtime_graph.into_state.return_value = persisted_runtime_state
        read_runtime_build_graph_mock.return_value = persisted_runtime_graph
        compare_definition_hashes_mock.return_value = (
            [("function-uuid", "function-source", "function-manifest")],
            [("layer-uuid", "layer-source", "layer-manifest")],
        )

        with patch.object(build_graph, "_read") as read_mock:
            build_graph.update_definition_hash()

        read_mock.assert_not_called()
        compare_definition_hashes_mock.assert_called_once_with(
            [("current-function-row",)],
            [("persisted-function-row",)],
            [("current-layer-row",)],
            [("persisted-layer-row",)],
        )
        write_hash_mock.assert_called_once_with(
            {"function-uuid": BuildHashingInformation("function-source", "function-manifest")},
            {"layer-uuid": BuildHashingInformation("layer-source", "layer-manifest")},
        )

    def test_compare_hash_changes_should_succeed(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_definition = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                None,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            updated_definition = FunctionBuildDefinition(
                TestBuildGraph.RUNTIME,
                TestBuildGraph.CODEURI,
                None,
                TestBuildGraph.ZIP,
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.METADATA,
                TestBuildGraph.HANDLER,
                "new_value",
                "new_manifest_value",
                TestBuildGraph.ENV_VARS,
            )
            updated_definition.uuid = build_definition.uuid

            layer_definition = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.ARCHITECTURE_FIELD,
                TestBuildGraph.SOURCE_HASH,
                TestBuildGraph.MANIFEST_HASH,
                TestBuildGraph.ENV_VARS,
            )
            updated_layer = LayerBuildDefinition(
                TestBuildGraph.LAYER_NAME,
                TestBuildGraph.LAYER_CODEURI,
                TestBuildGraph.LAYER_RUNTIME,
                [TestBuildGraph.LAYER_RUNTIME],
                TestBuildGraph.ARCHITECTURE_FIELD,
                "new_value",
                "new_manifest_value",
                TestBuildGraph.ENV_VARS,
            )
            updated_layer.uuid = layer_definition.uuid

            build_graph._function_build_definitions = [build_definition]
            build_graph._layer_build_definitions = [layer_definition]

            function_content = BuildGraph._compare_hash_changes(
                [updated_definition], build_graph._function_build_definitions
            )
            layer_content = BuildGraph._compare_hash_changes([updated_layer], build_graph._layer_build_definitions)
            self.assertEqual(function_content, {build_definition.uuid: ("new_value", "new_manifest_value")})
            self.assertEqual(layer_content, {layer_definition.uuid: ("new_value", "new_manifest_value")})

    @parameterized.expand(
        [
            ("manifest_hash", "manifest_hash", False),
            ("manifest_hash", "new_manifest_hash", True),
        ]
    )
    def test_compare_hash_changes_should_preserve_download_dependencies(
        self, old_manifest, new_manifest, download_dependencies
    ):
        updated_definition = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, X86_64, {}, "app.handler", manifest_hash=old_manifest
        )
        existing_definition = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, X86_64, {}, "app.handler", manifest_hash=new_manifest
        )
        BuildGraph._compare_hash_changes([updated_definition], [existing_definition])
        self.assertEqual(existing_definition.download_dependencies, download_dependencies)

    def test_write_source_hash_should_succeed(self):
        with osutils.mkdir_temp() as temp_base_dir:
            build_dir = Path(temp_base_dir, ".aws-sam", "build")
            build_dir.mkdir(parents=True)

            build_graph_path = Path(build_dir.parent, "build.toml")
            build_graph_path.write_text(TestBuildGraph.BUILD_GRAPH_CONTENTS)

            build_graph = BuildGraph(str(build_dir))

            build_graph._write_source_hash(
                {TestBuildGraph.UUID: BuildHashingInformation("new_value", "new_manifest_value")},
                {TestBuildGraph.LAYER_UUID: BuildHashingInformation("new_value", "new_manifest_value")},
            )

            txt = build_graph_path.read_text()
            document = cast(Dict, tomlkit.loads(txt))

            self.assertEqual(
                document["function_build_definitions"][TestBuildGraph.UUID][SOURCE_HASH_FIELD], "new_value"
            )
            self.assertEqual(
                document["function_build_definitions"][TestBuildGraph.UUID][MANIFEST_HASH_FIELD], "new_manifest_value"
            )
            self.assertEqual(
                document["layer_build_definitions"][TestBuildGraph.LAYER_UUID][SOURCE_HASH_FIELD], "new_value"
            )
            self.assertEqual(
                document["layer_build_definitions"][TestBuildGraph.LAYER_UUID][MANIFEST_HASH_FIELD],
                "new_manifest_value",
            )

    def test_empty_get_function_build_definition_with_logical_id(self):
        build_graph = BuildGraph("build_dir")
        self.assertIsNone(build_graph.get_function_build_definition_with_full_path("function_logical_id"))

    def test_get_function_build_definition_with_logical_id(self):
        build_graph = BuildGraph("build_dir")
        logical_id = "function_logical_id"
        function = Mock()
        function.full_path = logical_id
        function_build_definition = Mock(functions=[function])
        build_graph._function_build_definitions = [function_build_definition]

        self.assertEqual(
            build_graph.get_function_build_definition_with_full_path(logical_id), function_build_definition
        )

    def test_populate_from_runtime_graph_plan_replaces_python_facade_lists(self):
        build_graph = BuildGraph("build_dir")
        build_graph._function_build_definitions = [Mock()]
        build_graph._layer_build_definitions = [Mock()]
        functions = [generate_function(function_id="fn1"), generate_function(function_id="fn2")]
        layers = [
            generate_layer(arn="arn:aws:lambda:region:account-id:layer:layer-name:1"),
            generate_layer(arn="arn:aws:lambda:region:account-id:layer:layer-name:2"),
        ]
        function_record = Mock(
            uuid="fn-uuid",
            source_hash="source",
            manifest_hash="manifest",
            runtime="python3.12",
            codeuri="src",
            imageuri=None,
            packagetype="Zip",
            architecture=X86_64,
            handler="app.handler",
            metadata_json="{}",
            env_vars_json="{}",
        )
        layer_record = Mock(
            uuid="layer-uuid",
            source_hash="source",
            manifest_hash="manifest",
            full_path="Layer",
            codeuri="layer",
            build_method="python3.12",
            compatible_runtimes=["python3.12"],
            architecture=X86_64,
            env_vars_json="{}",
        )
        runtime_graph_plan = Mock()
        runtime_graph_plan.function_groups.return_value = [[0, 1]]
        runtime_graph_plan.function_records.return_value = [function_record]
        runtime_graph_plan.layer_groups.return_value = [[0, 1]]
        runtime_graph_plan.layer_records.return_value = [layer_record]
        runtime_graph_plan.into_state.return_value = "runtime-state"

        build_graph.populate_from_runtime_graph_plan(runtime_graph_plan, functions, layers)

        function_definition = build_graph.get_function_build_definitions()[0]
        layer_definition = build_graph.get_layer_build_definitions()[0]
        self.assertEqual(function_definition.uuid, "fn-uuid")
        self.assertEqual(function_definition.functions, functions)
        self.assertEqual(layer_definition.uuid, "layer-uuid")
        self.assertEqual(layer_definition.layer, layers[1])
        self.assertEqual(build_graph._runtime_state, "runtime-state")

    def test_legacy_graph_append_invalidates_runtime_state(self):
        build_graph = BuildGraph("build_dir")
        build_graph._runtime_state = "runtime-state"
        function_definition = FunctionBuildDefinition("runtime", "codeuri", None, ZIP, X86_64, {}, "handler")

        build_graph.put_pre_deduped_function_build_definition(function_definition, [generate_function()])

        self.assertIsNone(build_graph._runtime_state)

    def test_runtime_state_records_share_updates_with_facades(self):
        build_graph = BuildGraph("build_dir")
        function_record = Mock(
            uuid="fn-uuid",
            source_hash="source",
            manifest_hash="manifest",
            runtime="python3.12",
            codeuri="src",
            imageuri=None,
            packagetype="Zip",
            architecture=X86_64,
            handler="app.handler",
            metadata_json="{}",
            env_vars_json="{}",
        )
        state_record = Mock(source_hash="source")
        runtime_graph_plan = Mock()
        runtime_graph_plan.function_groups.return_value = [[0]]
        runtime_graph_plan.function_records.return_value = [function_record]
        runtime_graph_plan.layer_groups.return_value = []
        runtime_graph_plan.layer_records.return_value = []
        runtime_graph_plan.into_state.return_value = Mock(function_records=Mock(return_value=[state_record]))

        build_graph.populate_from_runtime_graph_plan(runtime_graph_plan, [generate_function()], [])
        build_graph.get_function_build_definitions()[0].source_hash = "updated"

        # This unit-level fake only proves the facade mutation path remains intact;
        # native shared-record identity is verified by the Rust-mode integration check.
        self.assertEqual(build_graph.get_function_build_definitions()[0].source_hash, "updated")

    def test_definition_rows_prefer_runtime_state_when_available(self):
        build_graph = BuildGraph("build_dir")
        runtime_state = Mock()
        runtime_state.definition_function_rows.return_value = [("function-row",)]
        runtime_state.definition_layer_rows.return_value = [("layer-row",)]
        build_graph._runtime_state = runtime_state

        self.assertEqual(build_graph.definition_function_rows(), [("function-row",)])
        self.assertEqual(build_graph.definition_layer_rows(), [("layer-row",)])

    def test_persisted_rows_prefer_runtime_state_when_available(self):
        build_graph = BuildGraph("build_dir")
        function = generate_function()
        layer = generate_layer()
        function_definition = FunctionBuildDefinition("runtime", "codeuri", None, ZIP, X86_64, {}, "handler")
        function_definition.add_function(function)
        layer_definition = LayerBuildDefinition("Layer", "codeuri", "method", ["runtime"], X86_64)
        layer_definition.layer = layer
        build_graph._function_build_definitions = [function_definition]
        build_graph._layer_build_definitions = [layer_definition]
        runtime_state = Mock()
        runtime_state.persisted_function_rows.return_value = [("function-row",)]
        runtime_state.persisted_layer_rows.return_value = [("layer-row",)]
        build_graph._runtime_state = runtime_state

        self.assertEqual(build_graph.persisted_function_rows(), [("function-row",)])
        self.assertEqual(build_graph.persisted_layer_rows(), [("layer-row",)])
        runtime_state.persisted_function_rows.assert_called_once_with([[function.full_path]])
        runtime_state.persisted_layer_rows.assert_called_once_with([layer.full_path])


class TestBuildDefinition(TestCase):
    @patch("samcli.lib.build.build_graph.create_runtime_definition_record")
    def test_runtime_state_fields_delegate_to_optional_rust_record(self, create_record):
        record = Mock(uuid="record-uuid", source_hash="record-source", manifest_hash="record-manifest")
        create_record.return_value = record
        build_definition = FunctionBuildDefinition("runtime", "codeuri", None, ZIP, X86_64, {}, "handler")

        self.assertEqual(build_definition.uuid, "record-uuid")
        self.assertEqual(build_definition.source_hash, "record-source")
        self.assertEqual(build_definition.manifest_hash, "record-manifest")

        build_definition.uuid = "new-uuid"
        build_definition.source_hash = "new-source"
        build_definition.manifest_hash = "new-manifest"

        self.assertEqual(record.uuid, "new-uuid")
        self.assertEqual(record.source_hash, "new-source")
        self.assertEqual(record.manifest_hash, "new-manifest")

    @patch("samcli.lib.build.build_graph.create_runtime_function_record")
    def test_function_runtime_scalar_fields_delegate_to_optional_rust_record(self, create_record):
        record = Mock(
            uuid="uuid",
            source_hash="source",
            manifest_hash="manifest",
            runtime="record-runtime",
            codeuri="record-codeuri",
            imageuri="record-imageuri",
            packagetype="record-packagetype",
            architecture="record-architecture",
            handler="record-handler",
            metadata_json='{"record":"metadata"}',
            env_vars_json='{"record":"env"}',
        )
        create_record.return_value = record
        build_definition = FunctionBuildDefinition("runtime", "codeuri", None, ZIP, X86_64, {}, "handler")

        self.assertEqual(build_definition.runtime, "record-runtime")
        self.assertEqual(build_definition.codeuri, "record-codeuri")
        self.assertEqual(build_definition.imageuri, "record-imageuri")
        self.assertEqual(build_definition.packagetype, "record-packagetype")
        self.assertEqual(build_definition.architecture, "record-architecture")
        self.assertEqual(build_definition.handler, "record-handler")
        self.assertEqual(build_definition.metadata, {"record": "metadata"})
        self.assertEqual(build_definition.env_vars, {"record": "env"})

    def test_function_can_materialize_directly_from_rust_record(self):
        record = Mock(
            uuid="",
            source_hash="source",
            manifest_hash="manifest",
            runtime="record-runtime",
            codeuri="record-codeuri",
            imageuri="record-imageuri",
            packagetype="record-packagetype",
            architecture="record-architecture",
            handler="record-handler",
            metadata_json='{"record":"metadata"}',
            env_vars_json='{"record":"env"}',
        )

        build_definition = FunctionBuildDefinition.from_runtime_record(record)

        self.assertEqual(build_definition.runtime, "record-runtime")
        self.assertEqual(build_definition.metadata, {"record": "metadata"})
        self.assertEqual(build_definition.env_vars, {"record": "env"})
        self.assertTrue(build_definition.uuid)
        self.assertEqual(record.uuid, build_definition.uuid)

    def test_function_equality_delegates_to_rust_record_when_present(self):
        left = FunctionBuildDefinition("runtime", "codeuri", None, ZIP, X86_64, {}, "handler")
        right = FunctionBuildDefinition("runtime", "codeuri", None, ZIP, X86_64, {}, "handler")
        left._runtime_record = Mock(metadata_json="{}", env_vars_json="{}")
        right._runtime_record = Mock(metadata_json="{}", env_vars_json="{}")
        left._runtime_record.equivalent_for_build.return_value = True

        self.assertEqual(left, right)
        left._runtime_record.equivalent_for_build.assert_called_once()

    @patch("samcli.lib.build.build_graph.create_runtime_layer_record")
    def test_layer_runtime_scalar_fields_delegate_to_optional_rust_record(self, create_record):
        record = Mock(
            uuid="uuid",
            source_hash="source",
            manifest_hash="manifest",
            full_path="record-layer",
            codeuri="record-codeuri",
            build_method="record-method",
            compatible_runtimes=["record-runtime"],
            architecture="record-architecture",
            env_vars_json='{"record":"env"}',
        )
        create_record.return_value = record
        build_definition = LayerBuildDefinition("Layer", "codeuri", "method", ["python3.12"], X86_64)

        self.assertEqual(build_definition.full_path, "record-layer")
        self.assertEqual(build_definition.codeuri, "record-codeuri")
        self.assertEqual(build_definition.build_method, "record-method")
        self.assertEqual(build_definition.compatible_runtimes, ["record-runtime"])
        self.assertEqual(build_definition.architecture, "record-architecture")
        self.assertEqual(build_definition.env_vars, {"record": "env"})

    def test_layer_can_materialize_directly_from_rust_record(self):
        record = Mock(
            uuid="",
            source_hash="source",
            manifest_hash="manifest",
            full_path="record-layer",
            codeuri="record-codeuri",
            build_method="record-method",
            compatible_runtimes=["record-runtime"],
            architecture="record-architecture",
            env_vars_json='{"record":"env"}',
        )

        build_definition = LayerBuildDefinition.from_runtime_record(record)

        self.assertEqual(build_definition.full_path, "record-layer")
        self.assertEqual(build_definition.env_vars, {"record": "env"})
        self.assertTrue(build_definition.uuid)
        self.assertEqual(record.uuid, build_definition.uuid)

    def test_layer_equality_delegates_to_rust_record_when_present(self):
        left = LayerBuildDefinition("Layer", "codeuri", "method", ["python3.12"], X86_64)
        right = LayerBuildDefinition("Layer", "codeuri", "method", ["python3.12"], X86_64)
        left._runtime_record = Mock()
        right._runtime_record = Mock()
        left._runtime_record.equivalent_for_build.return_value = True

        self.assertEqual(left, right)
        left._runtime_record.equivalent_for_build.assert_called_once()

    def test_single_function_should_return_function_and_handler_name(self):
        build_definition = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            X86_64,
            {},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value"},
        )
        build_definition.add_function(generate_function())
        self.assertEqual(build_definition.get_handler_name(), "handler")
        self.assertEqual(build_definition.get_function_name(), "name")

    def test_no_function_should_raise_exception(self):
        build_definition = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            X86_64,
            {},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value"},
        )

        self.assertRaises(InvalidBuildGraphException, build_definition.get_handler_name)
        self.assertRaises(InvalidBuildGraphException, build_definition.get_function_name)

    def test_same_runtime_codeuri_metadata_should_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, {"key": "value"}, "handler", "source_hash", "manifest_hash"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, {"key": "value"}, "handler", "source_hash", "manifest_hash"
        )

        self.assertEqual(build_definition1, build_definition2)

    def test_skip_sam_related_metadata_should_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            ARM64,
            {"key": "value", "SamResourceId": "resourceId1", "SamNormalized": True},
            "handler",
            "source_hash",
            "manifest_hash",
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            ARM64,
            {"key": "value", "SamResourceId": "resourceId2", "SamNormalized": True},
            "handler",
            "source_hash",
            "manifest_hash",
        )

        self.assertEqual(build_definition1, build_definition2)

    def test_same_env_vars_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            X86_64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value"},
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            X86_64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value"},
        )

        self.assertEqual(build_definition1, build_definition2)

    @parameterized.expand(
        [
            (
                "runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
                "runtime",
                "codeuri",
                ({"key": "different_value"}),
                "source_hash",
            ),
            (
                "runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
                "different_runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
            ),
            (
                "runtime",
                "codeuri",
                ({"key": "value"}),
                "source_hash",
                "runtime",
                "different_codeuri",
                ({"key": "value"}),
                "source_hash",
            ),
            # custom build method with Makefile definition should always be identified as different
            (
                "runtime",
                "codeuri",
                ({"BuildMethod": "makefile"}),
                "source_hash",
                "runtime",
                "codeuri",
                ({"BuildMethod": "makefile"}),
                "source_hash",
            ),
        ]
    )
    def test_different_runtime_codeuri_metadata_should_not_reflect_as_same_object(
        self, runtime1, codeuri1, metadata1, source_hash_1, runtime2, codeuri2, metadata2, source_hash_2
    ):
        build_definition1 = FunctionBuildDefinition(runtime1, codeuri1, None, ZIP, ARM64, metadata1, source_hash_1)
        build_definition2 = FunctionBuildDefinition(runtime2, codeuri2, None, ZIP, ARM64, metadata2, source_hash_2)

        self.assertNotEqual(build_definition1, build_definition2)

    def test_different_architecture_should_not_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, X86_64, {"key": "value"}, "handler", "source_md5", {"env_vars": "value"}
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, {"key": "value"}, "handler", "source_md5", {"env_vars": "value"}
        )

        self.assertNotEqual(build_definition1, build_definition2)

    def test_different_env_vars_should_not_reflect_as_same_object(self):
        build_definition1 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            ARM64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value1"},
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime",
            "codeuri",
            None,
            ZIP,
            ARM64,
            {"key": "value"},
            "handler",
            "source_hash",
            "manifest_hash",
            {"env_vars": "value2"},
        )

        self.assertNotEqual(build_definition1, build_definition2)

    def test_euqality_with_another_object(self):
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, X86_64, None, "source_hash", "manifest_hash"
        )
        self.assertNotEqual(build_definition, {})

    def test_str_representation(self):
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, None, "handler", "source_hash", "manifest_hash"
        )
        self.assertEqual(
            str(build_definition),
            f"BuildDefinition(runtime, codeuri, Zip, source_hash, {build_definition.uuid}, {{}}, {{}}, arm64, [])",
        )

    def test_esbuild_definitions_equal_objects_independent_build_method(self):
        build_graph = BuildGraph("build/path")
        metadata = {"BuildMethod": "esbuild"}
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler-1"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, metadata, "app.handler", "source_hash", "manifest_hash"
        )
        function2 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler-2"
        )
        build_graph.put_function_build_definition(build_definition1, function1)
        build_graph.put_function_build_definition(build_definition2, function2)

        build_definitions = build_graph.get_function_build_definitions()

        self.assertNotEqual(build_definition1, build_definition2)
        self.assertEqual(len(build_definitions), 2)
        self.assertEqual(len(build_definition1.functions), 1)
        self.assertEqual(len(build_definition2.functions), 1)

    def test_independent_build_definitions_equal_objects_one_esbuild_build_method(self):
        build_graph = BuildGraph("build/path")
        metadata = {"BuildMethod": "esbuild"}
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler-1"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, {}, "handler", "source_hash", "manifest_hash"
        )
        function2 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata={}, handler="handler-2"
        )
        build_graph.put_function_build_definition(build_definition1, function1)
        build_graph.put_function_build_definition(build_definition2, function2)

        build_definitions = build_graph.get_function_build_definitions()

        self.assertNotEqual(build_definition1, build_definition2)
        self.assertEqual(len(build_definitions), 2)
        self.assertEqual(len(build_definition1.functions), 1)
        self.assertEqual(len(build_definition2.functions), 1)

    def test_two_esbuild_methods_same_handler(self):
        build_graph = BuildGraph("build/path")
        metadata = {"BuildMethod": "esbuild"}
        build_definition1 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler"
        )
        build_definition2 = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function2 = generate_function(
            runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, metadata={}, handler="handler"
        )
        build_graph.put_function_build_definition(build_definition1, function1)
        build_graph.put_function_build_definition(build_definition2, function2)

        build_definitions = build_graph.get_function_build_definitions()

        self.assertEqual(build_definition1, build_definition2)
        self.assertEqual(len(build_definitions), 1)
        self.assertEqual(len(build_definition1.functions), 2)

    @parameterized.expand([(True,), (False,)])
    @patch("samcli.lib.build.build_graph.is_experimental_enabled")
    def test_build_folder_with_multiple_functions(self, build_improvements_22_enabled, patched_is_experimental):
        patched_is_experimental.return_value = build_improvements_22_enabled
        build_graph = BuildGraph("build/path")
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, {}, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, handler="handler")
        function2 = generate_function(runtime=TestBuildGraph.RUNTIME, codeuri=TestBuildGraph.CODEURI, handler="handler")
        build_graph.put_function_build_definition(build_definition, function1)
        build_graph.put_function_build_definition(build_definition, function2)

        if not build_improvements_22_enabled:
            self.assertEqual(
                build_definition.get_build_dir("build_dir"), build_definition.functions[0].get_build_dir("build_dir")
            )
        else:
            self.assertEqual(
                build_definition.get_build_dir("build_dir"),
                build_definition.functions[0].get_build_dir("build_dir") + "-Shared",
            )

    def test_deepcopy_build_definition(self):
        build_definition = FunctionBuildDefinition(
            "runtime", "codeuri", None, ZIP, ARM64, {}, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(runtime="runtime", codeuri="codeuri", handler="handler")
        function2 = generate_function(runtime="runtime", codeuri="codeuri", handler="handler")
        build_definition.add_function(function1)
        build_definition.add_function(function2)
        build_definitions = [build_definition]

        copied_build_definitions = copy.deepcopy(build_definitions)

        self.assertEqual(copied_build_definitions, build_definitions)

    def test_go_runtime_different_handlers_are_not_equal(self):
        build_graph = BuildGraph("build/path")
        metadata = {}
        build_definition1 = FunctionBuildDefinition(
            "go1.x", "codeuri", None, ZIP, ARM64, metadata, "handler", "source_hash", "manifest_hash"
        )
        function1 = generate_function(
            runtime="go1.x", codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler"
        )
        build_definition2 = FunctionBuildDefinition(
            "go1.x", "codeuri", None, ZIP, ARM64, metadata, "handler.new", "source_hash", "manifest_hash"
        )
        function2 = generate_function(
            runtime="go1.x", codeuri=TestBuildGraph.CODEURI, metadata=metadata, handler="handler.new"
        )
        build_graph.put_function_build_definition(build_definition1, function1)
        build_graph.put_function_build_definition(build_definition2, function2)

        build_definitions = build_graph.get_function_build_definitions()

        self.assertNotEqual(build_definition1, build_definition2)
        self.assertEqual(len(build_definitions), 2)
        self.assertEqual(len(build_definition1.functions), 1)
        self.assertEqual(len(build_definition2.functions), 1)
