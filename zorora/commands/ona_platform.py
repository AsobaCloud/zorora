"""
ONA Platform remote commands for Zorora.
Maps REPL commands to ONA platform API endpoints.
"""

import os
from typing import List, Dict, Any
from zorora.remote_command import RemoteCommand, CommandError
from zorora.http_client import ZororaHTTPClient, HTTPError


class ListChallengersCommand(RemoteCommand):
    """List challenger models for a customer."""
    
    def __init__(self, http_client: ZororaHTTPClient):
        super().__init__(
            name='ml-list-challengers',
            description='List challenger models for a customer',
            http_client=http_client
        )
    
    def execute(self, args: List[str], context: Dict[str, Any]) -> str:
        self.validate_args(args, 1, 'ml-list-challengers <customer_id>')
        
        customer_id = args[0]
        
        try:
            result = self.http_client.get('/challengers', params={'customer_id': customer_id})
            return self.format_response(result)
        except HTTPError as e:
            raise CommandError(f'Failed to list challengers: {e.message}')


class ShowMetricsCommand(RemoteCommand):
    """Show evaluation metrics for a model."""
    
    def __init__(self, http_client: ZororaHTTPClient):
        super().__init__(
            name='ml-show-metrics',
            description='Show evaluation metrics for a model',
            http_client=http_client
        )
    
    def execute(self, args: List[str], context: Dict[str, Any]) -> str:
        self.validate_args(args, 1, 'ml-show-metrics <model_id>')
        
        model_id = args[0]
        
        try:
            result = self.http_client.get(f'/metrics/{model_id}')
            return self.format_response(result)
        except HTTPError as e:
            if e.status_code == 404:
                raise CommandError(f'Model {model_id} not found')
            raise CommandError(f'Failed to fetch metrics: {e.message}')


class DiffModelsCommand(RemoteCommand):
    """Compare challenger vs production model."""
    
    def __init__(self, http_client: ZororaHTTPClient):
        super().__init__(
            name='ml-diff',
            description='Compare challenger vs production model',
            http_client=http_client
        )
    
    def execute(self, args: List[str], context: Dict[str, Any]) -> str:
        self.validate_args(args, 2, 'ml-diff <challenger_id> <production_id>')
        
        challenger_id = args[0]
        production_id = args[1]
        
        try:
            result = self.http_client.get('/diff', params={
                'challenger_id': challenger_id,
                'production_id': production_id
            })
            return self.format_response(result)
        except HTTPError as e:
            raise CommandError(f'Failed to compare models: {e.message}')


class PromoteModelCommand(RemoteCommand):
    """Promote challenger to production."""
    
    def __init__(self, http_client: ZororaHTTPClient, ui=None):
        super().__init__(
            name='ml-promote',
            description='Promote challenger model to production',
            http_client=http_client
        )
        self.ui = ui
    
    def _confirm_action(self, message: str) -> bool:
        """Prompt user for confirmation."""
        if not self.ui:
            # If no UI, require explicit confirmation via environment variable
            return os.getenv('ZORORA_AUTO_CONFIRM', 'false').lower() == 'true'
        
        # Use Zorora UI to prompt (adjust to actual UI API)
        # For now, use a simple input prompt
        try:
            response = input(f"{message} (yes/no): ")
            return response.lower() in ['yes', 'y']
        except:
            return False
    
    def execute(self, args: List[str], context: Dict[str, Any]) -> str:
        if len(args) < 3:
            raise CommandError('Usage: ml-promote <customer_id> <model_id> <reason> [--force]')
        
        customer_id = args[0]
        model_id = args[1]
        reason = ' '.join([a for a in args[2:] if a != '--force'])
        force = '--force' in args
        
        if len(reason) < 10:
            raise CommandError('Reason must be at least 10 characters')
        
        # Show diff first
        try:
            # Get challenger info
            challengers_result = self.http_client.get('/challengers', params={'customer_id': customer_id})
            challenger = next((c for c in challengers_result.get('challengers', []) if c.get('model_id') == model_id), None)
            
            if not challenger:
                raise CommandError(f'Challenger {model_id} not found')
            
            # Get production model ID from registry
            # For now, use a placeholder - would need additional endpoint or parse from registry
            production_id = f"{customer_id}/production/latest"  # Placeholder
            
            # Get diff
            diff_result = self.http_client.get('/diff', params={
                'challenger_id': model_id,
                'production_id': production_id
            })
            
            # Show comparison
            output = f"Model Comparison:\n{self.format_response(diff_result)}\n\n"
            
            if diff_result.get('verdict') != 'eligible' and not force:
                raise CommandError(f'Challenger is not eligible for promotion. Verdict: {diff_result.get("verdict")}')
            
            # Confirmation prompt
            if not self._confirm_action(f'Promote challenger {model_id} to production for customer {customer_id}?'):
                return 'Promotion cancelled by user'
            
            # Additional confirmation for force
            if force:
                if not self._confirm_action('WARNING: Using --force bypasses safety gates. Continue?'):
                    return 'Promotion cancelled by user'
            
            # Execute promotion
            result = self.http_client.post('/promote', json_data={
                'customer_id': customer_id,
                'model_id': model_id,
                'reason': reason,
                'force': force,
                'actor': context.get('actor', 'zorora-user')
            })
            
            return f"{output}✓ Promotion successful:\n{self.format_response(result)}"
        except HTTPError as e:
            raise CommandError(f'Failed to promote model: {e.message}')


class RollbackModelCommand(RemoteCommand):
    """Rollback production model."""
    
    def __init__(self, http_client: ZororaHTTPClient, ui=None):
        super().__init__(
            name='ml-rollback',
            description='Rollback production model to previous version',
            http_client=http_client
        )
        self.ui = ui
    
    def _confirm_action(self, message: str) -> bool:
        """Prompt user for confirmation."""
        if not self.ui:
            return os.getenv('ZORORA_AUTO_CONFIRM', 'false').lower() == 'true'
        
        try:
            response = input(f"{message} (yes/no): ")
            return response.lower() in ['yes', 'y']
        except:
            return False
    
    def execute(self, args: List[str], context: Dict[str, Any]) -> str:
        if len(args) < 2:
            raise CommandError('Usage: ml-rollback <customer_id> <reason>')
        
        customer_id = args[0]
        reason = ' '.join(args[1:])
        
        if len(reason) < 10:
            raise CommandError('Reason must be at least 10 characters')
        
        # Confirmation prompt
        if not self._confirm_action(f'Rollback production model for customer {customer_id}? This will restore the previous production model.'):
            return 'Rollback cancelled by user'
        
        try:
            result = self.http_client.post('/rollback', json_data={
                'customer_id': customer_id,
                'reason': reason,
                'actor': context.get('actor', 'zorora-user')
            })
            return f"✓ Rollback successful:\n{self.format_response(result)}"
        except HTTPError as e:
            raise CommandError(f'Failed to rollback model: {e.message}')


class AuditLogCommand(RemoteCommand):
    """Get audit log for a customer."""
    
    def __init__(self, http_client: ZororaHTTPClient):
        super().__init__(
            name='ml-audit-log',
            description='Get audit log for a customer',
            http_client=http_client
        )
    
    def execute(self, args: List[str], context: Dict[str, Any]) -> str:
        self.validate_args(args, 1, 'ml-audit-log <customer_id>')
        
        customer_id = args[0]
        
        try:
            result = self.http_client.get('/audit-log', params={'customer_id': customer_id})
            return self.format_response(result)
        except HTTPError as e:
            raise CommandError(f'Failed to fetch audit log: {e.message}')


def register_ona_commands(repl):
    """
    Register ONA platform commands with Zorora REPL.
    
    Args:
        repl: REPL instance to register commands with
    """
    # Initialize HTTP client
    base_url = os.getenv('ONA_API_BASE_URL', 'https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1')
    auth_token = os.getenv('ONA_API_TOKEN', '')
    use_iam = os.getenv('ONA_USE_IAM', 'false').lower() == 'true'
    
    http_client = ZororaHTTPClient(
        base_url=base_url,
        auth_token=auth_token,
        use_iam=use_iam
    )
    
    # Get UI instance from REPL
    ui = getattr(repl, 'ui', None)
    
    # Register commands with UI for confirmation prompts
    repl.register_remote_command(ListChallengersCommand(http_client))
    repl.register_remote_command(ShowMetricsCommand(http_client))
    repl.register_remote_command(DiffModelsCommand(http_client))
    repl.register_remote_command(PromoteModelCommand(http_client, ui=ui))
    repl.register_remote_command(RollbackModelCommand(http_client, ui=ui))
    repl.register_remote_command(AuditLogCommand(http_client))
