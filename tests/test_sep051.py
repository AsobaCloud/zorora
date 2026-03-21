"""Tests for SEP-051: Zorora ECR repository and image push.

These tests verify the script-level requirements from the operator's perspective:

1. scripts/deploy-ecr.sh exists at the project root
2. The script is executable
3. The script passes bash syntax check (bash -n)
4. The script targets the correct ECR repository name (ona-zorora)
5. The script defaults to the af-south-1 region
6. The script creates the ECR repo idempotently (ecr create-repository)
7. The script authenticates Docker against ECR (ecr get-login-password)
8. The script builds a linux/amd64 image (Fargate-compatible)
9. The script pushes the built image (docker push)
10. The script produces both a mutable stage tag and an immutable stage-SHA tag
11. The script uses set -euo pipefail for safety
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "deploy-ecr.sh"


# ---------------------------------------------------------------------------
# Criterion 1: File existence
# ---------------------------------------------------------------------------

class TestScriptExists:
    """The deploy script must exist at the expected location."""

    def test_deploy_ecr_script_exists(self):
        """scripts/deploy-ecr.sh must exist at the project root."""
        assert SCRIPT_PATH.exists(), (
            f"scripts/deploy-ecr.sh not found at {SCRIPT_PATH}. "
            "Create the script as part of SEP-051."
        )

    def test_deploy_ecr_script_is_a_regular_file(self):
        """scripts/deploy-ecr.sh must be a regular file, not a directory or symlink."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")
        assert SCRIPT_PATH.is_file(), (
            f"{SCRIPT_PATH} exists but is not a regular file"
        )


# ---------------------------------------------------------------------------
# Criterion 2: Executable permission
# ---------------------------------------------------------------------------

class TestScriptPermissions:
    """The script must have the executable bit set so it can be run directly."""

    def test_script_is_executable_by_owner(self):
        """scripts/deploy-ecr.sh must have the owner +x permission bit set."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        mode = SCRIPT_PATH.stat().st_mode
        owner_exec = bool(mode & stat.S_IXUSR)
        assert owner_exec, (
            f"scripts/deploy-ecr.sh is not executable (mode: {oct(mode)}). "
            "Run: chmod +x scripts/deploy-ecr.sh"
        )

    def test_script_is_executable_by_group_or_others(self):
        """scripts/deploy-ecr.sh should be executable by group or others for
        CI runners that may not own the file."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        mode = SCRIPT_PATH.stat().st_mode
        group_or_other_exec = bool(mode & (stat.S_IXGRP | stat.S_IXOTH))
        assert group_or_other_exec, (
            f"scripts/deploy-ecr.sh is not executable by group/others (mode: {oct(mode)}). "
            "Run: chmod a+x scripts/deploy-ecr.sh"
        )


# ---------------------------------------------------------------------------
# Criterion 3: Bash syntax validity
# ---------------------------------------------------------------------------

class TestBashSyntax:
    """The script must be valid bash — no syntax errors."""

    def test_script_passes_bash_syntax_check(self):
        """bash -n scripts/deploy-ecr.sh must exit 0 (no syntax errors)."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"scripts/deploy-ecr.sh has bash syntax errors:\n{result.stderr}"
        )

    def test_script_has_bash_shebang(self):
        """The script must start with a bash shebang line."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        first_line = SCRIPT_PATH.read_text().splitlines()[0]
        assert first_line.startswith("#!/"), (
            f"Script must start with a shebang line, got: {first_line!r}"
        )
        assert "bash" in first_line, (
            f"Script shebang must reference bash, got: {first_line!r}"
        )


# ---------------------------------------------------------------------------
# Criterion 4: ECR repository name
# ---------------------------------------------------------------------------

class TestEcrRepoName:
    """The script must target the ona-zorora ECR repository."""

    def test_script_contains_ecr_repo_name_ona_zorora(self):
        """The script must reference 'ona-zorora' as the ECR repository name."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "ona-zorora" in content, (
            "scripts/deploy-ecr.sh must reference 'ona-zorora' as the ECR "
            "repository name. This is the canonical name per SEP-051."
        )

    def test_ecr_repo_name_is_assigned_to_variable(self):
        """The ECR repo name should be assigned to a shell variable
        (not only hardcoded inline) so it is easy to change."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        # Pattern: REPO_NAME=... or ECR_REPO=... or similar assignment
        import re
        repo_var_pattern = re.compile(
            r'(?:REPO|ECR_REPO|REPO_NAME|APP_NAME|IMAGE_NAME)\s*=\s*["\']?ona-zorora["\']?',
            re.IGNORECASE,
        )
        has_var = bool(repo_var_pattern.search(content))
        assert has_var, (
            "scripts/deploy-ecr.sh should assign 'ona-zorora' to a named "
            "variable (e.g., REPO_NAME=\"ona-zorora\") for maintainability. "
            f"Script content (first 800 chars):\n{content[:800]}"
        )


# ---------------------------------------------------------------------------
# Criterion 5: Default AWS region af-south-1
# ---------------------------------------------------------------------------

class TestAwsRegion:
    """The script must default to the af-south-1 region where the platform is hosted."""

    def test_script_defaults_to_af_south_1(self):
        """The script must set or use AWS_DEFAULT_REGION=af-south-1 (or --region af-south-1)."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "af-south-1" in content, (
            "scripts/deploy-ecr.sh must default to af-south-1 region. "
            "Specify via AWS_DEFAULT_REGION=af-south-1, --region af-south-1, "
            "or a REGION variable defaulting to af-south-1."
        )

    def test_region_is_configurable_via_variable(self):
        """The region should be stored in a variable (not only hardcoded in every
        aws CLI call) so it can be overridden from the environment."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        import re
        # Accept: REGION=af-south-1, AWS_DEFAULT_REGION=af-south-1, AWS_REGION=af-south-1
        region_var = re.compile(
            r'(?:REGION|AWS_DEFAULT_REGION|AWS_REGION)\s*[=:].*af-south-1',
            re.IGNORECASE,
        )
        has_region_var = bool(region_var.search(content))
        assert has_region_var, (
            "scripts/deploy-ecr.sh should assign af-south-1 to a REGION or "
            "AWS_DEFAULT_REGION variable rather than inlining it in every command."
        )


# ---------------------------------------------------------------------------
# Criterion 6: ECR repository creation (idempotent)
# ---------------------------------------------------------------------------

class TestEcrRepoCreation:
    """The script must create the ECR repository if it does not exist."""

    def test_script_uses_ecr_create_repository(self):
        """The script must call 'aws ecr create-repository' to create the repo."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "ecr create-repository" in content, (
            "scripts/deploy-ecr.sh must call 'aws ecr create-repository' "
            "to create the ona-zorora ECR repository."
        )

    def test_script_handles_existing_repo_idempotently(self):
        """The script must not fail if the ECR repo already exists.
        Idempotency is achieved by ignoring the RepositoryAlreadyExistsException
        error or by using --query to check existence first."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        # Common patterns for idempotent ECR repo creation:
        # 1. || true after create-repository
        # 2. aws ecr describe-repositories check before creation
        # 3. 2>/dev/null or 2>&1 with error suppression
        # 4. RepositoryAlreadyExistsException handling
        idempotency_patterns = [
            "|| true",
            "2>/dev/null",
            "RepositoryAlreadyExistsException",
            "describe-repositories",
            "|| :",
            "|| echo",
            "already",
        ]
        has_idempotency = any(pat in content for pat in idempotency_patterns)
        assert has_idempotency, (
            "scripts/deploy-ecr.sh must handle the case where the ECR repo "
            "already exists (idempotent creation). Use '|| true' or check "
            "with describe-repositories first.\n"
            f"Script does not contain any of: {idempotency_patterns}"
        )


# ---------------------------------------------------------------------------
# Criterion 7: Docker authentication via ECR
# ---------------------------------------------------------------------------

class TestDockerAuthentication:
    """The script must authenticate Docker against ECR before pushing."""

    def test_script_uses_ecr_get_login_password(self):
        """The script must call 'aws ecr get-login-password' for Docker auth."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "ecr get-login-password" in content, (
            "scripts/deploy-ecr.sh must call 'aws ecr get-login-password' "
            "to authenticate Docker against the ECR registry."
        )

    def test_script_pipes_login_to_docker_login(self):
        """The login password must be piped to 'docker login' — the standard
        ECR authentication pattern."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "docker login" in content, (
            "scripts/deploy-ecr.sh must call 'docker login' to complete "
            "Docker authentication against ECR. The standard pattern is:\n"
            "  aws ecr get-login-password ... | docker login --username AWS "
            "--password-stdin <registry>"
        )


# ---------------------------------------------------------------------------
# Criterion 8: linux/amd64 platform build
# ---------------------------------------------------------------------------

class TestDockerBuild:
    """The script must build a linux/amd64 image for Fargate compatibility."""

    def test_script_uses_docker_build(self):
        """The script must call 'docker build' to build the image."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "docker build" in content, (
            "scripts/deploy-ecr.sh must call 'docker build' to build the image."
        )

    def test_script_specifies_linux_amd64_platform(self):
        """The build must use --platform linux/amd64 for Fargate (x86_64) compatibility."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "linux/amd64" in content, (
            "scripts/deploy-ecr.sh must pass --platform linux/amd64 to docker build. "
            "Fargate tasks run on x86_64; building on an ARM Mac without specifying "
            "the platform produces ARM images that crash on Fargate."
        )

    def test_script_passes_platform_flag_to_build(self):
        """The --platform flag must be passed to docker build (not just defined
        as a variable without being used)."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        import re
        # Match: docker build ... --platform linux/amd64 ...
        # or:    docker build ... --platform=linux/amd64 ...
        build_platform = re.compile(
            r'docker\s+build.*--platform[=\s]+linux/amd64',
            re.DOTALL,
        )
        has_build_platform = bool(build_platform.search(content))
        assert has_build_platform, (
            "The --platform linux/amd64 flag must appear in the docker build "
            "command, not just defined as a variable elsewhere in the script."
        )


# ---------------------------------------------------------------------------
# Criterion 9: Docker push
# ---------------------------------------------------------------------------

class TestDockerPush:
    """The script must push the built image to ECR."""

    def test_script_uses_docker_push(self):
        """The script must call 'docker push' to push the image to ECR."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "docker push" in content, (
            "scripts/deploy-ecr.sh must call 'docker push' to upload the "
            "built image to the ECR registry."
        )

    def test_script_pushes_to_ecr_registry_url(self):
        """The docker push command must target an ECR registry URL (*.amazonaws.com)."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        # ECR registry URLs match: <account>.dkr.ecr.<region>.amazonaws.com
        # or a variable that resolves to such a URL
        has_ecr_reference = (
            "amazonaws.com" in content
            or "ECR_REGISTRY" in content
            or "REGISTRY" in content
            or "dkr.ecr" in content
        )
        assert has_ecr_reference, (
            "scripts/deploy-ecr.sh must push to an ECR registry URL "
            "(<account>.dkr.ecr.<region>.amazonaws.com). "
            "The registry URL or a variable for it must appear in the script."
        )


# ---------------------------------------------------------------------------
# Criterion 10: Mutable + immutable tags
# ---------------------------------------------------------------------------

class TestImageTags:
    """The script must push both a mutable (stage) tag and an immutable
    (stage-SHA) tag so rollbacks are easy and deploys are traceable."""

    def test_script_produces_mutable_stage_tag(self):
        """The script must tag the image with the bare stage name (mutable).
        This allows 'docker pull <repo>:prod' to always get the current version."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        # Must reference $STAGE or ${STAGE} as a tag
        import re
        stage_tag = re.compile(r'\$\{?STAGE\}?')
        assert stage_tag.search(content), (
            "scripts/deploy-ecr.sh must use the $STAGE variable as a Docker "
            "tag (mutable tag, e.g., ':prod' or ':staging')."
        )

    def test_script_produces_immutable_sha_tag(self):
        """The script must tag the image with stage-SHA (immutable).
        This enables exact-version deploys and safe rollbacks."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        # Must reference both $STAGE and a git SHA variable
        import re
        sha_var = re.compile(r'\$\{?GIT_SHA\}?|\$\{?COMMIT\}?|\$\{?SHA\}?|\$\{?COMMIT_SHA\}?')
        has_sha = bool(sha_var.search(content))
        assert has_sha, (
            "scripts/deploy-ecr.sh must tag the image with a git SHA "
            "(e.g., $GIT_SHA or $COMMIT_SHA) to produce an immutable tag "
            "like ':prod-abc1234' for safe rollbacks."
        )

    def test_script_pushes_both_tags(self):
        """The script must call 'docker push' at least twice — once for the
        mutable stage tag and once for the immutable stage-SHA tag."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        push_count = content.count("docker push")
        assert push_count >= 2, (
            f"scripts/deploy-ecr.sh must call 'docker push' at least twice "
            f"(once per tag: mutable ':$STAGE' and immutable ':$STAGE-$GIT_SHA'). "
            f"Found {push_count} 'docker push' invocation(s)."
        )

    def test_script_tags_image_with_stage_sha_combination(self):
        """The immutable tag must combine stage and SHA (e.g., prod-abc1234),
        not just use the SHA alone."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        import re
        # Look for a tag pattern like ${STAGE}-${GIT_SHA} or $STAGE-$GIT_SHA
        combined_tag = re.compile(
            r'\$\{?STAGE\}?-\$\{?(?:GIT_SHA|SHA|COMMIT|COMMIT_SHA)\}?'
            r'|\$\{?(?:GIT_SHA|SHA|COMMIT|COMMIT_SHA)\}?-\$\{?STAGE\}?',
        )
        has_combined = bool(combined_tag.search(content))
        assert has_combined, (
            "scripts/deploy-ecr.sh must produce a combined tag like "
            "'${STAGE}-${GIT_SHA}' (e.g., 'prod-abc1234'). "
            "This is the immutable tag per SEP-051 acceptance criteria."
        )

    def test_git_sha_is_derived_from_git_command(self):
        """The GIT_SHA variable must be derived from git (e.g., git rev-parse)
        so the tag reflects the actual commit being deployed."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        import re
        git_rev = re.compile(r'git\s+rev-parse|git\s+log.*format|git\s+show.*format')
        has_git_rev = bool(git_rev.search(content))
        assert has_git_rev, (
            "scripts/deploy-ecr.sh must derive the git SHA via 'git rev-parse' "
            "or similar command, not hardcode it."
        )


# ---------------------------------------------------------------------------
# Criterion 11: Shell safety options
# ---------------------------------------------------------------------------

class TestShellSafety:
    """The script must use safe shell options to prevent silent failures."""

    def test_script_uses_set_euo_pipefail(self):
        """The script must use 'set -euo pipefail' to fail fast on any error."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        assert "set -euo pipefail" in content, (
            "scripts/deploy-ecr.sh must use 'set -euo pipefail' at the top "
            "so any failed command, unset variable, or pipeline error aborts "
            "the script immediately. This prevents partial deploys."
        )

    def test_set_pipefail_appears_near_top_of_script(self):
        """'set -euo pipefail' must appear early in the script (before any
        substantive commands) so it covers the full execution."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        lines = SCRIPT_PATH.read_text().splitlines()
        # Find the line number of set -euo pipefail
        pipefail_line = None
        for i, line in enumerate(lines, start=1):
            if "set -euo pipefail" in line:
                pipefail_line = i
                break

        assert pipefail_line is not None, (
            "scripts/deploy-ecr.sh must contain 'set -euo pipefail'"
        )
        # Should appear within the first 15 lines (after shebang + comments)
        assert pipefail_line <= 15, (
            f"'set -euo pipefail' must appear near the top of the script "
            f"(within first 15 lines), but found at line {pipefail_line}. "
            "Move it immediately after the shebang and initial comments."
        )


# ---------------------------------------------------------------------------
# Integration: Script structure completeness
# ---------------------------------------------------------------------------

class TestScriptStructure:
    """High-level checks that all required phases are present in the script."""

    def test_script_has_all_required_aws_ecr_calls(self):
        """The script must contain both ECR operations: create-repository and
        get-login-password."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        required_aws_calls = [
            "ecr create-repository",
            "ecr get-login-password",
        ]
        for call in required_aws_calls:
            assert call in content, (
                f"scripts/deploy-ecr.sh must contain 'aws {call}'. "
                f"Missing from script."
            )

    def test_script_has_all_required_docker_calls(self):
        """The script must contain: docker login, docker build, docker tag
        (or inline tagging), and docker push."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        required_docker_calls = [
            "docker login",
            "docker build",
            "docker push",
        ]
        for call in required_docker_calls:
            assert call in content, (
                f"scripts/deploy-ecr.sh must contain '{call}'. "
                f"Missing from script."
            )

    def test_script_references_dockerfile_at_project_root(self):
        """The docker build command should build from the project root (where
        the Dockerfile lives), not from a subdirectory."""
        if not SCRIPT_PATH.exists():
            pytest.skip("scripts/deploy-ecr.sh does not exist yet")

        content = SCRIPT_PATH.read_text()
        # The build context should reference '.' (current dir / project root)
        # or an explicit path. We check that a Dockerfile reference or '.' appears.
        import re
        build_context = re.compile(
            r'docker\s+build\b.*\s+\.',
            re.DOTALL,
        )
        has_root_context = bool(build_context.search(content))
        assert has_root_context, (
            "scripts/deploy-ecr.sh docker build command must use the project "
            "root ('.') as the build context so it finds the Dockerfile."
        )
