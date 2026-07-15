import pathlib
import subprocess
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

CHECKOUT_ACTION = "actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd"
SETUP_NODE_ACTION = "actions/setup-node@a0853c24544627f65ddf259abe73b1d18a591444"
SETUP_PYTHON_ACTION = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
SETUP_SAM_ACTION = "aws-actions/setup-sam@89ddb14d60e682855e3fea4be85b3c56485de310"
UPLOAD_ARTIFACT_ACTION = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
DOWNLOAD_ARTIFACT_ACTION = "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0"
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
                self.assertIn(f"data-dropper-{environment_name}-build-${{{{ github.sha }}}}", validate_section)
                self.assertIn("include-hidden-files: true", validate_section)
                self.assertGreater(second_verifier, text.index(UPLOAD_ARTIFACT_ACTION))
                self.assertIn(DOWNLOAD_ARTIFACT_ACTION, deploy_section)
                self.assertIn(SETUP_SAM_ACTION, deploy_section)
                self.assertIn("version: 1.163.0", deploy_section)
                self.assertIn(GITHUB_SCRIPT_ACTION, deploy_section)
                self.assertIn(CONFIGURE_AWS_ACTION, deploy_section)
                self.assertIn("sha256sum --check ../build-manifest.sha256", deploy_section)
                self.assertNotIn("python -m unittest", deploy_section)
                self.assertNotIn("sam build", deploy_section)
                self.assertNotIn(SETUP_PYTHON_ACTION, deploy_section)
                self.assertNotIn(CHECKOUT_ACTION, deploy_section)
                self.assertNotIn(SETUP_NODE_ACTION, deploy_section)
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


if __name__ == "__main__":
    unittest.main()
