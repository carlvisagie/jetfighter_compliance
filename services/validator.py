from pathlib import Path
import json
from jsonschema import validate, Draft7Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"

class SchemaRegistry:
    def __init__(self):
        self._cache = {}
    def load(self, name: str):
        if name not in self._cache:
            with open(SCHEMAS / name, "r", encoding="utf-8-sig") as f:
                self._cache[name] = json.load(f)
        return self._cache[name]
    def validate(self, name: str, instance: dict):
        schema = self.load(name)
        Draft7Validator.check_schema(schema)
        validate(instance=instance, schema=schema)

REGISTRY = SchemaRegistry()



