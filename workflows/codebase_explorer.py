"""Codebase exploration for understanding project structure and context."""

import os
import logging
from pathlib import Path
from typing import Dict, List, Set
import json

from workflows.code_tools import detect_project_type

logger = logging.getLogger(__name__)

# Directories to ignore
IGNORE_DIRS = {
    'node_modules', '.git', '__pycache__', 'venv', 'env', '.venv',
    'dist', 'build', '.next', '.nuxt', 'target', 'vendor',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', 'coverage',
    '.idea', '.vscode', '.vs', 'bin', 'obj'
}

# Binary/media files to skip
SKIP_EXTENSIONS = {
    '.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe',
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
    '.mp4', '.mov', '.avi', '.mp3', '.wav',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.lock', '.min.js', '.min.css'
}

# Important files to always analyze
IMPORTANT_FILES = {
    'package.json', 'package-lock.json',
    'requirements.txt', 'pyproject.toml', 'setup.py', 'Pipfile',
    'go.mod', 'go.sum',
    'Cargo.toml', 'Cargo.lock',
    'README.md', 'README.txt', 'README',
    '.env.example', '.env.template',
    'Makefile', 'Dockerfile', 'docker-compose.yml',
    'tsconfig.json', '.eslintrc.js', '.eslintrc.json',
    '.prettierrc', 'ruff.toml', '.pylintrc'
}


class CodebaseExplorer:
    """Explores and analyzes codebase structure."""

    def __init__(self, llm_client=None):
        """
        Initialize explorer.

        Args:
            llm_client: Optional LLM client for enhanced analysis
        """
        self.llm_client = llm_client

    def explore(self, directory: str, ui=None) -> Dict:
        """
        Explore codebase and generate structured summary.

        Args:
            directory: Directory to explore
            ui: Optional UI for progress feedback

        Returns:
            Dict with codebase summary
        """
        logger.info(f"Starting codebase exploration: {directory}")

        if ui:
            ui.console.print("\n[cyan]Phase 1: Codebase Exploration[/cyan]")
            ui.console.print(f"[dim]🔍 Exploring codebase in {directory}...[/dim]")

        # Check if directory exists
        dir_path = Path(directory)
        if not dir_path.exists():
            return {"error": f"Directory {directory} does not exist"}

        # Detect project type
        project_info = detect_project_type(directory)
        if ui:
            if project_info["type"] != "unknown":
                ui.console.print(f"[green]  ✓ Detected {project_info['type']} project[/green]")
            else:
                ui.console.print("[yellow]  ⚠ Could not detect project type[/yellow]")

        # Walk directory tree
        file_structure = self._walk_directory(directory)

        if ui:
            file_count = len(file_structure["all_files"])
            dir_count = len(file_structure["directories"])
            ui.console.print(f"[green]  ✓ Analyzed {file_count} files across {dir_count} directories[/green]")

            if file_count > 1000:
                ui.console.print(f"[yellow]  ⚠ Large codebase ({file_count} files) - exploration may take a moment[/yellow]")

        # Analyze important files
        important_file_contents = self._read_important_files(directory, file_structure["important_files"])
        if ui:
            ui.console.print(f"[green]  ✓ Read {len(important_file_contents)} configuration files[/green]")

        # Analyze file types and patterns
        patterns = self._analyze_patterns(file_structure, project_info)

        # Build summary
        summary = {
            "directory": directory,
            "project_type": project_info["type"],
            "language": project_info["language"],
            "framework": project_info["framework"],
            "package_manager": project_info["package_manager"],
            "linters": project_info["linters"],
            "file_count": len(file_structure["all_files"]),
            "directory_count": len(file_structure["directories"]),
            "directory_structure": file_structure["tree"],
            "important_files": important_file_contents,
            "file_types": patterns["file_types"],
            "source_directories": patterns["source_dirs"],
            "entry_points": patterns["entry_points"],
            "has_tests": patterns["has_tests"],
            "dependencies": self._extract_dependencies(important_file_contents, project_info["type"])
        }

        if ui:
            ui.console.print("[green]  ✓ Exploration complete[/green]")

        logger.info(f"Exploration complete: {file_count} files, {dir_count} directories")
        return summary

    def _walk_directory(self, directory: str) -> Dict:
        """
        Walk directory tree and collect file information.

        Returns:
            Dict with file structure information
        """
        all_files = []
        directories = []
        important_files = []
        tree = {}

        for root, dirs, files in os.walk(directory):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            rel_root = os.path.relpath(root, directory)
            if rel_root == ".":
                rel_root = ""

            directories.append(rel_root if rel_root else ".")

            for file in files:
                # Skip binary/media files
                ext = Path(file).suffix.lower()
                if ext in SKIP_EXTENSIONS:
                    continue

                rel_path = os.path.join(rel_root, file) if rel_root else file
                all_files.append(rel_path)

                # Track important files
                if file in IMPORTANT_FILES:
                    important_files.append(rel_path)

                # Build tree structure
                if rel_root not in tree:
                    tree[rel_root if rel_root else "."] = []
                tree[rel_root if rel_root else "."].append(file)

        return {
            "all_files": all_files,
            "directories": directories,
            "important_files": important_files,
            "tree": tree
        }

    def _read_important_files(self, directory: str, important_files: List[str]) -> Dict[str, str]:
        """
        Read contents of important configuration files.

        Returns:
            Dict mapping file paths to contents
        """
        contents = {}

        for file_path in important_files:
            try:
                full_path = Path(directory) / file_path
                # Limit file size to avoid huge config files
                if full_path.stat().st_size > 100_000:  # 100KB limit
                    contents[file_path] = "[File too large to include]"
                else:
                    contents[file_path] = full_path.read_text(encoding='utf-8')
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
                contents[file_path] = f"[Error reading file: {e}]"

        return contents

    def _analyze_patterns(self, file_structure: Dict, project_info: Dict) -> Dict:
        """
        Analyze file patterns and project structure.

        Returns:
            Dict with detected patterns
        """
        all_files = file_structure["all_files"]

        # Count file types
        file_types = {}
        for file_path in all_files:
            ext = Path(file_path).suffix.lower()
            if ext:
                file_types[ext] = file_types.get(ext, 0) + 1

        # Identify source directories
        source_dirs = set()
        for file_path in all_files:
            parts = Path(file_path).parts
            if len(parts) > 1:
                first_dir = parts[0]
                # Common source directory names
                if first_dir in ['src', 'lib', 'app', 'server', 'client', 'api', 'services', 'components']:
                    source_dirs.add(first_dir)

        # Detect entry points
        entry_points = []
        entry_point_names = {
            'index.js', 'index.ts', 'main.js', 'main.ts', 'app.js', 'app.ts', 'server.js', 'server.ts',
            'main.py', 'app.py', '__main__.py', 'manage.py',
            'main.go', 'main.rs'
        }
        for file_path in all_files:
            if Path(file_path).name in entry_point_names:
                entry_points.append(file_path)

        # Check for tests
        has_tests = any(
            'test' in file_path.lower() or 'spec' in file_path.lower()
            for file_path in all_files
        )

        return {
            "file_types": file_types,
            "source_dirs": list(source_dirs),
            "entry_points": entry_points,
            "has_tests": has_tests
        }

    def _extract_dependencies(self, important_files: Dict[str, str], project_type: str) -> List[str]:
        """
        Extract dependency list from configuration files.

        Returns:
            List of dependency names
        """
        dependencies = []

        try:
            if project_type == "nodejs" and "package.json" in important_files:
                pkg_content = important_files["package.json"]
                if not pkg_content.startswith("["):  # Not an error message
                    pkg = json.loads(pkg_content)
                    deps = list(pkg.get("dependencies", {}).keys())
                    dev_deps = list(pkg.get("devDependencies", {}).keys())
                    dependencies = deps + dev_deps

            elif project_type == "python":
                if "requirements.txt" in important_files:
                    req_content = important_files["requirements.txt"]
                    if not req_content.startswith("["):
                        # Parse requirements.txt
                        for line in req_content.splitlines():
                            line = line.strip()
                            if line and not line.startswith("#"):
                                # Extract package name (before == or >=)
                                pkg_name = line.split("==")[0].split(">=")[0].split("~=")[0].strip()
                                dependencies.append(pkg_name)

                elif "pyproject.toml" in important_files:
                    # Basic TOML parsing for dependencies
                    toml_content = important_files["pyproject.toml"]
                    if not toml_content.startswith("["):
                        # Very simple extraction - just look for lines with package names
                        in_dependencies = False
                        for line in toml_content.splitlines():
                            if "[tool.poetry.dependencies]" in line or "[project.dependencies]" in line:
                                in_dependencies = True
                            elif line.startswith("["):
                                in_dependencies = False
                            elif in_dependencies and "=" in line:
                                pkg_name = line.split("=")[0].strip().strip('"')
                                if pkg_name and pkg_name != "python":
                                    dependencies.append(pkg_name)

        except Exception as e:
            logger.warning(f"Error extracting dependencies: {e}")

        return dependencies[:50]  # Limit to top 50

    def generate_summary_text(self, summary: Dict) -> str:
        """
        Generate human-readable summary text from exploration results.

        Args:
            summary: Exploration summary dict

        Returns:
            Formatted summary text
        """
        lines = []
        lines.append("# Codebase Summary\n")

        # Project metadata
        lines.append(f"**Type**: {summary['project_type']}")
        if summary['framework']:
            lines.append(f"**Framework**: {summary['framework']}")
        if summary['language']:
            lines.append(f"**Language**: {summary['language']}")
        if summary['package_manager']:
            lines.append(f"**Package Manager**: {summary['package_manager']}")
        lines.append(f"**Files**: {summary['file_count']}")
        lines.append(f"**Directories**: {summary['directory_count']}")
        lines.append("")

        # File types
        if summary['file_types']:
            lines.append("**File Types**:")
            for ext, count in sorted(summary['file_types'].items(), key=lambda x: x[1], reverse=True)[:10]:
                lines.append(f"  - {ext}: {count} files")
            lines.append("")

        # Structure
        if summary['source_directories']:
            lines.append(f"**Source Directories**: {', '.join(summary['source_directories'])}")
        if summary['entry_points']:
            lines.append(f"**Entry Points**: {', '.join(summary['entry_points'])}")
        if summary['has_tests']:
            lines.append("**Tests**: Present")
        lines.append("")

        # Dependencies
        if summary['dependencies']:
            lines.append(f"**Dependencies** ({len(summary['dependencies'])}):")
            for dep in summary['dependencies'][:20]:  # Show top 20
                lines.append(f"  - {dep}")
            if len(summary['dependencies']) > 20:
                lines.append(f"  - ... and {len(summary['dependencies']) - 20} more")
            lines.append("")

        # Important files
        if summary['important_files']:
            lines.append("**Configuration Files**:")
            for file_path in summary['important_files'].keys():
                lines.append(f"  - {file_path}")

        return "\n".join(lines)
