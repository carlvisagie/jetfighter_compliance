import sys
import json
import logging
from pathlib import Path

from services.compliance_intelligence import run_compliance_intel_cycle
from services.organism_state.state import compute_organism_state

def main():
    # Setup basic logging to see any fetcher errors
    logging.basicConfig(level=logging.INFO)
    
    print("--- RUNNING CYCLE ---")
    summary = run_compliance_intel_cycle()
    print(summary.model_dump_json(indent=2))

    print("--- ORGANISM STATE ---")
    state = compute_organism_state()
    print(json.dumps({
        "health_state": state.get("health_state"),
        "current_bottleneck": state.get("current_bottleneck"),
        "next_recommended_action": state.get("next_recommended_action"),
        "compliance_intelligence": state.get("compliance_intelligence")
    }, indent=2))

if __name__ == "__main__":
    main()
