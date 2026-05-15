from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.build.app_builder import ApplicationBuilder


class TestRustDedupeShadow(TestCase):
    @patch("samcli.lib.build.app_builder.LOG")
    @patch("samcli.lib.build.app_builder.shadow_dedupe_function_specs")
    def test_logs_when_rust_function_dedupe_differs(self, shadow_dedupe_mock, log_mock):
        fn_a = Mock(full_path="FnA")
        fn_b = Mock(full_path="FnB")
        definition = Mock(functions=[fn_a, fn_b])
        build_graph = Mock()
        build_graph.get_function_build_definitions.return_value = [definition]
        shadow_dedupe_mock.return_value = [["FnA"], ["FnB"]]

        ApplicationBuilder._compare_rust_function_dedupe(build_graph, [], {})

        log_mock.warning.assert_called_once()

    @patch("samcli.lib.build.app_builder.LOG")
    @patch("samcli.lib.build.app_builder.shadow_dedupe_layer_specs")
    def test_logs_when_rust_layer_dedupe_differs(self, shadow_dedupe_mock, log_mock):
        layer_a = Mock(full_path="LayerA")
        definition = Mock(layer=layer_a)
        build_graph = Mock()
        build_graph.get_layer_build_definitions.return_value = [definition]
        shadow_dedupe_mock.return_value = [["LayerB"]]

        ApplicationBuilder._compare_rust_layer_dedupe(build_graph, [], [])

        log_mock.warning.assert_called_once()
