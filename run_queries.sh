#!/bin/bash
# Recreates the SQLite database and runs the Deliverable 4 queries and transaction.
# Requires the sqlite3 command-line tool. Run with:  bash run_queries.sh
# SQLite note: foreign keys are off by default per connection; every .sql file
# starts with PRAGMA foreign_keys = ON; so enforcement is active.

DB="marvel_rivals.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "sqlite3 is not installed or not on PATH."
    exit 1
fi

echo "Recreating database..."
rm -f "$DB"
sqlite3 -bail "$DB" < schema.sql      || { echo "schema.sql failed";      exit 1; }
sqlite3 -bail "$DB" < insert_data.sql || { echo "insert_data.sql failed"; exit 1; }

echo
echo "Running queries..."
sqlite3 -header -column "$DB" < queries.sql

echo
echo "Running transaction..."
sqlite3 -bail -header -column "$DB" < transaction.sql
status=$?

if [ "$status" -eq 0 ]; then
    echo "Transaction completed successfully."
else
    echo "Transaction failed."
    echo "Uncommitted changes were rolled back."
fi

echo
echo "Done."
