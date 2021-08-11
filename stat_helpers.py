# TO-DO:
# rework format_team_stats
# add arg to player_stats (include --all option)

# add total team kills, total team deaths, team K/D, etc to session_stats

# keep track of running stats
# most kills in one game (individual and team)
# most deaths in one game (individual and team)
# most damage in one game (individual and team)

# add more stats (damage taken, headshots, assists)


import time

# returns formatted list of players and their match stats
# player_dict format is expected to be {gamertag: [kills, deaths, damage]}
def format_team_stats(player_dict):
    format = ""
    for player, stats in player_dict.items():
        kills = stats[0]
        deaths = stats[1]
        kd_ratio = kills if deaths == 0 else round(kills / deaths, 2)
        damage = stats[2]

        player = map_player_name(player)
        format += f"    • {player}: {int(kills)}-{int(deaths)} ({kd_ratio} K/D), {int(damage)} damage.\n"

    return format

# formats cumulative session stats from the stats dictionary
def format_session_stats(stats_dict):
    team_matches = stats_dict["matches"]
    if team_matches == 0:
        return None

    start_time = stats_dict["session_start"]
    current_time = time.localtime()
    full_duration = round((time.mktime(current_time) - time.mktime(start_time)) / 60, 2)

    wins = stats_dict["wins"]
    win_str = "win" if wins == 1 else "wins"
    avg_placement = int(round(stats_dict["team_placements"] / team_matches, 2))

    return f"**Session Start**: {format_time(start_time)}\n" \
           f"**Matches Played**: {team_matches}\n" \
           f"**Average Team Placement**: {avg_placement} ({wins} {win_str})\n" \
           f"**Total Session Duration**: {full_duration} minutes\n"

# formats cumulative individual stats from the stats dictionary
def format_individual_stats(stats_dict, username):
    if stats_dict["matches"] == 0 or username not in stats_dict["players"]:
        return None

    player_stats = stats_dict["players"][username]
    kills = player_stats["kills"]
    deaths = player_stats["deaths"]
    damage = player_stats["damage"]
    matches = player_stats["individual_matches"] # separate from total matches in case player leaves early

    kd_ratio = kills if deaths == 0 else round(kills / deaths, 2)
    avg_kills = round(kills / matches, 2)
    avg_damage = round(damage / matches, 2)

    return f"Stats for **{username}**:\n" \
           f"**Matches Played**: {matches}\n" \
           f"**K/D**: {int(kills)}-{int(deaths)} ({kd_ratio})\n" \
           f"**Average Damage**: {avg_damage} ({int(damage)} total)\n"

# processes stats and assigns awards
# WIP
def format_awards(stats_dict):
    if team_matches == 0:
        return None

    best_kd = []
    worst_kd = []
    most_kills = []
    most_deaths = []

    for player, stats in stats_dict["players"]:
        kills = stats["kills"]
        deaths = stats["deaths"]
        damage = stats["damage"]
        kd_ratio = kills if deaths == 0 else round(kills / deaths, 2)


    # MVP (highest KD)
    # Carried (worst KD)
    # Bloodthirsty (most kills)
    # Cannon Fodder (most deaths)


# hardcode known gamertags to Discord message IDs
def map_player_name(player):
    if player == "bglowniak":
        player = "<@!250017966928691211>"
    elif player == "triplexlink":
        player = "<@!273518554517602305>"
    elif player == "funny_monkey998":
        player = "<@!479298269110075433>"
    elif player == "MisterDuV":
        player = "<@!425035767350296578>"
    elif player == "Sharkyplace":
        player = "<@!545430460860334082>"
    elif player == "TetoTeto":
        player = "<@!483853566281383946>"

    return player

def format_time(time_input):
    if time_input is None:
        return None

    return time.strftime("%m/%d %H:%M:%S", time_input)