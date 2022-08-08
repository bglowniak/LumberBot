import time


class StatTracker():
    def __init__(self):
        self.session_start = None
        self.stats_dict = {
            "wins": 0,
            "matches": 0,
            "team_placements": 0,
            "players": {}
        }

    def set_start_time(self, time):
        self.session_start = time

    def get_wins(self):
        return self.stats_dict["wins"]

    def get_num_matches(self):
        return self.stats_dict["matches"]

    def get_usernames(self):
        return self.stats_dict["players"].keys()

    def update_cumulative_match_stats(self, placement):
        self.stats_dict["matches"] += 1
        self.stats_dict["team_placements"] += placement

    def update_cumulative_player_stats(self, username, player_stats):
        if username not in self.stats_dict["players"]:
            self.stats_dict["players"][username] = {
                "kills": 0,
                "deaths": 0,
                "damage": 0,
                "individual_matches": 0,
                "headshots": 0,
                "assists": 0,
                "damage_taken": 0,
                "max_kills": 0,
                "max_deaths": 0
            }

        kills = player_stats["kills"]
        deaths = player_stats["deaths"]

        self.stats_dict["players"][username]["kills"] += kills
        self.stats_dict["players"][username]["deaths"] += deaths
        self.stats_dict["players"][username]["damage"] += player_stats["damageDone"]
        self.stats_dict["players"][username]["individual_matches"] += 1
        self.stats_dict["players"][username]["headshots"] += player_stats["headshots"]
        self.stats_dict["players"][username]["assists"] += player_stats["assists"]
        self.stats_dict["players"][username]["damage_taken"] += player_stats["damageTaken"]

        if kills > self.stats_dict["players"][username]["max_kills"]:
            self.stats_dict["players"][username]["max_kills"] = kills

        if deaths > self.stats_dict["players"][username]["max_deaths"]:
            self.stats_dict["players"][username]["max_deaths"] = deaths

    def format_win_message(self, match_data, match_stats):
        self.stats_dict["wins"] += 1

        match_start_time = time.strftime("%m/%d %H:%M:%S", time.localtime(match_data["utcStartSeconds"]))
        duration = round((match_data["utcEndSeconds"] - match_data["utcStartSeconds"]) / 60, 2)
        stats = self.format_win_message_stats(match_stats)
        map_name = self._replace_map_name(match_data["map"])

        message = "Congratulations on a recent Warzone win!\n" \
                  f"**Match Start Time**: {match_start_time}\n" \
                  f"**Match Duration**: {duration} minutes\n" \
                  f"**Map**: {map_name}\n" \
                  f"**Team Stats**:\n{stats}"

        return message

    # returns formatted list of players and their match stats
    def format_win_message_stats(self, match_stats):
        format = ""
        for player, stats in match_stats.items():
            kills = stats["kills"]
            deaths = stats["deaths"]
            kd_ratio = self._calc_ratio(kills, deaths)
            damage = stats["damage"]

            player = self._replace_player_name(player)
            format += f"    • {player}: {int(kills)}-{int(deaths)} ({kd_ratio} K/D), {int(damage)} damage.\n"

        return format

    # formats cumulative session stats from the stats dictionary
    def format_session_stats(self):
        team_matches = self.stats_dict["matches"]
        if team_matches == 0:
            return None

        current_time = time.localtime()
        full_duration = round((time.mktime(current_time) - time.mktime(self.session_start)) / 60, 2)

        wins = self.stats_dict["wins"]
        win_str = "win" if wins == 1 else "wins"
        avg_placement = int(round(self.stats_dict["team_placements"] / team_matches, 2))

        total_kills = 0
        total_deaths = 0
        max_kills = 0
        max_deaths = 0
        max_kills_usernames = set()
        max_deaths_usernames = set()
        for player, stats in self.stats_dict["players"].items():
            total_kills += stats["kills"]
            total_deaths += stats["deaths"]
            player_max_kills = stats["max_kills"]
            player_max_deaths = stats["max_deaths"]
            if player_max_kills > max_kills:
                max_kills = player_max_kills
                max_kills_usernames = {player}
            if player_max_kills == max_kills:
                max_kills_usernames.add(player)
            if player_max_deaths > max_deaths:
                max_deaths = player_max_deaths
                max_deaths_usernames = {player}
            if player_max_deaths == max_deaths:
                max_deaths_usernames.add(player)

        team_kd = self._calc_ratio(total_kills, total_deaths)

        max_kills_usernames = ', '.join(max_kills_usernames)
        max_deaths_usernames = ', '.join(max_deaths_usernames)

        return f"**Session Start**: {self._format_time(self.session_start)}\n" \
               f"**Matches Played**: {team_matches}\n" \
               f"**Team K/D**: {int(total_kills)}-{int(total_deaths)} ({team_kd})\n" \
               f"**Average Team Placement**: {avg_placement} ({wins} {win_str})\n" \
               f"**Max Kills**: {int(max_kills)} ({max_kills_usernames})\n" \
               f"**Max Deaths**: {int(max_deaths)} ({max_deaths_usernames})\n" \
               f"**Total Session Duration**: {full_duration} minutes\n"

    # formats cumulative individual stats from the stats dictionary
    def format_individual_stats(self, username):
        if self.stats_dict["matches"] == 0 or username not in self.stats_dict["players"]:
            return None

        player_stats = self.stats_dict["players"][username]
        kills = player_stats["kills"]
        deaths = player_stats["deaths"]
        damage = player_stats["damage"]
        matches = player_stats["individual_matches"]
        max_kills = player_stats["max_kills"]
        max_deaths = player_stats["max_deaths"]

        kd_ratio = self._calc_ratio(kills, deaths)
        avg_kills = round(kills / matches, 2)
        avg_deaths = round(deaths / matches, 2)
        avg_damage = round(damage / matches, 2)

        return f"Stats for **{username}**:\n" \
               f"**Matches Played**: {matches}\n" \
               f"**K/D**: {int(kills)}-{int(deaths)} ({kd_ratio})\n" \
               f"**Average Kills**: {avg_kills} (Max: {int(max_kills)})\n" \
               f"**Average Deaths**: {avg_deaths} (Max: {int(max_deaths)})\n" \
               f"**Average Damage**: {avg_damage} ({int(damage)} total)\n"

    # processes stats and assigns awards
    def format_awards(self):
        if self.stats_dict["matches"] == 0:
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

        for player, stats in self.stats_dict["players"].items():
            kills = stats["kills"]
            deaths = stats["deaths"]
            damage = stats["damage"]
            damage_taken = stats["damage_taken"]
            kd_ratio = self._calc_ratio(kills, deaths)
            damage_ratio = self._calc_ratio(damage, damage_taken)

            player = self._replace_player_name(player)

            # MVP Award (Best KD Ratio)
            if kd_ratio == best_kd:
                best_kd_winners.append(player)
            elif kd_ratio > best_kd:
                best_kd_winners = [player]  # clear list and replace with new winner
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
    def _replace_player_name(self, player):
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

    # replace map IDs with known map name
    def _replace_map_name(self, map_name):
        if map_name.startswith("mp_don"):
            return "Verdansk"
        elif map_name.startswith("mp_escape"):
            return "Rebirth"
        elif map_name.startswith("mp_wz_island"):
            return "Caldera"
        elif map_name.startswith("mp_sm_island"):
            return "Fortune's Keep"
        else:
            return map_name

    def _format_time(self, time_input):
        if time_input is None:
            return None

        return time.strftime("%m/%d %H:%M:%S", time_input)

    def _calc_ratio(self, kills, deaths):
        return kills if deaths == 0 else round(kills / deaths, 2)
