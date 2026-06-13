"""Batch migrate simple single-write files to defensive wiring."""
import re
from pathlib import Path

# Files with single .write_text() calls
files_to_migrate = [
    ("services/acquisition/export.py", "acquisition_export", "export generation"),
    ("services/acquisition/ideal_customer_profile.py", "acquisition_icp", "ICP update"),
    ("services/acquisition/outreach_safety.py", "acquisition_safety", "outreach safety check"),
    ("services/acquisition/connectors/reddit/learning.py", "reddit_learning", "Reddit learning update"),
    ("services/acquisition/connectors/reddit/poster.py", "reddit_poster", "Reddit post"),
    ("services/acquisition/connectors/reddit/__init__.py", "reddit_connector", "Reddit connector state"),
    ("services/acquisition/social_intelligence/subreddit_culture.py", "subreddit_culture", "culture analysis"),
]

for filepath, component, context in files_to_migrate:
    path = Path(filepath)
    if not path.exists():
        print(f"SKIP: {filepath} (not found)")
        continue
    
    content = path.read_text(encoding="utf-8")
    
    # Pattern 1: path.write_text(content, encoding="utf-8")
    pattern1 = r'(\s+)(\w+\.write_text\()([^,]+)(,\s*encoding="utf-8"\))'
    
    def replace_write(match):
        indent = match.group(1)
        varname = match.group(2).split('.')[0]
        content_arg = match.group(3)
        
        return (
            f'{indent}from services.defensive_wiring import safe_write_text\n'
            f'{indent}safe_write_text(\n'
            f'{indent}    {varname},\n'
            f'{indent}    {content_arg},\n'
            f'{indent}    component="{component}",\n'
            f'{indent}    context="{context}",\n'
            f'{indent}    severity="warning"\n'
            f'{indent})'
        )
    
    modified = re.sub(pattern1, replace_write, content)
    
    if modified != content:
        path.write_text(modified, encoding="utf-8")
        print(f"OK: {filepath}")
    else:
        print(f"NO CHANGE: {filepath}")

print("\nBatch migration complete.")
