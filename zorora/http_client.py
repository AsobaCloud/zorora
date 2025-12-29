"""
HTTP client module for Zorora remote command execution.
Provides standardized HTTP request handling with authentication, retries, and error mapping.
"""

import requests
import os
from typing import Optional, Dict, Any
from urllib.parse import urljoin


class ZororaHTTPClient:
    """
    Standardized HTTP client for Zorora remote command execution.
    
    Handles:
    - Authentication (Bearer token or IAM)
    - Retries and timeouts
    - Error mapping
    - Request/response logging
    """
    
    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        use_iam: bool = False,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize HTTP client.
        
        Args:
            base_url: Base URL for API (e.g., 'https://p0c7u3j9wi.execute-api.af-south-1.amazonaws.com/api/v1')
            auth_token: Bearer token for authentication (if not using IAM)
            use_iam: If True, use AWS IAM role assumption (requires AWS credentials)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.use_iam = use_iam
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Zorora/2.1.0'
        })
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers based on auth method."""
        headers = {}
        
        if self.use_iam:
            # Use AWS IAM role assumption
            # In production, this would use boto3 to get credentials
            # For now, check environment variables
            session_token = os.getenv('AWS_SESSION_TOKEN')
            if session_token:
                headers['X-Amz-Security-Token'] = session_token
            
            # Add role ARN if available
            role_arn = os.getenv('AWS_ROLE_ARN')
            if role_arn:
                headers['X-Amz-Role-Arn'] = role_arn
        elif self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        return headers
    
    def _get_actor(self) -> str:
        """Extract actor identity from environment or config."""
        # Check for explicit actor
        actor = os.getenv('ZORORA_ACTOR')
        if actor:
            return actor
        
        # Check for IAM role name
        if self.use_iam:
            role_arn = os.getenv('AWS_ROLE_ARN', '')
            if role_arn:
                # Extract role name from ARN: arn:aws:iam::ACCOUNT:role/ROLE_NAME
                parts = role_arn.split('/')
                if len(parts) > 1:
                    return parts[-1]
        
        # Fallback to username
        return os.getenv('USER', 'zorora-user')
    
    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with authentication and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., '/challengers')
            params: Query parameters
            json_data: JSON body for POST/PUT requests
            headers: Additional headers
        
        Returns:
            Parsed JSON response
        
        Raises:
            HTTPError: If request fails after retries
        """
        url = urljoin(self.base_url, path.lstrip('/'))
        
        # Merge headers
        request_headers = self._get_auth_headers()
        if headers:
            request_headers.update(headers)
        
        # Add actor header
        request_headers['X-Actor'] = self._get_actor()
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=request_headers,
                    timeout=self.timeout
                )
                
                # Check status code
                if response.status_code >= 200 and response.status_code < 300:
                    return response.json()
                elif response.status_code == 401:
                    raise HTTPError(f'Unauthorized: {response.text}', status_code=401)
                elif response.status_code == 404:
                    raise HTTPError(f'Not found: {response.text}', status_code=404)
                elif response.status_code >= 500:
                    # Server error - retry
                    if attempt < self.max_retries:
                        continue
                    raise HTTPError(f'Server error: {response.text}', status_code=response.status_code)
                else:
                    # Client error - don't retry
                    raise HTTPError(f'Client error: {response.text}', status_code=response.status_code)
            
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < self.max_retries:
                    continue
                raise HTTPError(f'Request timeout after {self.timeout}s', status_code=0)
            
            except requests.exceptions.ConnectionError as e:
                last_error = e
                if attempt < self.max_retries:
                    continue
                raise HTTPError(f'Connection error: {str(e)}', status_code=0)
        
        # If we get here, all retries failed
        raise HTTPError(f'Request failed after {self.max_retries} retries: {str(last_error)}', status_code=0)
    
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request."""
        return self.request('GET', path, params=params)
    
    def post(self, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request."""
        return self.request('POST', path, json_data=json_data)
    
    def put(self, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make PUT request."""
        return self.request('PUT', path, json_data=json_data)
    
    def delete(self, path: str) -> Dict[str, Any]:
        """Make DELETE request."""
        return self.request('DELETE', path)


class HTTPError(Exception):
    """HTTP request error."""
    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
