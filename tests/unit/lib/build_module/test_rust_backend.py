from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.build import rust_backend


class TestRustBackend(TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_is_disabled_by_default(self):
        with patch.object(rust_backend, "_native", Mock()):
            self.assertFalse(rust_backend.is_enabled())

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_sha256_checksum_uses_native_module_when_enabled(self):
        native = Mock()
        native.sha256_dir_checksum.return_value = "checksum"
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.sha256_dir_checksum("src", [".aws-sam"]), "checksum")
        native.sha256_dir_checksum.assert_called_once_with("src", [".aws-sam"])

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

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_SHADOW_ENV_VAR: "1"}, clear=True)
    def test_shadow_plan_graph_groups_returns_native_index_groups(self):
        native = Mock()
        native.plan_graph_groups.return_value = ([[0, 1]], [[0]])
        with patch.object(rust_backend, "_native", native):
            self.assertEqual(rust_backend.shadow_plan_graph_groups([("fn",)], [("layer",)]), ([[0, 1]], [[0]]))

    @patch.dict("os.environ", {rust_backend.RUST_BUILD_CORE_ENV_VAR: "1"}, clear=True)
    def test_write_hash_updates_uses_native_module_when_enabled(self):
        native = Mock()
        with patch.object(rust_backend, "_native", native):
            self.assertTrue(rust_backend.write_hash_updates("build.toml", [("fn", "s", "m")], []))
        native.write_hash_updates.assert_called_once_with("build.toml", [("fn", "s", "m")], [])
