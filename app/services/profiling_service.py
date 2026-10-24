"""
DataPulse Profiling Service
============================
Pure-function Pandas analysis layer.

Takes raw CSV text as input and returns a structured profiling dictionary
with quality metrics, column statistics, and a composite health score.

No file I/O — CSV text is passed in as a Python string so this works
correctly on Vercel's read-only serverless filesystem.
"""
import io
import math
import pandas as pd


def profile_csv(csv_text: str) -> dict:
    """
    Analyze a CSV string with Pandas and return a profiling summary.

    Args:
        csv_text: The raw contents of a CSV file as a Python string.

    Returns:
        A dictionary with the following keys:
            row_count        – number of data rows (excludes header)
            column_count     – number of columns
            columns          – list of per-column dicts (see below)
            total_missing    – total missing/NaN cells across all columns
            duplicate_rows   – number of fully duplicate rows
            health_score     – float 0–100, composite quality indicator

        Each column dict contains:
            name             – column header string
            dtype            – pandas dtype name (e.g. "int64", "object")
            missing_count    – count of NaN/null cells in this column
            missing_pct      – percentage of rows that are null (0–100)

    Raises:
        ValueError   – if the CSV cannot be parsed by Pandas
        UnicodeDecodeError – propagated if text contains invalid encoding
    """
    # Read the CSV from an in-memory string buffer (no disk I/O needed)
    try:
        df = pd.read_csv(io.StringIO(csv_text))
    except pd.errors.ParserError as exc:
        raise ValueError(f"CSV parsing failed: {exc}") from exc
    except pd.errors.EmptyDataError as exc:
        raise ValueError("The CSV file is empty or has no data rows.") from exc

    row_count = len(df)
    column_count = len(df.columns)

    # ----------------------------------------------------------------
    # Per-Column Statistics
    # ----------------------------------------------------------------
    columns_info = []
    for col in df.columns:
        missing_count = int(df[col].isna().sum())
        missing_pct = round((missing_count / row_count * 100), 2) if row_count > 0 else 0.0
        columns_info.append({
            "name": col,
            # Use str() to avoid JSON serialization issues with numpy dtype objects
            "dtype": str(df[col].dtype),
            "missing_count": missing_count,
            "missing_pct": missing_pct,
        })

    # ----------------------------------------------------------------
    # Aggregate Metrics
    # ----------------------------------------------------------------
    total_missing = int(df.isna().sum().sum())
    total_cells = row_count * column_count if column_count > 0 else 1  # avoid division by zero

    # Count rows where every value is identical to another row
    duplicate_rows = int(df.duplicated().sum())

    # ----------------------------------------------------------------
    # Health Score (0–100)
    #
    # Composite formula:
    #   Completeness  (40%) — fraction of cells that are NOT null
    #   Uniqueness    (35%) — fraction of rows that are NOT duplicates
    #   Validity      (25%) — constant 1.0 for now (Phase 3 placeholder;
    #                         schema validation rules come in Phase 5)
    # ----------------------------------------------------------------
    completeness = 1.0 - (total_missing / total_cells) if total_cells > 0 else 1.0
    uniqueness = 1.0 - (duplicate_rows / row_count) if row_count > 0 else 1.0
    validity = 1.0  # placeholder until type-enforcement rules are defined

    raw_score = (0.40 * completeness + 0.35 * uniqueness + 0.25 * validity) * 100
    health_score = round(min(max(raw_score, 0.0), 100.0), 2)

    return {
        "row_count": row_count,
        "column_count": column_count,
        "columns": columns_info,
        "total_missing": total_missing,
        "duplicate_rows": duplicate_rows,
        "health_score": health_score,
    }
