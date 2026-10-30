#!/usr/bin/env python3
"""PAB quick operational status checker."""

import sqlite3
import sys
from pathlib import Path


def main():
    db_path = Path.home() / ".pab" / "pab.db"
    if not db_path.is_file():
        print(f"[ERROR] PAB database not found at {db_path}")
        print("Run 'pab doctor' to initialize PAB environment.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Agent count
    cursor.execute("SELECT count(*) FROM agents")
    agent_count = cursor.fetchone()[0]

    # Skill count
    cursor.execute("SELECT count(*) FROM skills")
    skill_count = cursor.fetchone()[0]

    # Memory count
    cursor.execute("SELECT count(*) FROM memories")
    memory_count = cursor.fetchone()[0]

    # Active session count
    cursor.execute("SELECT count(*) FROM sessions")
    session_count = cursor.fetchone()[0]

    conn.close()

    print("========================================")
    print(" PersonaOS Agent Bridge (PAB) Status    ")
    print("========================================")
    print(f" Database: {db_path}")
    print(f" Registered Agents: {agent_count}")
    print(f" Canonical Skills:  {skill_count}")
    print(f" Shared Memories:   {memory_count}")
    print(f" Tracked Sessions:  {session_count}")
    print("========================================")
    print("Status: OPERATIONAL")
    sys.exit(0)


if __name__ == "__main__":
    main()
