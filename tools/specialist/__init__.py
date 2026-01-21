"""
Specialist model tools - modular implementation.

Provides access to specialized LLM models for different tasks:
- Coding agent for code generation
- Reasoning model for analysis and planning
- Search model for information retrieval
- Intent detector for request classification
- Nehanda for energy policy queries (RAG)
"""

from tools.specialist.coding import use_coding_agent
from tools.specialist.reasoning import use_reasoning_model
from tools.specialist.search import use_search_model
from tools.specialist.intent import use_intent_detector
from tools.specialist.energy import use_nehanda, use_energy_analyst  # use_energy_analyst is backwards compat alias

__all__ = [
    "use_coding_agent",
    "use_reasoning_model",
    "use_search_model",
    "use_intent_detector",
    "use_nehanda",
    "use_energy_analyst",  # backwards compat alias
]
