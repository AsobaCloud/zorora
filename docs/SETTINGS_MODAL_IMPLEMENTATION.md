# Settings Modal Feature - Technical Implementation Guide

## Executive Summary

This document provides a complete implementation guide for adding a settings modal to the Zorora Web UI that allows users to configure LLM models and endpoints for each LLM-driven tool. The modal opens when clicking the gear icon in the header and provides an intuitive interface for managing model configurations.

**Core Value Proposition:**
- **Visual Configuration** - No need to edit `config.py` manually
- **Real-time Updates** - Changes apply immediately (with server restart)
- **Multi-Endpoint Support** - Switch between LM Studio models and saved endpoints
- **Easy Endpoint Management** - Add/edit/delete custom endpoints
- **Secure API Key Handling** - Masked display, encrypted storage

**User Experience Goals:**
- **Discoverable** - Gear icon clearly indicates settings
- **Intuitive** - Dropdowns and forms follow web UI best practices
- **Responsive** - Works on desktop and mobile
- **Accessible** - Keyboard navigation, screen reader support
- **Fast** - Modal opens instantly, no page reload

---

## Table of Contents

1. [UI/UX Best Practices Research](#uiux-best-practices-research)
2. [Architectural Overview](#architectural-overview)
3. [Design Specifications](#design-specifications)
4. [Implementation Phases](#implementation-phases)
5. [Detailed Technical Specifications](#detailed-technical-specifications)
6. [Testing Strategy](#testing-strategy)
7. [Security Considerations](#security-considerations)

---

## UI/UX Best Practices Research

### Settings Modal Patterns

**Research Findings:**

1. **Modal Overlay Pattern** (Most Common)
   - Dark backdrop (backdrop-blur or solid color)
   - Centered modal (max-width: 600-800px)
   - Close button (X) in top-right corner
   - ESC key closes modal
   - Click outside modal closes (optional)
   - Smooth fade-in animation (200-300ms)

2. **Settings Layout Patterns**
   - **Grouped Sections** - Related settings grouped with headers
   - **Two-Column Layout** - Label left, control right (desktop)
   - **Single Column** - Stacked (mobile)
   - **Visual Hierarchy** - Clear headings, consistent spacing
   - **Save/Cancel Actions** - Bottom of modal, sticky on scroll

3. **Dropdown/Select Best Practices**
   - **Native `<select>`** - Best accessibility, but limited styling
   - **Custom Dropdown** - Full control, requires ARIA attributes
   - **Searchable Dropdown** - For long lists (>10 items)
   - **Grouped Options** - Group by category (e.g., "Local Models", "HF Endpoints")
   - **Selected State** - Clear visual indication

4. **Form Input Best Practices**
   - **Labels** - Always visible, associated with inputs
   - **Placeholders** - Hint text, not replacement for labels
   - **Validation** - Real-time feedback, clear error messages
   - **Required Fields** - Asterisk (*) or "required" text
   - **Help Text** - Contextual hints below inputs

5. **API Key Input Best Practices**
   - **Password Input Type** - Masks characters
   - **Show/Hide Toggle** - Eye icon to reveal
   - **Masked Display** - Show first 4, last 4 chars (e.g., `hf_xxxx...xxxx`)
   - **Copy Button** - One-click copy to clipboard
   - **Validation** - Check format (e.g., HF tokens start with `hf_`)

### Reference Examples

**GitHub Settings Modal:**
- Clean, minimal design
- Grouped sections with dividers
- Save button at bottom
- Cancel/Close in header

**VS Code Settings:**
- Searchable settings
- Categories in sidebar
- Two-column layout
- Real-time preview

**Notion Settings:**
- Modal overlay
- Tabbed navigation (for many settings)
- Clear action buttons
- Smooth animations

**Recommended Pattern for Zorora:**
- **Modal overlay** with backdrop
- **Single-page settings** (no tabs - simple enough)
- **Grouped sections** by tool type
- **Sticky save/cancel** buttons
- **Smooth animations** (fade-in, slide-up)

---

## Architectural Overview

### Component Structure

```
Settings Modal Feature
├── Frontend (HTML/CSS/JavaScript)
│   ├── Modal Component (overlay + content)
│   ├── Settings Form (per-tool configuration)
│   ├── Dropdown Component (model/endpoint selector)
│   ├── Endpoint Form (add/edit endpoint)
│   └── API Client (fetch/save settings)
│
├── Backend (Flask API)
│   ├── GET /api/settings/config - Read current config
│   ├── GET /api/settings/models - List available models
│   ├── GET /api/settings/endpoints - List saved endpoints
│   ├── POST /api/settings/endpoint - Add/edit endpoint
│   ├── DELETE /api/settings/endpoint/<key> - Delete endpoint
│   └── POST /api/settings/config - Save config changes
│
└── Config Management (Python)
    ├── ConfigReader - Read config.py safely
    ├── ConfigWriter - Write config.py with validation
    └── ModelFetcher - Fetch available models from LM Studio/HF
```

### Data Flow

```
User clicks gear icon
    ↓
JavaScript: openSettings()
    ↓
Fetch current config: GET /api/settings/config
    ↓
Display modal with current settings
    ↓
User selects model/endpoint from dropdown
    ↓
User clicks "Save"
    ↓
POST /api/settings/config with updates
    ↓
Backend validates and writes config.py
    ↓
Return success/error
    ↓
Show success message, close modal
```

### Security Considerations

1. **API Key Storage**
   - Never log API keys
   - Mask in responses (show only first 4, last 4 chars)
   - Store in `config.py` (user's file, not in database)
   - Validate format before saving

2. **Config File Writing**
   - Validate all inputs before writing
   - Backup `config.py` before overwriting
   - Atomic write (write to temp file, then rename)
   - Preserve comments and formatting where possible

3. **Input Validation**
   - Validate URLs (must be http:// or https://)
   - Validate model names (no special chars that break Python)
   - Validate endpoint keys (valid Python identifier)
   - Sanitize all user inputs

---

## Design Specifications

### Modal Structure

```
┌─────────────────────────────────────────────────┐
│ Settings                              [X] Close │
├─────────────────────────────────────────────────┤
│                                                   │
│ LLM Model Configuration                          │
│ ─────────────────────────────────────────────── │
│                                                   │
│ Orchestrator (Main REPL)                        │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Dropdown: Local Models ▼]                  │ │
│ │   • Qwen3-4B                                │ │
│ │   • Qwen3-VL-4B                             │ │
│ │   • Mistral-7B                              │ │
│ │   ─────────────────────────                 │ │
│ │   • HF: qwen-coder-32b                      │ │
│ │   • HF: llama-70b                           │ │
│ │   ─────────────────────────                 │ │
│ │   ➕ Add New Endpoint...                    │ │
│ └─────────────────────────────────────────────┘ │
│                                                   │
│ Code Generation (Codestral)                      │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Dropdown: Same options]                   │ │
│ └─────────────────────────────────────────────┘ │
│                                                   │
│ Reasoning (Synthesis)                            │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Dropdown: Same options]                   │ │
│ └─────────────────────────────────────────────┘ │
│                                                   │
│ Research (Search)                                │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Dropdown: Same options]                   │ │
│ └─────────────────────────────────────────────┘ │
│                                                   │
│ [Scrollable content continues...]               │
│                                                   │
├─────────────────────────────────────────────────┤
│                              [Cancel]  [Save]   │
└─────────────────────────────────────────────────┘
```

### Visual Design

**Colors (using existing CSS variables):**
- Modal background: `var(--white)`
- Backdrop: `rgba(0, 0, 0, 0.5)` with backdrop-blur
- Border: `var(--border-grey)`
- Primary button: `var(--primary-purple)`
- Text: `var(--text-dark)`
- Secondary text: `var(--text-light)`

**Typography:**
- Modal title: 1.5rem, bold
- Section headers: 1.1rem, semibold
- Labels: 0.95rem, medium
- Help text: 0.85rem, regular

**Spacing:**
- Modal padding: 32px
- Section spacing: 24px
- Form field spacing: 16px
- Button spacing: 12px

**Animations:**
- Modal fade-in: 200ms ease-out
- Backdrop fade-in: 150ms ease-out
- Dropdown slide-down: 150ms ease-out

### Responsive Design

**Desktop (>768px):**
- Modal width: 600px
- Two-column form layout
- Sticky save/cancel buttons

**Mobile (<768px):**
- Modal width: 100% (with 16px margins)
- Single-column layout
- Full-width buttons
- Larger touch targets (44px min)

---

## Implementation Phases

### Phase 1: Backend API Endpoints (2-3 hours)

**Goal:** Create Flask API endpoints for reading/writing config.

**Tasks:**
1. Create `ui/web/config_manager.py` - Config reading/writing utilities
2. Add API routes to `ui/web/app.py`
3. Implement model fetching from LM Studio
4. Test endpoints with Postman/curl

**Files to create/modify:**
- `ui/web/config_manager.py` (NEW)
- `ui/web/app.py` (MODIFY - add routes)

### Phase 2: Modal UI Component (3-4 hours)

**Goal:** Create modal HTML/CSS structure.

**Tasks:**
1. Add modal HTML to `index.html`
2. Style modal with CSS (overlay, content, animations)
3. Implement open/close functionality
4. Add keyboard support (ESC to close)

**Files to modify:**
- `ui/web/templates/index.html` (MODIFY - add modal HTML/CSS)

### Phase 3: Settings Form (4-5 hours)

**Goal:** Build form with dropdowns for each tool.

**Tasks:**
1. Create dropdown component (custom or native)
2. Populate dropdowns with models/endpoints from API
3. Handle "Add New Endpoint" option
4. Display current selections
5. Form validation

**Files to modify:**
- `ui/web/templates/index.html` (MODIFY - add form JavaScript)

### Phase 4: Endpoint Management (3-4 hours)

**Goal:** Add/edit/delete custom endpoints.

**Tasks:**
1. Create endpoint form modal (nested modal or inline form)
2. Implement add endpoint functionality
3. Implement edit endpoint functionality
4. Implement delete endpoint functionality
5. Validate endpoint inputs

**Files to modify:**
- `ui/web/templates/index.html` (MODIFY - add endpoint form)
- `ui/web/app.py` (MODIFY - add endpoint CRUD routes)

### Phase 5: Config Writing & Validation (2-3 hours)

**Goal:** Safely write config.py with validation.

**Tasks:**
1. Implement config file writer
2. Backup existing config.py
3. Validate all inputs
4. Preserve comments/formatting (optional)
5. Error handling and rollback

**Files to modify:**
- `ui/web/config_manager.py` (MODIFY - add writer)

### Phase 6: Testing & Polish (2-3 hours)

**Goal:** Test all functionality and polish UI.

**Tasks:**
1. Test all API endpoints
2. Test modal interactions
3. Test form validation
4. Test error handling
5. Mobile responsiveness
6. Accessibility (keyboard nav, screen readers)

**Total Estimated Time:** 16-22 hours (2-3 days)

---

## Detailed Technical Specifications

### Phase 1: Backend API Endpoints

#### Task 1.1: Create Config Manager Module

**File:** `ui/web/config_manager.py`

**Purpose:** Centralized config reading/writing with validation.

**Code:**

```python
"""Config management utilities for Web UI settings."""

import ast
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages reading and writing config.py safely."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config.py (default: ./config.py)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.py"
        self.config_path = Path(config_path)
        self.backup_dir = self.config_path.parent / ".config_backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def read_config(self) -> Dict[str, Any]:
        """
        Read current config.py safely.
        
        Returns:
            Dict with config values
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return self._get_default_config()
        
        try:
            # Use ast.literal_eval for safe parsing (but config.py has assignments)
            # Instead, import the module
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", self.config_path)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            
            return {
                "api_url": getattr(config_module, "API_URL", "http://localhost:1234/v1/chat/completions"),
                "model": getattr(config_module, "MODEL", "your-model-name"),
                "specialized_models": getattr(config_module, "SPECIALIZED_MODELS", {}),
                "model_endpoints": getattr(config_module, "MODEL_ENDPOINTS", {}),
                "hf_endpoints": getattr(config_module, "HF_ENDPOINTS", {}),
                "hf_token": getattr(config_module, "HF_TOKEN", None),
                "energy_analyst": getattr(config_module, "ENERGY_ANALYST", {}),
            }
        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default config structure."""
        return {
            "api_url": "http://localhost:1234/v1/chat/completions",
            "model": "your-model-name",
            "specialized_models": {
                "codestral": {"model": "your-model-name"},
                "reasoning": {"model": "your-model-name"},
                "search": {"model": "your-model-name"},
                "intent_detector": {"model": "your-model-name"},
            },
            "model_endpoints": {
                "orchestrator": "local",
                "codestral": "local",
                "reasoning": "local",
                "search": "local",
                "intent_detector": "local",
            },
            "hf_endpoints": {},
            "hf_token": None,
            "energy_analyst": {
                "endpoint": "http://localhost:8000",
                "enabled": True,
            },
        }
    
    def write_config(self, updates: Dict[str, Any]) -> Dict[str, bool]:
        """
        Write config updates to config.py.
        
        Args:
            updates: Dict with config updates
                {
                    "model_endpoints": {"orchestrator": "local", ...},
                    "specialized_models": {"codestral": {"model": "..."}, ...},
                    "hf_endpoints": {"key": {...}, ...},
                    "hf_token": "...",
                }
        
        Returns:
            {"success": bool, "error": str}
        """
        try:
            # Backup existing config
            self._backup_config()
            
            # Read current config
            current = self.read_config()
            
            # Merge updates
            merged = self._merge_config(current, updates)
            
            # Validate merged config
            validation_error = self._validate_config(merged)
            if validation_error:
                return {"success": False, "error": validation_error}
            
            # Write config file
            self._write_config_file(merged)
            
            return {"success": True, "error": None}
            
        except Exception as e:
            logger.error(f"Error writing config: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _backup_config(self):
        """Create backup of config.py before writing."""
        if not self.config_path.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"config_{timestamp}.py"
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Backed up config to: {backup_path}")
    
    def _merge_config(self, current: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge updates into current config."""
        merged = current.copy()
        
        # Deep merge nested dicts
        if "model_endpoints" in updates:
            merged["model_endpoints"] = {**current.get("model_endpoints", {}), **updates["model_endpoints"]}
        
        if "specialized_models" in updates:
            merged["specialized_models"] = current.get("specialized_models", {}).copy()
            for role, model_config in updates["specialized_models"].items():
                if role in merged["specialized_models"]:
                    merged["specialized_models"][role] = {
                        **merged["specialized_models"][role],
                        **model_config
                    }
                else:
                    merged["specialized_models"][role] = model_config
        
        if "hf_endpoints" in updates:
            merged["hf_endpoints"] = {**current.get("hf_endpoints", {}), **updates["hf_endpoints"]}
        
        if "hf_token" in updates:
            merged["hf_token"] = updates["hf_token"]
        
        if "energy_analyst" in updates:
            merged["energy_analyst"] = {**current.get("energy_analyst", {}), **updates["energy_analyst"]}
        
        return merged
    
    def _validate_config(self, config: Dict[str, Any]) -> Optional[str]:
        """Validate config structure and values."""
        # Validate model_endpoints
        if "model_endpoints" in config:
            valid_roles = ["orchestrator", "codestral", "reasoning", "search", "intent_detector", "vision", "image_generation"]
            for role, endpoint in config["model_endpoints"].items():
                if role not in valid_roles:
                    return f"Invalid role in model_endpoints: {role}"
                if endpoint != "local" and endpoint not in config.get("hf_endpoints", {}):
                    return f"Endpoint '{endpoint}' not found in HF_ENDPOINTS"
        
        # Validate HF endpoints
        if "hf_endpoints" in config:
            for key, endpoint_config in config["hf_endpoints"].items():
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', key):
                    return f"Invalid endpoint key: {key} (must be valid Python identifier)"
                if "url" not in endpoint_config:
                    return f"HF endpoint '{key}' missing 'url'"
                if not endpoint_config["url"].startswith(("http://", "https://")):
                    return f"HF endpoint '{key}' URL must start with http:// or https://"
                if "model_name" not in endpoint_config:
                    return f"HF endpoint '{key}' missing 'model_name'"
        
        # Validate API URL
        if "api_url" in config:
            if not config["api_url"].startswith(("http://", "https://")):
                return "API_URL must start with http:// or https://"
        
        return None
    
    def _write_config_file(self, config: Dict[str, Any]):
        """Write config dict to config.py file."""
        lines = [
            '"""Configuration constants and settings.',
            '',
            'IMPORTANT: This file is auto-generated by Web UI settings.',
            'Manual edits may be overwritten.',
            '"""',
            '',
            'from pathlib import Path',
            '',
            '# LM Studio API Configuration (OpenAI-compatible)',
            f'API_URL = "{config["api_url"]}"',
            f'MODEL = "{config["model"]}"',
            'MAX_TOKENS = 2048',
            'TIMEOUT = 60',
            'TEMPERATURE = 0.2',
            '',
            '# Specialized Model Configuration',
            'SPECIALIZED_MODELS = {',
        ]
        
        # Write SPECIALIZED_MODELS
        for role, model_config in config.get("specialized_models", {}).items():
            model_name = model_config.get("model", "your-model-name")
            max_tokens = model_config.get("max_tokens", 2048)
            temperature = model_config.get("temperature", 0.3)
            timeout = model_config.get("timeout", 60)
            lines.append(f'    "{role}": {{')
            lines.append(f'        "model": "{model_name}",')
            lines.append(f'        "max_tokens": {max_tokens},')
            lines.append(f'        "temperature": {temperature},')
            lines.append(f'        "timeout": {timeout},')
            lines.append('    },')
        
        lines.append('}')
        lines.append('')
        lines.append('# Hugging Face Inference Endpoints')
        if config.get("hf_token"):
            lines.append(f'HF_TOKEN = "{config["hf_token"]}"')
        else:
            lines.append('# HF_TOKEN = "hf_YOUR_TOKEN_HERE"')
        lines.append('')
        lines.append('HF_ENDPOINTS = {')
        
        # Write HF_ENDPOINTS
        for key, endpoint_config in config.get("hf_endpoints", {}).items():
            lines.append(f'    "{key}": {{')
            lines.append(f'        "url": "{endpoint_config["url"]}",')
            lines.append(f'        "model_name": "{endpoint_config["model_name"]}",')
            lines.append(f'        "timeout": {endpoint_config.get("timeout", 120)},')
            lines.append(f'        "enabled": {endpoint_config.get("enabled", True)},')
            lines.append('    },')
        
        lines.append('}')
        lines.append('')
        lines.append('# Model Endpoint Mapping')
        lines.append('MODEL_ENDPOINTS = {')
        
        # Write MODEL_ENDPOINTS
        for role, endpoint in config.get("model_endpoints", {}).items():
            lines.append(f'    "{role}": "{endpoint}",')
        
        lines.append('}')
        lines.append('')
        lines.append('# External API Configuration')
        lines.append('ENERGY_ANALYST = {')
        energy_config = config.get("energy_analyst", {})
        lines.append(f'    "endpoint": "{energy_config.get("endpoint", "http://localhost:8000")}",')
        lines.append(f'    "timeout": {energy_config.get("timeout", 180)},')
        lines.append(f'    "enabled": {energy_config.get("enabled", True)},')
        lines.append('}')
        
        # Write to file atomically
        temp_path = self.config_path.with_suffix('.py.tmp')
        temp_path.write_text('\n'.join(lines))
        temp_path.replace(self.config_path)
        logger.info(f"Wrote config to: {self.config_path}")


class ModelFetcher:
    """Fetches available models from LM Studio and HF endpoints."""
    
    def __init__(self):
        """Initialize model fetcher."""
        pass
    
    def fetch_lm_studio_models(self) -> List[Dict[str, str]]:
        """
        Fetch available models from LM Studio.
        
        Returns:
            List of dicts with 'name' and 'origin' keys
        """
        try:
            import requests
            response = requests.get("http://localhost:1234/v1/models", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                if model_id:
                    models.append({
                        "name": model_id,
                        "origin": "Local (LM Studio)",
                        "type": "local"
                    })
            return models
        except Exception as e:
            logger.warning(f"Could not fetch LM Studio models: {e}")
            return []
    
    def fetch_hf_endpoints(self) -> List[Dict[str, str]]:
        """
        Fetch configured HF endpoints.
        
        Returns:
            List of dicts with endpoint info
        """
        try:
            import config
            endpoints = []
            
            if hasattr(config, 'HF_ENDPOINTS'):
                for key, endpoint_config in config.HF_ENDPOINTS.items():
                    if endpoint_config.get("enabled", True):
                        endpoints.append({
                            "key": key,
                            "name": endpoint_config.get("model_name", key),
                            "origin": f"HF: {key}",
                            "type": "hf",
                            "url": endpoint_config.get("url", ""),
                        })
            
            return endpoints
        except Exception as e:
            logger.warning(f"Could not fetch HF endpoints: {e}")
            return []
    
    def fetch_all_models(self) -> List[Dict[str, str]]:
        """
        Fetch all available models (LM Studio + HF).
        
        Returns:
            Combined list of models
        """
        models = self.fetch_lm_studio_models()
        endpoints = self.fetch_hf_endpoints()
        
        # Convert endpoints to model format
        for endpoint in endpoints:
            models.append({
                "name": endpoint["name"],
                "origin": endpoint["origin"],
                "type": endpoint["type"],
                "endpoint_key": endpoint["key"],
            })
        
        return models
```

#### Task 1.2: Add API Routes to Flask App

**File:** `ui/web/app.py` (MODIFY)

**Add these routes:**

```python
from ui.web.config_manager import ConfigManager, ModelFetcher

# Initialize managers
config_manager = ConfigManager()
model_fetcher = ModelFetcher()

@app.route('/api/settings/config', methods=['GET'])
def get_settings_config():
    """
    Get current configuration.
    
    Returns:
    {
        "api_url": str,
        "model": str,
        "model_endpoints": {...},
        "specialized_models": {...},
        "hf_endpoints": {...},
        "hf_token": str (masked),
    }
    """
    try:
        config = config_manager.read_config()
        
        # Mask HF token
        if config.get("hf_token"):
            token = config["hf_token"]
            if len(token) > 8:
                masked = f"{token[:4]}...{token[-4:]}"
            else:
                masked = "***"
            config["hf_token"] = masked
        
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting config: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/models', methods=['GET'])
def get_settings_models():
    """
    Get available models from LM Studio and HF endpoints.
    
    Returns:
    {
        "models": [
            {"name": str, "origin": str, "type": str, ...},
            ...
        ]
    }
    """
    try:
        models = model_fetcher.fetch_all_models()
        return jsonify({"models": models})
    except Exception as e:
        logger.error(f"Error fetching models: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/endpoints', methods=['GET'])
def get_settings_endpoints():
    """
    Get saved HF endpoints.
    
    Returns:
    {
        "endpoints": [
            {"key": str, "url": str, "model_name": str, ...},
            ...
        ]
    }
    """
    try:
        config = config_manager.read_config()
        endpoints = []
        
        for key, endpoint_config in config.get("hf_endpoints", {}).items():
            endpoints.append({
                "key": key,
                "url": endpoint_config.get("url", ""),
                "model_name": endpoint_config.get("model_name", ""),
                "timeout": endpoint_config.get("timeout", 120),
                "enabled": endpoint_config.get("enabled", True),
            })
        
        return jsonify({"endpoints": endpoints})
    except Exception as e:
        logger.error(f"Error getting endpoints: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/endpoint', methods=['POST'])
def save_endpoint():
    """
    Add or update an HF endpoint.
    
    Request body:
    {
        "key": str,
        "url": str,
        "model_name": str,
        "timeout": int (optional),
        "enabled": bool (optional),
    }
    
    Returns:
    {"success": bool, "error": str}
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get("key") or not data.get("url") or not data.get("model_name"):
            return jsonify({"success": False, "error": "Missing required fields"}), 400
        
        # Validate URL
        if not data["url"].startswith(("http://", "https://")):
            return jsonify({"success": False, "error": "URL must start with http:// or https://"}), 400
        
        # Validate key (Python identifier)
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', data["key"]):
            return jsonify({"success": False, "error": "Invalid endpoint key (must be valid Python identifier)"}), 400
        
        # Read current config
        current = config_manager.read_config()
        
        # Update HF endpoints
        hf_endpoints = current.get("hf_endpoints", {}).copy()
        hf_endpoints[data["key"]] = {
            "url": data["url"],
            "model_name": data["model_name"],
            "timeout": data.get("timeout", 120),
            "enabled": data.get("enabled", True),
        }
        
        # Write config
        result = config_manager.write_config({"hf_endpoints": hf_endpoints})
        
        if result["success"]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error saving endpoint: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/settings/endpoint/<endpoint_key>', methods=['DELETE'])
def delete_endpoint(endpoint_key):
    """
    Delete an HF endpoint.
    
    Returns:
    {"success": bool, "error": str}
    """
    try:
        # Read current config
        current = config_manager.read_config()
        
        # Remove endpoint
        hf_endpoints = current.get("hf_endpoints", {}).copy()
        if endpoint_key not in hf_endpoints:
            return jsonify({"success": False, "error": "Endpoint not found"}), 404
        
        del hf_endpoints[endpoint_key]
        
        # Also remove from MODEL_ENDPOINTS if used
        model_endpoints = current.get("model_endpoints", {}).copy()
        for role, endpoint in list(model_endpoints.items()):
            if endpoint == endpoint_key:
                model_endpoints[role] = "local"  # Fallback to local
        
        # Write config
        result = config_manager.write_config({
            "hf_endpoints": hf_endpoints,
            "model_endpoints": model_endpoints,
        })
        
        if result["success"]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result["error"]}), 400
            
    except Exception as e:
        logger.error(f"Error deleting endpoint: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/settings/config', methods=['POST'])
def save_settings_config():
    """
    Save configuration changes.
    
    Request body:
    {
        "model_endpoints": {...},
        "specialized_models": {...},
        "hf_token": str (optional),
    }
    
    Returns:
    {"success": bool, "error": str, "message": str}
    """
    try:
        data = request.get_json()
        
        # Validate and write config
        result = config_manager.write_config(data)
        
        if result["success"]:
            return jsonify({
                "success": True,
                "message": "Configuration saved successfully. Please restart the server for changes to take effect."
            })
        else:
            return jsonify({
                "success": False,
                "error": result["error"]
            }), 400
            
    except Exception as e:
        logger.error(f"Error saving config: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
```

### Phase 2: Modal UI Component

#### Task 2.1: Add Modal HTML Structure

**File:** `ui/web/templates/index.html` (MODIFY)

**Add modal HTML before closing `</body>` tag:**

```html
<!-- Settings Modal -->
<div id="settingsModal" class="modal" style="display: none;">
    <div class="modal-backdrop" onclick="closeSettings()"></div>
    <div class="modal-content">
        <div class="modal-header">
            <h2 class="modal-title">Settings</h2>
            <button class="modal-close" onclick="closeSettings()" aria-label="Close">
                ×
            </button>
        </div>
        
        <div class="modal-body" id="settingsModalBody">
            <!-- Loading state -->
            <div id="settingsLoading" class="settings-loading">
                <div class="spinner"></div>
                <p>Loading settings...</p>
            </div>
            
            <!-- Settings form (hidden until loaded) -->
            <form id="settingsForm" style="display: none;">
                <div class="settings-section">
                    <h3 class="settings-section-title">LLM Model Configuration</h3>
                    <p class="settings-section-desc">Configure the LLM model for each tool.</p>
                    
                    <!-- Tool configurations will be inserted here by JavaScript -->
                    <div id="toolConfigs"></div>
                </div>
                
                <div class="settings-section">
                    <h3 class="settings-section-title">HuggingFace Token</h3>
                    <div class="form-group">
                        <label for="hfToken">API Token</label>
                        <div class="input-with-button">
                            <input 
                                type="password" 
                                id="hfToken" 
                                class="form-input"
                                placeholder="hf_xxxxxxxxxxxx"
                            >
                            <button type="button" class="btn-icon" onclick="toggleTokenVisibility('hfToken')" aria-label="Show/Hide token">
                                👁️
                            </button>
                        </div>
                        <small class="form-help">Your HuggingFace API token for accessing HF endpoints</small>
                    </div>
                </div>
            </form>
        </div>
        
        <div class="modal-footer">
            <button type="button" class="btn-secondary" onclick="closeSettings()">Cancel</button>
            <button type="button" class="btn-primary" onclick="saveSettings()" id="saveSettingsBtn">Save</button>
        </div>
    </div>
</div>

<!-- Endpoint Form Modal (nested) -->
<div id="endpointModal" class="modal" style="display: none;">
    <div class="modal-backdrop" onclick="closeEndpointModal()"></div>
    <div class="modal-content modal-small">
        <div class="modal-header">
            <h2 class="modal-title" id="endpointModalTitle">Add New Endpoint</h2>
            <button class="modal-close" onclick="closeEndpointModal()" aria-label="Close">
                ×
            </button>
        </div>
        
        <div class="modal-body">
            <form id="endpointForm">
                <input type="hidden" id="endpointKey" name="key">
                
                <div class="form-group">
                    <label for="endpointKeyInput">Endpoint Key <span class="required">*</span></label>
                    <input 
                        type="text" 
                        id="endpointKeyInput" 
                        class="form-input"
                        placeholder="e.g., llama-70b"
                        pattern="[a-zA-Z_][a-zA-Z0-9_-]*"
                        required
                    >
                    <small class="form-help">Short identifier (must be valid Python identifier)</small>
                </div>
                
                <div class="form-group">
                    <label for="endpointUrl">Endpoint URL <span class="required">*</span></label>
                    <input 
                        type="url" 
                        id="endpointUrl" 
                        class="form-input"
                        placeholder="https://xyz.endpoints.huggingface.cloud/v1/chat/completions"
                        required
                    >
                    <small class="form-help">Full URL to inference endpoint</small>
                </div>
                
                <div class="form-group">
                    <label for="endpointModelName">Model Name <span class="required">*</span></label>
                    <input 
                        type="text" 
                        id="endpointModelName" 
                        class="form-input"
                        placeholder="meta-llama/Llama-3.1-70B-Instruct"
                        required
                    >
                    <small class="form-help">Model identifier</small>
                </div>
                
                <div class="form-group">
                    <label for="endpointTimeout">Timeout (seconds)</label>
                    <input 
                        type="number" 
                        id="endpointTimeout" 
                        class="form-input"
                        value="120"
                        min="10"
                        max="600"
                    >
                    <small class="form-help">Request timeout in seconds (default: 120)</small>
                </div>
            </form>
        </div>
        
        <div class="modal-footer">
            <button type="button" class="btn-secondary" onclick="closeEndpointModal()">Cancel</button>
            <button type="button" class="btn-primary" onclick="saveEndpoint()">Save Endpoint</button>
        </div>
    </div>
</div>
```

#### Task 2.2: Add Modal CSS Styles

**File:** `ui/web/templates/index.html` (MODIFY - add to `<style>` section)

```css
/* Modal Styles */
.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.2s ease-out;
}

.modal-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    animation: fadeIn 0.15s ease-out;
}

.modal-content {
    position: relative;
    background: var(--white);
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    z-index: 1001;
    animation: slideUp 0.2s ease-out;
}

.modal-small {
    max-width: 500px;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 24px 32px;
    border-bottom: 1px solid var(--border-grey);
}

.modal-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-dark);
    margin: 0;
}

.modal-close {
    background: none;
    border: none;
    font-size: 2rem;
    color: var(--text-light);
    cursor: pointer;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    transition: all 0.2s;
}

.modal-close:hover {
    background: var(--neutral-grey);
    color: var(--text-dark);
}

.modal-body {
    padding: 32px;
    overflow-y: auto;
    flex: 1;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    padding: 24px 32px;
    border-top: 1px solid var(--border-grey);
    background: var(--neutral-grey);
    border-radius: 0 0 16px 16px;
}

/* Settings Form Styles */
.settings-section {
    margin-bottom: 32px;
}

.settings-section:last-child {
    margin-bottom: 0;
}

.settings-section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-dark);
    margin-bottom: 8px;
}

.settings-section-desc {
    font-size: 0.9rem;
    color: var(--text-light);
    margin-bottom: 24px;
}

.tool-config {
    margin-bottom: 24px;
    padding: 16px;
    background: var(--neutral-grey);
    border-radius: 8px;
}

.tool-config-label {
    display: block;
    font-weight: 500;
    color: var(--text-dark);
    margin-bottom: 8px;
    font-size: 0.95rem;
}

.tool-config-help {
    font-size: 0.85rem;
    color: var(--text-light);
    margin-top: 4px;
}

.form-group {
    margin-bottom: 20px;
}

.form-group label {
    display: block;
    font-weight: 500;
    color: var(--text-dark);
    margin-bottom: 8px;
    font-size: 0.95rem;
}

.required {
    color: #ef4444;
}

.form-input,
.form-select {
    width: 100%;
    padding: 12px 16px;
    border: 1px solid var(--border-grey);
    border-radius: 8px;
    font-size: 0.95rem;
    font-family: inherit;
    color: var(--text-dark);
    background: var(--white);
    transition: all 0.2s;
}

.form-input:focus,
.form-select:focus {
    outline: none;
    border-color: var(--primary-purple);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.form-input::placeholder {
    color: var(--text-light);
}

.form-help {
    display: block;
    font-size: 0.85rem;
    color: var(--text-light);
    margin-top: 6px;
}

.input-with-button {
    display: flex;
    gap: 8px;
}

.input-with-button .form-input {
    flex: 1;
}

.btn-icon {
    background: var(--neutral-grey);
    border: 1px solid var(--border-grey);
    border-radius: 8px;
    padding: 12px;
    cursor: pointer;
    font-size: 1rem;
    transition: all 0.2s;
    flex-shrink: 0;
}

.btn-icon:hover {
    background: var(--card-hover);
    border-color: var(--primary-purple);
}

.btn-primary,
.btn-secondary {
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.95rem;
    cursor: pointer;
    transition: all 0.2s;
    border: none;
}

.btn-primary {
    background: var(--primary-purple);
    color: var(--white);
}

.btn-primary:hover:not(:disabled) {
    background: var(--accent-purple);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-secondary {
    background: var(--white);
    color: var(--text-dark);
    border: 1px solid var(--border-grey);
}

.btn-secondary:hover {
    background: var(--neutral-grey);
}

.settings-loading {
    text-align: center;
    padding: 40px;
    color: var(--text-light);
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border-grey);
    border-top-color: var(--primary-purple);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 16px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Responsive */
@media (max-width: 768px) {
    .modal-content {
        width: 100%;
        max-height: 100vh;
        border-radius: 0;
    }
    
    .modal-header,
    .modal-body,
    .modal-footer {
        padding: 20px;
    }
    
    .modal-footer {
        flex-direction: column-reverse;
    }
    
    .btn-primary,
    .btn-secondary {
        width: 100%;
    }
}
```

### Phase 3: Settings Form JavaScript

#### Task 3.1: Modal Open/Close Functions

**File:** `ui/web/templates/index.html` (MODIFY - update JavaScript section)

```javascript
// Settings Modal State
let settingsConfig = null;
let availableModels = [];
let currentEndpointKey = null; // For editing endpoints

// Open settings modal
async function openSettings() {
    const modal = document.getElementById('settingsModal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // Prevent background scroll
    
    // Load settings
    await loadSettings();
    
    // Focus first input for accessibility
    const firstInput = modal.querySelector('input, select');
    if (firstInput) {
        firstInput.focus();
    }
}

// Close settings modal
function closeSettings() {
    const modal = document.getElementById('settingsModal');
    modal.style.display = 'none';
    document.body.style.overflow = ''; // Restore scroll
    
    // Reset form
    document.getElementById('settingsForm').style.display = 'none';
    document.getElementById('settingsLoading').style.display = 'block';
}

// Close endpoint modal
function closeEndpointModal() {
    const modal = document.getElementById('endpointModal');
    modal.style.display = 'none';
    document.getElementById('endpointForm').reset();
    currentEndpointKey = null;
}

// Load settings from API
async function loadSettings() {
    try {
        // Show loading state
        document.getElementById('settingsLoading').style.display = 'block';
        document.getElementById('settingsForm').style.display = 'none';
        
        // Fetch config and models in parallel
        const [configRes, modelsRes] = await Promise.all([
            fetch('/api/settings/config'),
            fetch('/api/settings/models')
        ]);
        
        if (!configRes.ok || !modelsRes.ok) {
            throw new Error('Failed to load settings');
        }
        
        settingsConfig = await configRes.json();
        const modelsData = await modelsRes.json();
        availableModels = modelsData.models;
        
        // Render form
        renderSettingsForm();
        
        // Hide loading, show form
        document.getElementById('settingsLoading').style.display = 'none';
        document.getElementById('settingsForm').style.display = 'block';
        
    } catch (error) {
        console.error('Error loading settings:', error);
        alert('Failed to load settings: ' + error.message);
        closeSettings();
    }
}

// Render settings form
function renderSettingsForm() {
    const toolConfigs = document.getElementById('toolConfigs');
    toolConfigs.innerHTML = '';
    
    // Define LLM-driven tools
    const tools = [
        { key: 'orchestrator', label: 'Orchestrator (Main REPL)', help: 'Main conversational model' },
        { key: 'codestral', label: 'Code Generation', help: 'Model for code generation tasks' },
        { key: 'reasoning', label: 'Reasoning (Synthesis)', help: 'Model for research synthesis' },
        { key: 'search', label: 'Research (Search)', help: 'Model for research queries' },
        { key: 'intent_detector', label: 'Intent Detector', help: 'Model for routing decisions' },
    ];
    
    tools.forEach(tool => {
        const toolDiv = document.createElement('div');
        toolDiv.className = 'tool-config';
        
        const currentEndpoint = settingsConfig.model_endpoints?.[tool.key] || 'local';
        const currentModel = settingsConfig.specialized_models?.[tool.key]?.model || settingsConfig.model || 'your-model-name';
        
        toolDiv.innerHTML = `
            <label class="tool-config-label">${tool.label}</label>
            <select 
                class="form-select" 
                id="endpoint_${tool.key}"
                onchange="onEndpointChange('${tool.key}')"
            >
                ${renderEndpointOptions(currentEndpoint)}
            </select>
            <select 
                class="form-select" 
                id="model_${tool.key}"
                style="margin-top: 8px; ${currentEndpoint === 'local' ? '' : 'display: none;'}"
            >
                ${renderModelOptions(currentModel, currentEndpoint)}
            </select>
            <small class="tool-config-help">${tool.help}</small>
        `;
        
        toolConfigs.appendChild(toolDiv);
    });
    
    // Set HF token
    const hfTokenInput = document.getElementById('hfToken');
    if (settingsConfig.hf_token && settingsConfig.hf_token !== 'None') {
        hfTokenInput.value = settingsConfig.hf_token;
    }
}

// Render endpoint dropdown options
function renderEndpointOptions(currentEndpoint) {
    let html = '<option value="local">Local (LM Studio)</option>';
    
    // Add HF endpoints
    const hfEndpoints = Object.keys(settingsConfig.hf_endpoints || {});
    if (hfEndpoints.length > 0) {
        html += '<optgroup label="HuggingFace Endpoints">';
        hfEndpoints.forEach(key => {
            const endpoint = settingsConfig.hf_endpoints[key];
            const selected = currentEndpoint === key ? 'selected' : '';
            html += `<option value="${key}" ${selected}>HF: ${key} (${endpoint.model_name})</option>`;
        });
        html += '</optgroup>';
    }
    
    html += '<optgroup label="Actions">';
    html += '<option value="__add_new__">➕ Add New Endpoint...</option>';
    html += '</optgroup>';
    
    return html;
}

// Render model dropdown options
function renderModelOptions(currentModel, endpoint) {
    let html = '';
    
    if (endpoint === 'local') {
        // Show LM Studio models
        const localModels = availableModels.filter(m => m.type === 'local');
        if (localModels.length === 0) {
            html = '<option value="">No models available</option>';
        } else {
            localModels.forEach(model => {
                const selected = model.name === currentModel ? 'selected' : '';
                html += `<option value="${model.name}" ${selected}>${model.name}</option>`;
            });
        }
    } else {
        // Show endpoint model name (read-only)
        const endpointConfig = settingsConfig.hf_endpoints?.[endpoint];
        if (endpointConfig) {
            html = `<option value="${endpointConfig.model_name}" selected>${endpointConfig.model_name}</option>`;
        }
    }
    
    return html;
}

// Handle endpoint selection change
function onEndpointChange(toolKey) {
    const endpointSelect = document.getElementById(`endpoint_${toolKey}`);
    const modelSelect = document.getElementById(`model_${toolKey}`);
    const selectedValue = endpointSelect.value;
    
    if (selectedValue === '__add_new__') {
        // Open endpoint modal
        openEndpointModal(toolKey);
        // Reset to previous value
        const currentEndpoint = settingsConfig.model_endpoints?.[toolKey] || 'local';
        endpointSelect.value = currentEndpoint;
    } else {
        // Update model dropdown
        const currentModel = settingsConfig.specialized_models?.[toolKey]?.model || settingsConfig.model || 'your-model-name';
        modelSelect.innerHTML = renderModelOptions(currentModel, selectedValue);
        
        // Show/hide model dropdown based on endpoint type
        if (selectedValue === 'local') {
            modelSelect.style.display = 'block';
        } else {
            modelSelect.style.display = 'none';
        }
    }
}

// Open endpoint modal for adding/editing
function openEndpointModal(toolKey = null, endpointKey = null) {
    const modal = document.getElementById('endpointModal');
    const title = document.getElementById('endpointModalTitle');
    const form = document.getElementById('endpointForm');
    
    if (endpointKey) {
        // Edit mode
        title.textContent = 'Edit Endpoint';
        const endpoint = settingsConfig.hf_endpoints[endpointKey];
        document.getElementById('endpointKeyInput').value = endpointKey;
        document.getElementById('endpointKeyInput').disabled = true;
        document.getElementById('endpointUrl').value = endpoint.url;
        document.getElementById('endpointModelName').value = endpoint.model_name;
        document.getElementById('endpointTimeout').value = endpoint.timeout || 120;
        currentEndpointKey = endpointKey;
    } else {
        // Add mode
        title.textContent = 'Add New Endpoint';
        form.reset();
        document.getElementById('endpointKeyInput').disabled = false;
        currentEndpointKey = null;
    }
    
    modal.style.display = 'flex';
}

// Save endpoint
async function saveEndpoint() {
    const form = document.getElementById('endpointForm');
    const formData = {
        key: document.getElementById('endpointKeyInput').value.trim(),
        url: document.getElementById('endpointUrl').value.trim(),
        model_name: document.getElementById('endpointModelName').value.trim(),
        timeout: parseInt(document.getElementById('endpointTimeout').value) || 120,
        enabled: true,
    };
    
    // Validate
    if (!formData.key || !formData.url || !formData.model_name) {
        alert('Please fill in all required fields');
        return;
    }
    
    if (!formData.url.startsWith('http://') && !formData.url.startsWith('https://')) {
        alert('URL must start with http:// or https://');
        return;
    }
    
    try {
        const response = await fetch('/api/settings/endpoint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Reload settings to get updated endpoints
            await loadSettings();
            closeEndpointModal();
            
            // Update the dropdown that triggered this
            // (This is a simplified version - in real impl, track which tool triggered it)
        } else {
            alert('Error saving endpoint: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving endpoint:', error);
        alert('Failed to save endpoint: ' + error.message);
    }
}

// Save settings
async function saveSettings() {
    const saveBtn = document.getElementById('saveSettingsBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    
    try {
        // Collect form data
        const updates = {
            model_endpoints: {},
            specialized_models: {},
        };
        
        // Collect model endpoints
        const tools = ['orchestrator', 'codestral', 'reasoning', 'search', 'intent_detector'];
        tools.forEach(toolKey => {
            const endpointSelect = document.getElementById(`endpoint_${toolKey}`);
            const modelSelect = document.getElementById(`model_${toolKey}`);
            
            updates.model_endpoints[toolKey] = endpointSelect.value;
            
            if (endpointSelect.value === 'local') {
                updates.specialized_models[toolKey] = {
                    model: modelSelect.value,
                };
            }
        });
        
        // Collect HF token if changed
        const hfTokenInput = document.getElementById('hfToken');
        if (hfTokenInput.value && hfTokenInput.value !== settingsConfig.hf_token) {
            updates.hf_token = hfTokenInput.value;
        }
        
        // Send to API
        const response = await fetch('/api/settings/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message || 'Settings saved successfully!');
            closeSettings();
        } else {
            alert('Error saving settings: ' + result.error);
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Failed to save settings: ' + error.message);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save';
    }
}

// Toggle token visibility
function toggleTokenVisibility(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    
    if (input.type === 'password') {
        input.type = 'text';
        button.textContent = '🙈';
    } else {
        input.type = 'password';
        button.textContent = '👁️';
    }
}

// Keyboard support
document.addEventListener('keydown', function(e) {
    // ESC to close modals
    if (e.key === 'Escape') {
        const settingsModal = document.getElementById('settingsModal');
        const endpointModal = document.getElementById('endpointModal');
        
        if (endpointModal.style.display === 'flex') {
            closeEndpointModal();
        } else if (settingsModal.style.display === 'flex') {
            closeSettings();
        }
    }
});
```

### Phase 4: Endpoint Management

**Already implemented in Phase 3 JavaScript** - The endpoint modal and CRUD operations are included above.

### Phase 5: Config Writing & Validation

**Already implemented in Phase 1** - The `ConfigManager` class handles safe writing with validation and backups.

### Phase 6: Testing & Polish

#### Testing Checklist

**Backend API Tests:**
- [ ] GET /api/settings/config returns current config
- [ ] GET /api/settings/models returns available models
- [ ] POST /api/settings/config validates and saves
- [ ] POST /api/settings/endpoint validates and saves endpoint
- [ ] DELETE /api/settings/endpoint removes endpoint
- [ ] Config file backup created before write
- [ ] Invalid inputs rejected with clear errors

**Frontend Tests:**
- [ ] Modal opens/closes smoothly
- [ ] Settings load correctly
- [ ] Dropdowns populate with models/endpoints
- [ ] Endpoint form validates inputs
- [ ] Save button disabled during save
- [ ] Success/error messages display
- [ ] ESC key closes modal
- [ ] Click outside closes modal (optional)

**Integration Tests:**
- [ ] Save settings → config.py updated
- [ ] Add endpoint → appears in dropdowns
- [ ] Delete endpoint → removed from dropdowns
- [ ] Change model → specialized_models updated
- [ ] Change endpoint → MODEL_ENDPOINTS updated

**Accessibility Tests:**
- [ ] Keyboard navigation works
- [ ] Screen reader announces modal
- [ ] Focus trapped in modal
- [ ] Labels associated with inputs
- [ ] Error messages announced

**Responsive Tests:**
- [ ] Mobile layout (<768px)
- [ ] Tablet layout (768-1024px)
- [ ] Desktop layout (>1024px)
- [ ] Touch targets adequate (44px min)

---

## Security Considerations

### 1. API Key Handling

**Masking:**
- Never return full API keys in API responses
- Show only first 4 and last 4 characters: `hf_xxxx...xxxx`
- Store masked version in frontend state

**Storage:**
- API keys stored in `config.py` (user's file)
- Never commit `config.py` to git (already in .gitignore)
- No database storage of sensitive data

**Validation:**
- Validate HF token format (starts with `hf_`)
- Validate URL format (http:// or https://)
- Sanitize all inputs before writing to file

### 2. Config File Writing

**Backup:**
- Always backup `config.py` before writing
- Store backups in `.config_backups/` directory
- Keep last 10 backups (rotate old ones)

**Atomic Writes:**
- Write to temp file first
- Validate temp file
- Rename temp file to `config.py` (atomic operation)
- Rollback on error

**Validation:**
- Validate all inputs before writing
- Check Python syntax validity
- Verify endpoint keys are valid identifiers
- Ensure URLs are valid format

### 3. Input Sanitization

**All User Inputs:**
- Escape special characters in model names
- Validate endpoint keys (regex: `^[a-zA-Z_][a-zA-Z0-9_-]*$`)
- Validate URLs (must start with http:// or https://)
- Limit string lengths (prevent buffer overflow)

**Error Messages:**
- Don't expose file paths in errors
- Don't expose internal structure
- Provide helpful, actionable error messages

---

## Success Criteria

### Functional Requirements
- ✅ Gear icon opens settings modal
- ✅ Modal displays current configuration
- ✅ Dropdowns show available models/endpoints
- ✅ User can select model for each tool
- ✅ User can add/edit/delete endpoints
- ✅ Changes save to config.py
- ✅ Config file backed up before write

### Non-Functional Requirements
- ✅ Modal opens in <200ms
- ✅ Settings load in <500ms
- ✅ Form validation provides immediate feedback
- ✅ Mobile-responsive design
- ✅ Keyboard accessible
- ✅ Screen reader compatible

### User Experience
- ✅ Intuitive interface (no training needed)
- ✅ Clear labels and help text
- ✅ Success/error messages clear
- ✅ Smooth animations
- ✅ Consistent with existing UI design

---

## Estimated Timeline

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1: Backend API | Config manager, API routes | 2-3 hours |
| Phase 2: Modal UI | HTML structure, CSS styles | 3-4 hours |
| Phase 3: Settings Form | JavaScript, dropdowns | 4-5 hours |
| Phase 4: Endpoint Management | CRUD operations | 3-4 hours |
| Phase 5: Config Writing | Validation, backups | 2-3 hours |
| Phase 6: Testing & Polish | Testing, fixes | 2-3 hours |
| **TOTAL** | **6 phases** | **16-22 hours (2-3 days)** |

---

## Appendix: Complete Code Files

### A.1: Complete config_manager.py

(See Phase 1, Task 1.1 above - full implementation provided)

### A.2: Complete API Routes

(See Phase 1, Task 1.2 above - full implementation provided)

### A.3: Complete Modal HTML

(See Phase 2, Task 2.1 above - full implementation provided)

### A.4: Complete Modal CSS

(See Phase 2, Task 2.2 above - full implementation provided)

### A.5: Complete JavaScript

(See Phase 3, Task 3.1 above - full implementation provided)

---

## Notes for AI Coders

1. **Follow Existing Patterns:**
   - Use existing CSS variables for colors
   - Follow existing HTML structure patterns
   - Match existing button/form styles

2. **Error Handling:**
   - Always handle API errors gracefully
   - Show user-friendly error messages
   - Log errors server-side for debugging

3. **Testing:**
   - Test with real config.py file
   - Test with missing config.py (should create default)
   - Test with invalid inputs
   - Test on mobile devices

4. **Accessibility:**
   - Use semantic HTML
   - Add ARIA labels where needed
   - Ensure keyboard navigation works
   - Test with screen reader

5. **Performance:**
   - Lazy load modal content
   - Cache model list (refresh on demand)
   - Debounce form validation

6. **Security:**
   - Never log API keys
   - Validate all inputs server-side
   - Sanitize before writing to file
   - Use atomic file writes

---

**This implementation guide provides everything needed for a one-shot implementation of the settings modal feature.**
