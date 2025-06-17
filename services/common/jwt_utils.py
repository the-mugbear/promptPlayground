# services/common/jwt_utils.py
import json
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token payload without verification (for inspection purposes only).
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dictionary or None if invalid
    """
    try:
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        # Decode the payload (second part)
        payload_part = parts[1]
        
        # Add padding if needed (JWT base64 might not be padded)
        missing_padding = len(payload_part) % 4
        if missing_padding:
            payload_part += '=' * (4 - missing_padding)
            
        # Decode from base64
        payload_bytes = base64.urlsafe_b64decode(payload_part)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        return payload
        
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.debug(f"Failed to decode JWT token: {e}")
        return None

def get_jwt_expiration_info(token: str) -> Tuple[Optional[datetime], Optional[str], bool]:
    """
    Extract expiration information from a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Tuple of (expiration_datetime, warning_message, is_expired)
    """
    payload = decode_jwt_payload(token)
    if not payload:
        return None, "Invalid or malformed JWT token", False
        
    # Check for expiration claim
    exp_timestamp = payload.get('exp')
    if not exp_timestamp:
        return None, "JWT token has no expiration claim", False
        
    try:
        # Convert Unix timestamp to datetime
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        
        # Check if expired
        is_expired = current_time >= exp_datetime
        
        # Generate warning message
        if is_expired:
            time_diff = current_time - exp_datetime
            if time_diff.days > 0:
                warning = f"Token expired {time_diff.days} days ago"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                warning = f"Token expired {hours} hours ago"
            else:
                minutes = time_diff.seconds // 60
                warning = f"Token expired {minutes} minutes ago"
        else:
            time_diff = exp_datetime - current_time
            if time_diff.days > 1:
                warning = f"Token expires in {time_diff.days} days"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                warning = f"Token expires in {hours} hours"
            elif time_diff.seconds > 300:  # More than 5 minutes
                minutes = time_diff.seconds // 60
                warning = f"Token expires in {minutes} minutes"
            else:
                warning = "Token expires very soon!"
                
        return exp_datetime, warning, is_expired
        
    except (ValueError, OSError) as e:
        logger.debug(f"Failed to parse JWT expiration timestamp: {e}")
        return None, "Invalid expiration timestamp in JWT token", False

def extract_auth_token_from_header(auth_header: str) -> Optional[str]:
    """
    Extract token from Authorization header.
    
    Args:
        auth_header: Authorization header value (e.g., "Bearer eyJ...")
        
    Returns:
        Token string or None if not found
    """
    if not auth_header:
        return None
        
    # Handle Bearer tokens
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
        
    # Handle other token formats if needed
    # Could add support for "Token", "JWT", etc.
    
    return None

def analyze_auth_headers(headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Analyze headers for authentication tokens and provide expiration warnings.
    
    Args:
        headers: Dictionary of headers
        
    Returns:
        Dictionary with analysis results
    """
    analysis = {
        'auth_headers_found': [],
        'jwt_analysis': {},
        'warnings': [],
        'has_expired_tokens': False
    }
    
    # Common authentication header names
    auth_header_names = ['Authorization', 'authorization', 'X-Auth-Token', 'X-API-Key', 'Api-Key']
    
    for header_name, header_value in headers.items():
        if header_name in auth_header_names:
            analysis['auth_headers_found'].append(header_name)
            
            # Try to extract and analyze JWT tokens
            if header_name.lower() in ['authorization', 'x-auth-token']:
                token = extract_auth_token_from_header(header_value)
                if token:
                    exp_datetime, warning, is_expired = get_jwt_expiration_info(token)
                    
                    analysis['jwt_analysis'][header_name] = {
                        'expiration_datetime': exp_datetime.isoformat() if exp_datetime else None,
                        'warning_message': warning,
                        'is_expired': is_expired,
                        'token_preview': token[:20] + '...' if len(token) > 20 else token
                    }
                    
                    if warning:
                        analysis['warnings'].append(f"{header_name}: {warning}")
                        
                    if is_expired:
                        analysis['has_expired_tokens'] = True
    
    return analysis