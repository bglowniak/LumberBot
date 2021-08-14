import time

# returns formatted list of players and their match stats
def format_win_message_stats(match_stats_dict):
    format = ""
    for player, stats in match_stats_dict.items():
        kills = stats["kills"]
        deaths = stats["deaths"]
        kd_ratio = calc_kd(kills, deaths)
        damage = stats["damage"]

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

    total_kills = 0
    total_deaths = 0
    for _, stats in stats_dict["players"].items():
        total_kills += stats["kills"]
        total_deaths += stats["deaths"]

    team_kd = calc_kd(total_kills, total_deaths)

    max_kills = stats_dict['single_game_max_kills']
    max_deaths = stats_dict['single_game_max_deaths']

    return f"**Session Start**: {format_time(start_time)}\n" \
           f"**Matches Played**: {team_matches}\n" \
           f"**Team K/D**: {int(total_kills)}-{int(total_deaths)} ({team_kd})\n" \
           f"**Average Team Placement**: {avg_placement} ({wins} {win_str})\n" \
           f"**Max Kills**: {int(max_kills[1])} ({max_kills[0]})\n" \
           f"**Max Deaths**: {int(max_deaths[1])} ({max_deaths[0]})\n" \
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

    kd_ratio = calc_kd(kills, deaths)
    avg_kills = round(kills / matches, 2)
    avg_damage = round(damage / matches, 2)

    return f"Stats for **{username}**:\n" \
           f"**Matches Played**: {matches}\n" \
           f"**K/D**: {int(kills)}-{int(deaths)} ({kd_ratio})\n" \
           f"**Average Damage**: {avg_damage} ({int(damage)} total)\n"

# processes stats and assigns awards
def format_awards(stats_dict):
    if stats_dict["matches"] == 0:
        return None

    # if there is a tie, there will be multiple usernames in the list
    best_kd = -1
    best_kd_winners = []

    worst_kd = 10000
    worst_kd_winners = []

    most_kills = -1
    most_kills_winners = []

    most_deaths = -1
    most_deaths_winners = []

    best_damage_ratio = -1
    best_damage_winners = []

    for player, stats in stats_dict["players"].items():
        kills = stats["kills"]
        deaths = stats["deaths"]
        damage = stats["damage"]
        damage_taken = stats["damage_taken"]
        kd_ratio = calc_kd(kills, deaths)
        damage_ratio = calc_kd(damage, damage_taken) # should probably rename the func lol

        player = map_player_name(player)

        # MVP Award (Best KD Ratio)
        if kd_ratio == best_kd:
            best_kd_winners.append(player)
        elif kd_ratio > best_kd:
            best_kd_winners = [player] # clear list and replace with new winner
            best_kd = kd_ratio

        # Carried Award (Worst KD Ratio)
        if kd_ratio == worst_kd:
            worst_kd_winners.append(player)
        elif kd_ratio < worst_kd:
            worst_kd_winners = [player]
            worst_kd = kd_ratio

        # Bloodthirsty Award (Most Kills)
        if kills == most_kills:
            most_kills_winners.append(player)
        elif kills > most_kills:
            most_kills_winners = [player]
            most_kills = kills
        
        # Cannon Fodder Award (Most Deaths)
        if deaths == most_deaths:
            most_deaths_winners.append(player)
        elif deaths > most_deaths:
            most_deaths_winners = [player]
            most_deaths = deaths

        # Commando Award (Best Damage Ratio)
        if damage_ratio == best_damage_ratio:
            best_damage_winners.append(player)
        elif damage_ratio > best_damage_ratio:
            best_damage_winners = [player]
            best_damage_ratio = damage_ratio

    return f"**Awards**\n" \
           f"    •**MVP**: {', '.join(best_kd_winners)} ({best_kd} K/D)\n" \
           f"    •**Carried**: {', '.join(worst_kd_winners)} ({worst_kd} K/D)\n" \
           f"    •**Bloodthirsty**: {', '.join(most_kills_winners)} ({int(most_kills)} kills)\n" \
           f"    •**Cannon Fodder**: {', '.join(most_deaths_winners)} ({int(most_deaths)} deaths)\n" \
           f"    •**Commando**: {', '.join(best_damage_winners)} ({best_damage_ratio} damage ratio)"

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
    elif player == "cooliodude13":
        player = "<@!137213864872902656>"

    return player

def format_time(time_input):
    if time_input is None:
        return None

    return time.strftime("%m/%d %H:%M:%S", time_input)

def calc_kd(kills, deaths):
    return kills if deaths == 0 else round(kills / deaths, 2)