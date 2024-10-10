from collections import namedtuple


Player = namedtuple("Player", ["id", "name", "active"])
Team = namedtuple("Team", ["id", "abbreviation", "name", "nickname"])
Trade = namedtuple("Trade", ["id", "date", "hash"])
TradeDetail = namedtuple("TradeDetail", ["trade_id", "player_id", "from_team_id", "to_team_id"])