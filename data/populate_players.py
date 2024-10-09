import sqlite3

from nba_api.stats.static import players

from models import Player
import config


conn = sqlite3.connect(config.DATABASE_NAME)
cursor = conn.cursor()

nba_api_players = players.get_players()
players_list = [(Player(player["id"], player["full_name"], player["is_active"])) for player in nba_api_players]
    
cursor.executemany("INSERT INTO Player (id, name, active) VALUES (?, ?, ?)",
                   [tuple(player) for player in players_list])

conn.commit()
conn.close()