-- =====================================================================
-- transaction.sql -- Record a complete new match as ONE atomic unit.
-- A match needs: a match row, BOTH match_team sides, and its participants.
-- If any step failed halfway (e.g. a bad player id) without a transaction,
-- the database would hold a match with a missing side or missing players,
-- which would corrupt win-rate and composition reports. The transaction
-- makes all inserts succeed together or none at all.
-- Demonstration ends with ROLLBACK so the sample data is unchanged;
-- change ROLLBACK to COMMIT to keep the match.
-- =====================================================================
PRAGMA foreign_keys = ON;   -- must be set OUTSIDE a transaction

.print Before transaction:
SELECT (SELECT COUNT(*) FROM match)             AS matches,
       (SELECT COUNT(*) FROM match_team)        AS sides,
       (SELECT COUNT(*) FROM match_participant) AS participants;

BEGIN TRANSACTION;

-- 1) the match itself (map 1 = Tokyo 2099: Shinjuku, Domination)
INSERT INTO match (match_id, map_id, played_at, duration_seconds)
VALUES (25, 1, '2026-11-01 20:00:00', 780);

-- 2) both sides with their results
INSERT INTO match_team (match_id, team_number, result) VALUES (25, 1, 'WIN');
INSERT INTO match_team (match_id, team_number, result) VALUES (25, 2, 'LOSS');

-- 3) participants with heroes and stats (hero 1=Captain America, 9=Spider-Man,
--    17=Luna Snow, 2=Hulk, 12=Hela, 18=Mantis)
INSERT INTO match_participant (match_id, player_id, team_number, hero_id, kills, deaths, assists, damage_dealt, damage_blocked, healing_done) VALUES
  (25, 1, 1, 1,  8, 4, 10,  9000, 15000,     0),
  (25, 2, 1, 9, 17, 5,  6, 19000,     0,     0),
  (25, 3, 1, 17, 2, 3, 20,  5000,     0, 17000),
  (25, 4, 2, 2,  6, 9,  7, 10000, 20000,     0),
  (25, 5, 2, 12,12, 8,  3, 16000,     0,     0),
  (25, 6, 2, 18, 1, 7, 14,  4000,     0, 12000);

.print Inside transaction (new match visible):
SELECT (SELECT COUNT(*) FROM match)             AS matches,
       (SELECT COUNT(*) FROM match_team)        AS sides,
       (SELECT COUNT(*) FROM match_participant) AS participants;

ROLLBACK;   -- undo everything above; use COMMIT; to make it permanent

.print After ROLLBACK (back to original counts):
SELECT (SELECT COUNT(*) FROM match)             AS matches,
       (SELECT COUNT(*) FROM match_team)        AS sides,
       (SELECT COUNT(*) FROM match_participant) AS participants;
