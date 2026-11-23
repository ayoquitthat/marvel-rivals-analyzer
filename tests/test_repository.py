"""Automated checks that the application's SQL works against the final database.

Run from the project folder:  python3 -m unittest discover tests
Each test builds a fresh in-memory database from schema.sql and insert_data.sql,
so the real marvel_rivals.db is never touched.
"""
import sqlite3
import unittest

from rivals_app import repository as repo
from rivals_app.db import build_database, connect


def stat_row(player_id, team_number, hero_id, kills=5):
    return {"player_id": player_id, "team_number": team_number, "hero_id": hero_id,
            "kills": kills, "deaths": 3, "assists": 7,
            "damage_dealt": 9000, "damage_blocked": 0, "healing_done": 0}


def table_counts(conn):
    return tuple(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("match", "match_team", "match_participant"))


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        build_database(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_foreign_keys_enabled(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_search_includes_players_with_no_matches(self):
        rows = repo.search_players(self.conn, "casual")
        self.assertEqual([(r["gamertag"], r["matches_played"]) for r in rows],
                         [("CasualCarl", 0)])

    def test_search_treats_input_as_data(self):
        self.assertEqual(repo.search_players(self.conn, "' OR 1=1 --"), [])
        self.assertEqual(repo.search_players(self.conn, "%"), [])

    def test_match_scoreboard_joins_related_tables(self):
        rows = repo.match_scoreboard(self.conn, 1)
        self.assertEqual(len(rows), 12)
        self.assertEqual({r["team"] for r in rows}, {1, 2})

    def test_add_and_rename_player(self):
        player_id = repo.add_player(self.conn, "NewRecruit", "2026-11-01")
        self.assertEqual(repo.find_player(self.conn, "newrecruit")["player_id"], player_id)
        repo.rename_player(self.conn, player_id, "Recruit2")
        self.assertEqual(repo.find_player(self.conn, str(player_id))["gamertag"], "Recruit2")

    def test_duplicate_gamertag_rejected(self):
        self.assertTrue(repo.gamertag_taken(self.conn, "novastrike"))
        with self.assertRaises(sqlite3.IntegrityError):
            repo.add_player(self.conn, "NovaStrike")

    def test_record_match_saves_all_rows(self):
        before = table_counts(self.conn)
        match_id = repo.record_match(self.conn, 1, "2026-11-01 20:00:00", 600, "WIN",
                                     [stat_row(1, 1, 1), stat_row(2, 2, 2)])
        self.assertEqual(table_counts(self.conn), (before[0] + 1, before[1] + 2, before[2] + 2))
        self.assertEqual(repo.get_match(self.conn, match_id)["team2_result"], "LOSS")

    def test_record_match_rolls_back_on_failure(self):
        before = table_counts(self.conn)
        with self.assertRaises(sqlite3.IntegrityError):
            repo.record_match(self.conn, 1, "2026-11-01 20:00:00", 600, "WIN",
                              [stat_row(1, 1, 1), stat_row(2, 2, 999)])  # hero 999 missing
        self.assertEqual(table_counts(self.conn), before)

    def test_update_stats(self):
        repo.update_participant_stats(self.conn, 1, 16, {**stat_row(16, 1, 1, kills=42)})
        self.assertEqual(repo.get_participant(self.conn, 1, 16)["kills"], 42)

    def test_negative_stats_rejected_by_check(self):
        with self.assertRaises(sqlite3.IntegrityError):
            repo.update_participant_stats(self.conn, 1, 16, {**stat_row(16, 1, 1, kills=-1)})

    def test_delete_match_cascades(self):
        repo.delete_match(self.conn, 1)
        self.assertIsNone(repo.get_match(self.conn, 1))
        self.assertEqual(repo.match_scoreboard(self.conn, 1), [])

    def test_player_with_matches_cannot_be_deleted(self):
        with self.assertRaises(sqlite3.IntegrityError):
            repo.delete_player(self.conn, 1)

    def test_reports_return_rows(self):
        self.assertTrue(repo.hero_performance(self.conn, min_picks=5))
        self.assertTrue(repo.player_leaderboard(self.conn, 5, "kda"))
        self.assertEqual(len(repo.map_mode_report(self.conn)), 9)
        self.assertTrue(repo.team_composition_report(self.conn, 1))
        self.assertEqual(repo.player_summary(self.conn, 1)["matches"], 17)


if __name__ == "__main__":
    unittest.main()
