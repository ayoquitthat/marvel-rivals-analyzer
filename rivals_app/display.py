"""Readable output: aligned tables, headings and friendly database error messages."""
import sqlite3

# Column headings that read better than a simple title-cased column name.
HEADING_OVERRIDES = {
    "win_rate_pct": "Win %",
    "kda": "KDA",
    "avg_kda": "Avg KDA",
    "team1_result": "Team 1",
    "team2_result": "Team 2",
    "match_id": "Match",
    "player_id": "ID",
    "hero_id": "ID",
    "map_id": "ID",
    "mode_id": "ID",
}


def heading(text):
    print()
    print(text)
    print("-" * len(text))


def _label(column):
    return HEADING_OVERRIDES.get(column, column.replace("_", " ").title())


def _cell(column, value):
    """Format one value; the column name decides decimals and thousands separators."""
    if value is None:
        return "-"
    if isinstance(value, float):
        decimals = 1 if ("pct" in column or "minutes" in column) else 2
        return f"{value:,.{decimals}f}"
    if isinstance(value, int):
        # IDs are labels, not quantities, so they get no thousands separator.
        return str(value) if column.endswith("id") else f"{value:,}"
    return str(value)


def print_table(rows, empty_message="No results found."):
    """Print sqlite3.Row results as an aligned table; numbers are right-aligned."""
    if not rows:
        print(f"  {empty_message}")
        return
    columns = list(rows[0].keys())
    cells = [[_cell(c, row[c]) for c in columns] for row in rows]
    numeric = [all(isinstance(row[c], (int, float)) or row[c] is None for row in rows)
               for c in columns]
    labels = [_label(c) for c in columns]
    widths = [max(len(labels[i]), *(len(r[i]) for r in cells)) for i in range(len(columns))]

    def line(values):
        return "  ".join(v.rjust(w) if num else v.ljust(w)
                         for v, w, num in zip(values, widths, numeric)).rstrip()

    print(line(labels))
    print("  ".join("-" * w for w in widths))
    for r in cells:
        print(line(r))
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")


def friendly_db_error(error):
    """Turn a sqlite3 exception into a message a user can act on (no stack trace)."""
    text = str(error)
    if isinstance(error, sqlite3.IntegrityError):
        if "UNIQUE" in text:
            return "That value already exists. Please choose a different one."
        if "FOREIGN KEY" in text:
            return ("That change would break a link between records "
                    "(a referenced record is missing, or this record is still in use).")
        if "CHECK" in text:
            return "A value is outside the allowed range for that field."
        if "NOT NULL" in text:
            return "A required value is missing."
        return "The change breaks a database rule and was not saved."
    if isinstance(error, sqlite3.OperationalError) and "locked" in text:
        return "The database is busy (open in another program?). Please try again."
    return "The database operation failed and nothing was changed."
