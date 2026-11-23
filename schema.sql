-- =====================================================================
-- Marvel Rivals Match & Team Analyzer -- Deliverable 3: schema.sql
-- DBMS: SQLite 3 (3.25+ recommended)
-- Run FIRST, then insert_data.sql.
-- =====================================================================

-- SQLite does NOT enforce foreign keys unless this is set on every connection.
PRAGMA foreign_keys = ON;

-- ---------- Clean-up (children first, so FKs never block a drop) ----------
DROP VIEW  IF EXISTS v_player_match_stats;
DROP VIEW  IF EXISTS v_hero_performance;
DROP INDEX IF EXISTS idx_participant_player;
DROP INDEX IF EXISTS idx_participant_hero;
DROP INDEX IF EXISTS idx_match_map_played;
DROP TABLE IF EXISTS match_participant;
DROP TABLE IF EXISTS match_team;
DROP TABLE IF EXISTS match;
DROP TABLE IF EXISTS map;
DROP TABLE IF EXISTS game_mode;
DROP TABLE IF EXISTS hero;
DROP TABLE IF EXISTS player;

-- ---------- Tables ----------
CREATE TABLE game_mode (
    mode_id    INTEGER PRIMARY KEY,
    mode_name  TEXT    NOT NULL UNIQUE
);

CREATE TABLE map (
    map_id     INTEGER PRIMARY KEY,
    map_name   TEXT    NOT NULL UNIQUE,
    mode_id    INTEGER NOT NULL,
    FOREIGN KEY (mode_id) REFERENCES game_mode(mode_id)
);

CREATE TABLE player (
    player_id  INTEGER PRIMARY KEY,
    gamertag   TEXT    NOT NULL UNIQUE,
    added_on   TEXT    NOT NULL DEFAULT (date('now'))
               CHECK (added_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
);

CREATE TABLE hero (
    hero_id    INTEGER PRIMARY KEY,
    hero_name  TEXT    NOT NULL UNIQUE,
    role       TEXT    NOT NULL CHECK (role IN ('Vanguard','Duelist','Strategist'))
);

CREATE TABLE match (
    match_id         INTEGER PRIMARY KEY,
    map_id           INTEGER NOT NULL,
    played_at        TEXT    NOT NULL
                     CHECK (played_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'),
    duration_seconds INTEGER CHECK (duration_seconds IS NULL OR duration_seconds > 0), -- optional
    FOREIGN KEY (map_id) REFERENCES map(map_id)
);

-- The two sides of one match. Deleting a match removes its sides.
CREATE TABLE match_team (
    match_id    INTEGER NOT NULL,
    team_number INTEGER NOT NULL CHECK (team_number IN (1, 2)),
    result      TEXT    NOT NULL CHECK (result IN ('WIN','LOSS','DRAW')),
    PRIMARY KEY (match_id, team_number),
    FOREIGN KEY (match_id) REFERENCES match(match_id) ON DELETE CASCADE
);

-- Junction table: resolves player <-> match (M:N); hero choice + stats live here.
-- A player appears at most once per match (composite PK).
-- The composite FK guarantees the participant's side belongs to the SAME match.
-- (The "1..6 players per side" rule is not expressible as a simple CHECK in SQLite;
--  it is respected by the sample data and enforced by the application layer.)
CREATE TABLE match_participant (
    match_id       INTEGER NOT NULL,
    player_id      INTEGER NOT NULL,
    team_number    INTEGER NOT NULL,
    hero_id        INTEGER NOT NULL,
    kills          INTEGER NOT NULL DEFAULT 0 CHECK (kills          >= 0),
    deaths         INTEGER NOT NULL DEFAULT 0 CHECK (deaths         >= 0),
    assists        INTEGER NOT NULL DEFAULT 0 CHECK (assists        >= 0),
    damage_dealt   INTEGER NOT NULL DEFAULT 0 CHECK (damage_dealt   >= 0),
    damage_blocked INTEGER NOT NULL DEFAULT 0 CHECK (damage_blocked >= 0),
    healing_done   INTEGER NOT NULL DEFAULT 0 CHECK (healing_done   >= 0),
    PRIMARY KEY (match_id, player_id),
    FOREIGN KEY (match_id, team_number) REFERENCES match_team(match_id, team_number) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES player(player_id),
    FOREIGN KEY (hero_id)   REFERENCES hero(hero_id)
);

-- ---------- Indexes (explicitly created; PK/UNIQUE auto-indexes don't count) ----------
-- The PK (match_id, player_id) can't serve "all matches for player X" lookups
-- or joins from player, so index player_id: supports player history/profile queries.
CREATE INDEX idx_participant_player ON match_participant(player_id);
-- Supports hero pick-rate / win-rate / team-composition queries (GROUP BY or filter on hero).
CREATE INDEX idx_participant_hero   ON match_participant(hero_id);
-- Supports filtering matches by map and ordering by date (map/mode reports, recent matches).
CREATE INDEX idx_match_map_played   ON match(map_id, played_at);

-- ---------- Views ----------
-- One row per player per match, joining 7 tables: a flat, readable match history.
-- Useful as the base for player stat pages and for later reports.
CREATE VIEW v_player_match_stats AS
SELECT  m.match_id,
        m.played_at,
        gm.mode_name,
        mp.map_name,
        p.player_id,
        p.gamertag,
        h.hero_name,
        h.role,
        mt.team_number,
        mt.result,
        s.kills, s.deaths, s.assists,
        ROUND((s.kills + s.assists) * 1.0 / MAX(s.deaths, 1), 2) AS kda,   -- avoid divide-by-zero
        s.damage_dealt, s.damage_blocked, s.healing_done
FROM match_participant s
JOIN match_team mt ON mt.match_id = s.match_id AND mt.team_number = s.team_number
JOIN match      m  ON m.match_id  = s.match_id
JOIN map        mp ON mp.map_id   = m.map_id
JOIN game_mode  gm ON gm.mode_id  = mp.mode_id
JOIN player     p  ON p.player_id = s.player_id
JOIN hero       h  ON h.hero_id   = s.hero_id;

-- Summary view: one row per hero (including never-picked heroes via LEFT JOIN).
CREATE VIEW v_hero_performance AS
SELECT  h.hero_id,
        h.hero_name,
        h.role,
        COUNT(s.player_id)                                              AS times_picked,
        SUM(CASE WHEN mt.result = 'WIN' THEN 1 ELSE 0 END)              AS wins,
        ROUND(100.0 * SUM(CASE WHEN mt.result = 'WIN' THEN 1 ELSE 0 END)
              / NULLIF(COUNT(s.player_id), 0), 1)                       AS win_rate_pct,
        ROUND(AVG(s.kills), 2)                                          AS avg_kills,
        ROUND(AVG(s.deaths), 2)                                         AS avg_deaths,
        ROUND(AVG(s.assists), 2)                                        AS avg_assists
FROM hero h
LEFT JOIN match_participant s ON s.hero_id = h.hero_id
LEFT JOIN match_team mt       ON mt.match_id = s.match_id AND mt.team_number = s.team_number
GROUP BY h.hero_id, h.hero_name, h.role;
