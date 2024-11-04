from nba_api.stats.static import teams

import db
from models import Team


def populate_teams():
    d = db.Database()
    conn = d.conn
    cursor = d.cursor

    nba_api_teams = teams.get_teams()
    teams_list = [(Team(team["id"], team["abbreviation"], team["full_name"], team["nickname"])) for team in nba_api_teams]
    
    cursor.executemany("INSERT INTO Team (id, abbreviation, name, nickname) VALUES (?, ?, ?, ?)",
                    [tuple(team) for team in teams_list])

    conn.commit()


if __name__ == "__main__":
    populate_teams()