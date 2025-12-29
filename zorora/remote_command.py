"""
Remote command interface for Zorora.
Defines the contract for commands that execute against remote APIs.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from zorora.http_client import ZororaHTTPClient, HTTPError


class RemoteCommand(ABC):
    """
    Base class for remote commands.
    
    Remote commands execute against external APIs (like ONA platform)
    and map REPL inputs to HTTP API calls.
    """
    
    def __init__(self, name: str, description: str, http_client: ZororaHTTPClient):
        """
        Initialize remote command.
        
        Args:
            name: Command name (e.g., 'ml-list-challengers')
            description: Command description for help text
            http_client: HTTP client for API calls
        """
        self.name = name
        self.description = description
        self.http_client = http_client
    
    @abstractmethod
    def execute(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Execute command with given arguments and context.
        
        Args:
            args: Command arguments (parsed from REPL input)
            context: Execution context (actor, environment, etc.)
        
        Returns:
            Formatted output string for REPL display
        
        Raises:
            CommandError: If command execution fails
        """
        pass
    
    def validate_args(self, args: List[str], required_count: int, usage: str) -> None:
        """
        Validate argument count.
        
        Args:
            args: Command arguments
            required_count: Required number of arguments
            usage: Usage string for error message
        
        Raises:
            CommandError: If argument count is invalid
        """
        if len(args) < required_count:
            raise CommandError(f'Usage: {usage}')
    
    def format_response(self, data: Dict[str, Any]) -> str:
        """
        Format API response for REPL display.
        
        Args:
            data: API response data
        
        Returns:
            Formatted string
        """
        import json
        return json.dumps(data, indent=2)


class CommandError(Exception):
    """Command execution error."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
