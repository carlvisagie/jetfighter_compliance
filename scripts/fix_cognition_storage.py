"""Fix cognition/storage.py to use defensive framework."""
import re
from pathlib import Path

file_path = Path("services/cognition/storage.py")
content = file_path.read_text(encoding="utf-8")

# Replace document write (lines 202-222)
content = re.sub(
    r'try:\s+with open\(doc_path, "w", encoding="utf-8"\) as f:\s+f\.write\(md_content\)\s+except OSError as e:.*?raise',
    '''# Write document with defensive framework
            safe_write_text(
                Path(doc_path),
                md_content,
                component="cognition",
                context=f"project {project_id} document {doc.doc_id}",
                severity="critical"
            )''',
    content,
    flags=re.DOTALL
)

# Replace summary/next_actions write (lines 238-256)
content = re.sub(
    r'try:\s+with open\(cognition_dir / "cognition_summary\.json", "w", encoding="utf-8"\) as f:\s+f\.write\(summary\.model_dump_json\(indent=2\)\).*?raise',
    '''# Write all cognition output files with defensive framework
        safe_write_text(
            cognition_dir / "cognition_summary.json",
            summary.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} summary",
            severity="critical"
        )
        
        safe_write_text(
            cognition_dir / "next_actions.json",
            "[]",
            component="cognition",
            context=f"project {project_id} next_actions",
            severity="critical"
        )''',
    content,
    flags=re.DOTALL
)

# Replace explanation write (lines 271-285)
content = re.sub(
    r'try:\s+with open\(cognition_dir / "generation_explanation\.json", "w", encoding="utf-8"\) as f:\s+json\.dump\(explanations, f, indent=2\).*?# Non-critical, continue',
    '''# Write explanation with defensive framework  
        safe_write_json(
            cognition_dir / "generation_explanation.json",
            explanations,
            component="cognition",
            context=f"project {project_id} generation_explanation",
            severity="warning"
        )''',
    content,
    flags=re.DOTALL
)

# Replace metrics write (lines 288-303)
content = re.sub(
    r'# 7\. Write metrics\.json\s+metrics = compute_metrics\(state, resolutions\)\s+try:.*?# Non-critical, continue',
    '''# Write metrics with defensive framework
        metrics = compute_metrics(state, resolutions)
        safe_write_text(
            cognition_dir / "metrics.json",
            metrics.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} metrics",
            severity="warning"
        )''',
    content,
    flags=re.DOTALL
)

# Replace validation write (lines 317-332)
content = re.sub(
    r'validation = build_validation_report\(project_id, state, resolutions, docs\)\s+try:.*?raise',
    '''# Write validation report with defensive framework
        validation = build_validation_report(project_id, state, resolutions, docs)
        safe_write_text(
            cognition_dir / "validation_report.json",
            validation.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} validation_report",
            severity="critical"
        )''',
    content,
    flags=re.DOTALL
)

# Replace score/gate write (lines 348-368)
content = re.sub(
    r'# 9\. Write organism_score\.json and launch_gate\.json\s+scorecard = calculate_scorecard.*?raise',
    '''# Write organism_score and launch_gate with defensive framework
        scorecard = calculate_scorecard(state, metrics, validation)
        safe_write_text(
            cognition_dir / "organism_score.json",
            scorecard.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} organism_score",
            severity="critical"
        )
        
        gate = evaluate_launch_gate(scorecard, metrics, validation)
        safe_write_text(
            cognition_dir / "launch_gate.json",
            gate.model_dump_json(indent=2),
            component="cognition",
            context=f"project {project_id} launch_gate",
            severity="critical"
        )''',
    content,
    flags=re.DOTALL
)

file_path.write_text(content, encoding="utf-8")
print(f"Fixed {file_path}")
