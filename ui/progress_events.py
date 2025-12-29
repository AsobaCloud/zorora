"""Progress event system for UI updates."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
import queue
import time


class EventType(Enum):
    """Progress event types."""
    WORKFLOW_START = "workflow_start"
    WORKFLOW_COMPLETE = "workflow_complete"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_ERROR = "step_error"
    TOOL_START = "tool_start"
    TOOL_COMPLETE = "tool_complete"
    TOOL_ERROR = "tool_error"
    MESSAGE = "message"  # Generic status message


@dataclass
class ProgressEvent:
    """Progress event emitted by workflows and tools."""
    event_type: EventType
    message: str
    parent_id: Optional[str] = None  # For hierarchical display
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Ensure event_type is EventType enum."""
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)


class ProgressEventQueue:
    """Thread-safe queue for progress events."""
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize event queue.
        
        Args:
            maxsize: Maximum queue size (prevents memory issues)
        """
        self._queue = queue.Queue(maxsize=maxsize)
        self._closed = False
    
    def put(self, event: ProgressEvent):
        """
        Emit a progress event (thread-safe).
        
        Args:
            event: ProgressEvent to emit
            
        Raises:
            RuntimeError: If queue is closed
        """
        if self._closed:
            raise RuntimeError("ProgressEventQueue is closed")
        try:
            self._queue.put(event, block=False)
        except queue.Full:
            # Drop oldest event if queue full (prevent memory issues)
            try:
                self._queue.get_nowait()
                self._queue.put(event, block=False)
            except queue.Empty:
                pass
    
    def get(self, timeout: float = 0.1) -> Optional[ProgressEvent]:
        """
        Get next event from queue (thread-safe).
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            ProgressEvent or None if timeout
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def drain(self, max_events: int = 100) -> list[ProgressEvent]:
        """
        Drain multiple events from queue (non-blocking).
        
        Args:
            max_events: Maximum events to drain
            
        Returns:
            List of ProgressEvent objects
        """
        events = []
        for _ in range(max_events):
            event = self.get(timeout=0)
            if event is None:
                break
            events.append(event)
        return events
    
    def close(self):
        """Close queue (no more events accepted)."""
        self._closed = True
    
    def is_closed(self) -> bool:
        """Check if queue is closed."""
        return self._closed
