"""Tests for SEP-053: Zorora application card in Ona platform.

Validates that application-select.html in the platform repo contains
a Zorora app card with the correct configuration.
"""

from __future__ import annotations

import pathlib
import re

import pytest

PLATFORM_UI = pathlib.Path.home() / "Workbench" / "platform" / "ui"
APP_SELECT = PLATFORM_UI / "application-select.html"


def _skip_if_missing():
    if not APP_SELECT.exists():
        pytest.skip("platform/ui/application-select.html not found")


def _content() -> str:
    _skip_if_missing()
    return APP_SELECT.read_text()


class TestZororaCardExists:
    """The APPLICATIONS array must contain a Zorora entry."""

    def test_application_select_contains_zorora_id(self):
        """application-select.html must have an app with id: zorora."""
        content = _content()
        assert "id: 'zorora'" in content, (
            "application-select.html must contain an app entry with id: 'zorora'"
        )

    def test_zorora_entry_has_title(self):
        """The Zorora card must have a title."""
        content = _content()
        assert "Zorora" in content, (
            "application-select.html must contain 'Zorora' in the card title"
        )


class TestZororaCardConfig:
    """The Zorora card must have the correct configuration."""

    def test_zorora_uses_zorora_api_endpoint(self):
        """The href must reference ZORORA_API_ENDPOINT from config.js."""
        content = _content()
        assert "ZORORA_API_ENDPOINT" in content, (
            "Zorora card href must reference window.ZORORA_API_ENDPOINT "
            "so the URL updates when the Fargate endpoint is configured"
        )

    def test_zorora_has_permission_zorora(self):
        """The Zorora card must be gated by permission: zorora."""
        content = _content()
        assert "permission: 'zorora'" in content, (
            "Zorora card must use permission: 'zorora' to gate access"
        )

    def test_zorora_has_category_operations(self):
        """The Zorora card must be in the operations category."""
        content = _content()
        zorora_match = re.search(
            r"id:\s*'zorora'.*?category:\s*'(\w+)'",
            content,
            re.DOTALL,
        )
        assert zorora_match is not None, (
            "Could not find category for the zorora app entry"
        )
        assert zorora_match.group(1) == "operations", (
            f"Zorora category must be 'operations', got '{zorora_match.group(1)}'"
        )

    def test_zorora_requires_auth(self):
        """The Zorora card must require authentication."""
        content = _content()
        zorora_match = re.search(
            r"id:\s*'zorora'.*?requiresAuth:\s*(true|false)",
            content,
            re.DOTALL,
        )
        assert zorora_match is not None, (
            "Could not find requiresAuth for the zorora app entry"
        )
        assert zorora_match.group(1) == "true", (
            "Zorora requiresAuth must be true"
        )

    def test_zorora_is_external(self):
        """The Zorora card must have external: true to open in a new tab."""
        content = _content()
        zorora_match = re.search(
            r"id:\s*'zorora'.*?external:\s*(true|false)",
            content,
            re.DOTALL,
        )
        assert zorora_match is not None, (
            "Could not find external flag for the zorora app entry"
        )
        assert zorora_match.group(1) == "true", (
            "Zorora external must be true (opens in new tab)"
        )

    def test_zorora_has_features_list(self):
        """The Zorora card must have a features array with at least 3 items."""
        content = _content()
        zorora_block = re.search(
            r"id:\s*'zorora'.*?features:\s*\[(.*?)\]",
            content,
            re.DOTALL,
        )
        assert zorora_block is not None, (
            "Could not find features array for the zorora app entry"
        )
        features_text = zorora_block.group(1)
        feature_count = features_text.count("'") // 2
        assert feature_count >= 3, (
            f"Zorora must have at least 3 features, found ~{feature_count}"
        )
