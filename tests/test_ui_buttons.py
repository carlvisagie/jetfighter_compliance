"""
Test UI buttons in control.html

Validates that all interactive buttons have:
- Valid IDs
- Event listeners attached
- Corresponding endpoints (if applicable)
- No orphan buttons
"""
import re
from pathlib import Path
from html.parser import HTMLParser


def test_control_buttons_have_listeners():
    """
    Verify all buttons in control.html have event listeners attached.
    """
    repo_root = Path(__file__).resolve().parents[1]
    control_html = repo_root / 'ui' / 'control.html'
    
    html_content = control_html.read_text(encoding='utf-8')
    
    # Extract all button IDs
    button_ids = set(re.findall(r'<button[^>]*id=["\']([^"\']+)["\']', html_content))
    
    # Find all addEventListener calls in control.html
    listener_pattern = r"getElementById\(['\"]([^'\"]+)['\"]\).*?\.addEventListener"
    listeners_in_html = set(re.findall(listener_pattern, html_content, re.DOTALL))
    
    # Find all onclick assignments
    onclick_pattern = r"getElementById\(['\"]([^'\"]+)['\"]\)\.onclick"
    onclick_listeners = set(re.findall(onclick_pattern, html_content))
    
    all_listeners = listeners_in_html | onclick_listeners
    
    # Check external JS files that might attach listeners
    js_dir = repo_root / 'ui' / 'assets' / 'js'
    external_listeners = set()
    
    for js_file in js_dir.glob('*.js'):
        js_content = js_file.read_text(encoding='utf-8')
        external_listeners |= set(re.findall(listener_pattern, js_content, re.DOTALL))
        external_listeners |= set(re.findall(onclick_pattern, js_content))
    
    all_listeners |= external_listeners
    
    # Check for buttons without listeners
    buttons_without_listeners = []
    for btn_id in button_ids:
        if btn_id not in all_listeners:
            # Check if it's a delegated event (data-fb-action, etc.)
            if f'data-fb-action' in html_content and btn_id in html_content:
                continue  # Delegated listener, OK
            if f'data-cko-' in html_content and btn_id in html_content:
                continue  # CKO delegated, OK
            buttons_without_listeners.append(btn_id)
    
    assert len(buttons_without_listeners) == 0, (
        f"Found {len(buttons_without_listeners)} buttons without event listeners: "
        f"{', '.join(buttons_without_listeners)}"
    )


def test_no_orphan_buttons():
    """
    Verify no buttons exist that reference non-existent endpoints.
    """
    repo_root = Path(__file__).resolve().parents[1]
    control_html = repo_root / 'ui' / 'control.html'
    server_py = repo_root / 'server.py'
    
    html_content = control_html.read_text(encoding='utf-8')
    server_content = server_py.read_text(encoding='utf-8')
    
    # Extract API calls from control.html
    api_calls = set(re.findall(r'fetch\(["\']([^"\']+)["\']', html_content))
    api_calls |= set(re.findall(r"fetch\('([^']+)'", html_content))
    api_calls |= set(re.findall(r'fetch\("([^"]+)"', html_content))
    
    # Filter to only /api/ endpoints
    api_endpoints = {call for call in api_calls if call.startswith('/api/')}
    
    # Extract all routes from server.py
    route_pattern = r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
    server_routes = set()
    for match in re.finditer(route_pattern, server_content):
        route = match.group(2)
        # Convert {param} to regex pattern for matching
        route_pattern_str = re.sub(r'\{[^}]+\}', '[^/]+', route)
        server_routes.add(route_pattern_str)
    
    # Check each API call
    missing_endpoints = []
    for endpoint in api_endpoints:
        # Remove query parameters
        base_endpoint = endpoint.split('?')[0]
        
        # Check if endpoint matches any server route
        found = False
        for route in server_routes:
            if re.match(f"^{route}$", base_endpoint):
                found = True
                break
        
        if not found:
            missing_endpoints.append(base_endpoint)
    
    assert len(missing_endpoints) == 0, (
        f"Found {len(missing_endpoints)} orphan API endpoints: "
        f"{', '.join(missing_endpoints)}"
    )


def test_button_ids_unique():
    """
    Verify all button IDs are unique.
    """
    repo_root = Path(__file__).resolve().parents[1]
    control_html = repo_root / 'ui' / 'control.html'
    
    html_content = control_html.read_text(encoding='utf-8')
    
    # Extract all button IDs
    button_ids = re.findall(r'<button[^>]*id=["\']([^"\']+)["\']', html_content)
    
    # Check for duplicates
    duplicates = [btn_id for btn_id in set(button_ids) if button_ids.count(btn_id) > 1]
    
    assert len(duplicates) == 0, (
        f"Found {len(duplicates)} duplicate button IDs: {', '.join(duplicates)}"
    )


def test_critical_buttons_exist():
    """
    Verify critical operational buttons exist.
    """
    repo_root = Path(__file__).resolve().parents[1]
    control_html = repo_root / 'ui' / 'control.html'
    
    html_content = control_html.read_text(encoding='utf-8')
    
    critical_buttons = [
        'orgRefresh',  # Refresh organism
        'ckoToggleBtn',  # Toggle knowledge overlay
        'acquisitionIntelRunBtn',  # Run acquisition
        'complianceIntelRunBtn',  # Run compliance check
    ]
    
    missing_buttons = []
    for btn_id in critical_buttons:
        if f'id="{btn_id}"' not in html_content and f"id='{btn_id}'" not in html_content:
            missing_buttons.append(btn_id)
    
    assert len(missing_buttons) == 0, (
        f"Missing critical buttons: {', '.join(missing_buttons)}"
    )
