import sqlite3

from nba_api.stats.static import teams

from models import Team
import config


conn = sqlite3.connect(config.DATABASE_NAME)
cursor = conn.cursor()

nba_api_teams = teams.get_teams()
teams_list = [(Team(team["id"], team["abbreviation"], team["full_name"], team["nickname"])) for team in nba_api_teams]
    
cursor.executemany("INSERT INTO Team (id, abbreviation, name, nickname) VALUES (?, ?, ?, ?)",
                   [tuple(team) for team in teams_list])

conn.commit()
conn.close()