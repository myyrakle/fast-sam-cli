from unittest import TestCase
from unittest.mock import Mock

from samcli.lib.build.rust_compact import current_function_rows, definition_function_rows


class TestRustCompact(TestCase):
    def test_current_function_rows_normalize_sam_metadata(self):
        function = Mock(
            runtime="python3.12",
            codeuri="src",
            imageuri=None,
            packagetype="Zip",
            architecture="x86_64",
            metadata={"BuildMethod": "esbuild", "SamResourceId": "Fn", "SamNormalized": True},
            handler="app.handler",
            full_path="Fn",
        )

        self.assertEqual(
            current_function_rows([function], {"Fn": {"A": "B"}}),
            [
                (
                    "python3.12",
                    "src",
                    None,
                    "Zip",
                    "x86_64",
                    '{"BuildMethod":"esbuild"}',
                    "esbuild",
                    "app.handler",
                    '{"A":"B"}',
                )
            ],
        )

    def test_definition_function_rows_keep_runtime_identity_fields_together(self):
        definition = Mock(
            uuid="uuid",
            source_hash="source",
            manifest_hash="manifest",
            runtime="python3.12",
            codeuri="src",
            imageuri=None,
            packagetype="Zip",
            architecture="x86_64",
            metadata={"BuildMethod": "esbuild"},
            handler="app.handler",
            env_vars={"A": "B"},
        )

        self.assertEqual(
            definition_function_rows([definition]),
            [
                (
                    "uuid",
                    "source",
                    "manifest",
                    "python3.12",
                    "src",
                    None,
                    "Zip",
                    "x86_64",
                    '{"BuildMethod":"esbuild"}',
                    "esbuild",
                    "app.handler",
                    '{"A":"B"}',
                )
            ],
        )
