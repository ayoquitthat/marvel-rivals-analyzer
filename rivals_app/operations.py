"""One function per menu option. Each gathers validated input, calls the
repository, and prints the result. Errors are handled by the menu loop."""
from . import repository as repo
from .db import build_database
from .display import heading, print_table
from .prompts import (Cancelled, ask_choice, ask_date, ask_datetime, ask_float,
                      ask_int, ask_text, confirm)

GAMERTAG_MAX_LEN = 24

# (column, label, max value) for per-match stats; all must be >= 0.
STAT_FIELDS = [
    ("kills", "Kills", 100),
    ("deaths", "Deaths", 100),
    ("assists", "Assists", 100),
    ("damage_dealt", "Damage dealt", 200_000),
    ("damage_blocked", "Damage blocked", 200_000),
    ("healing_done", "Healing done", 200_000),
]


# ------------------------------------------------------------- choosers

def choose_player(conn, label="Player (ID or gamertag)"):
    while True:
        player = repo.find_player(conn, ask_text(label))
        if player:
            return player
        print("  No player with that ID or gamertag. Try again, or q to cancel.")


def choose_hero(conn, label="Hero (ID or name)"):
    while True:
        hero = repo.find_hero(conn, ask_text(label))
        if hero:
            return hero
        print("  No hero with that ID or name. Use menu option 2 to see the roster.")


def choose_match(conn):
    while True:
        match = repo.get_match(conn, ask_int("Match ID", min_value=1))
        if match:
            return match
        print("  No match with that ID. Use menu option 3 to browse matches.")


def choose_map(conn):
    heading("Maps")
    print_table(repo.list_maps(conn))
    while True:
        map_row = repo.get_map(conn, ask_int("Map ID", min_value=1))
        if map_row:
            return map_row
        print("  No map with that ID.")


def choose_mode_id(conn):
    """Returns a mode_id, or None for 'all modes'."""
    modes = repo.list_modes(conn)
    names = [m["mode_name"] for m in modes]
    picked = ask_choice("Game mode, blank for all", names, allow_blank=True)
    return next((m["mode_id"] for m in modes if m["mode_name"] == picked), None)


def ask_stats(defaults=None):
    """Prompt for the six stat fields; blank keeps the default (0 for new entries)."""
    defaults = defaults or {}
    return {field: ask_int(f"  {label}", min_value=0, max_value=max_value,
                           default=defaults.get(field, 0))
            for field, label, max_value in STAT_FIELDS}


def show_match(conn, match):
    minutes = (f"{match['duration_seconds'] / 60:.1f} min"
               if match["duration_seconds"] else "duration unknown")
    heading(f"Match {match['match_id']}: {match['map_name']} ({match['mode_name']})")
    print(f"Played {match['played_at']}, {minutes}. "
          f"Team 1: {match['team1_result']}   Team 2: {match['team2_result']}")
    print()
    print_table(repo.match_scoreboard(conn, match["match_id"]),
                empty_message="No participants recorded.")


# ------------------------------------------------------- search / browse

def search_players(conn):
    """1. Search players by part of a gamertag."""
    text = ask_text("Gamertag contains (blank lists everyone)", required=False) or ""
    heading("Players")
    print_table(repo.search_players(conn, text), empty_message="No players match that search.")


def browse_heroes(conn):
    """2. Browse the hero roster, optionally by role."""
    role = ask_choice("Role, blank for all", repo.ROLES, allow_blank=True)
    heading(f"{role or 'All'} heroes")
    print_table(repo.browse_heroes(conn, role))


def browse_matches(conn):
    """3. Browse recent matches with mode and date filters."""
    mode_id = choose_mode_id(conn)
    from_date = ask_date("From date YYYY-MM-DD (blank = no limit)")
    to_date = ask_date("To date   YYYY-MM-DD (blank = no limit)")
    if from_date and to_date and from_date > to_date:
        print("  The start date is after the end date, so nothing can match.")
        return
    limit = ask_int("How many matches to show", min_value=1, max_value=200, default=15)
    heading("Matches, newest first")
    print_table(repo.browse_matches(conn, mode_id, from_date, to_date, limit),
                empty_message="No matches fit those filters.")


# ----------------------------------------------------------- related data

def view_match(conn):
    """4. Full scoreboard of one match (match, map, mode, sides, players, heroes)."""
    show_match(conn, choose_match(conn))


def view_player_history(conn):
    """5. One player's recent matches with map, hero, result and stats."""
    player = choose_player(conn)
    heading(f"Recent matches for {player['gamertag']}")
    print_table(repo.player_history(conn, player["player_id"]),
                empty_message="This player has no recorded matches yet.")


# ------------------------------------------------------------------- add

def register_player(conn):
    """6. Register a new player."""
    while True:
        gamertag = ask_text("New gamertag", max_len=GAMERTAG_MAX_LEN)
        if repo.gamertag_taken(conn, gamertag):
            print("  That gamertag is already registered (names are case-insensitive).")
            continue
        break
    player_id = repo.add_player(conn, gamertag)
    print(f"Registered {gamertag} as player {player_id}.")


def record_match(conn):
    """7. Record a complete match: match, both sides and every participant, in one transaction."""
    map_row = choose_map(conn)
    played_at = ask_datetime("Played at YYYY-MM-DD HH:MM")
    minutes = ask_float("Duration in minutes (blank if unknown)", min_value=1, max_value=60,
                        required=False)
    duration_seconds = round(minutes * 60) if minutes is not None else None
    team1_result = ask_choice("Team 1 result", repo.RESULTS)
    print(f"  Team 2 result will be {repo.OPPOSITE_RESULT[team1_result]}.")

    participants, players_in_match = [], set()
    for team in (1, 2):
        heading(f"Team {team}")
        count = ask_int(f"Number of players on Team {team}", min_value=1, max_value=6, default=6)
        heroes_on_side = set()
        for slot in range(1, count + 1):
            print(f"Team {team}, player {slot} of {count}")
            while True:
                player = choose_player(conn, "  Player (ID or gamertag)")
                if player["player_id"] not in players_in_match:
                    break
                print("  That player is already in this match.")
            while True:
                hero = choose_hero(conn, "  Hero (ID or name)")
                if hero["hero_id"] not in heroes_on_side:
                    break
                print("  That hero is already picked on this side.")
            players_in_match.add(player["player_id"])
            heroes_on_side.add(hero["hero_id"])
            participants.append({"player_id": player["player_id"], "team_number": team,
                                 "hero_id": hero["hero_id"], "gamertag": player["gamertag"],
                                 "hero_name": hero["hero_name"], **ask_stats()})

    heading("Review")
    print(f"{map_row['map_name']} ({map_row['mode_name']}), {played_at}, "
          f"Team 1 {team1_result} / Team 2 {repo.OPPOSITE_RESULT[team1_result]}")
    for p in participants:
        print(f"  Team {p['team_number']}: {p['gamertag']} as {p['hero_name']} "
              f"({p['kills']}/{p['deaths']}/{p['assists']})")
    if not confirm("Save this match?"):
        print("Match discarded; nothing was saved.")
        return
    match_id = repo.record_match(conn, map_row["map_id"], played_at, duration_seconds,
                                 team1_result, participants)
    print(f"Saved as match {match_id}, with both sides and {len(participants)} players.")


# ------------------------------------------------------- update / delete

def rename_player(conn):
    """8. Change a player's gamertag."""
    player = choose_player(conn)
    while True:
        new_tag = ask_text(f"New gamertag for {player['gamertag']}", max_len=GAMERTAG_MAX_LEN)
        if new_tag == player["gamertag"]:
            print("  That is already the current gamertag.")
            continue
        if repo.gamertag_taken(conn, new_tag, exclude_player_id=player["player_id"]):
            print("  That gamertag is already registered.")
            continue
        break
    repo.rename_player(conn, player["player_id"], new_tag)
    print(f"Renamed {player['gamertag']} to {new_tag}.")


def correct_stats(conn):
    """9. Fix a player's stats in a match (blank keeps the current value)."""
    match = choose_match(conn)
    show_match(conn, match)
    while True:
        player = choose_player(conn, "Player to correct (ID or gamertag)")
        current = repo.get_participant(conn, match["match_id"], player["player_id"])
        if current:
            break
        print("  That player did not play in this match.")
    print(f"Editing {player['gamertag']} ({current['hero_name']}). Press Enter to keep a value.")
    new_stats = ask_stats(defaults=dict(current))
    if all(new_stats[f] == current[f] for f, _, _ in STAT_FIELDS):
        print("No values changed.")
        return
    repo.update_participant_stats(conn, match["match_id"], player["player_id"], new_stats)
    print("Stats updated.")


def delete_match(conn):
    """10. Delete a match recorded by mistake (its sides and participants go with it)."""
    match = choose_match(conn)
    show_match(conn, match)
    if not confirm(f"Permanently delete match {match['match_id']} and all its player stats?"):
        print("Nothing was deleted.")
        return
    repo.delete_match(conn, match["match_id"])
    print(f"Match {match['match_id']} deleted.")


def delete_player(conn):
    """11. Remove a player who has no recorded matches."""
    player = choose_player(conn)
    played = repo.count_player_matches(conn, player["player_id"])
    if played:
        print(f"  {player['gamertag']} appears in {played} recorded match(es), so deleting "
              "them would break those records. Delete those matches first.")
        return
    if confirm(f"Delete player {player['gamertag']}?"):
        repo.delete_player(conn, player["player_id"])
        print(f"Deleted {player['gamertag']}.")
    else:
        print("Nothing was deleted.")


# ---------------------------------------------------------------- reports

def report_heroes(conn):
    """12. Hero win rates, from the v_hero_performance view."""
    role = ask_choice("Role, blank for all", repo.ROLES, allow_blank=True)
    min_picks = ask_int("Minimum times picked", min_value=0, max_value=1000, default=5)
    heading("Hero performance (best win rate first)")
    print_table(repo.hero_performance(conn, role, min_picks),
                empty_message="No heroes have been picked that often.")


def report_leaderboard(conn):
    """13. Player leaderboard."""
    min_matches = ask_int("Minimum matches played", min_value=1, max_value=1000, default=5)
    sort_key = ask_choice("Sort by", list(repo.LEADERBOARD_SORTS), default="win rate")
    heading(f"Player leaderboard by {sort_key}")
    print_table(repo.player_leaderboard(conn, min_matches, sort_key),
                empty_message="No players have that many matches.")


def report_maps(conn):
    """14. Map and mode report."""
    heading("Maps and modes")
    print_table(repo.map_mode_report(conn))


def report_compositions(conn):
    """15. Team composition win rates."""
    min_sides = ask_int("Minimum times a composition was played", min_value=1, max_value=1000,
                        default=3)
    heading("Team compositions (V = Vanguard, D = Duelist, S = Strategist)")
    print_table(repo.team_composition_report(conn, min_sides),
                empty_message="No composition was played that often.")


# ------------------------------------------------------- additional ops

def player_profile(conn):
    """16. Player profile: overall record, best heroes and role breakdown."""
    player = choose_player(conn)
    summary = repo.player_summary(conn, player["player_id"])
    heading(f"Profile: {player['gamertag']} (player {player['player_id']}, "
            f"registered {player['added_on']})")
    if not summary["matches"]:
        print("  No matches recorded yet.")
        return
    print(f"Record {summary['wins']}W-{summary['losses']}L-{summary['draws']}D over "
          f"{summary['matches']} matches ({summary['win_rate_pct']}% wins). "
          f"Avg KDA {summary['avg_kda']}, avg damage {summary['avg_damage']:,}, "
          f"avg healing {summary['avg_healing']:,}.")
    heading("Best heroes (2+ games)")
    print_table(repo.player_best_heroes(conn, player["player_id"]),
                empty_message="No hero played twice yet.")
    heading("By role")
    print_table(repo.player_role_breakdown(conn, player["player_id"]))


def reset_database(conn):
    """17. Rebuild the database from schema.sql and insert_data.sql."""
    if not confirm("This erases every change and reloads the sample data. Continue?"):
        print("Nothing was changed.")
        return
    build_database(conn)
    print("Database rebuilt from schema.sql and insert_data.sql.")


__all__ = ["Cancelled"]
