"""All SQL used by the application.

Every value that comes from the user is passed as a ? placeholder, never
pasted into the SQL text. The only SQL built at run time is the ORDER BY
clause of the leaderboard, which is chosen from a fixed whitelist below.

Functions that change data run inside `with conn:`, which commits on
success and rolls back if any statement fails.
"""
from datetime import date

ROLES = ("Vanguard", "Duelist", "Strategist")
RESULTS = ("WIN", "LOSS", "DRAW")
OPPOSITE_RESULT = {"WIN": "LOSS", "LOSS": "WIN", "DRAW": "DRAW"}


# ---------------------------------------------------------------- lookups

def find_player(conn, text):
    """Look up a player by numeric ID or by gamertag (case-insensitive)."""
    if text.isdigit():
        row = conn.execute(
            "SELECT player_id, gamertag, added_on FROM player WHERE player_id = ?",
            (int(text),),
        ).fetchone()
        if row:
            return row
    return conn.execute(
        "SELECT player_id, gamertag, added_on FROM player WHERE gamertag = ? COLLATE NOCASE",
        (text,),
    ).fetchone()


def find_hero(conn, text):
    """Look up a hero by numeric ID or by name (case-insensitive)."""
    if text.isdigit():
        row = conn.execute(
            "SELECT hero_id, hero_name, role FROM hero WHERE hero_id = ?", (int(text),)
        ).fetchone()
        if row:
            return row
    return conn.execute(
        "SELECT hero_id, hero_name, role FROM hero WHERE hero_name = ? COLLATE NOCASE",
        (text,),
    ).fetchone()


def gamertag_taken(conn, gamertag, exclude_player_id=None):
    """Case-insensitive duplicate check, so 'novastrike' can't sit beside 'NovaStrike'."""
    row = conn.execute(
        "SELECT 1 FROM player WHERE gamertag = ? COLLATE NOCASE AND player_id IS NOT ?",
        (gamertag, exclude_player_id),
    ).fetchone()
    return row is not None


def list_modes(conn):
    return conn.execute("SELECT mode_id, mode_name FROM game_mode ORDER BY mode_name").fetchall()


def list_maps(conn):
    return conn.execute(
        """SELECT mp.map_id, mp.map_name, g.mode_name
           FROM map mp JOIN game_mode g ON g.mode_id = mp.mode_id
           ORDER BY g.mode_name, mp.map_name"""
    ).fetchall()


def get_map(conn, map_id):
    return conn.execute(
        """SELECT mp.map_id, mp.map_name, g.mode_name
           FROM map mp JOIN game_mode g ON g.mode_id = mp.mode_id
           WHERE mp.map_id = ?""",
        (map_id,),
    ).fetchone()


def get_match(conn, match_id):
    """Match header: when, where, how long, and each side's result."""
    return conn.execute(
        """SELECT m.match_id, m.played_at, g.mode_name, mp.map_name, m.duration_seconds,
                  t1.result AS team1_result, t2.result AS team2_result
           FROM match m
           JOIN map mp        ON mp.map_id  = m.map_id
           JOIN game_mode g   ON g.mode_id  = mp.mode_id
           JOIN match_team t1 ON t1.match_id = m.match_id AND t1.team_number = 1
           JOIN match_team t2 ON t2.match_id = m.match_id AND t2.team_number = 2
           WHERE m.match_id = ?""",
        (match_id,),
    ).fetchone()


def get_participant(conn, match_id, player_id):
    return conn.execute(
        """SELECT s.*, h.hero_name
           FROM match_participant s JOIN hero h ON h.hero_id = s.hero_id
           WHERE s.match_id = ? AND s.player_id = ?""",
        (match_id, player_id),
    ).fetchone()


def count_player_matches(conn, player_id):
    return conn.execute(
        "SELECT COUNT(*) FROM match_participant WHERE player_id = ?", (player_id,)
    ).fetchone()[0]


# ---------------------------------------------------------- search / browse

def search_players(conn, text):
    """Players whose gamertag contains `text`, with how many matches each has played.

    LEFT JOIN keeps players who have never played (they show 0 matches).
    """
    # Escape LIKE wildcards so a search for "_" or "%" is taken literally.
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return conn.execute(
        """SELECT p.player_id, p.gamertag, p.added_on, COUNT(s.match_id) AS matches_played
           FROM player p
           LEFT JOIN match_participant s ON s.player_id = p.player_id
           WHERE p.gamertag LIKE ? ESCAPE '\\'
           GROUP BY p.player_id, p.gamertag, p.added_on
           ORDER BY p.gamertag""",
        (f"%{escaped}%",),
    ).fetchall()


def browse_heroes(conn, role=None):
    """Hero roster, optionally filtered to one role. `role` None means all roles."""
    return conn.execute(
        """SELECT hero_id, hero_name, role
           FROM hero
           WHERE (? IS NULL OR role = ?)
           ORDER BY role, hero_name""",
        (role, role),
    ).fetchall()


def browse_matches(conn, mode_id=None, from_date=None, to_date=None, limit=15):
    """Recent matches, newest first, with optional game-mode and date filters."""
    return conn.execute(
        """SELECT m.match_id, m.played_at, g.mode_name, mp.map_name,
                  ROUND(m.duration_seconds / 60.0, 1) AS minutes,
                  t1.result AS team1_result,
                  (SELECT COUNT(*) FROM match_participant s
                    WHERE s.match_id = m.match_id) AS players
           FROM match m
           JOIN map mp        ON mp.map_id  = m.map_id
           JOIN game_mode g   ON g.mode_id  = mp.mode_id
           JOIN match_team t1 ON t1.match_id = m.match_id AND t1.team_number = 1
           WHERE (? IS NULL OR g.mode_id = ?)
             AND (? IS NULL OR date(m.played_at) >= ?)
             AND (? IS NULL OR date(m.played_at) <= ?)
           ORDER BY m.played_at DESC
           LIMIT ?""",
        (mode_id, mode_id, from_date, from_date, to_date, to_date, limit),
    ).fetchall()


# ------------------------------------------------------------ related data

def match_scoreboard(conn, match_id):
    """Every participant in a match with hero and stats (v_player_match_stats joins 7 tables)."""
    return conn.execute(
        """SELECT team_number AS team, gamertag, hero_name, role,
                  kills, deaths, assists, kda,
                  damage_dealt, damage_blocked, healing_done
           FROM v_player_match_stats
           WHERE match_id = ?
           ORDER BY team_number, damage_dealt DESC""",
        (match_id,),
    ).fetchall()


def player_history(conn, player_id, limit=20):
    """A player's recent matches: map, mode, hero, result and stats."""
    return conn.execute(
        """SELECT match_id, played_at, mode_name, map_name, hero_name, result,
                  kills, deaths, assists, kda, damage_dealt
           FROM v_player_match_stats
           WHERE player_id = ?
           ORDER BY played_at DESC
           LIMIT ?""",
        (player_id, limit),
    ).fetchall()


# ---------------------------------------------------------------- changes

def add_player(conn, gamertag, added_on=None):
    with conn:
        cur = conn.execute(
            "INSERT INTO player (gamertag, added_on) VALUES (?, ?)",
            (gamertag, added_on or date.today().isoformat()),
        )
    return cur.lastrowid


def rename_player(conn, player_id, new_gamertag):
    with conn:
        cur = conn.execute(
            "UPDATE player SET gamertag = ? WHERE player_id = ?", (new_gamertag, player_id)
        )
    return cur.rowcount


def delete_player(conn, player_id):
    """Fails with an IntegrityError (foreign key) if the player still has matches."""
    with conn:
        cur = conn.execute("DELETE FROM player WHERE player_id = ?", (player_id,))
    return cur.rowcount


def update_participant_stats(conn, match_id, player_id, stats):
    with conn:
        cur = conn.execute(
            """UPDATE match_participant
               SET kills = ?, deaths = ?, assists = ?,
                   damage_dealt = ?, damage_blocked = ?, healing_done = ?
               WHERE match_id = ? AND player_id = ?""",
            (stats["kills"], stats["deaths"], stats["assists"],
             stats["damage_dealt"], stats["damage_blocked"], stats["healing_done"],
             match_id, player_id),
        )
    return cur.rowcount


def delete_match(conn, match_id):
    """ON DELETE CASCADE removes the match's two sides and all participant rows."""
    with conn:
        cur = conn.execute("DELETE FROM match WHERE match_id = ?", (match_id,))
    return cur.rowcount


def record_match(conn, map_id, played_at, duration_seconds, team1_result, participants):
    """Insert a complete match as ONE transaction.

    A match is only valid with its match row, both match_team sides, and
    every participant. If any insert fails (bad ID, constraint), the whole
    match is rolled back so reports never see a half-recorded match.

    participants: list of dicts with player_id, team_number, hero_id and
    the six stat fields.
    """
    with conn:  # BEGIN ... COMMIT, or ROLLBACK on any exception
        cur = conn.execute(
            "INSERT INTO match (map_id, played_at, duration_seconds) VALUES (?, ?, ?)",
            (map_id, played_at, duration_seconds),
        )
        match_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO match_team (match_id, team_number, result) VALUES (?, ?, ?)",
            [(match_id, 1, team1_result), (match_id, 2, OPPOSITE_RESULT[team1_result])],
        )
        conn.executemany(
            """INSERT INTO match_participant
                 (match_id, player_id, team_number, hero_id, kills, deaths, assists,
                  damage_dealt, damage_blocked, healing_done)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(match_id, p["player_id"], p["team_number"], p["hero_id"],
              p["kills"], p["deaths"], p["assists"],
              p["damage_dealt"], p["damage_blocked"], p["healing_done"])
             for p in participants],
        )
    return match_id


# ---------------------------------------------------------------- reports

def hero_performance(conn, role=None, min_picks=1):
    """Pick count and win rate per hero, from the v_hero_performance view."""
    return conn.execute(
        """SELECT hero_name, role, times_picked, wins, win_rate_pct,
                  avg_kills, avg_deaths, avg_assists
           FROM v_hero_performance
           WHERE (? IS NULL OR role = ?)
             AND times_picked >= ?
           ORDER BY win_rate_pct DESC, times_picked DESC""",
        (role, role, min_picks),
    ).fetchall()


# ORDER BY cannot use a ? placeholder, so the user picks a key and the
# clause comes from this fixed whitelist -- user text never reaches the SQL.
LEADERBOARD_SORTS = {
    "win rate": "win_rate_pct DESC, avg_kda DESC",
    "kda": "avg_kda DESC, win_rate_pct DESC",
    "damage": "avg_damage DESC, win_rate_pct DESC",
}


def player_leaderboard(conn, min_matches=5, sort_key="win rate"):
    order_by = LEADERBOARD_SORTS[sort_key]
    return conn.execute(
        f"""SELECT gamertag,
                   COUNT(*)                                          AS matches,
                   SUM(result = 'WIN')                               AS wins,
                   ROUND(100.0 * SUM(result = 'WIN') / COUNT(*), 1)  AS win_rate_pct,
                   ROUND(AVG(kda), 2)                                AS avg_kda,
                   CAST(ROUND(AVG(damage_dealt)) AS INTEGER)         AS avg_damage
            FROM v_player_match_stats
            GROUP BY player_id, gamertag
            HAVING COUNT(*) >= ?
            ORDER BY {order_by}""",
        (min_matches,),
    ).fetchall()


def map_mode_report(conn):
    """Matches, average length and most-picked hero per map; unplayed maps show 0."""
    return conn.execute(
        """SELECT g.mode_name, mp.map_name,
                  COUNT(m.match_id)                       AS matches,
                  ROUND(AVG(m.duration_seconds) / 60.0, 1) AS avg_minutes,
                  (SELECT h.hero_name
                     FROM match_participant s
                     JOIN match m2 ON m2.match_id = s.match_id
                     JOIN hero h   ON h.hero_id   = s.hero_id
                    WHERE m2.map_id = mp.map_id
                    GROUP BY h.hero_id, h.hero_name
                    ORDER BY COUNT(*) DESC, h.hero_name
                    LIMIT 1)                              AS most_picked_hero
           FROM map mp
           JOIN game_mode g ON g.mode_id = mp.mode_id
           LEFT JOIN match m ON m.map_id = mp.map_id
           GROUP BY mp.map_id, g.mode_name, mp.map_name
           ORDER BY g.mode_name, matches DESC, mp.map_name"""
    ).fetchall()


def team_composition_report(conn, min_sides=1):
    """Win rate by role makeup (e.g. 2 Vanguard / 2 Duelist / 2 Strategist).

    A composition is not stored; it is derived from the heroes on one side.
    """
    return conn.execute(
        """WITH side AS (
               SELECT s.match_id, s.team_number, mt.result,
                      SUM(h.role = 'Vanguard')   AS vanguards,
                      SUM(h.role = 'Duelist')    AS duelists,
                      SUM(h.role = 'Strategist') AS strategists
               FROM match_participant s
               JOIN hero h        ON h.hero_id   = s.hero_id
               JOIN match_team mt ON mt.match_id = s.match_id
                                 AND mt.team_number = s.team_number
               GROUP BY s.match_id, s.team_number, mt.result
           )
           SELECT vanguards || 'V / ' || duelists || 'D / ' || strategists || 'S' AS composition,
                  COUNT(*)                                          AS sides,
                  SUM(result = 'WIN')                               AS wins,
                  ROUND(100.0 * SUM(result = 'WIN') / COUNT(*), 1)  AS win_rate_pct
           FROM side
           GROUP BY vanguards, duelists, strategists
           HAVING COUNT(*) >= ?
           ORDER BY win_rate_pct DESC, sides DESC""",
        (min_sides,),
    ).fetchall()


# ------------------------------------------------------- player profile

def player_summary(conn, player_id):
    return conn.execute(
        """SELECT COUNT(*)                                          AS matches,
                  SUM(result = 'WIN')                               AS wins,
                  SUM(result = 'LOSS')                              AS losses,
                  SUM(result = 'DRAW')                              AS draws,
                  ROUND(100.0 * SUM(result = 'WIN') / COUNT(*), 1)  AS win_rate_pct,
                  ROUND(AVG(kda), 2)                                AS avg_kda,
                  CAST(ROUND(AVG(damage_dealt)) AS INTEGER)         AS avg_damage,
                  CAST(ROUND(AVG(healing_done)) AS INTEGER)         AS avg_healing
           FROM v_player_match_stats
           WHERE player_id = ?""",
        (player_id,),
    ).fetchone()


def player_best_heroes(conn, player_id, min_games=2, limit=5):
    """The player's heroes ranked by win rate, ignoring one-off picks."""
    return conn.execute(
        """SELECT hero_name, role,
                  COUNT(*)                                          AS games,
                  SUM(result = 'WIN')                               AS wins,
                  ROUND(100.0 * SUM(result = 'WIN') / COUNT(*), 1)  AS win_rate_pct,
                  ROUND(AVG(kda), 2)                                AS avg_kda
           FROM v_player_match_stats
           WHERE player_id = ?
           GROUP BY hero_name, role
           HAVING COUNT(*) >= ?
           ORDER BY win_rate_pct DESC, games DESC
           LIMIT ?""",
        (player_id, min_games, limit),
    ).fetchall()


def player_role_breakdown(conn, player_id):
    return conn.execute(
        """SELECT role,
                  COUNT(*)                                          AS games,
                  ROUND(100.0 * SUM(result = 'WIN') / COUNT(*), 1)  AS win_rate_pct,
                  ROUND(AVG(kda), 2)                                AS avg_kda
           FROM v_player_match_stats
           WHERE player_id = ?
           GROUP BY role
           ORDER BY games DESC""",
        (player_id,),
    ).fetchall()
