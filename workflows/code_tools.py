"""Code development tools for file operations and validation."""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


def write_file(path: str, content: str, working_directory: str) -> str:
    """
    Write content to a new file.

    Args:
        path: Relative path from working directory
        content: File content to write
        working_directory: Base directory (must be within this)

    Returns:
        Success message or error
    """
    try:
        # Ensure path is within working directory
        full_path = Path(working_directory) / path
        full_path = full_path.resolve()

        if not str(full_path).startswith(str(Path(working_directory).resolve())):
            return f"Error: Path {path} is outside working directory"

        # Check if file already exists
        if full_path.exists():
            return f"Error: File {path} already exists. Use edit_file to modify it."

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        full_path.write_text(content, encoding='utf-8')

        line_count = len(content.splitlines())
        logger.info(f"Created {path} ({line_count} lines)")
        return f"✓ Created {path} ({line_count} lines)"

    except Exception as e:
        logger.error(f"Error writing {path}: {e}")
        return f"Error writing {path}: {e}"


def edit_file(path: str, old_content: str, new_content: str, working_directory: str) -> str:
    """
    Edit an existing file by replacing old_content with new_content.

    Args:
        path: Relative path from working directory
        old_content: Content to replace (must match exactly)
        new_content: Replacement content
        working_directory: Base directory

    Returns:
        Success message or error
    """
    try:
        # Ensure path is within working directory
        full_path = Path(working_directory) / path
        full_path = full_path.resolve()

        if not str(full_path).startswith(str(Path(working_directory).resolve())):
            return f"Error: Path {path} is outside working directory"

        # Check if file exists
        if not full_path.exists():
            return f"Error: File {path} does not exist. Use write_file to create it."

        # Read current content
        current_content = full_path.read_text(encoding='utf-8')

        # Check if old_content exists in file
        if old_content not in current_content:
            return f"Error: old_content not found in {path}. File may have changed."

        # Replace content
        updated_content = current_content.replace(old_content, new_content, 1)

        # Write back
        full_path.write_text(updated_content, encoding='utf-8')

        logger.info(f"Modified {path}")
        return f"✓ Modified {path}"

    except Exception as e:
        logger.error(f"Error editing {path}: {e}")
        return f"Error editing {path}: {e}"


def detect_project_type(directory: str) -> Dict[str, any]:
    """
    Detect project type and configuration.

    Args:
        directory: Directory to analyze

    Returns:
        Dict with project metadata
    """
    dir_path = Path(directory)
    result = {
        "type": "unknown",
        "language": None,
        "framework": None,
        "package_manager": None,
        "linters": [],
        "config_files": []
    }

    # Check for Node.js
    if (dir_path / "package.json").exists():
        result["type"] = "nodejs"
        result["language"] = "javascript"
        result["package_manager"] = "npm"
        result["config_files"].append("package.json")

        # Check for framework indicators
        try:
            import json
            pkg = json.loads((dir_path / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            if "express" in deps:
                result["framework"] = "express"
            elif "next" in deps:
                result["framework"] = "next.js"
            elif "react" in deps:
                result["framework"] = "react"
            elif "vue" in deps:
                result["framework"] = "vue"

            # Check for linters
            if "eslint" in deps:
                result["linters"].append("eslint")
            if "prettier" in deps:
                result["linters"].append("prettier")
        except Exception as e:
            logger.warning(f"Error parsing package.json: {e}")

    # Check for Python
    elif (dir_path / "requirements.txt").exists() or (dir_path / "pyproject.toml").exists():
        result["type"] = "python"
        result["language"] = "python"

        if (dir_path / "requirements.txt").exists():
            result["config_files"].append("requirements.txt")
            result["package_manager"] = "pip"

        if (dir_path / "pyproject.toml").exists():
            result["config_files"].append("pyproject.toml")
            result["package_manager"] = "poetry"

        # Check for linters
        if (dir_path / ".ruff.toml").exists() or (dir_path / "ruff.toml").exists():
            result["linters"].append("ruff")
        if (dir_path / ".pylintrc").exists():
            result["linters"].append("pylint")

    # Check for Go
    elif (dir_path / "go.mod").exists():
        result["type"] = "go"
        result["language"] = "go"
        result["package_manager"] = "go"
        result["config_files"].append("go.mod")
        result["linters"] = ["gofmt", "golint"]

    # Check for Rust
    elif (dir_path / "Cargo.toml").exists():
        result["type"] = "rust"
        result["language"] = "rust"
        result["package_manager"] = "cargo"
        result["config_files"].append("Cargo.toml")
        result["linters"] = ["rustfmt", "clippy"]

    return result


def lint_file(path: str, working_directory: str, linter: Optional[str] = None) -> Dict[str, any]:
    """
    Lint a file using appropriate linter.

    Args:
        path: Relative path from working directory
        working_directory: Base directory
        linter: Optional specific linter to use

    Returns:
        Dict with lint results
    """
    try:
        full_path = Path(working_directory) / path

        if not full_path.exists():
            return {"success": False, "error": f"File {path} does not exist"}

        # Detect project type if linter not specified
        if not linter:
            project_info = detect_project_type(working_directory)
            available_linters = project_info.get("linters", [])

            # Choose linter based on file extension
            ext = full_path.suffix
            if ext in [".js", ".jsx", ".ts", ".tsx"]:
                linter = "eslint" if "eslint" in available_linters else None
            elif ext == ".py":
                linter = "ruff" if "ruff" in available_linters else "pylint" if "pylint" in available_linters else None
            elif ext == ".go":
                linter = "gofmt"
            elif ext == ".rs":
                linter = "rustfmt"

        if not linter:
            return {"success": True, "message": "No linter configured", "skipped": True}

        # Run linter
        result = {"success": False, "linter": linter, "output": "", "auto_fixed": False}

        if linter == "eslint":
            # Try to auto-fix
            proc = subprocess.run(
                ["npx", "eslint", "--fix", str(full_path)],
                cwd=working_directory,
                capture_output=True,
                text=True
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0
            if result["success"]:
                result["auto_fixed"] = True

        elif linter == "prettier":
            proc = subprocess.run(
                ["npx", "prettier", "--write", str(full_path)],
                cwd=working_directory,
                capture_output=True,
                text=True
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0
            result["auto_fixed"] = True

        elif linter == "ruff":
            # Try to auto-fix
            proc = subprocess.run(
                ["ruff", "check", "--fix", str(full_path)],
                cwd=working_directory,
                capture_output=True,
                text=True
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0
            if result["success"]:
                result["auto_fixed"] = True

        elif linter == "pylint":
            proc = subprocess.run(
                ["pylint", str(full_path)],
                cwd=working_directory,
                capture_output=True,
                text=True
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0

        elif linter == "gofmt":
            proc = subprocess.run(
                ["gofmt", "-w", str(full_path)],
                cwd=working_directory,
                capture_output=True,
                text=True
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0
            result["auto_fixed"] = True

        elif linter == "rustfmt":
            proc = subprocess.run(
                ["rustfmt", str(full_path)],
                cwd=working_directory,
                capture_output=True,
                text=True
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0
            result["auto_fixed"] = True

        return result

    except FileNotFoundError:
        return {"success": True, "message": f"Linter {linter} not found", "skipped": True}
    except Exception as e:
        logger.error(f"Error linting {path}: {e}")
        return {"success": False, "error": str(e)}


def install_dependencies(working_directory: str, project_type: str) -> Dict[str, any]:
    """
    Install project dependencies based on project type.

    Args:
        working_directory: Project directory
        project_type: Type of project (nodejs, python, etc.)

    Returns:
        Dict with installation results
    """
    try:
        result = {"success": False, "output": "", "command": ""}

        if project_type == "nodejs":
            result["command"] = "npm install"
            proc = subprocess.run(
                ["npm", "install"],
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0

        elif project_type == "python":
            # Try pip install
            result["command"] = "pip install -r requirements.txt"
            if Path(working_directory, "requirements.txt").exists():
                proc = subprocess.run(
                    ["pip", "install", "-r", "requirements.txt"],
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                result["output"] = proc.stdout + proc.stderr
                result["success"] = proc.returncode == 0
            elif Path(working_directory, "pyproject.toml").exists():
                result["command"] = "poetry install"
                proc = subprocess.run(
                    ["poetry", "install"],
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                result["output"] = proc.stdout + proc.stderr
                result["success"] = proc.returncode == 0

        elif project_type == "go":
            result["command"] = "go mod download"
            proc = subprocess.run(
                ["go", "mod", "download"],
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=300
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0

        elif project_type == "rust":
            result["command"] = "cargo build"
            proc = subprocess.run(
                ["cargo", "build"],
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=600  # Rust can take longer
            )
            result["output"] = proc.stdout + proc.stderr
            result["success"] = proc.returncode == 0

        else:
            result["success"] = False
            result["error"] = f"Unknown project type: {project_type}"

        return result

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Installation timeout (5 minutes)"}
    except Exception as e:
        logger.error(f"Error installing dependencies: {e}")
        return {"success": False, "error": str(e)}
