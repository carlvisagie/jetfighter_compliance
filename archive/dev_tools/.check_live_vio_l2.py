import urllib.request
import sys

try:
    req = urllib.request.Request(
        'https://jetfighter-compliance.onrender.com/ui/assets/js/vio-level2.js',
        headers={'User-Agent': 'curl'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    js = resp.read().decode('utf-8')
    
    # Check for common syntax errors
    if 'function _timeAxis' not in js:
        print("ERROR: _timeAxis function missing")
        sys.exit(1)
    
    if 'function _iconBroker' not in js:
        print("ERROR: _iconBroker function missing")
        sys.exit(1)
    
    # Check for the adaptive spacing logic
    if 'ADAPTIVE TIME AXIS' not in js:
        print("WARNING: Adaptive axis comment missing")
    
    if 'LOG_BASE' not in js:
        print("ERROR: LOG_BASE constant missing (adaptive axis not deployed)")
        sys.exit(1)
        
    # Check for common syntax issues
    lines = js.split('\n')
    for i, line in enumerate(lines, 1):
        if 'stamps.add(g)' in line:
            print(f"ERROR: Line {i}: stamps.add(g) should be stamps.add(t)")
            print(f"  {line.strip()}")
            sys.exit(1)
    
    print(f"JS parsed OK, {len(js)} bytes, {len(lines)} lines")
    print("✓ _timeAxis found")
    print("✓ Adaptive axis logic present")
    print("✓ _iconBroker found")
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
