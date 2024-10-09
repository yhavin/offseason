import sqlite3
import re
from datetime import datetime
import pprint

import requests
from bs4 import BeautifulSoup

import config
from models import Team, Player, Trade, TradeDetail


def get_teams(cursor: sqlite3.Cursor):
    cursor.execute("SELECT id, abbreviation, name, nickname FROM Team")
    teams = [Team(*team) for team in cursor.fetchall()]
    return teams


def get_players(cursor: sqlite3.Cursor):
    cursor.execute("SELECT id, name, active FROM Player")
    players = [Player(id, name, bool(active)) for id, name, active in cursor.fetchall()]
    return players


def pull_trade_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    article_html = soup.find("div", class_=re.compile("^ArticleContent"))
    return article_html


def parse_page_to_blocks(trade_page):
    hr_tags = trade_page.find_all_next("hr")

    blocks = []

    for i in range(len(hr_tags) - 1):
        html_content = ""
        next_tag = hr_tags[i].find_next_sibling()

        while next_tag and next_tag != hr_tags[i + 1]:
            html_content += str(next_tag)
            next_tag = next_tag.find_next_sibling()

        block = BeautifulSoup(html_content, "html.parser")
        blocks.append(block)

    return blocks


def extract_date(block, year):
    match = re.search(r"\((\w+\.? \d{1,2})\)", block.get_text())

    if match:
        date_string = match.group(1).replace(".", "")
        try:
            date = datetime.strptime(date_string, "%B %d")
        except ValueError:
            date = datetime.strptime(date_string, "%b %d")

        date = date.replace(year=year).strftime("%Y-%m-%d")
        return date

    return f"{year}-01-01"


def extract_teams(block):
    teams = []
    
    for p_tag in block.find_all("p"):
        if " receive:" in p_tag.get_text():
            team_nickname = p_tag.get_text().replace(" receive:", "").strip()
            team = teams_by_nickname.get(team_nickname, teams_by_nickname.get(alternative_nickname_mapping.get(team_nickname)))
            if team:
                teams.append(team)

    return teams


def is_valid_player_name(player_name):
    if "cash" in player_name.lower():
        return False
    if "pick" in player_name.lower() and sum(1 for char in player_name if char.isupper()) < 2:
        return False
    return True


def extract_players(block, num_teams):
    players = []

    ul_tags = block.find_all("ul")

    if num_teams == 2:  # Standard trade
        team_1_names_received = [clean_player_name(li.get_text()) for li in ul_tags[0].find_all("li") if is_valid_player_name(li.get_text())]
        team_2_names_received = [clean_player_name(li.get_text()) for li in ul_tags[1].find_all("li") if is_valid_player_name(li.get_text())]

        team_1_players_received = [players_by_name.get(name) or Player(None, name, True) for name in team_1_names_received]
        team_2_players_received = [players_by_name.get(name) or Player(None, name, True) for name in team_2_names_received]

        players.append(team_1_players_received)
        players.append(team_2_players_received)
    elif num_teams > 2:  # Multi-team trade
            pass
    
    return players


def clean_player_name(player):
    player = re.sub(r"(draft\s+)?rights\sto\s+", "", player, flags=re.IGNORECASE)
    return re.sub(r"\s*\(.*?\)", "", player).strip().replace("’", "'")


def generate_trade_details(teams_players):
    trade_details = []

    if len(teams_players) == 2:  # Standard trade
        for index, (to_team, players_received) in enumerate(teams_players):
            from_team = teams_players[1 - index][0]  # Other team
            for player in players_received:
                trade_detail = TradeDetail(
                    trade_id=None,  # Placeholder
                    player_id=player.id,  # Potentially placeholder
                    from_team_id=from_team.id,
                    to_team_id=to_team.id
                )
                trade_details.append(trade_detail)
    elif len(teams_players) > 2:  # Multi-team trade
        pass

    return trade_details


def insert_trade(cursor: sqlite3.Cursor, trade):
    cursor.execute("INSERT INTO Trade (trade_date) VALUES (?)", (trade.trade_date,))
    return cursor.lastrowid


def parse_block_to_teams_players(block):
    teams_players = []
    
    teams = extract_teams(block)
    players = extract_players(block, len(teams))

    if len(teams) == 2:  # Standard trade
        teams_players = list(zip(teams, players))
    if len(teams) > 2:  # Multi-team trade
        pass

    return teams_players


if __name__ == "__main__":
    alternative_nickname_mapping = {
        "Mavs": "Mavericks",
        "Blazers": "Trail Blazers"
    }


    year = 2024
    url_2024 = "https://www.nba.com/news/2024-offseason-trade-tracker"

    conn = sqlite3.connect(config.DATABASE_NAME)
    cursor = conn.cursor()

    all_teams = get_teams(cursor)
    teams_by_nickname = {team.nickname: team for team in all_teams}

    all_players = get_players(cursor)
    players_by_name = {player.name: player for player in all_players}

    if year == 2024:
        trade_page = pull_trade_page(url_2024)
        blocks = parse_page_to_blocks(trade_page)

        for index, block in enumerate(blocks):
            print(f"*******START {index}")
            date = extract_date(block, year)
            trade = Trade(None, date)
            teams_players = parse_block_to_teams_players(block)
            trade_details = generate_trade_details(teams_players)
            pprint.pprint(trade)
            pprint.pprint(trade_details)
            print(f"*******END   {index}")
        quit()



        # block_index = 25
        # current_block = blocks[block_index]

        # date = extract_date(current_block, year)
        # trade = Trade(None, date)

        # teams_players = parse_block_to_teams_players(current_block)
        # print(teams_players)
        # quit()
        # trade_details = generate_trade_details(teams_players)
        