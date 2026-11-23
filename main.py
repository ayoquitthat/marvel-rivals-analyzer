#!/usr/bin/env python3
"""Marvel Rivals Match & Team Analyzer -- interactive command-line application.

Run:  python3 main.py           (creates marvel_rivals.db on first run)
      python3 main.py --reset   (rebuilds the database from the SQL files first)
"""
import sqlite3
import sys

from rivals_app import operations as ops
from rivals_app.db import DB_PATH, build_database, connect, is_initialized
from rivals_app.display import friendly_db_error
from rivals_app.prompts import Cancelled

# (section title, [(menu key, label, function), ...])
MENU = [
    ("Search & browse", [
        ("1", "Search players", ops.search_players),
        ("2", "Browse heroes by role", ops.browse_heroes),
        ("3", "Browse matches (filter by mode and date)", ops.browse_matches),
    ]),
    ("Related data", [
        ("4", "View a match scoreboard", ops.view_match),
        ("5", "View a player's match history", ops.view_player_history),
    ]),
    ("Add", [
        ("6", "Register a new player", ops.register_player),
        ("7", "Record a complete match", ops.record_match),
    ]),
    ("Update & delete", [
        ("8", "Rename a player", ops.rename_player),
        ("9", "Correct a player's stats in a match", ops.correct_stats),
        ("10", "Delete a match", ops.delete_match),
        ("11", "Delete a player with no matches", ops.delete_player),
    ]),
    ("Reports", [
        ("12", "Hero performance", ops.report_heroes),
        ("13", "Player leaderboard", ops.report_leaderboard),
        ("14", "Maps and modes", ops.report_maps),
        ("15", "Team composition win rates", ops.report_compositions),
    ]),
    ("More", [
        ("16", "Player profile and best heroes", ops.player_profile),
        ("17", "Reset database to sample data", ops.reset_database),
    ]),
]
ACTIONS = {key: (label, func) for _, items in MENU for key, label, func in items}


def print_menu():
    print()
    print("=" * 52)
    print(" Marvel Rivals Match & Team Analyzer")
    print("=" * 52)
    for section, items in MENU:
        print(f" {section}")
        for key, label, _ in items:
            print(f"  {key:>2}. {label}")
    print("   0. Exit")


def run_action(conn, key):
    label, func = ACTIONS[key]
    print(f"\n>> {label}   (type q at any prompt to cancel)")
    try:
        func(conn)
    except Cancelled:
        print("Cancelled; nothing was changed.")
    except sqlite3.Error as error:
        # The repository uses `with conn:` so a failed change is already rolled back.
        print(f"Error: {friendly_db_error(error)}")


def main():
    reset = "--reset" in sys.argv[1:]
    try:
        conn = connect(DB_PATH)
    except sqlite3.Error as error:
        print(f"Could not open the database at {DB_PATH}: {friendly_db_error(error)}")
        return 1
    try:
        if reset or not is_initialized(conn):
            print(f"Building database {DB_PATH.name} from schema.sql and insert_data.sql...")
            try:
                build_database(conn)
            except (OSError, sqlite3.Error) as error:
                print(f"Setup failed (are schema.sql and insert_data.sql next to main.py?): "
                      f"{error}")
                return 1
        while True:
            print_menu()
            try:
                choice = input("Choose an option: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if choice == "0":
                break
            if choice not in ACTIONS:
                print("  Please enter a number from the menu (0 to exit).")
                continue
            run_action(conn, choice)
    finally:
        conn.close()
        print("Database connection closed. Goodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
