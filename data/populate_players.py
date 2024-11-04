from nba_api.stats.static import players

import db
from models import Player


def populate_players():
    d = db.Database()
    conn = d.conn
    cursor = d.cursor

    nba_api_players = players.get_players()
    players_list = [(Player(player["id"], player["full_name"], player["is_active"])) for player in nba_api_players]
        
    cursor.executemany("INSERT INTO Player (id, name, active) VALUES (?, ?, ?)",
                    [tuple(player) for player in players_list])

    conn.commit()


if __name__ == "__main__":
    populate_players()