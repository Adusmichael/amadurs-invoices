import os
from functools import wraps
from flask import request, jsonify


def requires_cron(f):
    """
    Decorator to protect internal cron endpoints.
    Requires X-CRON-TOKEN header to match CRON_TOKEN environment variable.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the token from the request header
        token = request.headers.get('X-CRON-TOKEN')
        
        # Get the expected token from environment
        expected_token = os.environ.get('CRON_TOKEN')
        
        # Check if token is missing or doesn't match
        if not token or not expected_token or token != expected_token:
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Token is valid, proceed with the request
        return f(*args, **kwargs)
    
    return decorated_function