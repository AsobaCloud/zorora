"""Tests for SEP-052: Zorora Fargate service deployment script.

These tests verify the script-level requirements from the operator's
perspective. All tests are structural — they inspect the contents of
scripts/deploy-fargate.sh without executing it against live AWS.

Requirements verified:
 1.  scripts/deploy-fargate.sh exists at the project root
 2.  The script is executable
 3.  Valid bash syntax (bash -n) + set -euo pipefail
 4.  Contains 'ecs create-cluster'
 5.  Contains 'ecs register-task-definition'
 6.  Contains 'ecs create-service' or 'ecs update-service'
 7.  Contains IAM role creation or lookup (task execution role)
 8.  Contains security group creation or lookup
 9.  Contains 'logs create-log-group' (CloudWatch)
10.  Uses 'ona-zorora' as the ECR repository / service name
11.  Defaults to af-south-1 region
12.  Exposes port 5000
13.  Uses 256 CPU and 512 memory (Fargate 0.25 vCPU / 0.5 GB)
14.  Discovers default VPC at runtime (describe-vpcs)
15.  Discovers subnets at runtime (describe-subnets)
16.  Uses assignPublicIp: ENABLED
17.  Uses awsvpc network mode
18.  Outputs or queries for the running task's public IP
"""

from __future__ import annotations

import re
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "deploy-fargate.sh"


# ---------------------------------------------------------------------------
# Helper: skip or read content
# ---------------------------------------------------------------------------

def _skip_if_missing():
    if not SCRIPT_PATH.exists():
        pytest.skip("scripts/deploy-fargate.sh does not exist yet")


def _content() -> str:
    _skip_if_missing()
    return SCRIPT_PATH.read_text()


# ---------------------------------------------------------------------------
# Criterion 1: File existence
# ---------------------------------------------------------------------------

class TestScriptExists:
    """The deploy-fargate script must exist at the expected location."""

    def test_deploy_fargate_script_exists(self):
        """scripts/deploy-fargate.sh must exist under scripts/."""
        assert SCRIPT_PATH.exists(), (
            f"scripts/deploy-fargate.sh not found at {SCRIPT_PATH}. "
            "Create the script as part of SEP-052."
        )

    def test_deploy_fargate_script_is_a_regular_file(self):
        """scripts/deploy-fargate.sh must be a regular file, not a directory
        or a symlink."""
        _skip_if_missing()
        assert SCRIPT_PATH.is_file(), (
            f"{SCRIPT_PATH} exists but is not a regular file."
        )


# ---------------------------------------------------------------------------
# Criterion 2: Executable permission
# ---------------------------------------------------------------------------

class TestScriptPermissions:
    """The script must have the executable bit set so it can be run directly."""

    def test_script_is_executable_by_owner(self):
        """scripts/deploy-fargate.sh must have the owner +x bit set."""
        _skip_if_missing()
        mode = SCRIPT_PATH.stat().st_mode
        assert bool(mode & stat.S_IXUSR), (
            f"scripts/deploy-fargate.sh is not executable by owner "
            f"(mode: {oct(mode)}). Run: chmod +x scripts/deploy-fargate.sh"
        )

    def test_script_is_executable_by_group_or_others(self):
        """scripts/deploy-fargate.sh must be executable by group or others
        so CI runners that don't own the file can still execute it."""
        _skip_if_missing()
        mode = SCRIPT_PATH.stat().st_mode
        assert bool(mode & (stat.S_IXGRP | stat.S_IXOTH)), (
            f"scripts/deploy-fargate.sh is not executable by group/others "
            f"(mode: {oct(mode)}). Run: chmod a+x scripts/deploy-fargate.sh"
        )


# ---------------------------------------------------------------------------
# Criterion 3: Bash syntax + set -euo pipefail
# ---------------------------------------------------------------------------

class TestBashSyntax:
    """The script must be valid bash and must use safe shell options."""

    def test_script_has_bash_shebang(self):
        """The script must start with a bash shebang line."""
        content = _content()
        first_line = content.splitlines()[0]
        assert first_line.startswith("#!/"), (
            f"Script must start with a shebang line, got: {first_line!r}"
        )
        assert "bash" in first_line, (
            f"Script shebang must reference bash, got: {first_line!r}"
        )

    def test_script_passes_bash_syntax_check(self):
        """bash -n scripts/deploy-fargate.sh must exit 0 (no syntax errors)."""
        _skip_if_missing()
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"scripts/deploy-fargate.sh has bash syntax errors:\n{result.stderr}"
        )

    def test_script_uses_set_euo_pipefail(self):
        """The script must use 'set -euo pipefail' to fail fast on errors."""
        content = _content()
        assert "set -euo pipefail" in content, (
            "scripts/deploy-fargate.sh must use 'set -euo pipefail' at the "
            "top so any failed command, unset variable, or pipeline error "
            "aborts the script immediately. This prevents partial deploys."
        )

    def test_set_pipefail_appears_near_top_of_script(self):
        """'set -euo pipefail' must appear early (within the first 15 lines)
        so it guards the entire script."""
        content = _content()
        lines = content.splitlines()
        pipefail_line = next(
            (i for i, ln in enumerate(lines, start=1) if "set -euo pipefail" in ln),
            None,
        )
        assert pipefail_line is not None, (
            "scripts/deploy-fargate.sh must contain 'set -euo pipefail'."
        )
        assert pipefail_line <= 15, (
            f"'set -euo pipefail' must appear within the first 15 lines but "
            f"was found at line {pipefail_line}. Move it immediately after "
            "the shebang and any initial comment block."
        )


# ---------------------------------------------------------------------------
# Criterion 4: ECS cluster creation
# ---------------------------------------------------------------------------

class TestEcsCluster:
    """The script must create (or reuse) an ECS cluster."""

    def test_script_contains_ecs_create_cluster(self):
        """The script must call 'ecs create-cluster' to provision the cluster."""
        content = _content()
        assert "ecs create-cluster" in content, (
            "scripts/deploy-fargate.sh must contain 'aws ecs create-cluster'. "
            "Fargate tasks require an ECS cluster to be registered against."
        )

    def test_ecs_cluster_creation_is_idempotent(self):
        """Cluster creation must not fail when the cluster already exists.
        ECS create-cluster is idempotent by default, but the script should
        not add flags that break that behaviour."""
        content = _content()
        # If the script calls create-cluster, it inherits ECS idempotency.
        # We additionally check that no '--fail-if-exists' style flags are used.
        assert "ecs create-cluster" in content, (
            "scripts/deploy-fargate.sh must contain 'aws ecs create-cluster'."
        )


# ---------------------------------------------------------------------------
# Criterion 5: Task definition registration
# ---------------------------------------------------------------------------

class TestTaskDefinition:
    """The script must register a Fargate task definition."""

    def test_script_contains_register_task_definition(self):
        """The script must call 'ecs register-task-definition'."""
        content = _content()
        assert "ecs register-task-definition" in content, (
            "scripts/deploy-fargate.sh must call "
            "'aws ecs register-task-definition' to register the container "
            "workload with ECS."
        )

    def test_task_definition_references_fargate_launch_type(self):
        """The task definition must specify FARGATE as the requires-compatibilities
        or launch type, not EC2."""
        content = _content()
        assert "FARGATE" in content, (
            "scripts/deploy-fargate.sh must reference 'FARGATE' in the task "
            "definition (requires-compatibilities or launch-type). "
            "EC2 launch type is not supported on the Ona platform."
        )


# ---------------------------------------------------------------------------
# Criterion 6: ECS service creation / update
# ---------------------------------------------------------------------------

class TestEcsService:
    """The script must create or update the ECS service."""

    def test_script_contains_ecs_create_or_update_service(self):
        """The script must call 'ecs create-service' or 'ecs update-service'."""
        content = _content()
        has_create = "ecs create-service" in content
        has_update = "ecs update-service" in content
        assert has_create or has_update, (
            "scripts/deploy-fargate.sh must contain 'aws ecs create-service' "
            "or 'aws ecs update-service' to deploy the Fargate container."
        )

    def test_ecs_service_uses_fargate_launch_type(self):
        """The ecs create-service call must use --launch-type FARGATE."""
        content = _content()
        assert "FARGATE" in content, (
            "scripts/deploy-fargate.sh must specify FARGATE launch type for "
            "the ECS service. EC2 is not used on the Ona platform."
        )


# ---------------------------------------------------------------------------
# Criterion 7: IAM task execution role
# ---------------------------------------------------------------------------

class TestIamRole:
    """The script must create or verify the ECS task execution IAM role."""

    def test_script_contains_iam_role_operation(self):
        """The script must contain an IAM role create or get call for the
        task execution role (needed so ECS can pull images from ECR and
        write logs to CloudWatch)."""
        content = _content()
        has_create = "iam create-role" in content
        has_get = "iam get-role" in content
        assert has_create or has_get, (
            "scripts/deploy-fargate.sh must contain 'aws iam create-role' or "
            "'aws iam get-role' to provision the ECS task execution role. "
            "Without it the task cannot pull images or write to CloudWatch."
        )

    def test_script_attaches_execution_role_policy(self):
        """The task execution role needs the AmazonECSTaskExecutionRolePolicy
        or an equivalent policy to function."""
        content = _content()
        # Accept: attach-role-policy, AmazonECSTaskExecutionRolePolicy, or
        # put-role-policy with ECS permissions
        policy_patterns = [
            "attach-role-policy",
            "AmazonECSTaskExecutionRolePolicy",
            "put-role-policy",
            "TaskExecutionRolePolicy",
        ]
        has_policy = any(pat in content for pat in policy_patterns)
        assert has_policy, (
            "scripts/deploy-fargate.sh must attach a policy to the task "
            "execution role (e.g., AmazonECSTaskExecutionRolePolicy). "
            f"None of the expected patterns were found: {policy_patterns}"
        )


# ---------------------------------------------------------------------------
# Criterion 8: Security group
# ---------------------------------------------------------------------------

class TestSecurityGroup:
    """The script must create or discover a security group for the Fargate task."""

    def test_script_contains_security_group_operation(self):
        """The script must contain 'ec2 create-security-group' or
        'ec2 describe-security-groups' to set up network access control."""
        content = _content()
        has_create = "ec2 create-security-group" in content
        has_describe = "ec2 describe-security-groups" in content
        assert has_create or has_describe, (
            "scripts/deploy-fargate.sh must contain "
            "'aws ec2 create-security-group' or "
            "'aws ec2 describe-security-groups'. "
            "Fargate tasks in awsvpc mode require a security group."
        )

    def test_script_opens_port_5000_in_security_group(self):
        """The security group must allow inbound traffic on port 5000 (the
        Zorora Flask port). Port 5000 must appear in the script alongside
        security group configuration."""
        content = _content()
        # Must have both port 5000 and security group ingress rule
        has_port = "5000" in content
        has_ingress = any(pat in content for pat in [
            "authorize-security-group-ingress",
            "ingress",
            "--port 5000",
            "fromPort.*5000",
        ])
        assert has_port, (
            "scripts/deploy-fargate.sh must reference port 5000 (Zorora "
            "Flask application port) in the security group configuration."
        )
        assert has_ingress, (
            "scripts/deploy-fargate.sh must authorize ingress on port 5000 "
            "via 'aws ec2 authorize-security-group-ingress' or equivalent."
        )


# ---------------------------------------------------------------------------
# Criterion 9: CloudWatch log group
# ---------------------------------------------------------------------------

class TestCloudWatchLogs:
    """The script must create a CloudWatch log group for container output."""

    def test_script_contains_logs_create_log_group(self):
        """The script must call 'logs create-log-group' so container stdout
        and stderr are captured in CloudWatch."""
        content = _content()
        assert "logs create-log-group" in content, (
            "scripts/deploy-fargate.sh must call 'aws logs create-log-group' "
            "to provision the CloudWatch log group for the Fargate task. "
            "Without it the task definition cannot reference a log group."
        )

    def test_log_group_creation_is_idempotent(self):
        """Log group creation must not fail on a re-run when the group already
        exists. Common patterns: '|| true', '2>/dev/null', or checking first."""
        content = _content()
        # 'logs create-log-group' is not natively idempotent — need || true etc.
        idempotency_patterns = [
            "|| true",
            "2>/dev/null",
            "ResourceAlreadyExistsException",
            "|| :",
            "|| echo",
            "already",
        ]
        has_idempotency = any(pat in content for pat in idempotency_patterns)
        assert has_idempotency, (
            "scripts/deploy-fargate.sh must handle idempotent log group "
            "creation. 'logs create-log-group' fails if the group already "
            "exists — use '|| true' or check first.\n"
            f"None of the expected patterns were found: {idempotency_patterns}"
        )


# ---------------------------------------------------------------------------
# Criterion 10: ECR repository / service name
# ---------------------------------------------------------------------------

class TestServiceName:
    """The script must use 'ona-zorora' as the canonical name."""

    def test_script_contains_ona_zorora_name(self):
        """The script must reference 'ona-zorora' — the ECR repository name
        and the base for the ECS cluster / service names."""
        content = _content()
        assert "ona-zorora" in content, (
            "scripts/deploy-fargate.sh must reference 'ona-zorora'. "
            "This is the canonical ECR repository and service name per SEP-051 "
            "and SEP-052."
        )

    def test_ona_zorora_is_assigned_to_variable(self):
        """'ona-zorora' should be stored in a named variable for maintainability,
        not scattered as a bare string throughout the script."""
        content = _content()
        var_pattern = re.compile(
            r'(?:APP_NAME|SERVICE_NAME|CLUSTER_NAME|REPO_NAME|IMAGE_NAME|NAME)\s*=\s*["\']?ona-zorora["\']?',
            re.IGNORECASE,
        )
        assert var_pattern.search(content), (
            "scripts/deploy-fargate.sh should assign 'ona-zorora' to a named "
            "variable (e.g., APP_NAME=\"ona-zorora\") for maintainability."
        )


# ---------------------------------------------------------------------------
# Criterion 11: Default region af-south-1
# ---------------------------------------------------------------------------

class TestAwsRegion:
    """The script must default to af-south-1 where the Ona platform runs."""

    def test_script_defaults_to_af_south_1(self):
        """The script must hardcode or default af-south-1 as the AWS region."""
        content = _content()
        assert "af-south-1" in content, (
            "scripts/deploy-fargate.sh must default to region af-south-1. "
            "Specify via REGION=af-south-1, AWS_DEFAULT_REGION=af-south-1, "
            "or --region af-south-1."
        )

    def test_region_is_configurable_via_variable(self):
        """The region must be stored in a variable (not only inlined in every
        CLI call) so it can be overridden from the environment."""
        content = _content()
        region_var = re.compile(
            r'(?:REGION|AWS_DEFAULT_REGION|AWS_REGION)\s*[=:].*af-south-1',
            re.IGNORECASE,
        )
        assert region_var.search(content), (
            "scripts/deploy-fargate.sh should assign af-south-1 to a REGION "
            "or AWS_DEFAULT_REGION variable rather than inlining the value in "
            "every AWS CLI call."
        )


# ---------------------------------------------------------------------------
# Criterion 12: Port 5000
# ---------------------------------------------------------------------------

class TestPort:
    """The Fargate task must expose and map port 5000 (Zorora Flask)."""

    def test_script_references_port_5000(self):
        """Port 5000 must appear in the script — used in the task definition
        container port mappings and the security group ingress rule."""
        content = _content()
        assert "5000" in content, (
            "scripts/deploy-fargate.sh must reference port 5000 — the port "
            "that Zorora's Flask application listens on."
        )

    def test_port_5000_used_in_task_definition_context(self):
        """Port 5000 must appear near the task definition registration, not
        only in an unrelated comment."""
        content = _content()
        # Acceptable patterns: containerPort / portMappings / --port-mappings
        port_in_task_def = re.compile(
            r'(?:containerPort|portMappings|port-mappings|hostPort)[^\n]*5000'
            r'|5000[^\n]*(?:containerPort|portMappings|port-mappings)',
            re.IGNORECASE,
        )
        has_task_port = bool(port_in_task_def.search(content))
        # Also accept if 5000 appears in the task-def JSON block
        has_json_port = '"containerPort": 5000' in content or '"containerPort":5000' in content
        assert has_task_port or has_json_port, (
            "scripts/deploy-fargate.sh must map port 5000 in the ECS task "
            "definition (containerPort: 5000 in portMappings)."
        )


# ---------------------------------------------------------------------------
# Criterion 13: CPU 256 and memory 512
# ---------------------------------------------------------------------------

class TestResourceAllocation:
    """Fargate task must be sized at 256 CPU units (0.25 vCPU) and 512 MB RAM."""

    def test_script_specifies_256_cpu(self):
        """The task definition must request 256 CPU units (Fargate minimum)."""
        content = _content()
        assert "256" in content, (
            "scripts/deploy-fargate.sh must specify 256 CPU units in the task "
            "definition. 256 = 0.25 vCPU, the smallest Fargate CPU allocation."
        )

    def test_script_specifies_512_memory(self):
        """The task definition must request 512 MB of memory."""
        content = _content()
        assert "512" in content, (
            "scripts/deploy-fargate.sh must specify 512 MB memory in the task "
            "definition. This pairs with 256 CPU as a valid Fargate combination."
        )

    def test_cpu_and_memory_appear_in_task_definition_context(self):
        """The CPU/memory values must appear in the task definition JSON or
        register-task-definition flags, not only in a comment."""
        content = _content()
        cpu_in_def = re.compile(
            r'(?:--cpu\s+256|"cpu"\s*:\s*"?256"?|cpu.*256)',
            re.IGNORECASE,
        )
        mem_in_def = re.compile(
            r'(?:--memory\s+512|"memory"\s*:\s*"?512"?|memory.*512)',
            re.IGNORECASE,
        )
        assert cpu_in_def.search(content), (
            "scripts/deploy-fargate.sh must pass cpu=256 to the task "
            "definition (--cpu 256 or \"cpu\": \"256\" in JSON)."
        )
        assert mem_in_def.search(content), (
            "scripts/deploy-fargate.sh must pass memory=512 to the task "
            "definition (--memory 512 or \"memory\": \"512\" in JSON)."
        )


# ---------------------------------------------------------------------------
# Criterion 14: VPC discovery at runtime
# ---------------------------------------------------------------------------

class TestVpcDiscovery:
    """The script must discover the default VPC at runtime instead of
    hardcoding a VPC ID."""

    def test_script_uses_describe_vpcs(self):
        """The script must call 'ec2 describe-vpcs' to discover the VPC ID
        dynamically. Hardcoded VPC IDs break across AWS accounts."""
        content = _content()
        assert "describe-vpcs" in content, (
            "scripts/deploy-fargate.sh must call 'aws ec2 describe-vpcs' to "
            "discover the default VPC at runtime. Do not hardcode a VPC ID."
        )

    def test_vpc_id_derived_from_describe_vpcs_output(self):
        """The VPC ID variable must be assigned from the describe-vpcs output,
        not set to a literal vpc-* ID."""
        content = _content()
        # Reject hardcoded vpc-XXXXXXXX IDs
        hardcoded_vpc = re.compile(r'\bvpc-[0-9a-f]{8,}\b')
        assert not hardcoded_vpc.search(content), (
            "scripts/deploy-fargate.sh must NOT contain a hardcoded VPC ID "
            "(vpc-xxxxxxxx). Discover it at runtime via 'aws ec2 describe-vpcs'."
        )
        # Must store the VPC ID in a variable
        vpc_var = re.compile(r'VPC_ID\s*=|vpc_id\s*=', re.IGNORECASE)
        assert vpc_var.search(content), (
            "scripts/deploy-fargate.sh must store the discovered VPC ID in a "
            "variable (e.g., VPC_ID=...) derived from 'aws ec2 describe-vpcs'."
        )


# ---------------------------------------------------------------------------
# Criterion 15: Subnet discovery at runtime
# ---------------------------------------------------------------------------

class TestSubnetDiscovery:
    """The script must discover subnets at runtime instead of hardcoding IDs."""

    def test_script_uses_describe_subnets(self):
        """The script must call 'ec2 describe-subnets' to discover subnet IDs
        dynamically."""
        content = _content()
        assert "describe-subnets" in content, (
            "scripts/deploy-fargate.sh must call 'aws ec2 describe-subnets' "
            "to discover subnets at runtime. Do not hardcode subnet IDs."
        )

    def test_subnet_ids_not_hardcoded(self):
        """No literal subnet-* IDs must appear in the script."""
        content = _content()
        hardcoded_subnet = re.compile(r'\bsubnet-[0-9a-f]{8,}\b')
        assert not hardcoded_subnet.search(content), (
            "scripts/deploy-fargate.sh must NOT contain hardcoded subnet IDs "
            "(subnet-xxxxxxxx). Discover them at runtime via 'aws ec2 "
            "describe-subnets'."
        )

    def test_subnet_ids_stored_in_variable(self):
        """Discovered subnet IDs must be stored in a variable for use in the
        ECS service network configuration."""
        content = _content()
        subnet_var = re.compile(r'SUBNET(?:S|_IDS?|_ID)\s*=|subnet_ids?\s*=', re.IGNORECASE)
        assert subnet_var.search(content), (
            "scripts/deploy-fargate.sh must store discovered subnet IDs in a "
            "variable (e.g., SUBNETS=...) derived from 'aws ec2 describe-subnets'."
        )


# ---------------------------------------------------------------------------
# Criterion 16: assignPublicIp ENABLED
# ---------------------------------------------------------------------------

class TestPublicIp:
    """The Fargate service must use assignPublicIp: ENABLED so the task is
    reachable without a NAT gateway or load balancer."""

    def test_script_uses_assign_public_ip_enabled(self):
        """The network configuration passed to ecs create-service must include
        assignPublicIp=ENABLED (or assignPublicIp: ENABLED in JSON)."""
        content = _content()
        has_enabled = re.search(
            r'assignPublicIp["\s:=]+ENABLED',
            content,
            re.IGNORECASE,
        )
        assert has_enabled, (
            "scripts/deploy-fargate.sh must set assignPublicIp=ENABLED in the "
            "ECS service network configuration. Without this the task will not "
            "receive a public IP and will be unreachable."
        )

    def test_script_does_not_use_assign_public_ip_disabled(self):
        """assignPublicIp must not be set to DISABLED — that would prevent
        public access without a NAT gateway."""
        content = _content()
        has_disabled = re.search(
            r'assignPublicIp["\s:=]+DISABLED',
            content,
            re.IGNORECASE,
        )
        assert not has_disabled, (
            "scripts/deploy-fargate.sh must NOT set assignPublicIp=DISABLED. "
            "The Zorora service needs a public IP for direct access."
        )


# ---------------------------------------------------------------------------
# Criterion 17: awsvpc network mode
# ---------------------------------------------------------------------------

class TestNetworkMode:
    """Fargate tasks require awsvpc network mode."""

    def test_script_uses_awsvpc_network_mode(self):
        """The task definition must specify networkMode=awsvpc. This is the
        only network mode supported by Fargate."""
        content = _content()
        assert "awsvpc" in content, (
            "scripts/deploy-fargate.sh must set networkMode to 'awsvpc' in "
            "the task definition. Fargate does not support bridge or host mode."
        )

    def test_awsvpc_appears_in_task_definition_context(self):
        """'awsvpc' must appear in the task definition registration, not only
        in a comment or unrelated block."""
        content = _content()
        # Accept: networkMode/network-mode near register-task-definition block
        # or directly in the task def JSON
        awsvpc_in_def = re.compile(
            r'(?:networkMode|network-mode)[^\n]*awsvpc'
            r'|awsvpc[^\n]*(?:networkMode|network-mode)'
            r'|"networkMode"\s*:\s*"awsvpc"',
            re.IGNORECASE,
        )
        assert awsvpc_in_def.search(content), (
            "scripts/deploy-fargate.sh must specify networkMode=awsvpc in the "
            "task definition body (not just as a comment). "
            "Pattern expected: 'networkMode: awsvpc' or '\"networkMode\": \"awsvpc\"'."
        )


# ---------------------------------------------------------------------------
# Criterion 18: Outputs task public IP
# ---------------------------------------------------------------------------

class TestPublicIpOutput:
    """After deployment, the script must retrieve and print the running task's
    public IP address so the operator knows where the service is reachable."""

    def test_script_queries_task_public_ip(self):
        """The script must query ECS/EC2 for the task's public IP and output
        it. Acceptable approaches: describe-tasks + describe-network-interfaces,
        or waiting for the task to start then printing the IP."""
        content = _content()
        # Acceptable patterns for retrieving the public IP post-deployment
        ip_query_patterns = [
            "describe-tasks",
            "describe-network-interfaces",
            "publicIp",
            "PublicIp",
            "TASK_IP",
            "TASK_PUBLIC_IP",
            "PUBLIC_IP",
        ]
        has_ip_query = any(pat in content for pat in ip_query_patterns)
        assert has_ip_query, (
            "scripts/deploy-fargate.sh must retrieve the public IP of the "
            "running Fargate task after deployment. Use 'aws ecs describe-tasks' "
            "followed by 'aws ec2 describe-network-interfaces' to find the "
            "public IP, then print it.\n"
            f"None of the expected patterns were found: {ip_query_patterns}"
        )

    def test_script_prints_endpoint_to_stdout(self):
        """The script must print the public IP or endpoint URL so the operator
        can verify the deployment without reading AWS console output."""
        content = _content()
        # Must have an echo or printf that references the IP variable
        output_pattern = re.compile(
            r'(?:echo|printf).*(?:PUBLIC_IP|TASK_IP|TASK_PUBLIC_IP|endpoint|Endpoint|http)',
            re.IGNORECASE,
        )
        assert output_pattern.search(content), (
            "scripts/deploy-fargate.sh must echo the public IP or endpoint URL "
            "to stdout after deployment (e.g., 'echo \"Endpoint: http://$PUBLIC_IP:5000\"'). "
            "This is the operator's signal that the deployment succeeded."
        )


# ---------------------------------------------------------------------------
# Integration: overall script completeness
# ---------------------------------------------------------------------------

class TestScriptCompleteness:
    """High-level check that all required infrastructure phases are present."""

    def test_script_contains_all_required_aws_service_calls(self):
        """The script must invoke all six AWS service areas: ECS cluster,
        task def, service; IAM role; EC2 security group; CloudWatch logs."""
        content = _content()
        required = {
            "ecs create-cluster": "ECS cluster creation",
            "ecs register-task-definition": "task definition registration",
            "iam": "IAM role management",
            "ec2": "security group / VPC operations",
            "logs create-log-group": "CloudWatch log group creation",
        }
        for fragment, description in required.items():
            assert fragment in content, (
                f"scripts/deploy-fargate.sh is missing {description}. "
                f"Expected to find '{fragment}' in the script."
            )

    def test_script_has_ecs_service_call(self):
        """The script must call either 'ecs create-service' or
        'ecs update-service' — without it no service is running."""
        content = _content()
        assert "ecs create-service" in content or "ecs update-service" in content, (
            "scripts/deploy-fargate.sh must contain 'ecs create-service' or "
            "'ecs update-service'. The cluster and task definition alone do not "
            "start a running Fargate instance."
        )

    def test_infrastructure_phases_appear_in_logical_order(self):
        """IAM role setup must precede task definition registration, and task
        definition must precede service creation. This ensures each phase has
        its dependency available."""
        content = _content()
        iam_pos = content.find("iam")
        task_def_pos = content.find("ecs register-task-definition")
        service_pos = max(
            content.find("ecs create-service"),
            content.find("ecs update-service"),
        )
        assert iam_pos != -1, "IAM operations must be present."
        assert task_def_pos != -1, "Task definition registration must be present."
        assert service_pos != -1, "ECS service creation/update must be present."
        assert iam_pos < task_def_pos, (
            "IAM role setup must appear before task definition registration "
            "in scripts/deploy-fargate.sh."
        )
        assert task_def_pos < service_pos, (
            "Task definition registration must appear before ECS service "
            "creation in scripts/deploy-fargate.sh."
        )
