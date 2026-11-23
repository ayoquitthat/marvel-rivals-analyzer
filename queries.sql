-- =====================================================================
-- Marvel Rivals Match & Team Analyzer -- Deliverable 4: queries.sql
-- DBMS: SQLite. Run by run_queries.sh with: sqlite3 -header -column
-- (.print lines below are sqlite3 shell commands that label each result.)
-- =====================================================================
PRAGMA foreign_keys = ON;

.print
.print === Requirement 1: Filtering and Sorting ===
-- Requirement 1: Filtering and Sorting
-- Which October 2026 matches ran longer than 15 minutes, longest first?
-- (Matches with an unknown duration are excluded by the filter.)
SELECT match_id,
       played_at,
       duration_seconds,
       ROUND(duration_seconds / 60.0, 1) AS duration_minutes
FROM   match
WHERE  played_at >= '2026-10-01'
  AND  duration_seconds > 900
ORDER BY duration_seconds DESC;

.print
.print === Requirement 2: INNER JOIN ===
-- Requirement 2: INNER JOIN
-- Report: the ten highest single-match damage performances, showing who
-- played which hero. Combines player, match_participant and hero.
SELECT p.gamertag,
       h.hero_name,
       s.match_id,
       s.damage_dealt
FROM   match_participant s
INNER JOIN player p ON p.player_id = s.player_id
INNER JOIN hero   h ON h.hero_id   = s.hero_id
ORDER BY s.damage_dealt DESC
LIMIT 10;

.print
.print === Requirement 3: LEFT JOIN ===
-- Requirement 3: LEFT JOIN
-- Report: every registered player with the number of matches played,
-- including players who have never played (CasualCarl shows 0).
SELECT p.gamertag,
       p.added_on,
       COUNT(s.match_id) AS matches_played
FROM   player p
LEFT JOIN match_participant s ON s.player_id = p.player_id
GROUP BY p.player_id, p.gamertag, p.added_on
ORDER BY matches_played ASC, p.gamertag
LIMIT 6;

.print
.print === Requirement 4: Three-Table Join (match + map + game_mode, plus match_team) ===
-- Requirement 4: Three-Table Join
-- Report: match history showing which map and game mode each match was
-- played on and how Team 1 finished. This needs match, map, game_mode
-- (and match_team for the result); no single table has all of it.
SELECT m.match_id,
       m.played_at,
       gm.mode_name,
       mp.map_name,
       mt.result AS team1_result
FROM   match m
JOIN   map        mp ON mp.map_id  = m.map_id
JOIN   game_mode  gm ON gm.mode_id = mp.mode_id
JOIN   match_team mt ON mt.match_id = m.match_id AND mt.team_number = 1
ORDER BY m.played_at
LIMIT 10;

.print
.print === Requirement 5: Aggregate Query ===
-- Requirement 5: Aggregate Query
-- Report: league-wide summary of recorded match activity.
SELECT COUNT(*)                          AS matches_recorded,
       ROUND(AVG(duration_seconds)/60.0, 1) AS avg_minutes,
       MIN(duration_seconds)             AS shortest_seconds,
       MAX(duration_seconds)             AS longest_seconds,
       SUM(duration_seconds IS NULL)     AS matches_missing_duration
FROM   match;

.print
.print === Requirement 6: GROUP BY and HAVING ===
-- Requirement 6: GROUP BY and HAVING
-- Hero analysis (core proposal question): which heroes picked at least
-- 15 times have the best win rate? HAVING drops rarely-picked heroes
-- whose win rate would be misleading.
SELECT h.hero_name,
       h.role,
       COUNT(*)                                             AS times_picked,
       SUM(CASE WHEN mt.result = 'WIN' THEN 1 ELSE 0 END)   AS wins,
       ROUND(100.0 * SUM(CASE WHEN mt.result = 'WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate_pct
FROM   match_participant s
JOIN   hero       h  ON h.hero_id = s.hero_id
JOIN   match_team mt ON mt.match_id = s.match_id AND mt.team_number = s.team_number
GROUP BY h.hero_id, h.hero_name, h.role
HAVING COUNT(*) >= 15
ORDER BY win_rate_pct DESC, times_picked DESC;

.print
.print === Requirement 7: Subquery ===
-- Requirement 7: Subquery
-- Player analysis: which players average more kills per match than the
-- league-wide average of all participant rows? The scalar subquery
-- computes that benchmark.
SELECT p.gamertag,
       COUNT(*)              AS matches_played,
       ROUND(AVG(s.kills),2) AS avg_kills,
       (SELECT ROUND(AVG(kills),2) FROM match_participant) AS league_avg_kills
FROM   match_participant s
JOIN   player p ON p.player_id = s.player_id
GROUP BY p.player_id, p.gamertag
HAVING AVG(s.kills) > (SELECT AVG(kills) FROM match_participant)
ORDER BY avg_kills DESC;

.print
.print === Requirement 8: Set Operation (EXCEPT) ===
-- Requirement 8: Set Operation
-- Map/mode analysis: heroes that have been picked on Domination maps but
-- never on Convergence maps (Convergence has the fewest matches).
-- Both SELECTs return hero names filtered by game mode, so the sets are comparable.
SELECT h.hero_name
FROM   match_participant s
JOIN   hero h      ON h.hero_id = s.hero_id
JOIN   match m     ON m.match_id = s.match_id
JOIN   map mp      ON mp.map_id = m.map_id
JOIN   game_mode g ON g.mode_id = mp.mode_id
WHERE  g.mode_name = 'Domination'
EXCEPT
SELECT h.hero_name
FROM   match_participant s
JOIN   hero h      ON h.hero_id = s.hero_id
JOIN   match m     ON m.match_id = s.match_id
JOIN   map mp      ON mp.map_id = m.map_id
JOIN   game_mode g ON g.mode_id = mp.mode_id
WHERE  g.mode_name = 'Convergence'
ORDER BY hero_name;

.print
.print === Requirement 9: View (v_player_match_stats) ===
-- Requirement 9: View
-- Player leaderboard: win rate, average KDA and total damage for each
-- player with at least 10 matches. The view already joins 7 tables and
-- computes KDA, so this report needs no joins of its own.
SELECT gamertag,
       COUNT(*)                                                   AS matches,
       SUM(result = 'WIN')                                        AS wins,
       ROUND(100.0 * SUM(result = 'WIN') / COUNT(*), 1)           AS win_rate_pct,
       ROUND(AVG(kda), 2)                                         AS avg_kda,
       SUM(damage_dealt)                                          AS total_damage
FROM   v_player_match_stats
GROUP BY player_id, gamertag
HAVING COUNT(*) >= 10
ORDER BY win_rate_pct DESC, avg_kda DESC;

.print
.print === Extra (team composition, proposal question): win rate by role makeup ===
-- Extra: Team Composition Analysis
-- Which role mixes (Vanguard/Duelist/Strategist counts on one side) win
-- most often? A composition is derived from the heroes on a match_team.
WITH side AS (
    SELECT s.match_id, s.team_number, mt.result,
           SUM(h.role = 'Vanguard')   AS vanguards,
           SUM(h.role = 'Duelist')    AS duelists,
           SUM(h.role = 'Strategist') AS strategists
    FROM   match_participant s
    JOIN   hero h        ON h.hero_id = s.hero_id
    JOIN   match_team mt ON mt.match_id = s.match_id AND mt.team_number = s.team_number
    GROUP BY s.match_id, s.team_number, mt.result
)
SELECT vanguards || 'V / ' || duelists || 'D / ' || strategists || 'S' AS composition,
       COUNT(*)                                             AS sides,
       SUM(result = 'WIN')                                  AS wins,
       ROUND(100.0 * SUM(result = 'WIN') / COUNT(*), 1)     AS win_rate_pct
FROM   side
GROUP BY vanguards, duelists, strategists
ORDER BY sides DESC;
