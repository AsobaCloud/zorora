# Zorora 4B Routing Improvement Plan

## Executive Summary

This plan implements 7 key improvements to make zorora's orchestrator routing robust for 4B models:

1. JSON-first routing with structured schemas
2. Heuristic pre-filtering layer
3. Confidence-based model fallback
4. Multi-step planning capability
5. Enhanced tool metadata in prompts
6. Structured JSON parsing
7. Intelligent error recovery with reprompting

**Expected Impact:**
- 40-60% reduction in bad routing decisions
- 2-3x faster responses for simple queries (heuristic bypass)
- Graceful degradation with confidence fallback
- Better context passing for multi-step tasks

---

## Phase 1: JSON Routing Foundation

### 1.1 New System Prompt Architecture

**File:** `system_prompt.txt`

**Current:** String-based `function_call: tool_name("arg")`
**New:** Structured JSON with explicit schemas

**New Prompt Structure:**
```
You are a local coding assistant router. Your ONLY job is to select the right tool.

CRITICAL: Respond ONLY with valid JSON in this exact format:
{
  "tool": "<tool_name>",
  "input": "<string>",
  "confidence": <0.0-1.0>
}

Available Tools (with signatures):

1. web_search(query: str) -> List[SearchResult]
   Use when: User needs current information from the internet
   Example: "latest AI news", "Python 3.12 features"

2. use_codestral(code_context: str) -> str
   Use when: ANY code generation, modification, debugging
   Example: "write a function", "fix this bug", "refactor code"

3. use_reasoning_model(task: str) -> str
   Use when: Complex analysis, planning, multi-step reasoning
   Example: "plan a feature", "analyze architecture", "design system"

4. use_search_model(query: str) -> str
   Use when: Research using AI knowledge (not web)
   Example: "explain concept", "what is X", "how does Y work"

5. use_energy_analyst(query: str) -> str
   Use when: Energy policy, FERC, ISO, NEM, tariffs, regulations
   Example: "FERC Order 2222", "ISO tariff rules"

6. read_file(path: str) -> str
   Use when: User wants to view file contents
   Example: "show me config.py", "read the README"

7. write_file(path: str, content: str) -> str
   Use when: User wants to save content to a file
   Example: "save this to report.md", "write to output.txt"

8. list_files(path: str) -> List[str]
   Use when: User wants to see directory contents
   Example: "list files", "show directory structure"

9. run_shell(command: str) -> str
   Use when: Execute shell commands
   Example: "run tests", "git status", "npm install"

10. generate_image(prompt: str) -> str
    Use when: Create images from text descriptions
    Example: "generate an image of", "create a picture of"

Confidence Guidelines:
- 0.9-1.0: Obvious, single keyword match (e.g., "search X" → web_search)
- 0.7-0.8: Clear intent with context clues
- 0.4-0.6: Ambiguous, multiple valid tools
- 0.0-0.3: Unclear, need more information

Examples:

Input: "What's the latest AI news?"
Output: {"tool": "web_search", "input": "latest AI news", "confidence": 0.95}

Input: "Write a function to validate emails"
Output: {"tool": "use_codestral", "input": "Write a Python function to validate email addresses", "confidence": 0.98}

Input: "Show me config.py"
Output: {"tool": "read_file", "input": "config.py", "confidence": 0.92}

Input: "Analyze this architecture"
Output: {"tool": "use_reasoning_model", "input": "Analyze this architecture", "confidence": 0.65}

RULES:
1. ALWAYS output valid JSON (no markdown, no explanation)
2. Choose ONLY ONE tool per request
3. Set confidence honestly (low = fallback to better model)
4. For code tasks, ALWAYS use use_codestral
5. If unclear, lower confidence (system will handle fallback)
```

**Migration Strategy:**
- Keep old prompt as `system_prompt_legacy.txt`
- Add config flag: `USE_JSON_ROUTING = True`
- Support both formats during transition

---

### 1.2 Update Tool Executor Parsing

**File:** `tool_executor.py`

**Add new method:**
```python
def parse_json_tool_call(self, response_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON tool call from orchestrator response.

    Expected format:
    {
      "tool": "tool_name",
      "input": "user input",
      "confidence": 0.85
    }

    Returns:
        Dict with 'tool', 'arguments', 'confidence' or None if invalid
    """
    try:
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{[^{}]*"tool"[^{}]*\}', response_text, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group(0))

        # Validate required fields
        if "tool" not in data or "input" not in data:
            logger.warning(f"Invalid JSON tool call: missing 'tool' or 'input' fields")
            return None

        tool_name = data["tool"]
        user_input = data["input"]
        confidence = data.get("confidence", 0.5)

        # Map input to correct parameter name for each tool
        param_mapping = {
            "web_search": "query",
            "use_codestral": "code_context",
            "use_reasoning_model": "task",
            "use_search_model": "query",
            "use_energy_analyst": "query",
            "read_file": "path",
            "write_file": "content",  # Special case: needs path too
            "list_files": "path",
            "run_shell": "command",
            "generate_image": "prompt",
        }

        param_name = param_mapping.get(tool_name, "input")
        arguments = {param_name: user_input}

        return {
            "tool": tool_name,
            "arguments": arguments,
            "confidence": confidence
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON tool call: {e}")
        return None
```

---

## Phase 2: Heuristic Router Layer

### 2.1 Create Router Module

**New File:** `router.py`

```python
"""Heuristic routing layer for fast, keyword-based tool selection."""

from typing import Optional, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)


class HeuristicRouter:
    """Fast keyword-based routing before LLM."""

    # Keyword patterns mapped to tools
    PATTERNS = {
        "web_search": [
            r'\b(search|google|find|lookup|latest|current|news|today)\b',
            r'\b(what is|what are|who is|where is)\b.*\b(today|now|current|latest)\b',
        ],
        "use_codestral": [
            r'\b(write|create|generate|implement|code|function|class|script)\b.*\b(code|function|class|script|program)\b',
            r'\b(fix|debug|refactor|optimize|improve)\b.*\b(code|bug|error|function)\b',
            r'\b(add|update|modify|change)\b.*\b(function|class|method|code)\b',
        ],
        "use_reasoning_model": [
            r'\b(plan|design|architect|analyze|think|reason|strategy)\b',
            r'\b(how should|what approach|best way)\b',
            r'\b(pros and cons|tradeoffs|compare|evaluate)\b',
        ],
        "read_file": [
            r'\b(read|show|display|view|cat|open|see)\b.*\.(py|js|md|txt|json|yaml|yml|sh|ts|html|css)',
            r'\b(what\'s in|contents of|show me)\b.*\.(py|js|md|txt|json|yaml|yml|sh|ts|html|css)',
        ],
        "write_file": [
            r'\b(write|save|store|create)\b.*\b(to|in|as)\b.*\.(py|js|md|txt|json|yaml|yml|sh|ts|html|css)',
        ],
        "list_files": [
            r'\b(list|ls|dir|show)\b.*\b(files|directory|folder|contents)\b',
        ],
        "run_shell": [
            r'\b(run|execute|exec)\b.*\b(command|shell|bash|test|tests)\b',
            r'\b(git|npm|pip|docker|kubectl)\b',
        ],
        "use_energy_analyst": [
            r'\b(FERC|ISO|NEM|tariff|energy policy|grid)\b',
            r'\b(regulatory|compliance|interconnection)\b.*\b(energy|utility|power)\b',
        ],
        "generate_image": [
            r'\b(generate|create|make|draw)\b.*\b(image|picture|photo|illustration)\b',
        ],
    }

    def route(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Attempt heuristic routing based on keywords.

        Args:
            user_input: User's request

        Returns:
            Dict with 'tool', 'input', 'confidence' if matched, None otherwise
        """
        user_lower = user_input.lower()

        # Track all matches with scores
        matches = []

        for tool, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, user_lower):
                    matches.append(tool)
                    break  # Only count each tool once

        # No matches → defer to LLM
        if not matches:
            logger.info("No heuristic match found, deferring to LLM")
            return None

        # Single match → high confidence
        if len(matches) == 1:
            tool = matches[0]
            logger.info(f"Heuristic match (high confidence): {tool}")
            return {
                "tool": tool,
                "input": user_input,
                "confidence": 0.95  # High confidence for single match
            }

        # Multiple matches → defer to LLM (ambiguous)
        logger.info(f"Multiple heuristic matches: {matches}, deferring to LLM")
        return None

    def add_pattern(self, tool: str, pattern: str):
        """Add a custom pattern for a tool."""
        if tool not in self.PATTERNS:
            self.PATTERNS[tool] = []
        self.PATTERNS[tool].append(pattern)
        logger.info(f"Added pattern for {tool}: {pattern}")
```

### 2.2 Integrate Heuristic Router

**File:** `turn_processor.py`

**Add to `__init__`:**
```python
from router import HeuristicRouter

def __init__(self, ...):
    # ... existing code ...
    self.heuristic_router = HeuristicRouter()
```

**Update `process()` method (before intent detection):**
```python
def process(self, user_input: str, tools_available: bool = True) -> tuple[str, float]:
    # ... existing code ...

    # PHASE 1: Try heuristic routing (fastest)
    heuristic_result = self.heuristic_router.route(user_input)
    if heuristic_result and heuristic_result["confidence"] >= 0.9:
        logger.info(f"Heuristic router matched: {heuristic_result['tool']}")
        forced_result = self._execute_forced_tool_call(
            heuristic_result["tool"],
            user_input
        )
        if forced_result:
            # ... handle result ...
            return forced_result, time.time() - total_start_time

    # PHASE 2: Intent detection (current system)
    if self._should_use_intent_detection(user_input):
        # ... existing intent detection code ...

    # PHASE 3: Full orchestrator LLM (fallback)
    # ... existing orchestrator code ...
```

---

## Phase 3: Confidence-Based Fallback

### 3.1 Model Fallback Configuration

**File:** `config.py`

**Add:**
```python
# Routing configuration
CONFIDENCE_THRESHOLD_HIGH = 0.85  # Execute immediately
CONFIDENCE_THRESHOLD_LOW = 0.60   # Fallback to larger model
FALLBACK_MODEL_ENDPOINT = "hf_8b"  # 8B model for low confidence

# Model tiers for fallback
MODEL_TIERS = {
    "orchestrator_4b": {
        "endpoint": "local",
        "confidence_threshold": 0.60
    },
    "orchestrator_8b": {
        "endpoint": "hf_8b",
        "confidence_threshold": 0.40
    }
}
```

### 3.2 Implement Fallback Logic

**File:** `turn_processor.py`

**Add method:**
```python
def _route_with_fallback(self, user_input: str) -> Dict[str, Any]:
    """
    Route user input with confidence-based fallback.

    Flow:
    1. Try 4B orchestrator
    2. If confidence < threshold, fallback to 8B
    3. If still low confidence, return for manual handling

    Returns:
        Dict with 'tool', 'input', 'confidence'
    """
    # Try primary (4B) orchestrator
    response = self.llm_client.chat_complete(
        [{"role": "user", "content": user_input}],
        tools=None
    )
    content = self.llm_client.extract_content(response)

    # Parse JSON routing decision
    routing_decision = self.tool_executor.parse_json_tool_call(content)

    if not routing_decision:
        logger.warning("Failed to parse routing decision from 4B model")
        return None

    confidence = routing_decision.get("confidence", 0.5)

    # High confidence → execute
    if confidence >= config.CONFIDENCE_THRESHOLD_HIGH:
        logger.info(f"High confidence ({confidence:.2f}), executing")
        return routing_decision

    # Low confidence → fallback to 8B
    if confidence < config.CONFIDENCE_THRESHOLD_LOW:
        logger.info(f"Low confidence ({confidence:.2f}), falling back to 8B model")

        # Create fallback client
        fallback_client = self._create_fallback_client()
        if fallback_client:
            response = fallback_client.chat_complete(
                [{"role": "user", "content": user_input}],
                tools=None
            )
            content = fallback_client.extract_content(response)
            routing_decision = self.tool_executor.parse_json_tool_call(content)

            if routing_decision:
                logger.info(f"8B fallback decision: {routing_decision['tool']}")
                return routing_decision

    # Medium confidence or fallback failed → execute anyway
    logger.info(f"Medium confidence ({confidence:.2f}), executing cautiously")
    return routing_decision

def _create_fallback_client(self) -> Optional[LLMClient]:
    """Create LLM client for fallback model (8B)."""
    if not hasattr(config, 'HF_ENDPOINTS'):
        return None

    endpoint_key = config.FALLBACK_MODEL_ENDPOINT
    if endpoint_key not in config.HF_ENDPOINTS:
        logger.warning(f"Fallback endpoint '{endpoint_key}' not configured")
        return None

    hf_config = config.HF_ENDPOINTS[endpoint_key]
    return LLMClient(
        api_url=hf_config["url"],
        model=hf_config["model_name"],
        max_tokens=config.MAX_TOKENS,
        timeout=hf_config.get("timeout", config.TIMEOUT),
        temperature=config.TEMPERATURE,
        auth_token=config.HF_TOKEN if hasattr(config, 'HF_TOKEN') else None
    )
```

---

## Phase 4: Multi-Step Planning

### 4.1 Create Planner Module

**New File:** `planner.py`

```python
"""Multi-step task planner for complex workflows."""

from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class TaskPlanner:
    """Plans and executes multi-step tasks."""

    PLANNER_PROMPT = """You are a task planner. Break down the user's request into a sequence of tool calls.

Output ONLY valid JSON array:
[
  {"tool": "tool_name", "input": "what to pass", "reason": "why this step"},
  {"tool": "tool_name", "input": "what to pass", "reason": "why this step"}
]

Available tools: web_search, use_codestral, use_reasoning_model, use_search_model,
read_file, write_file, list_files, run_shell, use_energy_analyst, generate_image

Example:
User: "Research React hooks and create a custom hook for form handling"
Output:
[
  {"tool": "web_search", "input": "React hooks best practices 2025", "reason": "Get current patterns"},
  {"tool": "use_search_model", "input": "Explain React custom hooks", "reason": "Understand concept"},
  {"tool": "use_codestral", "input": "Create a custom React hook for form handling using modern patterns", "reason": "Generate code"}
]

User request: {user_input}
"""

    def __init__(self, llm_client, tool_executor):
        self.llm_client = llm_client
        self.tool_executor = tool_executor

    def should_plan(self, user_input: str) -> bool:
        """
        Determine if request needs multi-step planning.

        Indicators:
        - Contains "and then", "after that", "first..then"
        - Multiple distinct actions
        - Research + implementation patterns
        """
        multi_step_indicators = [
            r'\band then\b',
            r'\bafter that\b',
            r'\bfirst.*then\b',
            r'\bthen\b',
            r'\bnext\b',
            r'\band create\b',
            r'\band implement\b',
            r'\bresearch.*and.*(?:create|implement|build)\b',
        ]

        import re
        for pattern in multi_step_indicators:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.info(f"Multi-step indicator found: {pattern}")
                return True

        return False

    def create_plan(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Create execution plan for user request.

        Returns:
            List of steps: [{"tool": "...", "input": "...", "reason": "..."}]
        """
        prompt = self.PLANNER_PROMPT.format(user_input=user_input)

        response = self.llm_client.chat_complete(
            [{"role": "user", "content": prompt}],
            tools=None
        )

        content = self.llm_client.extract_content(response)

        # Parse JSON plan
        try:
            # Extract JSON array
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not json_match:
                logger.warning("No JSON array found in planner output")
                return []

            plan = json.loads(json_match.group(0))

            # Validate plan structure
            if not isinstance(plan, list):
                logger.warning("Plan is not a list")
                return []

            for step in plan:
                if not all(k in step for k in ["tool", "input"]):
                    logger.warning(f"Invalid step: {step}")
                    return []

            logger.info(f"Created plan with {len(plan)} steps")
            return plan

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}")
            return []

    def execute_plan(self, plan: List[Dict[str, Any]], ui=None) -> str:
        """
        Execute plan steps sequentially.

        Args:
            plan: List of steps from create_plan()
            ui: Optional UI for feedback

        Returns:
            Combined result from all steps
        """
        results = []

        for i, step in enumerate(plan, 1):
            tool = step["tool"]
            user_input = step["input"]
            reason = step.get("reason", "")

            if ui:
                ui.console.print(f"\n[cyan]Step {i}/{len(plan)}:[/cyan] {reason}")
                ui.console.print(f"[dim]  Tool: {tool}[/dim]")

            logger.info(f"Executing step {i}: {tool}({user_input[:50]}...)")

            # Execute tool (reuse forced execution logic)
            # This needs to be imported from turn_processor or refactored
            # For now, placeholder:
            result = f"[Step {i} result placeholder]"
            results.append(result)

        return "\n\n".join(results)
```

### 4.2 Integrate Planner

**File:** `turn_processor.py`

```python
from planner import TaskPlanner

def __init__(self, ...):
    # ... existing code ...
    self.planner = TaskPlanner(self.llm_client, self.tool_executor)

def process(self, user_input: str, tools_available: bool = True) -> tuple[str, float]:
    # ... existing code ...

    # Check if multi-step planning needed
    if self.planner.should_plan(user_input):
        logger.info("Creating multi-step plan")
        plan = self.planner.create_plan(user_input)
        if plan:
            result = self.planner.execute_plan(plan, ui=self.ui)
            return result, time.time() - total_start_time

    # ... rest of existing process logic ...
```

---

## Phase 5: Enhanced Error Recovery

### 5.1 Reprompt on Bad Routing

**File:** `turn_processor.py`

**Add method:**
```python
def _reprompt_on_error(self, user_input: str, error: str, previous_attempt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Reprompt orchestrator with error context.

    Args:
        user_input: Original user input
        error: Error message from failed attempt
        previous_attempt: The routing decision that failed

    Returns:
        New routing decision or None
    """
    reprompt = f"""Previous attempt failed:
User request: {user_input}
Your decision: {previous_attempt}
Error: {error}

Please try again with a different tool or approach. Output JSON:
{{"tool": "...", "input": "...", "confidence": 0.0-1.0}}
"""

    response = self.llm_client.chat_complete(
        [{"role": "user", "content": reprompt}],
        tools=None
    )

    content = self.llm_client.extract_content(response)
    return self.tool_executor.parse_json_tool_call(content)
```

**Update tool execution with retry:**
```python
def _execute_with_retry(self, tool_name: str, arguments: Dict[str, Any], user_input: str, max_retries: int = 1) -> str:
    """Execute tool with automatic retry on error."""

    for attempt in range(max_retries + 1):
        result = self.tool_executor.execute(tool_name, arguments)

        # Success
        if not result.startswith("Error:"):
            return result

        # Failed - try to recover
        if attempt < max_retries:
            logger.warning(f"Tool execution failed (attempt {attempt + 1}), trying reprompt")

            routing_decision = {
                "tool": tool_name,
                "input": arguments,
                "confidence": 0.5
            }

            new_decision = self._reprompt_on_error(user_input, result, routing_decision)

            if new_decision:
                tool_name = new_decision["tool"]
                # Map input to arguments
                # ... (reuse logic from parse_json_tool_call)
                logger.info(f"Retrying with new tool: {tool_name}")
                continue

        # All retries exhausted
        return result
```

---

## Phase 6: Implementation Order

### Recommended Rollout Sequence:

**Week 1: Foundation**
1. Create new JSON system prompt
2. Implement `parse_json_tool_call()` in tool_executor.py
3. Add config flag for A/B testing (JSON vs legacy)
4. Test with 4B model on 20 common queries

**Week 2: Heuristic Layer**
5. Implement `router.py` with keyword patterns
6. Integrate into `turn_processor.py` (Phase 1 routing)
7. Benchmark: measure % of queries handled by heuristic
8. Tune patterns based on logs

**Week 3: Confidence Fallback**
9. Implement fallback client creation
10. Add `_route_with_fallback()` method
11. Configure 8B endpoint in config
12. Test fallback triggering with low-confidence queries

**Week 4: Advanced Features**
13. Implement `planner.py` for multi-step tasks
14. Add error reprompting logic
15. Integration testing with real workflows
16. Documentation and user guide

---

## Phase 7: Testing Strategy

### Unit Tests

**File:** `tests/test_router.py`
```python
def test_heuristic_router_web_search():
    router = HeuristicRouter()
    result = router.route("search for latest Python news")
    assert result["tool"] == "web_search"
    assert result["confidence"] >= 0.9

def test_heuristic_router_code():
    router = HeuristicRouter()
    result = router.route("write a function to parse JSON")
    assert result["tool"] == "use_codestral"
```

**File:** `tests/test_json_parsing.py`
```python
def test_parse_json_tool_call():
    executor = ToolExecutor(registry)
    text = '{"tool": "web_search", "input": "AI news", "confidence": 0.95}'
    result = executor.parse_json_tool_call(text)
    assert result["tool"] == "web_search"
    assert result["confidence"] == 0.95
```

### Integration Tests

**Test Suite:** 50 real-world queries across categories:
- 10 simple file operations
- 10 code generation tasks
- 10 research queries
- 10 multi-step workflows
- 10 ambiguous requests

**Metrics:**
- Routing accuracy (correct tool chosen)
- Response latency (heuristic vs LLM)
- Fallback trigger rate
- Error recovery success rate

### A/B Testing

**Config:**
```python
ROUTING_STRATEGY = "json"  # or "legacy"
```

Run same queries through both systems, compare:
- Accuracy
- Latency
- User satisfaction (manual review)

---

## Phase 8: Rollback Plan

### Fallback Strategy

1. **Immediate Rollback:**
   - Set `ROUTING_STRATEGY = "legacy"`
   - Restart REPL
   - Old prompt still in `system_prompt_legacy.txt`

2. **Gradual Rollback:**
   - Disable heuristic router (bypass Phase 1)
   - Disable confidence fallback
   - Keep JSON parsing as backup

3. **Monitoring:**
   - Log all routing decisions to `logs/routing.jsonl`
   - Track error rates: `grep "Error:" logs/routing.jsonl | wc -l`
   - Alert if error rate > 10%

### Known Risks

| Risk | Mitigation |
|------|------------|
| 4B model can't output valid JSON | Fallback to regex parsing (current system) |
| Heuristics over-match | Tune patterns, add negative patterns |
| 8B endpoint unavailable | Graceful degradation to 4B only |
| Latency increase from fallback | Cache routing decisions for repeated queries |

---

## Phase 9: Success Metrics

### Target Improvements

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Routing Accuracy | 60% (4B) | 85% | Manual review of 100 queries |
| Avg Latency (simple) | 2.5s | 0.5s | Heuristic router bypass |
| Fallback Rate | N/A | 15-20% | Log analysis |
| Error Recovery | 0% | 60% | Reprompt success rate |

### Monitoring Dashboard

Log format: `logs/routing.jsonl`
```json
{
  "timestamp": "2025-12-18T10:30:00",
  "user_input": "search for Python news",
  "routing_method": "heuristic",
  "tool": "web_search",
  "confidence": 0.95,
  "latency_ms": 120,
  "success": true
}
```

Analysis queries:
```bash
# Heuristic success rate
jq 'select(.routing_method=="heuristic") | .success' logs/routing.jsonl | grep true | wc -l

# Average latency by method
jq -r '[.routing_method, .latency_ms] | @csv' logs/routing.jsonl | awk -F, '{sum[$1]+=$2; count[$1]++} END {for (m in sum) print m, sum[m]/count[m]}'

# Fallback trigger rate
jq 'select(.routing_method=="fallback_8b")' logs/routing.jsonl | wc -l
```

---

## Appendix A: File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `system_prompt.txt` | Major Rewrite | JSON routing format |
| `tool_executor.py` | Add Method | `parse_json_tool_call()` |
| `router.py` | New File | Heuristic routing layer |
| `planner.py` | New File | Multi-step task planning |
| `turn_processor.py` | Refactor | Integrate new routing phases |
| `config.py` | Add Settings | Confidence thresholds, fallback config |
| `tests/test_router.py` | New File | Router unit tests |
| `tests/test_json_parsing.py` | New File | JSON parsing tests |
| `ROUTING_IMPROVEMENT_PLAN.md` | New File | This document |

---

## Appendix B: Example Flow

**Query:** "Research React hooks and write a custom form hook"

**Flow:**

1. **Heuristic Router:** No single match (ambiguous) → Pass to Phase 2
2. **Planner Detection:** Multi-step indicators found ("research...and write")
3. **Plan Creation:**
   ```json
   [
     {"tool": "web_search", "input": "React hooks 2025", "reason": "Get latest"},
     {"tool": "use_search_model", "input": "custom hooks patterns", "reason": "Learn"},
     {"tool": "use_codestral", "input": "Create React form hook", "reason": "Implement"}
   ]
   ```
4. **Execution:**
   - Step 1: web_search → Returns articles
   - Step 2: use_search_model → Returns explanation (with step 1 context)
   - Step 3: use_codestral → Generates code (with steps 1-2 context)
5. **Result:** Combined output from all 3 steps

**Latency:** ~8s (3 sequential calls)
**Accuracy:** High (structured plan ensures right tools)

---

## Next Steps

**Ready for Implementation?**

Choose rollout approach:
- **Conservative:** Phases 1-2 only (JSON + heuristics)
- **Balanced:** Phases 1-3 (add confidence fallback)
- **Aggressive:** All phases (complete overhaul)

**Decision Required:**
1. Which phases to implement?
2. Timeline/milestones?
3. Testing requirements before merge?

---

*Plan Version: 1.0*
*Date: 2025-12-18*
*Author: Based on feedback for 4B model optimization*
