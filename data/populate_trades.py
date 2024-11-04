import db
from parser import Parser


def populate_trades():
    d = db.Database()

    all_teams = d.get_teams()
    teams_by_nickname = {team.nickname: team for team in all_teams}

    all_players = d.get_players()
    players_by_name = {player.name: player for player in all_players}

    offseasons = [
        # {"year": 2021, "url": "https://www.nba.com/news/2021-22-nba-trade-tracker"},
        # {"year": 2022, "url": "https://www.nba.com/news/2022-23-nba-trade-tracker"},
        # {"year": 2023, "url": "https://www.nba.com/news/2023-24-nba-trade-tracker"},
        {"year": 2024, "url": "https://www.nba.com/news/2024-offseason-trade-tracker"}
    ]

    for offseason in offseasons:
        p = Parser(offseason["year"], offseason["url"], teams_by_nickname, players_by_name)

        for index, trade in enumerate(p.all_trades):
            # if index + 1 == 5:
                try:
                    d.insert_trade_and_details(trade, *p.all_trade_details[index])
                except Exception as e:
                    print(f"Failed to enter trade {index + 1}: error {e}")


if __name__ == "__main__":
    populate_trades()