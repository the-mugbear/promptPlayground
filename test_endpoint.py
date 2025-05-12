import requests
import json
from bs4 import BeautifulSoup

# Start a session to maintain cookies
session = requests.Session()

# First, log in to get a session
login_url = "http://localhost:8021/auth/login"
login_data = {
    "username": "admin",  # Replace with your actual username
    "password": "admin"   # Replace with your actual password
}

try:
    # First, get the login page to get the CSRF token
    login_page = session.get(login_url)
    print(f"Login page status: {login_page.status_code}")
    
    # Parse the CSRF token from the login page
    soup = BeautifulSoup(login_page.text, 'html.parser')
    csrf_token = soup.find('input', {'id': 'csrf_token'})['value']
    print(f"Found CSRF token: {csrf_token}")
    
    # Add the CSRF token to the login data
    login_data['csrf_token'] = csrf_token
    
    # Now try to log in
    login_response = session.post(login_url, data=login_data, allow_redirects=True)
    print(f"Login status: {login_response.status_code}")
    print(f"Login response URL: {login_response.url}")  # Check if we were redirected
    print(f"Login response headers: {dict(login_response.headers)}")
    
    # Check if we're logged in by requesting a protected page
    test_auth = session.get("http://localhost:8021/endpoints/")
    print(f"\nTest Auth Request:")
    print(f"Status code: {test_auth.status_code}")
    print(f"URL after auth check: {test_auth.url}")
    
    # Try both endpoint IDs 1 and 3
    for endpoint_id in [1, 3]:
        # Now make the create_header request using the same session
        url = f"http://localhost:8021/endpoints/{endpoint_id}/create_header"
        headers = {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf_token  # Use the same CSRF token from login
        }
        data = {
            "key": "Authorization",
            "value": "Bearer [token]",
            "csrf_token": csrf_token  # Use the same CSRF token from login
        }
        
        response = session.post(url, headers=headers, json=data)
        print(f"\nCreate Header Request for endpoint {endpoint_id}:")
        print(f"Status code: {response.status_code}")
        print(f"Response URL: {response.url}")
        print(f"Response headers: {dict(response.headers)}")
        
        # Try to parse response as JSON if possible
        try:
            print(f"Response JSON: {response.json()}")
        except:
            pass
        
        print(f"Response text: {response.text[:500]}...")  # Print first 500 chars only
        
except requests.exceptions.RequestException as e:
    print(f"Request failed: {str(e)}") 