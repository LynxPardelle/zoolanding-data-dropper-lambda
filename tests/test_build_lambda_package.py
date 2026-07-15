import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock


REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[1]


class BuildLambdaPackageTests(unittest.TestCase):
    def test_builder_copies_only_lambda_function_and_removes_stale_files(self):
        try:
            from tools.build_lambda_package import build_lambda_package
        except ModuleNotFoundError as error:
            self.fail(f"missing runtime package builder: {error}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            source = root / "repository"
            output = source / ".build" / "data-dropper"
            source.mkdir()
            output.mkdir(parents=True)
            (source / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            (source / "README.md").write_text("must not be packaged\n", encoding="utf-8")
            (output / "stale.txt").write_text("stale\n", encoding="utf-8")

            build_lambda_package(source_root=source, output_directory=output)

            files = sorted(
                path.relative_to(output).as_posix()
                for path in output.rglob("*")
                if path.is_file() or path.is_symlink()
            )
            self.assertEqual(files, ["lambda_function.py"])
            self.assertEqual((output / "lambda_function.py").read_bytes(), b"RUNTIME = True\n")

    def test_builder_rejects_an_output_directory_outside_the_source_root(self):
        from tools.build_lambda_package import build_lambda_package

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            source = root / "repository"
            output = root / "outside"
            source.mkdir()
            output.mkdir()
            (source / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            sentinel = output / "must-survive.txt"
            sentinel.write_text("do not delete\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "inside source root"):
                build_lambda_package(source_root=source, output_directory=output)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not delete\n")

    def test_builder_rejects_an_in_repository_directory_other_than_its_build_path(self):
        from tools.build_lambda_package import build_lambda_package

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = pathlib.Path(temporary_directory) / "repository"
            output = source / "docs"
            source.mkdir()
            output.mkdir()
            (source / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            sentinel = output / "must-survive.txt"
            sentinel.write_text("do not delete\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, r"\.build/data-dropper"):
                build_lambda_package(source_root=source, output_directory=output)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not delete\n")

    def test_builder_rejects_a_junction_like_build_root_before_deleting_output(self):
        from tools.build_lambda_package import build_lambda_package

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = pathlib.Path(temporary_directory) / "repository"
            output = source / ".build" / "data-dropper"
            output.mkdir(parents=True)
            (source / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            sentinel = output / "must-survive.txt"
            sentinel.write_text("do not delete\n", encoding="utf-8")

            with mock.patch(
                "tools.build_lambda_package._is_unsafe_link",
                side_effect=lambda path: path == output.parent,
            ):
                with self.assertRaisesRegex(RuntimeError, "junction or symbolic link"):
                    build_lambda_package(source_root=source, output_directory=output)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not delete\n")

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_builder_rejects_a_real_windows_build_root_junction(self):
        from tools.build_lambda_package import build_lambda_package

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            source = root / "repository"
            external = root / "external"
            build_root = source / ".build"
            source.mkdir()
            external.mkdir()
            (source / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            sentinel = external / "must-survive.txt"
            sentinel.write_text("do not delete\n", encoding="utf-8")
            junction = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(build_root), str(external)],
                capture_output=True,
                text=True,
                check=False,
            )
            if junction.returncode != 0:
                self.skipTest(f"mklink /J unavailable: {junction.stderr.strip()}")

            try:
                with self.assertRaisesRegex(RuntimeError, "junction or symbolic link"):
                    build_lambda_package(
                        source_root=source,
                        output_directory=build_root / "data-dropper",
                    )
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not delete\n")
            finally:
                build_root.rmdir()

    def test_sam_build_verifier_rejects_any_file_outside_the_exact_build_set(self):
        try:
            from tools.build_lambda_package import verify_sam_build
        except ImportError as error:
            self.fail(f"missing SAM build verifier: {error}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            function_directory = root / ".aws-sam" / "build" / "DataDropperFunction"
            function_directory.mkdir(parents=True)
            (root / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            (function_directory / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            (root / ".aws-sam" / "build" / "template.yaml").write_text(
                "Resources: {}\n",
                encoding="utf-8",
            )

            self.assertEqual(
                verify_sam_build(repository_root=root),
                ("DataDropperFunction/lambda_function.py", "template.yaml"),
            )

            (function_directory / "README.md").write_text("unexpected\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "SAM build file set mismatch"):
                verify_sam_build(repository_root=root)

    def test_sam_build_verifier_rejects_a_junction_like_inventory_entry(self):
        from tools.build_lambda_package import verify_sam_build

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            function_directory = root / ".aws-sam" / "build" / "DataDropperFunction"
            function_directory.mkdir(parents=True)
            (root / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            (function_directory / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            (root / ".aws-sam" / "build" / "template.yaml").write_text(
                "Resources: {}\n",
                encoding="utf-8",
            )

            with mock.patch(
                "tools.build_lambda_package._is_unsafe_link",
                side_effect=lambda path: path.name == "DataDropperFunction",
            ):
                with self.assertRaisesRegex(RuntimeError, "inventory entry"):
                    verify_sam_build(repository_root=root)

    def test_sam_build_verifier_requires_byte_identical_runtime_code(self):
        from tools.build_lambda_package import verify_sam_build

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            function_directory = root / ".aws-sam" / "build" / "DataDropperFunction"
            function_directory.mkdir(parents=True)
            (root / "lambda_function.py").write_bytes(b"EXPECTED = True\n")
            (function_directory / "lambda_function.py").write_bytes(b"CHANGED = True\n")
            (root / ".aws-sam" / "build" / "template.yaml").write_text(
                "Resources: {}\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "runtime bytes mismatch"):
                verify_sam_build(repository_root=root)

    def test_cli_supports_default_build_and_explicit_sam_verification(self):
        try:
            from tools.build_lambda_package import main
        except ImportError as error:
            self.fail(f"missing builder CLI: {error}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            function_directory = root / ".aws-sam" / "build" / "DataDropperFunction"
            function_directory.mkdir(parents=True)
            (root / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            (function_directory / "lambda_function.py").write_bytes(b"RUNTIME = True\n")
            (root / ".aws-sam" / "build" / "template.yaml").write_text(
                "Resources: {}\n",
                encoding="utf-8",
            )

            main([], repository_root=root)
            self.assertEqual(
                (root / ".build" / "data-dropper" / "lambda_function.py").read_bytes(),
                b"RUNTIME = True\n",
            )
            main(["--verify-sam-build"], repository_root=root)

    def test_sam_template_uses_only_the_ignored_generated_runtime_directory(self):
        template = (REPOSITORY_ROOT / "template.yaml").read_text(encoding="utf-8")
        ignored_paths = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn("      CodeUri: .build/data-dropper", template)
        self.assertNotIn("      CodeUri: .\n", template)
        self.assertIn(".build/", ignored_paths)
        self.assertIn(".aws-sam/", ignored_paths)


if __name__ == "__main__":
    unittest.main()
