# Marvel Rivals Match & Team Analyzer

A database-backed application for recording Marvel Rivals match history and analyzing
how heroes, players, maps, game modes and team compositions perform.

Final project for the database course: SQLite database plus an interactive Python
command-line application.

## Project overview

**What it does.** Marvel Rivals has no public API for match history, so this system
lets a user enter matches by hand and then answer questions the game itself doesn't
show. Each match records the map, the two sides and their result, and for every player
the hero they used and their kills, deaths, assists, damage dealt, damage blocked and
healing done. Typical questions:

- Which heroes win most often, and in which role?
- Which players have the best win rate or KDA?
- What happens on each map: how many matches, how long they last, and which hero is picked most?
- Which team compositions win (for example 2 Vanguards, 2 Duelists, 2 Strategists)?

**Intended users.** A player, a group of friends or a small team (for example a college
esports roster or a coach) who want to keep their own match records and review
performance over time.

**Major functionality.**

- Search players, browse the hero roster and browse matches by mode and date.
- View a full match scoreboard or a player's match history.
- Register players, and record complete matches in a single transaction.
- Rename players, correct stats, and delete matches or players.
- Reports for heroes, a player leaderboard, maps and modes, and team compositions.
- A profile for each player: overall record, best heroes and a breakdown by role.

## Repository contents

| Path | What it is |
|---|---|
| `erd.pdf` | Final ER diagram (matches `schema.sql`) |
| `schema.sql` | Creates all tables, constraints, indexes and views (drops them first) |
| `insert_data.sql` | Synthetic sample data, 411 rows |
| `generate_data.py` | Script that produced `insert_data.sql` (fixed seed; optional) |
| `queries.sql` | The nine required SQL queries plus one team-composition query |
| `transaction.sql` | Records a complete match atomically, then rolls back |
| `run_queries.sh` | Rebuilds the database and runs `queries.sql` and `transaction.sql` |
| `main.py` | Starts the application |
| `rivals_app/` | Application source: `db.py`, `repository.py` (all SQL), `operations.py`, `prompts.py`, `display.py` |
| `tests/test_repository.py` | Automated tests of the app's database operations |
| `requirements.txt` | Dependency list (empty: only the standard library is used) |
| `.env.example` | Template for the one optional setting (no secrets exist) |

## DBMS

**SQLite 3**, tested with 3.45.1. The database is a single local file, so no server,
hosted service, account or credentials are involved.

## Database design

There are seven tables. The full diagram is in `erd.pdf`.

- **`game_mode`** and **`map`**: each map belongs to one game mode.
- **`player`** and **`hero`**: entity tables. Gamertags and hero names are unique, and a
  hero's role must be Vanguard, Duelist or Strategist.
- **`match`**: one row per match, with its map, time and optional duration.
- **`match_team`**: the two sides of a match, with key `(match_id, team_number)` and each
  side's result.
- **`match_participant`**: the junction table that resolves the many-to-many relationship
  between player and match. It stores the hero picked and the stats.
  - Its primary key `(match_id, player_id)` means a player appears at most once per match.
  - The composite foreign key `(match_id, team_number)` → `match_team` means a
    participant's side must belong to the same match.
- **Views:**
  - `v_player_match_stats` joins seven tables into one row per player per match, with a
    computed KDA.
  - `v_hero_performance` gives pick count, win rate and averages per hero, including
    heroes that have never been picked.
- **Indexes:** `match_participant(player_id)` for player lookups,
  `match_participant(hero_id)` for hero reports, and `match(map_id, played_at)` for map
  reports and recent-match lists.

## Database setup

**Required software:** the `sqlite3` command-line tool (for the SQL scripts) and Python 3.

- macOS: `sqlite3` is preinstalled.
- Ubuntu/Debian: `sudo apt install sqlite3`.
- Windows: download "sqlite-tools" from sqlite.org and put `sqlite3.exe` on your PATH,
  then run the scripts from Git Bash or WSL.

**Option A — run everything with one command** (rebuilds the database, then runs all the
SQL):

```bash
bash run_queries.sh
```

**Option B — run the files by hand, in this order:**

```bash
sqlite3 marvel_rivals.db < schema.sql
sqlite3 marvel_rivals.db < insert_data.sql
sqlite3 -header -column marvel_rivals.db < queries.sql
sqlite3 -bail -header -column marvel_rivals.db < transaction.sql
```

**Option C — no `sqlite3` tool at all:** just start the application (below). It builds
the database from `schema.sql` and `insert_data.sql` on its first run.

**DBMS-specific notes:**

- SQLite leaves foreign-key enforcement off by default, and the setting applies per
  connection. Every SQL file starts with `PRAGMA foreign_keys = ON;`, and the application
  runs the same statement on every connection it opens. In your own `sqlite3` session,
  run `PRAGMA foreign_keys = ON;` first.
- `schema.sql` starts with `DROP ... IF EXISTS`, so it can be re-run at any time to
  rebuild the database cleanly.
- `queries.sql` uses `.print` lines, which are `sqlite3` shell commands, to label each
  result.
- `transaction.sql` ends with `ROLLBACK`, so running it leaves the sample data unchanged.

**Configuration:** none required. The database is the file `marvel_rivals.db` in the
project folder, and there are no passwords or connection strings.

## Application setup

- **Language:** Python 3.8 or newer (tested on 3.12).
- **Packages:** none. The app uses only the standard library (`sqlite3`, `pathlib`,
  `datetime`), so there is nothing to install.
- **Database connection:** by default the app opens `marvel_rivals.db` next to `main.py`.
  To use another file, set the `MR_DB_PATH` environment variable (see `.env.example`):

  ```bash
  MR_DB_PATH=/tmp/test.db python3 main.py
  ```

**Start the application:**

```bash
git clone <repository-url>
cd marvel-rivals-analyzer
python3 main.py              # on Windows: python main.py
```

- If the database doesn't exist yet, the app creates it from the SQL files.
- `python3 main.py --reset` (or menu option 17) rebuilds the database from the sample
  data.
- Changes made in the app are saved to `marvel_rivals.db` and are still there the next
  time you start it.

**Run the automated tests (optional):**

```bash
python3 -m unittest discover tests
```

The tests use a fresh in-memory database, so they never touch `marvel_rivals.db`.

## Major application operations

Type a menu number and press Enter. Typing `q` at any prompt cancels the current
operation, and `0` exits and closes the database connection. Players and heroes can be
entered by ID or by name (not case-sensitive).

| Category | Menu option | What it does |
|---|---|---|
| Search / browse | 1 Search players | Gamertag search, with each player's match count (players with 0 matches included) |
| | 2 Browse heroes by role | Hero roster, filtered by role |
| | 3 Browse matches | Recent matches, filtered by game mode and date range |
| Related data | 4 View a match scoreboard | Map, mode, both sides' results, and every player's hero and stats |
| | 5 View a player's match history | A player's recent matches with map, hero, result and stats |
| Add | 6 Register a new player | INSERT into `player` |
| | 7 Record a complete match | INSERTs the match, both sides and every participant in **one transaction** |
| Update / delete | 8 Rename a player | UPDATE `player` |
| | 9 Correct a player's stats | UPDATE `match_participant` |
| | 10 Delete a match | DELETE, which cascades to its sides and participants |
| | 11 Delete a player | DELETE, allowed only for players with no recorded matches |
| Reports | 12 Hero performance | Win rate per hero from `v_hero_performance` |
| | 13 Player leaderboard | Sort by win rate, KDA or damage, with a minimum match count |
| | 14 Maps and modes | Matches, average length and most-picked hero per map |
| | 15 Team composition win rates | Win rate by role mix, derived from heroes on each side |
| Additional | 16 Player profile | Overall record, best heroes and a breakdown by role |
| | 17 Reset database | Rebuilds the database from the SQL files |

## How the application uses the database

- **SQL lives in one place.** All of it is in `rivals_app/repository.py`. Filtering,
  sorting, joins, aggregation and grouping run in SQL, and Python only formats the
  results. The app keeps no copy of the data outside the database.
- **User values are always parameters.** Every value the user supplies is passed as a `?`
  placeholder, never pasted into the SQL. The one piece of SQL built at run time is the
  leaderboard's `ORDER BY`, because a placeholder can't stand in for a column name. It is
  chosen from a fixed whitelist, so user text never reaches the SQL. Searches also
  escape `%` and `_`.
- **Transactions.** Every change runs inside `with conn:`, which commits on success and
  rolls back on any error. Recording a match spans several tables (1 `match`, 2
  `match_team` and up to 12 `match_participant` rows), so a failure partway through
  leaves nothing behind.
- **Validation** happens before anything reaches the database:
  - menu choices, required values, number types and ranges
  - date formats, and no future match times
  - gamertag length and case-insensitive duplicates
  - unknown IDs
  - the same player twice in a match, or the same hero twice on one side
- **Errors.** Database errors are caught and shown as plain messages instead of stack
  traces. The schema's constraints (UNIQUE, CHECK, foreign keys) stay in place as the
  final safety net.

## Known limitations

- **Players per side.** The ERD's rule of 1 to 6 players per side is enforced by the
  application, not the database: a simple SQLite CHECK constraint can't count rows in
  another table. Rows inserted with raw SQL could break this rule.
- **Single-user.** SQLite is a local, single-file database meant for one user at a time.
  If two programs write to it at once, the second gets a "database is busy" message.
- **Manual entry only.** Matches are typed in; nothing is imported from the game.
- **Synthetic sample data.** The players and stats are generated test data, not real
  matches. Hero, map and mode names follow the game but aren't kept up to date with game
  patches.
- **Shared database file.** `run_queries.sh` deletes and rebuilds `marvel_rivals.db`, the
  same file the application uses. Running it erases any changes made in the app. This is
  intended, so the SQL always runs on known data.
- **Fixed result pairing.** Team 2's result is always the opposite of Team 1's (WIN/LOSS,
  or DRAW/DRAW), matching how the game works. Unusual results such as a forfeit can't be
  recorded.

There are no other known problems. The SQL scripts, the application and the 13
automated tests all pass on a freshly built database.
