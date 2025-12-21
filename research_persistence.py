"""Research persistence for saving and loading research findings.

Simple file-based storage in ~/.zorora/research/
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
import json

logger = logging.getLogger(__name__)


class ResearchPersistence:
    """
    Manages saving and loading research findings.

    Storage format:
    - Directory: ~/.zorora/research/
    - Format: {topic_slug}.md (markdown with frontmatter)
    - Metadata: JSON frontmatter with timestamp, query, sources
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize research persistence.

        Args:
            base_dir: Base directory for research storage
                     Defaults to ~/.zorora/research/
        """
        if base_dir is None:
            self.base_dir = Path.home() / ".zorora" / "research"
        else:
            self.base_dir = Path(base_dir)

        # Ensure directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Research storage: {self.base_dir}")

    def save(
        self,
        topic: str,
        content: str,
        query: Optional[str] = None,
        sources: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> Path:
        """
        Save research findings.

        Args:
            topic: Topic name (will be slugified for filename)
            content: Research content (markdown)
            query: Original query (optional)
            sources: List of sources used (optional)
            metadata: Additional metadata (optional)

        Returns:
            Path to saved file
        """
        # Create filename from topic
        slug = self._slugify(topic)
        filename = f"{slug}.md"
        filepath = self.base_dir / filename

        # Build frontmatter
        frontmatter = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "sources": sources or [],
        }

        if metadata:
            frontmatter.update(metadata)

        # Build full content with frontmatter
        full_content = self._build_document(frontmatter, content)

        # Write file
        filepath.write_text(full_content, encoding="utf-8")
        logger.info(f"Saved research to: {filepath}")

        return filepath

    def load(self, topic: str) -> Optional[Dict]:
        """
        Load research findings.

        Args:
            topic: Topic name or filename

        Returns:
            Dict with 'metadata' and 'content', or None if not found
        """
        # Try as slug
        slug = self._slugify(topic)
        filepath = self.base_dir / f"{slug}.md"

        if not filepath.exists():
            # Try as exact filename
            filepath = self.base_dir / topic
            if not filepath.exists():
                logger.warning(f"Research not found: {topic}")
                return None

        # Read and parse
        full_content = filepath.read_text(encoding="utf-8")
        metadata, content = self._parse_document(full_content)

        logger.info(f"Loaded research: {filepath}")
        return {
            "metadata": metadata,
            "content": content,
            "filepath": str(filepath)
        }

    def list_all(self) -> List[Dict]:
        """
        List all saved research.

        Returns:
            List of dicts with metadata for each research file
        """
        research_files = []

        for filepath in sorted(self.base_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                full_content = filepath.read_text(encoding="utf-8")
                metadata, _ = self._parse_document(full_content)

                research_files.append({
                    "filename": filepath.name,
                    "topic": metadata.get("topic", filepath.stem),
                    "timestamp": metadata.get("timestamp"),
                    "query": metadata.get("query"),
                    "filepath": str(filepath)
                })
            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")
                continue

        return research_files

    def delete(self, topic: str) -> bool:
        """
        Delete research file.

        Args:
            topic: Topic name

        Returns:
            True if deleted, False if not found
        """
        slug = self._slugify(topic)
        filepath = self.base_dir / f"{slug}.md"

        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted research: {filepath}")
            return True
        else:
            logger.warning(f"Research not found for deletion: {topic}")
            return False

    def _slugify(self, text: str) -> str:
        """
        Convert text to valid filename slug.

        Args:
            text: Input text

        Returns:
            Slugified filename (lowercase, underscores, no special chars)
        """
        import re

        # Lowercase
        slug = text.lower()

        # Replace spaces and hyphens with underscores
        slug = re.sub(r'[\s\-]+', '_', slug)

        # Remove non-alphanumeric (except underscores)
        slug = re.sub(r'[^a-z0-9_]', '', slug)

        # Remove multiple underscores
        slug = re.sub(r'_+', '_', slug)

        # Trim underscores
        slug = slug.strip('_')

        # Truncate if too long
        if len(slug) > 100:
            slug = slug[:100]

        return slug or "research"

    def _build_document(self, metadata: Dict, content: str) -> str:
        """
        Build markdown document with JSON frontmatter.

        Args:
            metadata: Metadata dict
            content: Main content

        Returns:
            Full document string
        """
        frontmatter_json = json.dumps(metadata, indent=2)

        document = f"""---
{frontmatter_json}
---

{content}
"""
        return document

    def _parse_document(self, full_content: str) -> tuple:
        """
        Parse markdown document with frontmatter.

        Args:
            full_content: Full document string

        Returns:
            Tuple of (metadata dict, content string)
        """
        import re

        # Match frontmatter
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', full_content, re.DOTALL)

        if match:
            try:
                metadata = json.loads(match.group(1))
                content = match.group(2).strip()
                return metadata, content
            except json.JSONDecodeError:
                logger.warning("Invalid frontmatter JSON, treating as plain content")
                return {}, full_content
        else:
            # No frontmatter
            return {}, full_content
