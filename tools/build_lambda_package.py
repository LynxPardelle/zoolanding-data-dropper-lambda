from __future__ import annotations

import argparse
import os
import pathlib
import shutil


REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_FILES = ("lambda_function.py",)
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / ".build" / "data-dropper"
SAM_BUILD_FILES = ("DataDropperFunction/lambda_function.py", "template.yaml")


def _is_unsafe_link(path: pathlib.Path) -> bool:
    junction_check = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(junction_check and junction_check())


def _file_set(root: pathlib.Path) -> tuple[str, ...]:
    if _is_unsafe_link(root):
        raise RuntimeError("inventory root is a junction or symbolic link")

    files: list[str] = []
    for current_root, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = pathlib.Path(current_root)
        for name in (*directory_names, *file_names):
            path = current_path / name
            if _is_unsafe_link(path):
                raise RuntimeError(
                    f"inventory entry is a junction or symbolic link: "
                    f"{path.relative_to(root).as_posix()}"
                )
        files.extend(
            (current_path / name).relative_to(root).as_posix()
            for name in file_names
        )
    return tuple(sorted(files))


def build_lambda_package(
    *,
    source_root: pathlib.Path = REPOSITORY_ROOT,
    output_directory: pathlib.Path = DEFAULT_OUTPUT_DIRECTORY,
) -> tuple[str, ...]:
    source_root = pathlib.Path(source_root).absolute()
    output_directory = pathlib.Path(output_directory).absolute()
    build_root = source_root / ".build"
    for path in (build_root, output_directory):
        if _is_unsafe_link(path):
            raise RuntimeError("runtime package path is a junction or symbolic link")
    resolved_source_root = source_root.resolve(strict=True)
    resolved_output_directory = output_directory.resolve(strict=False)
    if (
        resolved_output_directory == resolved_source_root
        or not resolved_output_directory.is_relative_to(resolved_source_root)
    ):
        raise RuntimeError("runtime package output must be inside source root")
    expected_output_directory = source_root / ".build" / "data-dropper"
    if output_directory != expected_output_directory:
        raise RuntimeError("runtime package output must be .build/data-dropper")

    for relative_path in RUNTIME_FILES:
        source_file = source_root / relative_path
        if not source_file.is_file() or source_file.is_symlink():
            raise RuntimeError(f"runtime source missing or invalid: {relative_path}")

    if output_directory.is_symlink() or output_directory.is_file():
        output_directory.unlink()
    elif output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)

    for relative_path in RUNTIME_FILES:
        shutil.copyfile(source_root / relative_path, output_directory / relative_path)

    actual_files = _file_set(output_directory)
    if actual_files != RUNTIME_FILES:
        raise RuntimeError(f"runtime package file set mismatch: {actual_files!r}")
    return actual_files


def verify_sam_build(*, repository_root: pathlib.Path = REPOSITORY_ROOT) -> tuple[str, ...]:
    repository_root = pathlib.Path(repository_root)
    build_directory = repository_root / ".aws-sam" / "build"
    actual_files = _file_set(build_directory)
    if actual_files != SAM_BUILD_FILES:
        raise RuntimeError(f"SAM build file set mismatch: {actual_files!r}")
    if (repository_root / "lambda_function.py").read_bytes() != (
        build_directory / "DataDropperFunction" / "lambda_function.py"
    ).read_bytes():
        raise RuntimeError("SAM build runtime bytes mismatch")
    return actual_files


def main(
    argv: list[str] | None = None,
    *,
    repository_root: pathlib.Path = REPOSITORY_ROOT,
) -> tuple[str, ...]:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--verify-sam-build", action="store_true")
    arguments = parser.parse_args(argv)
    repository_root = pathlib.Path(repository_root)
    if arguments.verify_sam_build:
        return verify_sam_build(repository_root=repository_root)
    return build_lambda_package(
        source_root=repository_root,
        output_directory=repository_root / ".build" / "data-dropper",
    )


if __name__ == "__main__":
    main()
