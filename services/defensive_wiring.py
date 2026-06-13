"""Defensive wiring utilities - automatic telemetry for file operations."""
from pathlib import Path
from typing import Any, Callable, Optional
import json


def safe_write_text(
    path: Path,
    content: str,
    *,
    component: str,
    context: str = "",
    encoding: str = "utf-8",
    severity: str = "critical"
) -> None:
    """Write text file with automatic error telemetry.
    
    Args:
        path: File path to write
        content: Text content to write
        component: Component name for telemetry (e.g., "acquisition", "alerts")
        context: Human-readable context for the operation (e.g., "ICP update", "digest generation")
        encoding: File encoding (default: utf-8)
        severity: Telemetry severity on failure (default: critical)
    
    Raises:
        OSError: On write failure (after emitting telemetry)
    """
    try:
        path.write_text(content, encoding=encoding)
    except OSError as e:
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                component,
                "file_write_failed",
                severity=severity,
                metadata={
                    "path": str(path),
                    "context": context,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise


def safe_write_json(
    path: Path,
    data: Any,
    *,
    component: str,
    context: str = "",
    indent: int = 2,
    severity: str = "critical"
) -> None:
    """Write JSON file with automatic error telemetry.
    
    Args:
        path: File path to write
        data: Data to serialize as JSON
        component: Component name for telemetry
        context: Human-readable context for the operation
        indent: JSON indentation (default: 2)
        severity: Telemetry severity on failure (default: critical)
    
    Raises:
        OSError: On write failure (after emitting telemetry)
    """
    try:
        path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                component,
                "json_write_failed",
                severity=severity,
                metadata={
                    "path": str(path),
                    "context": context,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise


def safe_append_jsonl(
    path: Path,
    record: dict,
    *,
    component: str,
    context: str = "",
    severity: str = "critical"
) -> None:
    """Append to JSONL file with automatic error telemetry.
    
    Args:
        path: JSONL file path
        record: Dictionary to append as JSON line
        component: Component name for telemetry
        context: Human-readable context
        severity: Telemetry severity on failure (default: critical)
    
    Raises:
        OSError: On write failure (after emitting telemetry)
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                component,
                "jsonl_append_failed",
                severity=severity,
                metadata={
                    "path": str(path),
                    "context": context,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        except Exception:
            pass
        raise


def safe_file_operation(
    operation: Callable,
    *,
    component: str,
    context: str,
    severity: str = "critical",
    **kwargs
) -> Any:
    """Execute file operation with automatic error telemetry.
    
    Generic wrapper for any file operation.
    
    Args:
        operation: Callable that performs the file operation
        component: Component name for telemetry
        context: Human-readable context
        severity: Telemetry severity on failure
        **kwargs: Additional metadata for telemetry
    
    Returns:
        Result of the operation
    
    Raises:
        Exception: Original exception (after emitting telemetry)
    """
    try:
        return operation()
    except (OSError, IOError) as e:
        try:
            from services.memory.telemetry import emit_telemetry
            emit_telemetry(
                component,
                "file_operation_failed",
                severity=severity,
                metadata={
                    "context": context,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    **kwargs
                }
            )
        except Exception:
            pass
        raise


# Convenience function for backwards compatibility
def defensive_write(path: Path, content: str, component: str, context: str = "") -> None:
    """Alias for safe_write_text for backwards compatibility."""
    safe_write_text(path, content, component=component, context=context)
