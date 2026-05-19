from unittest import TestCase
from unittest.mock import Mock, patch
from pathlib import Path

from samcli.lib.build import rust_backend


class TestRustBackend(TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_is_enabled_by_default(self):
        with patch.object(rust_backend, "_native", Mock()):
            self.assertTrue(rust_backend.is_enabled())
            self.assertEqual(rust_backend.backend_mode(), "active")

    @patch.dict("os.environ", {}, clear=True)
    def test_default_policy_can_disable_rust_without_changing_call_sites(self):
        with patch.object(rust_backend, "_native", Mock()), patch.object(
            rust_backend, "RUST_BUILD_CORE_DEFAULT_ENABLED", False
        ):
            self.assertFalse(rust_backend.is_enabled())
            self.assertEqual(rust_backend.backend_mode(), "python")

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "0"}, clear=True)
    def test_explicit_disable_overrides_default_policy(self):
        with patch.object(rust_backend, "_native", Mock()), patch.object(
            rust_backend, "RUST_BUILD_CORE_DEFAULT_ENABLED", True
        ):
            self.assertFalse(rust_backend.is_enabled())
            self.assertEqual(rust_backend.backend_mode(), "python")

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_mode_is_selected_when_active_backend_is_not_enabled(self):
        with patch.object(rust_backend, "_native", Mock()):
            self.assertFalse(rust_backend.is_enabled())
            self.assertTrue(rust_backend.is_shadow_enabled())
            self.assertEqual(rust_backend.backend_mode(), "shadow")

    @patch.dict(
        "os.environ",
        {
            rust_backend.RUST_BUILD_CORE_ENV_VAR: "1",
            rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1",
        },
        clear=True,
    )
    def test_active_mode_suppresses_shadow_mode(self):
        with patch.object(rust_backend, "_native", Mock()):
            self.assertTrue(rust_backend.is_enabled())
            self.assertFalse(rust_backend.is_shadow_enabled())
            self.assertEqual(rust_backend.backend_mode(), "active")

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_sha256_checksum_uses_native_module_when_enabled(self):
        native = Mock()
        native.sha256_dir_checksum.return_value = "checksum"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.sha256_dir_checksum("src", [".aws-sam"]), "checksum")
        native.sha256_dir_checksum.assert_called_once_with("src", [".aws-sam"])

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_md5_checksum_uses_native_module_when_enabled(self):
        native = Mock()
        native.md5_dir_checksum.return_value = "checksum"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.md5_dir_checksum("src", [".aws-sam"]), "checksum")
        native.md5_dir_checksum.assert_called_once_with("src", [".aws-sam"])

    @patch.dict("os.environ", {}, clear=True)
    def test_sha256_checksum_falls_back_when_native_path_is_unavailable(self):
        native = Mock()
        native.sha256_dir_checksum.side_effect = OSError("missing")
        with patch.object(rust_backend, "_native", native):
            self.assertIsNone(rust_backend.sha256_dir_checksum("src", [".aws-sam"]))

    @patch.dict("os.environ", {}, clear=True)
    def test_sha256_checksum_accepts_path_like_inputs(self):
        native = Mock()
        native.sha256_dir_checksum.return_value = "checksum"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.sha256_dir_checksum(Path("src"), [".aws-sam"]), "checksum")
        native.sha256_dir_checksum.assert_called_once_with("src", [".aws-sam"])

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_create_runtime_definition_record_uses_native_module_when_enabled(self):
        native = Mock()
        native.RuntimeDefinitionRecord.return_value = "record"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.create_runtime_definition_record("uuid", "source", "manifest"), "record")
        native.RuntimeDefinitionRecord.assert_called_once_with("uuid", "source", "manifest")

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_create_runtime_function_record_uses_native_module_when_enabled(self):
        native = Mock()
        native.RuntimeFunctionRecord.return_value = "record"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.create_runtime_function_record(
                    "uuid",
                    "source",
                    "manifest",
                    "python3.12",
                    "src",
                    None,
                    "Zip",
                    "x86_64",
                    "app.handler",
                    {},
                    {},
                ),
                "record",
            )
        native.RuntimeFunctionRecord.assert_called_once_with(
            "uuid",
            "source",
            "manifest",
            "python3.12",
            "src",
            None,
            "Zip",
            "x86_64",
            "app.handler",
            "{}",
            "{}",
        )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "0"}, clear=True)
    def test_create_runtime_function_record_skips_serialization_when_disabled(self):
        self.assertIsNone(
            rust_backend.create_runtime_function_record(
                "uuid",
                "source",
                "manifest",
                "python3.12",
                "src",
                None,
                "Zip",
                "x86_64",
                "app.handler",
                Mock(),
                Mock(),
            )
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_create_runtime_function_record_falls_back_when_metadata_is_not_serializable(self):
        with patch.object(rust_backend, "_native", Mock()):
            self.assertIsNone(
                rust_backend.create_runtime_function_record(
                    "uuid", "source", "manifest", "python3.12", "src", None, "Zip", "x86_64", "handler", Mock(), {}
                )
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_create_runtime_layer_record_uses_native_module_when_enabled(self):
        native = Mock()
        native.RuntimeLayerRecord.return_value = "record"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.create_runtime_layer_record(
                    "uuid",
                    "source",
                    "manifest",
                    "Layer",
                    "layer",
                    "python3.12",
                    ["python3.12"],
                    "x86_64",
                    {},
                ),
                "record",
            )
        native.RuntimeLayerRecord.assert_called_once_with(
            "uuid",
            "source",
            "manifest",
            "Layer",
            "layer",
            "python3.12",
            ["python3.12"],
            "x86_64",
            "{}",
        )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "0"}, clear=True)
    def test_create_runtime_layer_record_skips_serialization_when_disabled(self):
        self.assertIsNone(
            rust_backend.create_runtime_layer_record(
                "uuid",
                "source",
                "manifest",
                "Layer",
                "layer",
                "python3.12",
                ["python3.12"],
                "x86_64",
                Mock(),
            )
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_create_runtime_layer_record_falls_back_when_env_vars_are_not_serializable(self):
        with patch.object(rust_backend, "_native", Mock()):
            self.assertIsNone(
                rust_backend.create_runtime_layer_record(
                    "uuid", "source", "manifest", "Layer", "src", "makefile", [], "x86_64", Mock()
                )
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_plan_build_returns_native_mapping(self):
        native = Mock()
        native.plan_build.return_value = {"mode": "incremental"}
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.plan_build("python3.12", False, True, "a", "a", "m", "m", True),
                {"mode": "incremental"},
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_plan_build_returns_native_mapping(self):
        native = Mock()
        native.plan_build.return_value = {"mode": "cached"}
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.shadow_plan_build("go1.x", False, False, "", "", None, "", False),
                {"mode": "cached"},
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_batch_plan_builds_returns_native_mappings(self):
        native = Mock()
        native.batch_plan_builds.return_value = [{"id": "Fn", "mode": "incremental"}]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.shadow_batch_plan_builds([{"id": "Fn"}]),
                [{"id": "Fn", "mode": "incremental"}],
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_batch_plan_modes_returns_native_pairs(self):
        native = Mock()
        native.batch_plan_modes.return_value = [("Fn", "incremental")]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.shadow_batch_plan_modes([("Fn", "python3.12", False)]),
                [("Fn", "incremental")],
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_dedupe_function_specs_returns_native_groups(self):
        native = Mock()
        native.dedupe_function_specs.return_value = [["FnA", "FnB"]]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.shadow_dedupe_function_specs([{"full_path": "FnA"}]), [["FnA", "FnB"]])

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_dedupe_function_specs_returns_native_groups(self):
        native = Mock()
        native.dedupe_function_specs.return_value = [["FnA", "FnB"]]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.dedupe_function_specs([{"full_path": "FnA"}]), [["FnA", "FnB"]])

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_dedupe_layer_specs_returns_native_groups(self):
        native = Mock()
        native.dedupe_layer_specs.return_value = [["LayerA"]]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.shadow_dedupe_layer_specs([{"full_path": "LayerA"}]), [["LayerA"]])

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_dedupe_layer_specs_returns_native_groups(self):
        native = Mock()
        native.dedupe_layer_specs.return_value = [["LayerA"]]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.dedupe_layer_specs([{"full_path": "LayerA"}]), [["LayerA"]])

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_plan_graph_groups_returns_native_index_groups(self):
        native = Mock()
        native.plan_graph_groups.return_value = ([[0, 1]], [[0]])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.plan_graph_groups([("fn",)], [("layer",)]), ([[0, 1]], [[0]]))

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_plan_graph_groups_from_resources_returns_native_index_groups(self):
        native = Mock()
        native.plan_graph_groups_from_resources.return_value = ([[0, 1]], [[0]])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.plan_graph_groups_from_resources(["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}),
                ([[0, 1]], [[0]]),
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_plan_graph_groups_from_resources_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(
                rust_backend.plan_graph_groups_from_resources(["fn"], {"Fn": {}}, ["layer"], {"Layer": {}})
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_current_graph_rows_returns_native_rows(self):
        native = Mock()
        native.current_graph_rows.return_value = ([("fn",)], [("layer",)])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.current_graph_rows(["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}),
                ([("fn",)], [("layer",)]),
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_current_graph_rows_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(rust_backend.current_graph_rows(["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}))

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_current_graph_rows_returns_native_rows(self):
        native = Mock()
        native.current_graph_rows.return_value = ([("fn",)], [("layer",)])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.shadow_current_graph_rows(["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}),
                ([("fn",)], [("layer",)]),
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_current_graph_rows_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(
                rust_backend.shadow_current_graph_rows(["fn"], {"Fn": {}}, ["layer"], {"Layer": {}})
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_reconcile_graph_groups_returns_native_runtime_groups(self):
        native = Mock()
        native.reconcile_graph_groups.return_value = (
            [([0, 1], "fn-uuid", "source", "manifest")],
            [([0], "layer-uuid", "source", "manifest")],
        )
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.reconcile_graph_groups([("fn",)], [("layer",)], [("old-fn",)], [("old-layer",)]),
                (
                    [([0, 1], "fn-uuid", "source", "manifest")],
                    [([0], "layer-uuid", "source", "manifest")],
                ),
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_reconcile_graph_groups_from_resources_returns_native_runtime_groups(self):
        native = Mock()
        native.reconcile_graph_groups_from_resources.return_value = (
            [([0, 1], "fn-uuid", "source", "manifest")],
            [([0], "layer-uuid", "source", "manifest")],
        )
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.reconcile_graph_groups_from_resources(
                    ["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}, [("old-fn",)], [("old-layer",)]
                ),
                (
                    [([0, 1], "fn-uuid", "source", "manifest")],
                    [([0], "layer-uuid", "source", "manifest")],
                ),
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_reconcile_graph_groups_from_resources_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(
                rust_backend.reconcile_graph_groups_from_resources(
                    ["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}, [("old-fn",)], [("old-layer",)]
                )
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_reconcile_graph_plan_returns_native_materialization_plan(self):
        native = Mock()
        graph_plan = Mock()
        native.reconcile_graph_plan.return_value = graph_plan
        with patch.object(rust_backend, "_native", native):
            self.assertIs(
                rust_backend.reconcile_graph_plan([("fn",)], [("layer",)], [("old-fn",)], [("old-layer",)]),
                graph_plan,
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_reconcile_graph_plan_from_resources_returns_native_materialization_plan(self):
        native = Mock()
        graph_plan = Mock()
        native.reconcile_graph_plan_from_resources.return_value = graph_plan
        with patch.object(rust_backend, "_native", native):
            self.assertIs(
                rust_backend.reconcile_graph_plan_from_resources(
                    ["fn"],
                    {"Fn": {}},
                    ["layer"],
                    {"Layer": {}},
                    [("old-fn",)],
                    [("old-layer",)],
                ),
                graph_plan,
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_reconcile_graph_plan_from_resources_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(
                rust_backend.reconcile_graph_plan_from_resources(
                    ["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}, [("old-fn",)], [("old-layer",)]
                )
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_runtime_graph_plan_from_resource_groups_returns_native_materialization_plan(self):
        native = Mock()
        graph_plan = Mock()
        native.runtime_graph_plan_from_resource_groups.return_value = graph_plan
        with patch.object(rust_backend, "_native", native):
            self.assertIs(
                rust_backend.runtime_graph_plan_from_resource_groups(
                    ["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}, [([0], "fn", "s", "m")], [([0], "l", "s", "m")]
                ),
                graph_plan,
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_runtime_graph_plan_from_resource_groups_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(
                rust_backend.runtime_graph_plan_from_resource_groups(
                    ["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}, [([0], "fn", "s", "m")], [([0], "l", "s", "m")]
                )
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_compare_definition_hashes_returns_native_updates(self):
        native = Mock()
        native.compare_definition_hashes.return_value = ([("fn", "s", "m")], [("layer", "s", "m")])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.compare_definition_hashes([("fn",)], [("old-fn",)], [("layer",)], [("old-layer",)]),
                ([("fn", "s", "m")], [("layer", "s", "m")]),
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_plan_graph_groups_returns_native_index_groups(self):
        native = Mock()
        native.plan_graph_groups.return_value = ([[0, 1]], [[0]])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.shadow_plan_graph_groups([("fn",)], [("layer",)]), ([[0, 1]], [[0]]))

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_plan_graph_groups_from_resources_returns_native_index_groups(self):
        native = Mock()
        native.plan_graph_groups_from_resources.return_value = ([[0, 1]], [[0]])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.shadow_plan_graph_groups_from_resources(
                    ["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}
                ),
                ([[0, 1]], [[0]]),
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_plan_graph_groups_from_resources_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(
                rust_backend.shadow_plan_graph_groups_from_resources(
                    ["fn"], {"Fn": {}}, ["layer"], {"Layer": {}}
                )
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_write_hash_updates_uses_native_module_when_enabled(self):
        native = Mock()
        with patch.object(rust_backend, "_native", native):
            self.assertTrue(rust_backend.write_hash_updates("build.toml", [("fn", "s", "m")], []))
        native.write_hash_updates.assert_called_once_with("build.toml", [("fn", "s", "m")], [])

    @patch.dict("os.environ", {}, clear=True)
    def test_remove_redundant_folders_accepts_path_like_inputs(self):
        native = Mock()
        native.remove_redundant_folders.return_value = ["removed"]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.remove_redundant_folders(Path("cache"), ["keep"]), ["removed"])
        native.remove_redundant_folders.assert_called_once_with("cache", ["keep"])

    @patch.dict("os.environ", {}, clear=True)
    def test_remove_redundant_folders_falls_back_for_non_path_like_inputs(self):
        native = Mock()
        with patch.object(rust_backend, "_native", native):
            self.assertIsNone(rust_backend.remove_redundant_folders(object(), ["keep"]))
        native.remove_redundant_folders.assert_not_called()

    @patch.dict("os.environ", {}, clear=True)
    def test_create_package_zip_returns_native_artifact(self):
        native = Mock()
        native.create_package_zip.return_value = "artifact.zip"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.create_package_zip(Path("artifact"), Path("src"), True), "artifact.zip")
        native.create_package_zip.assert_called_once_with("artifact", "src", True)

    @patch.dict("os.environ", {}, clear=True)
    def test_create_package_zip_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(rust_backend.create_package_zip("artifact", "src", False))

    @patch.dict("os.environ", {}, clear=True)
    def test_create_lambda_zip_with_sha256_returns_native_artifact(self):
        native = Mock()
        native.create_lambda_zip_with_sha256.return_value = ("artifact.zip", "sha256")
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.create_lambda_zip_with_sha256(Path("artifact"), Path("src")),
                ("artifact.zip", "sha256"),
            )
        native.create_lambda_zip_with_sha256.assert_called_once_with("artifact", "src")

    @patch.dict("os.environ", {}, clear=True)
    def test_create_lambda_zip_with_sha256_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(rust_backend.create_lambda_zip_with_sha256("artifact", "src"))

    @patch.dict("os.environ", {}, clear=True)
    def test_sha256_file_checksum_returns_native_hash(self):
        native = Mock()
        native.sha256_file_checksum.return_value = "sha256"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.sha256_file_checksum(Path("artifact.zip")), "sha256")
        native.sha256_file_checksum.assert_called_once_with("artifact.zip")

    @patch.dict("os.environ", {}, clear=True)
    def test_sha256_file_checksum_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(rust_backend.sha256_file_checksum("artifact.zip"))

    @patch.dict("os.environ", {}, clear=True)
    def test_md5_file_checksum_returns_native_hash(self):
        native = Mock()
        native.md5_file_checksum.return_value = "md5"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.md5_file_checksum(Path("artifact.zip")), "md5")
        native.md5_file_checksum.assert_called_once_with("artifact.zip")

    @patch.dict("os.environ", {}, clear=True)
    def test_md5_file_checksum_returns_none_when_native_api_is_unavailable(self):
        with patch.object(rust_backend, "_native", object()):
            self.assertIsNone(rust_backend.md5_file_checksum("artifact.zip"))

    @patch.dict("os.environ", {}, clear=True)
    def test_write_sync_state_compact_uses_native_module(self):
        native = Mock()
        with patch.object(rust_backend, "_native", native):
            self.assertTrue(
                rust_backend.write_sync_state_compact("sync.toml", True, 1.0, [("Fn", "hash", 2.0)])
            )
        native.write_sync_state_compact.assert_called_once_with("sync.toml", True, 1.0, [("Fn", "hash", 2.0)])

    @patch.dict("os.environ", {}, clear=True)
    def test_read_sync_state_compact_returns_native_rows(self):
        native = Mock()
        native.read_sync_state_compact.return_value = (True, 1.0, [("Fn", "hash", 2.0)])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.read_sync_state_compact("sync.toml"),
                (True, 1.0, [("Fn", "hash", 2.0)]),
            )

    @patch.dict("os.environ", {}, clear=True)
    def test_create_runtime_sync_state_returns_native_handle(self):
        native = Mock()
        runtime_state = Mock()
        native.RuntimeSyncState.return_value = runtime_state
        with patch.object(rust_backend, "_native", native):
            self.assertIs(
                rust_backend.create_runtime_sync_state(True, 1.0, [("Fn", "hash", 2.0)]),
                runtime_state,
            )
        native.RuntimeSyncState.assert_called_once_with(True, 1.0, [("Fn", "hash", 2.0)])

    @patch.dict("os.environ", {}, clear=True)
    def test_read_runtime_sync_state_returns_native_handle(self):
        native = Mock()
        runtime_state = Mock()
        native.read_runtime_sync_state.return_value = runtime_state
        with patch.object(rust_backend, "_native", native):
            self.assertIs(rust_backend.read_runtime_sync_state(Path("sync.toml")), runtime_state)
        native.read_runtime_sync_state.assert_called_once_with("sync.toml")

    @patch.dict("os.environ", {}, clear=True)
    def test_create_runtime_resource_type_index_returns_native_handle(self):
        native = Mock()
        runtime_index = Mock()
        rows = [("", "Fn", "Fn", "AWS::Serverless::Function")]
        native.RuntimeResourceTypeIndex.return_value = runtime_index
        with patch.object(rust_backend, "_native", native):
            self.assertIs(rust_backend.create_runtime_resource_type_index(rows), runtime_index)
        native.RuntimeResourceTypeIndex.assert_called_once_with(rows)

    @patch.dict("os.environ", {}, clear=True)
    def test_dependent_function_ids_returns_native_matches(self):
        native = Mock()
        rows = [("FnA", ["LayerA"]), ("FnB", ["LayerB"])]
        native.dependent_function_ids.return_value = ["FnA"]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.dependent_function_ids("LayerA", rows), ["FnA"])
        native.dependent_function_ids.assert_called_once_with("LayerA", rows)

    @patch.dict("os.environ", {}, clear=True)
    def test_read_definition_bytes_with_sha256_returns_native_body_and_hash(self):
        native = Mock()
        native.read_definition_bytes_with_sha256.return_value = (b"{}", "sha256")
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.read_definition_bytes_with_sha256(Path("openapi.json")), (b"{}", "sha256"))
        native.read_definition_bytes_with_sha256.assert_called_once_with("openapi.json")

    @patch.dict("os.environ", {}, clear=True)
    def test_read_definition_text_with_sha256_returns_native_body_and_hash(self):
        native = Mock()
        native.read_definition_text_with_sha256.return_value = ("{}", "sha256")
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.read_definition_text_with_sha256(Path("state.json")), ("{}", "sha256"))
        native.read_definition_text_with_sha256.assert_called_once_with("state.json")

    @patch.dict("os.environ", {}, clear=True)
    def test_function_resource_api_call_rows_returns_native_rows(self):
        native = Mock()
        native.function_resource_api_call_rows.return_value = [
            ("Layer", ["Build"]),
            ("Function", ["UpdateFunctionCode", "UpdateFunctionConfiguration"]),
        ]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.function_resource_api_call_rows("Function", ["Layer"], "CodeUri/", False),
                [
                    ("Layer", ["Build"]),
                    ("Function", ["UpdateFunctionCode", "UpdateFunctionConfiguration"]),
                ],
            )
        native.function_resource_api_call_rows.assert_called_once_with("Function", ["Layer"], "CodeUri/", False)

    @patch.dict("os.environ", {}, clear=True)
    def test_lock_keys_from_api_call_rows_returns_native_keys(self):
        native = Mock()
        rows = [("Function", ["UpdateFunctionCode", "UpdateFunctionConfiguration"])]
        native.lock_keys_from_api_call_rows.return_value = [
            "Function_UpdateFunctionCode",
            "Function_UpdateFunctionConfiguration",
        ]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.lock_keys_from_api_call_rows(rows),
                {"Function_UpdateFunctionCode", "Function_UpdateFunctionConfiguration"},
            )
        native.lock_keys_from_api_call_rows.assert_called_once_with(rows)

    @patch.dict("os.environ", {}, clear=True)
    def test_collect_rest_api_stage_names_returns_native_stages(self):
        native = Mock()
        stage_rows = [("prod", "Api1", "Deployment1")]
        native.collect_rest_api_stage_names.return_value = ["beta", "Stage", "prod"]
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.collect_rest_api_stage_names(
                    "Api1",
                    "AWS::Serverless::Api",
                    "beta",
                    ["Stage"],
                    stage_rows,
                    ["Deployment1"],
                ),
                {"beta", "Stage", "prod"},
            )
        native.collect_rest_api_stage_names.assert_called_once_with(
            "Api1",
            "AWS::Serverless::Api",
            "beta",
            ["Stage"],
            stage_rows,
            ["Deployment1"],
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_local_hash_matches_returns_native_result(self):
        native = Mock()
        native.local_hash_matches.return_value = True
        with patch.object(rust_backend, "_native", native):
            self.assertTrue(rust_backend.local_hash_matches("hash", "hash"))
        native.local_hash_matches.assert_called_once_with("hash", "hash")

    @patch.dict("os.environ", {}, clear=True)
    def test_sync_execution_decision_returns_native_plan(self):
        native = Mock()
        native.sync_execution_decision.return_value = (True, False)
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.sync_execution_decision(False, None), (True, False))
        native.sync_execution_decision.assert_called_once_with(False, None)

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_read_build_graph_decodes_native_json_when_enabled(self):
        native = Mock()
        native.read_build_graph.return_value = '{"function_build_definitions": [], "layer_build_definitions": []}'
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(
                rust_backend.read_build_graph("build.toml"),
                {"function_build_definitions": [], "layer_build_definitions": []},
            )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_read_runtime_build_graph_returns_native_handle_when_enabled(self):
        native = Mock()
        graph = Mock()
        native.read_runtime_build_graph.return_value = graph
        with patch.object(rust_backend, "_native", native):
            self.assertIs(rust_backend.read_runtime_build_graph("build.toml"), graph)

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_write_build_graph_encodes_native_json_when_enabled(self):
        native = Mock()
        with patch.object(rust_backend, "_native", native):
            self.assertTrue(
                rust_backend.write_build_graph(
                    "build.toml",
                    {"function_build_definitions": [], "layer_build_definitions": []},
                )
            )
        native.write_build_graph.assert_called_once_with(
            "build.toml",
            '{"function_build_definitions":[],"layer_build_definitions":[]}',
        )

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_write_build_graph_compact_uses_native_module_when_enabled(self):
        native = Mock()
        with patch.object(rust_backend, "_native", native):
            self.assertTrue(rust_backend.write_build_graph_compact("build.toml", [("fn",)], [("layer",)]))
        native.write_build_graph_compact.assert_called_once_with("build.toml", [("fn",)], [("layer",)])
