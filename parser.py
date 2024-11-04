import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from models import Team, Player, Trade, TradeDetail



class Parser:
    def __init__(self, year, url, teams_by_nickname, players_by_name):
        self.year = year
        self.url = url
        self.teams_by_nickname = teams_by_nickname
        self.players_by_name = players_by_name
        self.alternative_nickname_mapping = {
            "Mavs": "Mavericks",
            "Blazers": "Trail Blazers",
            "San": "Spurs",
            "Wolves": "Timberwolves",
            "Sixers": "76ers"
        }

        self.pull_trade_page()
        self.parse_page_to_blocks()

        self.all_trades = []
        self.all_trade_details = []

        for block in self.blocks:
            self.all_trades.append(Trade(None, self.extract_date(block), None))
            self.all_trade_details.append(self.parse_block_to_trade_details(block))

    def pull_trade_page(self):
        """Get trade page into BeautifulSoup tree."""
        response = requests.get(self.url)
        soup = BeautifulSoup(response.content, "html.parser")
        article_html = soup.find("div", class_=re.compile("^ArticleContent"))
        self.trade_page = article_html

    def parse_page_to_blocks(self):
        """Parse trade page to list of trade blocks."""
        hr_tags = self.trade_page.find_all_next("hr")

        blocks = []

        for i in range(len(hr_tags) - 1):
            html_content = ""
            next_tag = hr_tags[i].find_next_sibling()

            while next_tag and next_tag != hr_tags[i + 1]:
                html_content += str(next_tag)
                next_tag = next_tag.find_next_sibling()

            block = BeautifulSoup(html_content, "html.parser")
            blocks.append(block)

        self.blocks = blocks

    def extract_date(self, block):
        """Extract trade date from trade block."""
        match = re.search(r"\((\w+\.? \d{1,2})\)", block.get_text())

        if match:
            date_string = match.group(1).replace(".", "")
            try:
                date = datetime.strptime(date_string, "%B %d")
            except ValueError:
                date = datetime.strptime(date_string, "%b %d")

            date = date.replace(year=self.year).strftime("%Y-%m-%d")
            return date

        return f"{self.year}-01-01"

    def parse_block_to_trade_details(self, block):
        """Wrapper to extract teams and player from a trade block, and create trade details list."""
        teams = self.extract_teams(block)
        players = self.extract_players(block, len(teams))
        trade_details = self.generate_trade_details(teams, players)
        return trade_details

    def extract_teams(self, block):
        """Extract teams from a trade block."""
        teams = []
        
        for p_tag in block.find_all("p"):
            if " receive:" in p_tag.get_text() or " get:" in p_tag.get_text():
                team_nickname = p_tag.get_text().replace(" receive:", "").replace(" get:", "").strip()
                team = self.teams_by_nickname.get(team_nickname, self.teams_by_nickname.get(self.alternative_nickname_mapping.get(team_nickname)))
                if team:
                    teams.append(team)

        for div_tag in block.find_all("div", class_="p-rich_text_section"):
            b_tag = div_tag.find("b")
            if b_tag and " receive:" in b_tag.get_text():
                team_nickname = b_tag.get_text().replace(" receive:", "").strip()
                team = self.teams_by_nickname.get(team_nickname, self.teams_by_nickname.get(self.alternative_nickname_mapping.get(team_nickname)))
                if team:
                    teams.append(team)

        return teams

    def extract_players(self, block, num_teams):
        """Extract players from a trade block."""
        ul_tags = block.find_all("ul")

        if num_teams == 2:  # Standard trade
            players = self.extract_players_standard_trade(ul_tags)
        elif num_teams > 2:  # Multi-team trade
            players = self.extract_players_multiteam_trade(ul_tags)
        
        return players
    
    def generate_trade_details(self, teams, players):
        """Create trade details list using extracted teams and players."""
        trade_details = []
        unmatched_players = []
        unmatched_teams = []

        if len(teams) == 2:  # Standard trade
            teams_players = list(zip(teams, players))
            for index, (to_team, players_received) in enumerate(teams_players):
                from_team = teams_players[1 - index][0]  # Other team
                for player in players_received:
                    trade_detail = TradeDetail(
                        trade_id=None,  # Placeholder
                        player_id=player.id,  # None for unmatched player
                        from_team_id=from_team.id,
                        to_team_id=to_team.id
                    )
                    trade_details.append(trade_detail)

                    if player.id is None:
                        unmatched_players.append(player)
        elif len(teams) > 2:  # Multi-team trade
            for index, to_team in enumerate(teams):
                players_received = players[index]
                for player in players_received:
                    trade_detail = TradeDetail(
                        trade_id=None,  # Placeholder
                        player_id=player[0].id,  # None for unmatched player
                        from_team_id=player[1].id,  # None for unmatched team
                        to_team_id=to_team.id
                    )
                    trade_details.append(trade_detail)

                    if player[0].id is None:
                        unmatched_players.append(player[0])
                    if player[1].id is None:
                        unmatched_teams.append(player[1])

        return trade_details, unmatched_players, unmatched_teams

    def extract_players_standard_trade(self, ul_tags):
        """Extract players from a standard trade block."""
        players = []

        team_1_names_received = [self.clean_player_name(li.get_text()) for li in ul_tags[0].find_all("li") if self.is_valid_player_name(li.get_text())]
        team_2_names_received = [self.clean_player_name(li.get_text()) for li in ul_tags[1].find_all("li") if self.is_valid_player_name(li.get_text())]

        team_1_players_received = [self.players_by_name.get(name) or Player(None, name, True) for name in team_1_names_received]
        team_2_players_received = [self.players_by_name.get(name) or Player(None, name, True) for name in team_2_names_received]

        players.append(team_1_players_received)
        players.append(team_2_players_received)

        return players

    def extract_players_multiteam_trade(self, ul_tags):
        """Extract players from a multi-team trade block."""
        players = []

        for ul_tag in ul_tags:
            received_players = []
            for li_tag in ul_tag.find_all("li"):
                player_name_with_via = li_tag.get_text()
                player_name = self.clean_player_name(li_tag.get_text())
                from_team = self.extract_via_team(player_name_with_via)

                if self.is_valid_player_name(player_name):
                    player = self.players_by_name.get(player_name) or Player(None, player_name, True)
                    received_players.append((player, from_team))

            players.append(received_players)

        return players
    
    def is_valid_player_name(self, player_name):
        """Return True if a player name is valid else False."""
        if "cash" in player_name.lower():
            return False
        if "pick" in player_name.lower() and sum(1 for char in player_name if char.isupper()) < 2:
            return False
        return True
    
    def clean_player_name(self, player_name):
        """Clean player name string."""
        player_name = re.sub(r"(draft\s+)?rights\sto\s+", "", player_name, flags=re.IGNORECASE)
        return re.sub(r"\s*\(.*?\)", "", player_name).strip().replace("’", "'")

    def extract_via_team(self, player_name):
        """Extract team name from 'via <team>' in player name string."""
        via_match = re.search(r"via\s+(\w+)", player_name)
        if via_match:
            from_team_nickname = via_match.group(1).replace("via ", "")
            from_team = self.teams_by_nickname.get(from_team_nickname, self.teams_by_nickname.get(self.alternative_nickname_mapping.get(from_team_nickname)))
            if from_team:
                return from_team
        return Team(None, "NA", "Unknown", "Unknown")
        