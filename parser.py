import sqlite3
import re
from datetime import datetime
import pprint
import hashlib

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

    for div_tag in block.find_all("div", class_="p-rich_text_section"):
        b_tag = div_tag.find("b")
        if b_tag and " receive:" in b_tag.get_text():
            team_nickname = b_tag.get_text().replace(" receive:", "").strip()
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
    ul_tags = block.find_all("ul")

    if num_teams == 2:  # Standard trade
        players = extract_players_standard_trade(ul_tags)
    elif num_teams > 2:  # Multi-team trade
        players = extract_players_multiteam_trade(ul_tags)
    
    return players


def extract_players_standard_trade(ul_tags):
    players = []

    team_1_names_received = [clean_player_name(li.get_text()) for li in ul_tags[0].find_all("li") if is_valid_player_name(li.get_text())]
    team_2_names_received = [clean_player_name(li.get_text()) for li in ul_tags[1].find_all("li") if is_valid_player_name(li.get_text())]

    team_1_players_received = [players_by_name.get(name) or Player(None, name, True) for name in team_1_names_received]
    team_2_players_received = [players_by_name.get(name) or Player(None, name, True) for name in team_2_names_received]

    players.append(team_1_players_received)
    players.append(team_2_players_received)

    return players


def extract_players_multiteam_trade(ul_tags):
    players = []

    for ul_tag in ul_tags:
        received_players = []
        for li_tag in ul_tag.find_all("li"):
            player_name_with_via = li_tag.get_text()
            player_name = clean_player_name(li_tag.get_text())
            from_team = extract_via_team(player_name_with_via)

            if is_valid_player_name(player_name):
                player = players_by_name.get(player_name) or Player(None, player_name, True)
                received_players.append((player, from_team))

        players.append(received_players)

    return players


def extract_via_team(player_name):
    via_match = re.search(r"via\s+([\w\s]+)", player_name)
    if via_match:
        from_team_nickname = via_match.group(1).replace("via ", "")
        from_team = teams_by_nickname.get(from_team_nickname, teams_by_nickname.get(alternative_nickname_mapping.get(from_team_nickname)))
        if from_team:
            return from_team
    return Team(None, "NA", "Unknown", "Unknown")


def clean_player_name(player):
    player = re.sub(r"(draft\s+)?rights\sto\s+", "", player, flags=re.IGNORECASE)
    return re.sub(r"\s*\(.*?\)", "", player).strip().replace("’", "'")


def parse_block_to_trade_details(block): 
    teams = extract_teams(block)
    players = extract_players(block, len(teams))
    trade_details = generate_trade_details(teams, players)
    return trade_details


def generate_trade_details(teams, players):
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


def compute_trade_hash(trade_details):
    trade_details_string = "".join(f"{trade_detail.player_id}-{trade_detail.from_team_id}-{trade_detail.to_team_id}" for trade_detail in trade_details)
    return hashlib.sha256(trade_details_string.encode("utf-8")).hexdigest()


def insert_trade_and_details(cursor, trade, trade_details, unmatched_players, unmatched_teams):
    try:
        cursor.execute("BEGIN TRANSACTION;")

        trade_hash = compute_trade_hash(trade_details)

        cursor.execute("""
            INSERT INTO Trade (date, hash)
            VALUES (?, ?)
            ON CONFLICT(hash) DO NOTHING
        """, (trade.date, trade_hash))
        trade_id = cursor.lastrowid

        if not trade_id:  # Trade already exists
            cursor.execute("ROLLBACK;")
            print(f"Trade already exists: {trade_id}. Skipping...")
            return

        for player in unmatched_players:
            cursor.execute("INSERT INTO Player (name, active) VALUES (?, ?)",
                           (player.name, player.active))
            player_id = cursor.lastrowid

            for index, trade_detail in enumerate(trade_details):
                if trade_detail.player_id is None:
                    trade_details[index] = trade_detail._replace(player_id=player_id)
                    break  # Move to next player since unmatched players list order corresponds with trade_details.player_id is None list order

        for team in unmatched_teams:
            cursor.execute("""
                INSERT INTO Team (abbreviation, name, nickname)
                VALUES (?, ?, ?)
                ON CONFLICT(abbreviation) DO NOTHING
            """,(team.abbreviation, team.name, team.nickname))
            team_id = cursor.lastrowid
            if team_id == trade_id:  # No unmatched team inserted
                team_id = cursor.execute("SELECT id from TEAM WHERE abbreviation = ?", (team.abbreviation, )).fetchone()[0]

            for index, trade_detail in enumerate(trade_details):
                if trade_detail.from_team_id is None:
                    trade_details[index] = trade_detail._replace(from_team_id=team_id)
                    break  # Move to next team since unmatched teams list order corresponds with trade_details.from_team_id is None list order

        for trade_detail in trade_details:
            # print(f"Inserting: trade_id={trade_id}, player_id={trade_detail.player_id}, from_team_id={trade_detail.from_team_id}, to_team_id={trade_detail.to_team_id}")
            cursor.execute("""
                INSERT INTO TradeDetail (trade_id, player_id, from_team_id, to_team_id) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(player_id, from_team_id, to_team_id) DO NOTHING
            """, (trade_id, trade_detail.player_id, trade_detail.from_team_id, trade_detail.to_team_id))
            
        cursor.execute("COMMIT;")
        print(f"Transaction successful: {trade_id}")

    except Exception as e:
        cursor.execute("ROLLBACK;")
        raise e

        


if __name__ == "__main__":
    alternative_nickname_mapping = {
        "Mavs": "Mavericks",
        "Blazers": "Trail Blazers",
        "San Antonio": "Spurs",
        "Wolves": "Timberwolves"
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
            # print(f"*******START {index}")
            date = extract_date(block, year)
            trade = Trade(None, date, None)
            trade_details, unmatched_players, unmatched_teams = parse_block_to_trade_details(block)
            insert_trade_and_details(cursor, trade, trade_details, unmatched_players, unmatched_teams)
            # pprint.pprint(trade)
            # pprint.pprint(trade_details)
            # pprint.pprint(unmatched_players)
            # pprint.pprint(unmatched_teams)
            # print(f"*******END   {index}")



        # block_index = 5
        # current_block = blocks[block_index]

        # date = extract_date(current_block, year)
        # trade = Trade(None, date)

        # trade_details = parse_block_to_trade_details(current_block)
        # pprint.pprint(trade_details)
        