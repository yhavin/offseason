import sqlite3

import config


conn = sqlite3.connect(config.DATABASE_NAME)
cursor = conn.cursor()

cursor.executescript("""
DROP TABLE IF EXISTS Team;
DROP TABLE IF EXISTS Player;
DROP TABLE IF EXISTS Trade;
DROP TABLE IF EXISTS TradeDetail;
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Team (
    id INTEGER PRIMARY KEY,
    abbreviation TEXT,
    name TEXT, 
    nickname TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Player (
    id INTEGER PRIMARY KEY,
    name TEXT,
    active INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Trade (
    id INTEGER PRIMARY KEY,
    date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS TradeDetail (
    trade_id INTEGER,
    player_id INTEGER,
    from_team_id INTEGER,
    to_team_id INTEGER,
    FOREIGN KEY (trade_id) REFERENCES Trade(id),
    FOREIGN KEY (player_id) REFERENCES Player(id),
    FOREIGN KEY (from_team_id) REFERENCES Team(id),
    FOREIGN KEY (to_team_id) REFERENCES Team(id)
)
""")

conn.commit()
conn.close()