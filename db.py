import os
import hashlib

import libsql_experimental as libsql
from dotenv import load_dotenv

from models import Team, Player


load_dotenv()


class Database:
    def __init__(self):
        self.database_url = os.getenv("TURSO_DATABASE_URL")
        self.auth_token = os.getenv("TURSO_AUTH_TOKEN")
        self.database_name = os.getenv("DATABASE_NAME")
        self.conn = libsql.connect(self.database_name, sync_url=self.database_url, auth_token=self.auth_token)
        self.cursor = self.conn.cursor()

    def get_teams(self):
        """Get all teams from database."""
        self.cursor.execute("SELECT id, abbreviation, name, nickname FROM Team")
        teams = [Team(*team) for team in self.cursor.fetchall()]
        return teams

    def get_players(self):
        """Get all players from database."""
        self.cursor.execute("SELECT id, name, active FROM Player")
        players = [Player(id, name, bool(active)) for id, name, active in self.cursor.fetchall()]
        return players
    
    def compute_trade_hash(self, trade_details):
        """Compute hash from trade details (excluding trade_id)."""
        trade_details_string = "".join(f"{trade_detail.player_id}-{trade_detail.from_team_id}-{trade_detail.to_team_id}" for trade_detail in trade_details)
        return hashlib.sha256(trade_details_string.encode("utf-8")).hexdigest()

    def insert_trade_and_details(self, trade, trade_details, unmatched_players, unmatched_teams):
        """Insert trade, trade details, and any new/unmatched players and teams in the trade into database in single transaction."""
        try:
            self.cursor.execute("BEGIN TRANSACTION;")

            trade_hash = self.compute_trade_hash(trade_details)

            self.cursor.execute("""
                INSERT INTO Trade (date, hash)
                VALUES (?, ?)
                ON CONFLICT(hash) DO NOTHING
            """, (trade.date, trade_hash))
            trade_id = self.cursor.lastrowid

            if not trade_id:  # Trade already exists
                self.conn.execute("ROLLBACK;")
                print("Trade already exists. Skipping...")
                return

            for player in unmatched_players:
                self.cursor.execute("INSERT INTO Player (name, active) VALUES (?, ?)",
                            (player.name, player.active))
                player_id = self.cursor.lastrowid

                for index, trade_detail in enumerate(trade_details):
                    if trade_detail.player_id is None:
                        trade_details[index] = trade_detail._replace(player_id=player_id)
                        break  # Move to next player since unmatched players list order corresponds with trade_details.player_id is None list order

            for team in unmatched_teams:
                self.cursor.execute("""
                    INSERT INTO Team (abbreviation, name, nickname)
                    VALUES (?, ?, ?)
                    ON CONFLICT(abbreviation) DO NOTHING
                """,(team.abbreviation, team.name, team.nickname))
                team_id = self.cursor.lastrowid
                if team_id == trade_id:  # No unmatched team inserted
                    team_id = self.cursor.execute("SELECT id from TEAM WHERE abbreviation = ?", (team.abbreviation, )).fetchone()[0]

                for index, trade_detail in enumerate(trade_details):
                    if trade_detail.from_team_id is None:
                        trade_details[index] = trade_detail._replace(from_team_id=team_id)
                        break  # Move to next team since unmatched teams list order corresponds with trade_details.from_team_id is None list order

            for trade_detail in trade_details:
                # print(f"Inserting: trade_id={trade_id}, player_id={trade_detail.player_id}, from_team_id={trade_detail.from_team_id}, to_team_id={trade_detail.to_team_id}")
                self.cursor.execute("""
                    INSERT INTO TradeDetail (trade_id, player_id, from_team_id, to_team_id) 
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(player_id, from_team_id, to_team_id) DO NOTHING
                """, (trade_id, trade_detail.player_id, trade_detail.from_team_id, trade_detail.to_team_id))
                
            self.conn.execute("COMMIT;")
            print(f"Transaction successful: new trade_id is {trade_id}")
        except Exception as e:
            self.conn.execute("ROLLBACK;")
            raise e