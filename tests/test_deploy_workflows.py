import pathlib
import shlex
import subprocess
import tomllib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

CHECKOUT_ACTION = "actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd"
SETUP_NODE_ACTION = "actions/setup-node@a0853c24544627f65ddf259abe73b1d18a591444"
SETUP_PYTHON_ACTION = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
SETUP_SAM_ACTION = "aws-actions/setup-sam@89ddb14d60e682855e3fea4be85b3c56485de310"
UPLOAD_ARTIFACT_ACTION = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
DOWNLOAD_ARTIFACT_ACTION = "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131"
GITHUB_SCRIPT_ACTION = "actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd"
CONFIGURE_AWS_ACTION = "aws-actions/configure-aws-credentials@517a711dbcd0e402f90c77e7e2f81e849156e31d"
VERIFIER_BLOB = "a1e369e4e6d7a24b3595e5604a6fddab51af526d"


class DeployWorkflowTests(unittest.TestCase):
    def test_dev_is_local_only(self):
        samconfig = (REPO_ROOT / "samconfig.toml").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        workflows_dir = REPO_ROOT / ".github" / "workflows"
        workflow_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(workflows_dir.glob("*.yml"))
        )
        deploy_environments = {
            line.removeprefix("[").removesuffix(".deploy.parameters]")
            for line in samconfig.splitlines()
            if line.startswith("[") and line.endswith(".deploy.parameters]")
        }

        self.assertEqual(deploy_environments, {"default", "test", "prod"})
        self.assertNotRegex(samconfig, r"(?m)^\[dev\.")
        self.assertFalse((workflows_dir / "deploy-dev.yml").exists())
        self.assertNotIn("--config-env dev", workflow_text)
        self.assertNotIn("includes `dev`, `test`, and `prod` deployment profiles", readme)
        self.assertNotRegex(readme, r"(?m)^- `dev` writes ")
        self.assertIn("Pushes to `dev` run CI only", readme)

    def test_ci_runs_the_audited_node_promotion_contract(self):
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn(CHECKOUT_ACTION, text)
        self.assertIn(SETUP_NODE_ACTION, text)
        self.assertIn(SETUP_PYTHON_ACTION, text)
        self.assertIn(SETUP_SAM_ACTION, text)
        self.assertIn("node-version: '22'", text)

        result = subprocess.run(
            ["node", "--test", "tests/promotion_provenance.spec.mjs"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ci_builds_and_verifies_the_exact_runtime_package(self):
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        builder = "python tools/build_lambda_package.py"
        validate = "sam validate --lint"
        sam_build = "sam build --no-cached"
        verify = "python tools/build_lambda_package.py --verify-sam-build"

        self.assertIn(builder, text)
        self.assertIn(validate, text)
        self.assertIn(sam_build, text)
        self.assertIn(verify, text)
        self.assertLess(text.index(builder), text.index(validate))
        self.assertLess(text.index(validate), text.index(sam_build))
        self.assertLess(text.index(sam_build), text.index(verify))

    def test_promotion_verifier_matches_the_audited_blob(self):
        verifier = REPO_ROOT / "tools" / "verify-promotion-commit.mjs"
        self.assertTrue(verifier.is_file())

        result = subprocess.run(
            ["git", "hash-object", "--path=tools/verify-promotion-commit.mjs", str(verifier)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), VERIFIER_BLOB)
        verifier_text = verifier.read_text(encoding="utf-8")
        self.assertNotIn("tip-only", verifier_text)
        self.assertIn("const finalTargetTipSha = await fetchTargetBranchSha", verifier_text)

    def test_ci_guard_uses_environment_indirection_for_github_refs(self):
        text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        for variable, expression in (
            ("EVENT_NAME", "github.event_name"),
            ("BASE_REF", "github.base_ref"),
            ("HEAD_REF", "github.head_ref"),
            ("HEAD_REPO", "github.event.pull_request.head.repo.full_name"),
            ("REPOSITORY", "github.repository"),
        ):
            self.assertIn(f"{variable}: ${{{{ {expression} }}}}", text)

        self.assertIn('if [[ "$EVENT_NAME" != "pull_request" ]]', text)
        self.assertIn('base="$BASE_REF"', text)
        self.assertIn('head="$HEAD_REF"', text)
        self.assertIn('if [[ "$base" == "test" || "$base" == "main" ]]', text)
        self.assertIn('[[ "$HEAD_REPO" != "$REPOSITORY" ]]', text)
        self.assertNotIn('if [[ "${{ github.event_name }}"', text)
        self.assertNotIn('base="${{ github.base_ref }}"', text)
        self.assertNotIn('head="${{ github.head_ref }}"', text)

    def test_samconfig_and_deploy_commands_match_exactly(self):
        with (REPO_ROOT / "samconfig.toml").open("rb") as samconfig_file:
            samconfig = tomllib.load(samconfig_file)

        expected_parameters = {
            "default": {
                "stack_name": "zoolanding-data-dropper",
                "region": "us-east-1",
                "resolve_s3": True,
                "confirm_changeset": False,
                "capabilities": "CAPABILITY_IAM",
                "parameter_overrides": (
                    "RawBucketName=zoolanding-data-raw LogLevel=INFO"
                ),
            },
            "test": {
                "stack_name": "zoolanding-data-dropper-test",
                "region": "us-east-1",
                "resolve_s3": True,
                "confirm_changeset": False,
                "capabilities": "CAPABILITY_IAM",
                "parameter_overrides": (
                    "EnvironmentName=test ManageRawBucket=true "
                    "RawBucketName=zoolanding-data-raw-test LogLevel=INFO"
                ),
            },
            "prod": {
                "stack_name": "zoolanding-data-dropper",
                "region": "us-east-1",
                "resolve_s3": True,
                "confirm_changeset": False,
                "capabilities": "CAPABILITY_IAM",
                "parameter_overrides": (
                    "EnvironmentName=prod ManageRawBucket=false "
                    "RawBucketName=zoolanding-data-raw LogLevel=INFO"
                ),
            },
        }
        self.assertEqual(set(samconfig), {"version", *expected_parameters})
        self.assertEqual(samconfig["version"], 0.1)

        expected_parameter_keys = {
            "stack_name",
            "region",
            "resolve_s3",
            "confirm_changeset",
            "capabilities",
            "parameter_overrides",
        }
        for environment, parameters in expected_parameters.items():
            with self.subTest(profile=environment):
                profile = samconfig[environment]
                self.assertEqual(set(profile), {"deploy"})
                self.assertEqual(set(profile["deploy"]), {"parameters"})
                actual_parameters = profile["deploy"]["parameters"]
                self.assertEqual(set(actual_parameters), expected_parameter_keys)
                self.assertEqual(actual_parameters, parameters)
                self.assertIs(actual_parameters["resolve_s3"], True)
                self.assertIs(actual_parameters["confirm_changeset"], False)

        workflow_profiles = {
            "deploy-test.yml": "test",
            "deploy-production.yml": "prod",
        }
        for workflow_name, profile_name in workflow_profiles.items():
            with self.subTest(workflow=workflow_name):
                text = (REPO_ROOT / ".github" / "workflows" / workflow_name).read_text(
                    encoding="utf-8"
                )
                deploy_line = next(
                    line.strip().removeprefix("run: ")
                    for line in text.splitlines()
                    if line.strip().startswith("run: sam deploy ")
                )
                parameters = expected_parameters[profile_name]
                expected_command = [
                    "sam",
                    "deploy",
                    "--template-file",
                    ".aws-sam/build/template.yaml",
                    "--stack-name",
                    parameters["stack_name"],
                    "--region",
                    parameters["region"],
                    "--resolve-s3",
                    "--capabilities",
                    parameters["capabilities"],
                    "--no-confirm-changeset",
                    "--no-fail-on-empty-changeset",
                    "--parameter-overrides",
                    *shlex.split(parameters["parameter_overrides"]),
                ]
                self.assertEqual(shlex.split(deploy_line), expected_command)

    def test_deploy_workflows_require_exact_merged_pr_provenance(self):
        cases = {
            "deploy-test.yml": ("dev", "test", "test"),
            "deploy-production.yml": ("test", "main", "production"),
        }
        inline_verifiers = []

        for workflow_name, (source_branch, target_branch, environment_name) in cases.items():
            with self.subTest(workflow=workflow_name):
                text = (REPO_ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
                jobs_index = text.index("\njobs:")
                top_level = text[:jobs_index]
                deploy_index = text.index("\n  deploy:")
                exact_command = (
                    f"node tools/verify-promotion-commit.mjs --source={source_branch} --target={target_branch}"
                )

                self.assertIn("workflow_dispatch:", text)
                self.assertIn("contents: read", top_level)
                self.assertIn("pull-requests: read", top_level)
                self.assertNotIn("id-token: write", top_level)
                self.assertIn("AWS_DEFAULT_REGION: us-east-1", top_level)
                self.assertIn("AWS_REGION: us-east-1", top_level)
                self.assertIn("SAM_CLI_TELEMETRY: 0", top_level)
                self.assertIn("concurrency:", top_level)
                self.assertIn(
                    f"group: data-dropper-{environment_name}-${{{{ github.repository }}}}-${{{{ github.ref }}}}",
                    top_level,
                )
                self.assertIn("cancel-in-progress: false", top_level)
                self.assertNotIn("cancel-in-progress: true", text)
                self.assertEqual(text.count(exact_command), 2)
                self.assertNotIn("--tip-only=true", text)
                for action in (
                    CHECKOUT_ACTION,
                    SETUP_NODE_ACTION,
                    SETUP_PYTHON_ACTION,
                    SETUP_SAM_ACTION,
                    UPLOAD_ARTIFACT_ACTION,
                ):
                    self.assertIn(action, text[:deploy_index])
                self.assertNotIn("rev-list --parents", text)
                self.assertNotIn("merge-base --is-ancestor", text)
                self.assertNotIn("HEAD^2", text)
                self.assertIn(f"environment: {environment_name}", text[deploy_index:])
                self.assertIn("id-token: write", text[deploy_index:])
                self.assertIn("pull-requests: read", text[deploy_index:])

                first_verifier = text.index(exact_command)
                second_verifier = text.index(exact_command, first_verifier + len(exact_command))
                validate_section = text[text.index("\n  validate:"):deploy_index]
                deploy_section = text[deploy_index:]
                credentials = text.index(CONFIGURE_AWS_ACTION, deploy_index)

                self.assertIn("sam build --no-cached", validate_section)
                self.assertIn("build-manifest.sha256", validate_section)
                self.assertIn(
                    f"data-dropper-{environment_name}-build-"
                    "${{ github.run_id }}-${{ github.run_attempt }}-${{ github.sha }}",
                    validate_section,
                )
                self.assertIn("include-hidden-files: true", validate_section)
                self.assertGreater(second_verifier, text.index(UPLOAD_ARTIFACT_ACTION))
                self.assertIn(DOWNLOAD_ARTIFACT_ACTION, deploy_section)
                self.assertIn(SETUP_SAM_ACTION, deploy_section)
                self.assertIn("version: 1.163.0", deploy_section)
                self.assertIn(GITHUB_SCRIPT_ACTION, deploy_section)
                self.assertIn(CONFIGURE_AWS_ACTION, deploy_section)
                self.assertIn("sha256sum --check --strict ../build-manifest.sha256", deploy_section)
                self.assertNotIn("python -m unittest", deploy_section)
                self.assertNotIn("sam build", deploy_section)
                self.assertNotIn(SETUP_PYTHON_ACTION, deploy_section)
                self.assertNotIn(CHECKOUT_ACTION, deploy_section)
                self.assertNotIn(SETUP_NODE_ACTION, deploy_section)
                self.assertNotIn("build_lambda_package.py", deploy_section)
                self.assertNotRegex(deploy_section, r"(?m)^\s+run:\s+python(?:\s|$)")
                self.assertNotIn("tools/verify-promotion-commit.mjs", deploy_section)
                self.assertNotIn("ACTIONS_ID_TOKEN_REQUEST", deploy_section)
                self.assertIn("pullRequest.base?.repo?.full_name === repository", deploy_section)
                self.assertIn("pullRequest.head?.repo?.full_name === repository", deploy_section)
                self.assertIn("pullRequest.merge_commit_sha == null", deploy_section)
                self.assertIn("parents[0] !== pullRequest.base.sha", deploy_section)
                self.assertIn("parents[1] !== pullRequest.head.sha", deploy_section)
                self.assertIn("event.after !== sha", deploy_section)
                self.assertIn("context.eventName !== 'workflow_dispatch'", deploy_section)
                self.assertIn("branch.commit.sha !== sha", deploy_section)
                self.assertIn("--template-file .aws-sam/build/template.yaml", deploy_section)
                github_script = text.index(GITHUB_SCRIPT_ACTION, deploy_index)
                credentials_step = text.rfind("\n      - uses:", github_script, credentials)
                self.assertLess(github_script, credentials)
                self.assertNotIn("\n      - ", text[text.index("branch.commit.sha !== sha", github_script):credentials_step])

                script_marker = "          script: |\n"
                script_start = text.index(script_marker, github_script) + len(script_marker)
                script_lines = []
                for line in text[script_start:].splitlines():
                    if line and not line.startswith("            "):
                        break
                    script_lines.append(line[12:] if line else "")
                inline_verifiers.append("\n".join(script_lines).strip())

        self.assertEqual(len(inline_verifiers), 2)
        self.assertEqual(inline_verifiers[0], inline_verifiers[1])

    def test_artifact_handoff_is_independently_bound_strict_and_rerunnable(self):
        cases = {
            "deploy-test.yml": "test",
            "deploy-production.yml": "production",
        }

        for workflow_name, environment_name in cases.items():
            with self.subTest(workflow=workflow_name):
                text = (REPO_ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8")
                deploy_index = text.index("\n  deploy:")
                validate_section = text[text.index("\n  validate:"):deploy_index]
                deploy_section = text[deploy_index:]

                self.assertIn("outputs:", validate_section)
                self.assertIn("artifact_id: ${{ steps.upload.outputs.artifact-id }}", validate_section)
                self.assertIn("artifact_name: ${{ steps.artifact_metadata.outputs.name }}", validate_section)
                self.assertIn("manifest_digest: ${{ steps.manifest.outputs.digest }}", validate_section)
                self.assertIn(f"uses: {UPLOAD_ARTIFACT_ACTION}", validate_section)
                self.assertIn("id: upload", validate_section)
                self.assertIn("id: artifact_metadata", validate_section)
                self.assertIn("id: manifest", validate_section)
                self.assertIn("python tools/build_lambda_package.py", validate_section)
                self.assertIn("python tools/build_lambda_package.py --verify-sam-build", validate_section)
                self.assertIn(
                    "path: |\n"
                    "            .aws-sam/build/\n"
                    "            .aws-sam/build-manifest.sha256",
                    validate_section,
                )

                self.assertIn(f"uses: {DOWNLOAD_ARTIFACT_ACTION}", deploy_section)
                self.assertIn("artifact-ids: ${{ needs.validate.outputs.artifact_id }}", deploy_section)
                self.assertIn("EXPECTED_ARTIFACT_ID: ${{ needs.validate.outputs.artifact_id }}", deploy_section)
                self.assertIn("EXPECTED_ARTIFACT_NAME: ${{ needs.validate.outputs.artifact_name }}", deploy_section)
                self.assertIn("EXPECTED_MANIFEST_DIGEST: ${{ needs.validate.outputs.manifest_digest }}", deploy_section)
                self.assertNotIn("github.run_attempt", deploy_section)
                self.assertIn("^[1-9][0-9]*$", deploy_section)
                self.assertIn("^[a-f0-9]{64}$", deploy_section)
                self.assertIn("sha256sum --check --strict -", deploy_section)
                self.assertIn("sha256sum --check --strict ../build-manifest.sha256", deploy_section)
                self.assertIn("./DataDropperFunction/lambda_function.py", deploy_section)
                self.assertIn("./template.yaml", deploy_section)
                self.assertIn("manifest-paths.txt", deploy_section)
                self.assertIn("artifact-paths.txt", deploy_section)
                self.assertIn("expected-build-files.txt", deploy_section)

                steps_start = deploy_section.index("\n    steps:")
                first_step_line = next(
                    line.strip()
                    for line in deploy_section[steps_start + len("\n    steps:"):].splitlines()
                    if line.strip()
                )
                self.assertEqual(first_step_line, "- name: Validate artifact handoff metadata")
                first_step = deploy_section.index("\n      - name:", steps_start)
                metadata_step = deploy_section.index("\n      - name: Validate artifact handoff metadata", steps_start)
                self.assertEqual(first_step, metadata_step)
                download_start = deploy_section.index(DOWNLOAD_ARTIFACT_ACTION)
                self.assertLess(metadata_step, download_start)
                download_end = deploy_section.index("\n      - name:", download_start)
                download_step = deploy_section[download_start:download_end]
                self.assertNotIn("name:", download_step)
                self.assertNotIn("run-id:", download_step)
                self.assertNotIn("github-token:", download_step)

    def test_deployment_docs_define_the_exact_runtime_and_rerun_contract(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        developer_guide = (REPO_ROOT / "docs" / "developer_guide.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("exactly one runtime file, `lambda_function.py`", readme)
        self.assertIn("`.build/data-dropper`", readme)
        self.assertIn("artifact ID, coordinated name, and manifest digest", readme)
        self.assertIn("rerun of only the failed deploy job", readme)
        self.assertIn("python tools/build_lambda_package.py", developer_guide)
        self.assertIn("python tools/build_lambda_package.py --verify-sam-build", developer_guide)
        self.assertNotIn("Zip the repository", developer_guide)


if __name__ == "__main__":
    unittest.main()
