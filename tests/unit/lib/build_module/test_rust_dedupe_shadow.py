from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.build.app_builder import ApplicationBuilder


class TestRustDedupeShadow(TestCase):
    @patch("samcli.lib.build.app_builder.LOG")
    @patch("samcli.lib.build.app_builder.is_rust_build_core_shadow_enabled", return_value=True)
    @patch("samcli.lib.build.app_builder.shadow_dedupe_function_specs")
    def test_logs_when_rust_function_dedupe_differs(self, shadow_dedupe_mock, _shadow_enabled_mock, log_mock):
        fn_a = Mock(full_path="FnA")
        fn_b = Mock(full_path="FnB")
        definition = Mock(functions=[fn_a, fn_b])
        build_graph = Mock()
        build_graph.get_function_build_definitions.return_value = [definition]
        shadow_dedupe_mock.return_value = [["FnA"], ["FnB"]]

        ApplicationBuilder._compare_rust_function_dedupe(build_graph, [], {})

        log_mock.warning.assert_called_once()

    @patch("samcli.lib.build.app_builder.LOG")
    @patch("samcli.lib.build.app_builder.is_rust_build_core_shadow_enabled", return_value=True)
    @patch("samcli.lib.build.app_builder.shadow_dedupe_layer_specs")
    def test_logs_when_rust_layer_dedupe_differs(self, shadow_dedupe_mock, _shadow_enabled_mock, log_mock):
        layer_a = Mock(full_path="LayerA")
        definition = Mock(layer=layer_a)
        build_graph = Mock()
        build_graph.get_layer_build_definitions.return_value = [definition]
        shadow_dedupe_mock.return_value = [["LayerB"]]

        ApplicationBuilder._compare_rust_layer_dedupe(build_graph, [], [])

        log_mock.warning.assert_called_once()

    @patch("samcli.lib.build.app_builder.is_rust_build_core_shadow_enabled", return_value=False)
    @patch("samcli.lib.build.app_builder.shadow_dedupe_function_specs")
    @patch.object(ApplicationBuilder, "_function_dedupe_specs")
    def test_function_shadow_compare_is_skipped_outside_shadow_mode(
        self, function_specs_mock, shadow_dedupe_mock, _shadow_enabled_mock
    ):
        ApplicationBuilder._compare_rust_function_dedupe(Mock(), [Mock()], {"Fn": {}})

        function_specs_mock.assert_not_called()
        shadow_dedupe_mock.assert_not_called()

    @patch("samcli.lib.build.app_builder.is_rust_build_core_shadow_enabled", return_value=False)
    @patch("samcli.lib.build.app_builder.shadow_dedupe_layer_specs")
    def test_layer_shadow_compare_is_skipped_outside_shadow_mode(self, shadow_dedupe_mock, _shadow_enabled_mock):
        ApplicationBuilder._compare_rust_layer_dedupe(Mock(), [Mock()], [{"full_path": "Layer"}])

        shadow_dedupe_mock.assert_not_called()
