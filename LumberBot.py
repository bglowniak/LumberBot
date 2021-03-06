import discord
from discord.ext import tasks
from discord.ext.commands import Bot, command, CommandNotFound
from dotenv import load_dotenv
import os
import random
import re
import requests
import logging
import time
import json

class LumberBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.greetings = ["hello", "hi", "hiya", "hey", "howdy",
                          "sup", "hola", "privet", "salve", "ciao",
                           "konnichiwa", "shalom"]
        load_dotenv()
        self.mention_id = os.getenv("BOT_MENTION_ID")
        self.salute_directory = os.getenv("SALUTE_DIRECTORY")
        self.cod_username = os.getenv("COD_USERNAME")

        # needed for authentication to API. See authenticate_warzone_api function
        self.cod_email = os.getenv("COD_EMAIL")
        self.cod_pw = os.getenv("COD_AUTH")
        self.auth_token = os.getenv("AUTH_TOKEN")
        self.device_id = os.getenv("DEVICE_ID")

        self.debug = kwargs["debug"]

        self.most_recent_match_id = None # used for warzone win tracking

        # Session variables
        self.session_start_time = None
        self.public_session = False # private session = messages will only be seen by me.
        self.start_server = None # which server the start_wz command is invoked in
        self.wins = 0
        self.bglow_stats = {
            "kills": 0,
            "deaths": 0,
            "matches": 0,
            "damage": 0,
            "teamPlacements": 0
        }

        # eventually add loop in init to add all commands regardless of number (to avoid having to hardcode)
        self.add_command(self.session_stats)
        self.add_command(self.start_wz)
        self.add_command(self.end_wz)
        self.add_command(self.clear_channel)

        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')

    @property
    def formatted_start_time(self):
        if self.session_start_time is None:
            return None

        return time.strftime("%m/%d %H:%M:%S", self.session_start_time)

    #################################    EVENTS    #################################

    async def on_ready(self):
        logging.info(f'{self.user} has connected to Discord')
        self.default_channels = self.collect_default_channels()
        if self.debug:
            self.server = "Bot Test Server"
        else:
            self.server = "lumber gang"
        logging.info(f"Debug mode: {self.debug}. Messages will default to {self.server}")

    # override on_message to implement some functionality outside of normal commands
    async def on_message(self, message):
        if message.author == self.user or message.author.bot:
            return

        content = message.content.strip().lower()
        author_mention = "<@!" + str(message.author.id) + ">"

        # check if the message @s our bot and greets it. Respond with a random greeting
        # didn't make this a separate command because this allows the bot to respond regardless
        # of punctuation or where the greeting is placed in the message
        if content.startswith(self.mention_id):
            # check for greeting
            greeting_patterns = "|".join(self.greetings)
            if re.search(rf'\b({greeting_patterns})\b', content):
                random_greeting = random.choice(self.greetings)
                response = author_mention + " " + random_greeting + "!"
                await message.channel.send(response)

        '''# check if the message includes "big _______" and respond accordingly
        next_word = self.check_for_big(content)
        if next_word != None:
            response = author_mention + " what kind of " + next_word + "?"
            await message.channel.send(response)
        else:
            print("No Big Detected")'''

        if "trip" in content:
            logging.info("\"trip\" detected in message. Sending response.")
            salute = random.choice(os.listdir(self.salute_directory))
            await message.channel.send(content=author_mention + " trip? triple? triplexlink?",
                                       file=discord.File(self.salute_directory + "/" + salute))

        # once we have checked the full message, process any commands that may be present
        await self.process_commands(message)

    # add help command functionality at some point
    async def on_command_error(self, ctx, error):
        if isinstance(error, CommandNotFound):
            logging.warning(f"Command in message \"{ctx.message.content}\" not found. Ignoring.")
            return
        raise error

    #################################    TASKS    #################################

    # started and stopped via the start_wz and end_wz commands
    @tasks.loop(minutes=8.0) # turned from 10 -> 8 to account for faster Rebirth matches
    async def warzone_session_tracker(self, api_session):
        logging.info("Running Warzone Win Tracker loop")

        # collect Warzone matches played in the last week.
        # start and end parameters don't actually work as expected
        base_URL = "https://my.callofduty.com/api/papi-client/"
        req_URL = base_URL + "crm/cod/v2/title/mw/platform/uno/gamer/" + self.cod_username + "/matches/wz/start/0/end/0/details"
        resp = api_session.get(req_URL)

        if resp.status_code != 200:
            logging.error(f"Unable to retrieve data from Warzone API. API responded with {resp.status_code}")
            return

        api_data = resp.json()

        # confirm that API is still authenticated and that response is as expected
        try:
            if api_data["status"] == "success":
                recent_matches = api_data["data"]["matches"]
                logging.info("Match data successfully retrieved.")
            elif api_data["data"]["message"] == "Not permitted: not authenticated":
                logging.error("API not authenticated. Attempting to reconnect.")
                if not self.authenticate_session(api_session):
                    logging.error("API authentication failed three times. Will retry on next iteration.")
                    return
                else:
                    logging.info("Restarting tracker.")
                    self.warzone_session_tracker.restart(api_session)
            else:
                logging.error(f"API returned 200 status code but there was an unknown error. API responded with {api_data}")
                return
        except KeyError:
            logging.error(f"Error indexing API response - check to see if expected key/values have changed. API responded with {api_data}")
            return

        # uncomment to dump API data to debug
        # with open("dump.json", "w") as f:
        #    f.write(json.dumps(recent_matches, indent=4))
        # return

        matches_checked = 0

        # the purpose of most_recent_match_id is to make sure we only process new matches added to the list
        if self.most_recent_match_id == None:
            self.most_recent_match_id = recent_matches[0]["matchID"]
        elif recent_matches[0]["matchID"] != self.most_recent_match_id: # there are new matches to process
            for match in recent_matches:
                current_ID = match["matchID"]
                if current_ID == self.most_recent_match_id: # we have processed all new matches in the list
                    break

                # get basic match data
                placement = match["playerStats"]["teamPlacement"]
                team = match["player"]["team"]
                duration = round((match["utcEndSeconds"] - match["utcStartSeconds"]) / 60, 2)

                # use match ID to get more detailed data/stats
                match_url = base_URL + "crm/cod/v2/title/mw/platform/uno/fullMatch/wz/" + current_ID + "/en"
                match_data = api_session.get(match_url).json()

                # no API auth or response checks here - if we don't get the expected data, just skip
                try:
                    all_player_stats = match_data["data"]["allPlayers"]
                except KeyError:
                    logging.error(f"Unable to retrieve match data from Warzone API. API responded with {match_data}")
                    continue

                team_stats = {}

                # collect stats for all players on my Warzone team
                for player in all_player_stats:
                    if player["player"]["team"] == team:
                        playerStats = player["playerStats"]
                        username = player["player"]["username"]
                        kills = playerStats["kills"] # putting this in var because we use it multiple times
                        team_stats[username] = [kills, playerStats["deaths"], playerStats["damageDone"]]

                        # log my individual stats separately
                        if username == "bglowniak":
                            self.bglow_stats["matches"] += 1
                            self.bglow_stats["kills"] += kills
                            self.bglow_stats["deaths"] += playerStats["deaths"]
                            self.bglow_stats["damage"] += playerStats["damageDone"]
                            self.bglow_stats["teamPlacements"] += placement

                        if kills >= 10:
                            logging.info(f"Found a 10+ kill game for {username}. Sending congrats message.")
                            discord_handle = self.map_player_name(username)
                            await self.default_channels[self.server].send(f"Congrats to {discord_handle} who has achieved **{int(kills)} kills** in a single Warzone match!")

                # if we won this match, send a congrats message to the channel
                if placement == 1:
                    self.wins += 1
                    logging.info(f"Warzone win found with ID {current_ID}. Creating stats message.")
                    match_start_time = time.strftime("%m/%d %H:%M:%S", time.localtime(match["utcStartSeconds"]))
                    stats = self.format_team_stats(team_stats)
                    salute = random.choice(os.listdir(self.salute_directory))

                    map = match["map"]
                    if map == "mp_don3" or map == "mp_don4":
                        map = "Verdansk"
                    elif map == "mp_escape2" or map == "mp_escape3":
                        map = "Rebirth"

                    await self.default_channels[self.server].send(content="Congratulations on a recent Warzone win!\n" \
                                                                            f"**Match Start Time**: {match_start_time}\n" \
                                                                            f"**Match Duration**: {duration} minutes\n" \
                                                                            f"**Map**: {map}\n" \
                                                                            f"**Team Stats**:\n{stats}",
                                                                    file=discord.File(self.salute_directory + "/" + salute))
                    if self.wins % 3 == 0:
                        await self.default_channels[self.server].send("Ah shit, that's a triple dub. Good work team")
                matches_checked += 1

            # update most recent match ID to avoid re-processing any matches
            self.most_recent_match_id = recent_matches[0]["matchID"]

        logging.info(f"Win tracker run complete. {matches_checked} recent matches checked.")

    #################################    COMMANDS    #################################

    # start a new Warzone session
    @command(name="start_wz")
    async def start_wz(ctx):
        if ctx.guild.name != "Bot Test Server":
            logging.info("start_wz command invoked in normal server. Ignoring.")
            return

        if ctx.bot.session_start_time is not None:
            logging.info("start_wz command invoked, but there is already an active session.")
            await ctx.channel.send(f"There is already an active session that was started at {ctx.bot.formatted_start_time}")
            return

        ctx.bot.public_session = False # = (ctx.guild.name != "Bot Test Server"), currently redundant
        ctx.bot.start_server = ctx.guild.name
        session_type = "Public" if ctx.bot.public_session else "Private" # currently redundant

        logging.info("start_wz invoked. Attempting to authenticate to the WZ API.")

        # create new API session and authenticate
        tracker_session = requests.Session()
        if not ctx.bot.authenticate_session(tracker_session):
            logging.error("API authentication failed three times. Tracker not started.")
            await ctx.channel.send("API authentication failed three times. Tracker not started.")
        else:
            logging.info(f"Starting {session_type} Warzone session.")
            ctx.bot.warzone_session_tracker.start(tracker_session)
            ctx.bot.session_start_time = time.localtime()
            await ctx.channel.send("Warzone tracker started. Good luck, team.")

    # end a Warzone session, send stats, and then reset.
    @command(name="end_wz")
    async def end_wz(ctx):
        if ctx.guild.name != "Bot Test Server":
            logging.info("end_wz command invoked in normal server. Ignoring.")
            return

        if ctx.bot.session_start_time is None:
            logging.info("end_wz command invoked, but there is currently no active session.")
            await ctx.channel.send("There is currently no active session to end.")
            return

        # a session can only be ended in the same server it was started in
        # this block is currently unnecessary, but will be needed if I allow sessions to be activated in the normal server
        if ctx.guild.name != ctx.bot.start_server:
            logging.info("end_wz command invoked in server different from where it started.")
            await ctx.channel.send("There is currently no active session to end.")

        logging.info("Warzone session has ended. Stopping tracker.")
        ctx.bot.warzone_session_tracker.cancel()

        num_matches = ctx.bot.bglow_stats["matches"]
        if num_matches == 0:
            await ctx.channel.send("Warzone tracker stopped. No matches were played.")
        elif ctx.bot.public_session:
            avg_placement = int(round(ctx.bot.bglow_stats["teamPlacements"] / num_matches, 2))
            await ctx.channel.send(f"Warzone tracker stopped. The team played {num_matches} games with an average placement of {avg_placement}.")
        else: # the session is private, so we can send my individual stats
            formatted_stats = ctx.bot.format_individual_stats(time.localtime())
            await ctx.channel.send(f"Warzone tracker stopped. Here are your final stats:\n{formatted_stats}")

        # reset session variables
        ctx.bot.reset_session_variables()

    # return my individual stats. Only works in my private test server.
    @command(name="session_stats")
    async def session_stats(ctx):
        if ctx.guild.name != "Bot Test Server": # this command is only for private use
            logging.info("Stats command invoked in normal server. Ignoring.")
            return

        if ctx.bot.session_start_time is None:
            logging.info("Stats command invoked, but there is currently no active session.")
            await ctx.channel.send("There is currently no active session to report stats on.")
            return

        formatted_stats = ctx.bot.format_individual_stats(time.localtime())

        if formatted_stats is None: # there were 0 matches to process
            logging.info("Stats command invoked with 0 matches logged. Skipping processing and informing user.")
            await ctx.channel.send("No matches logged for active session.")
            return

        logging.info("Stats command invoked. Processing logged stats and sending message.")
        await ctx.channel.send(f"Here are your current session stats:\n{formatted_stats}")

    @command(name="clear_channel")
    async def clear_channel(ctx):
        logging.info(f"Clearing #{ctx.channel} in {ctx.guild.name}")
        await ctx.channel.purge()

    #################################    HELPERS    #################################

    def check_for_big(self, message):
        words = message.split(" ")
        for index, word in enumerate(words):
            if word == "big" and index + 1 != len(words):
                return words[index + 1]

    def collect_default_channels(self):
        channels = {}
        for guild in self.guilds:
            for channel in guild.text_channels:
                if (guild.name == "lumber gang" and channel.name == "wz_bot") or (guild.name == "Bot Test Server" and channel.name == "general"):
                    channels[guild.name] = channel

        return channels

    # returns formatted list of players and their match stats
    # player_dict format is expected to be {gamertag: [kills, deaths, damage]}
    def format_team_stats(self, player_dict):
        format = ""
        for player, stats in player_dict.items():
            kills = stats[0]
            deaths = stats[1]
            kd_ratio = kills if deaths == 0 else round(kills / deaths, 2)
            damage = stats[2]

            player = self.map_player_name(player)
            format += f"    • {player}: {int(kills)}-{int(deaths)} ({kd_ratio} K/D), {int(damage)} damage.\n"

        return format

    # formats individual stats from the bglow_stats dictionary
    def format_individual_stats(self, current_time):
        matches = self.bglow_stats["matches"]
        if matches == 0:
            return None

        kills = self.bglow_stats["kills"]
        deaths = self.bglow_stats["deaths"]
        damage = self.bglow_stats["damage"]
        kd_ratio = kills if deaths == 0 else round(kills / deaths, 2)
        avg_kills = round(kills / matches, 2)
        avg_damage = round(damage / matches, 2)
        full_duration = round((time.mktime(current_time) - time.mktime(self.session_start_time)) / 60, 2)
        avg_placement = int(round(self.bglow_stats["teamPlacements"] / matches, 2))
        win_str = "win" if self.wins == 1 else "wins"

        return f"**Session Start**: {self.formatted_start_time}\n" \
               f"**Matches Played**: {matches}\n" \
               f"**Average Team Placement**: {avg_placement} ({self.wins} {win_str})\n" \
               f"**K/D**: {int(kills)}-{int(deaths)} ({kd_ratio})\n" \
               f"**Average Damage**: {avg_damage} ({int(damage)} total)\n" \
               f"**Total Session Duration**: {full_duration} minutes\n"

    # hardcode known gamertags to Discord message IDs
    def map_player_name(self, player):
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

    # takes in a session object and attempts to set the required cookies to make WZ API calls
    def authenticate_warzone_api(self, session):
        # how to regenerate device_id and auth_token if needed
        #device_id = hex(random.getrandbits(128)).lstrip("0x")
        #payload =  {"deviceId": device_id}
        #resp = s.post('https://profile.callofduty.com/cod/mapp/registerDevice', json=payload)
        #auth_token = resp.json()['data']['authHeader']

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "x_cod_device_id" : self.device_id,
        }

        data = {'email': self.cod_email, 'password': self.cod_pw}
        response = session.post('https://profile.callofduty.com/cod/mapp/login', headers=headers, json=data)

        if response.status_code == 200 and response.json()["success"] == True:
            logging.info("API Session successfully authenticated")
        else:
            logging.error(f"API session unable to be established. API returned {response.text}")
            raise Exception("API authentication failure")

    # helper function for session authentication. Retries 3 times in case of failure.
    def authenticate_session(self, session):
        connecting = True
        attempts = 0
        while connecting and attempts < 3:
            try:
                self.authenticate_warzone_api(session)
                connecting = False
            except:
                attempts += 1
                if attempts < 3: time.sleep(5) # space out attempts

        return (attempts != 3)

    def reset_session_variables(self):
        self.session_start_time = None
        self.start_server = None
        self.public_session = False
        self.wins = 0
        for key in self.bglow_stats:
            self.bglow_stats[key] = 0
