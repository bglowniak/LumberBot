import discord
from discord.ext import tasks
from discord.ext.commands import Bot, command, CommandNotFound, MissingRequiredArgument
from dotenv import load_dotenv
import os
import random
import re
import requests
import logging
import time
import json

from auth_helpers import authenticate_session
from stat_helpers import *

logger = logging.getLogger(__name__)

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
        self.atkn = os.getenv("ATKN")
        self.sso = os.getenv("ACT_SSO_COOKIE")

        self.debug = kwargs["debug"]

        self.most_recent_match_id = None # used for warzone win tracking
        #self.most_recent_match_id = "9429061249485592100"
        #self.most_recent_match_id = "10792965779580188529"

        # track cumulative stats throughout a session
        self.stats_dict = {
            "wins": 0,
            "matches": 0,
            "team_placements": 0,
            "session_start": None,
            "single_game_max_kills": ("", 0),
            "single_game_max_deaths": ("", 0),
            "players": {}
        }

        # eventually add loop in init to add all commands regardless of number (to avoid having to hardcode)
        self.add_command(self.session_stats)
        self.add_command(self.player_stats)
        self.add_command(self.awards)
        self.add_command(self.start_wz)
        self.add_command(self.end_wz)
        self.add_command(self.clear_channel)

    @property
    def session_start_time(self):
        return self.stats_dict["session_start"]

    @session_start_time.setter
    def session_start_time(self, new_time):
        self.stats_dict["session_start"] = new_time

    @property
    def formatted_start_time(self):
        return format_time(self.session_start_time)

    #################################    EVENTS    #################################

    async def on_ready(self):
        logging.info(f'{self.user} has connected to Discord')
        self.default_channels = self.collect_default_channels()
        if self.debug:
            self.server = "Bot Test Server"
        else:
            self.server = "lumber gang"
        logging.info(f"Debug mode: {self.debug}. Win messages will default to {self.server}")

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

    # general command error catch-all
    async def on_command_error(self, ctx, error):
        if isinstance(error, CommandNotFound):
            logging.debug(f"Command in message \"{ctx.message.content}\" not found. Ignoring.")
            return
        if isinstance(error, MissingRequiredArgument):
            # this error is handled in each specific command's error handler
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
                logging.error("API not authenticated. Please try re-generating tokens:")
                self.atkn = input("ATKN: ")
                self.sso = input("ACT_SSO_COOKIE: ")
                authenticate_session(api_session, self.atkn, self.sso)
                self.warzone_session_tracker.restart(api_session)
            else:
                logging.error(f"API returned 200 status code but there was an unknown error. API responded with {api_data}")
                return
        except KeyError:
            logging.error(f"Error indexing API response - check to see if expected key/values have changed. API responded with {api_data}")
            return

        #uncomment to dump API data to debug
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

                self.stats_dict["matches"] += 1

                # get basic match data
                placement = match["playerStats"]["teamPlacement"]
                self.stats_dict["team_placements"] += placement
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

                # collect individual match stats to report in case of win
                match_stats_dict = {}

                # collect stats for all players on my Warzone team
                for player in all_player_stats:
                    if player["player"]["team"] == team:
                        player_stats = player["playerStats"]
                        username = player["player"]["username"]

                        kills = player_stats["kills"]
                        deaths = player_stats["deaths"]
                        damage = player_stats["damageDone"]

                        # format stats for individual match
                        match_stats_dict[username] = {"kills": kills, "deaths": deaths, "damage": damage}

                        if not username in self.stats_dict["players"]:
                            self.stats_dict["players"][username] = { 
                                                                        "kills": 0, 
                                                                        "deaths": 0, 
                                                                        "damage": 0, 
                                                                        "individual_matches": 0,
                                                                        "headshots": 0,
                                                                        "assists": 0,
                                                                        "damage_taken": 0
                                                                   }

                        # log cumulative stats for session
                        self.stats_dict["players"][username]["kills"] += kills
                        self.stats_dict["players"][username]["deaths"] += deaths
                        self.stats_dict["players"][username]["damage"] += damage
                        self.stats_dict["players"][username]["individual_matches"] += 1
                        self.stats_dict["players"][username]["headshots"] += player_stats["headshots"]
                        self.stats_dict["players"][username]["assists"] += player_stats["assists"]
                        self.stats_dict["players"][username]["damage_taken"] += player_stats["damageTaken"]

                        if kills > self.stats_dict["single_game_max_kills"][1]:
                            self.stats_dict["single_game_max_kills"] = (username, kills)
                        
                        if deaths > self.stats_dict["single_game_max_deaths"][1]:
                            self.stats_dict["single_game_max_deaths"] = (username, deaths)

                        if kills >= 10:
                            logging.info(f"Found a 10+ kill game for {username}. Sending congrats message.")
                            discord_handle = map_player_name(username)
                            await self.default_channels[self.server].send(f"Congrats to {discord_handle} who has achieved **{int(kills)} kills** in a single Warzone match!")

                # if we won this match, send a congrats message to the channel
                if placement == 1:
                    self.stats_dict["wins"] += 1
                    logging.info(f"Warzone win found with ID {current_ID}. Creating stats message.")
                    match_start_time = time.strftime("%m/%d %H:%M:%S", time.localtime(match["utcStartSeconds"]))
                    stats = format_win_message_stats(match_stats_dict)
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
                    if self.stats_dict["wins"] % 3 == 0:
                        await self.default_channels[self.server].send("Ah shit, that's a triple dub. Good work team")
                matches_checked += 1

            # update most recent match ID to avoid re-processing any matches
            self.most_recent_match_id = recent_matches[0]["matchID"]

        logging.info(f"Win tracker run complete. {matches_checked} recent matches checked.")

    #################################    COMMANDS    #################################

    # start a new Warzone session
    # can only be invoked in private test server
    @command(name="start_wz")
    async def start_wz(ctx):
        if ctx.guild.name != "Bot Test Server":
            logging.info("start_wz command invoked in normal server. Ignoring.")
            return

        if ctx.bot.session_start_time is not None:
            logging.info("start_wz command invoked, but there is already an active session.")
            await ctx.channel.send(f"There is already an active session that was started at {ctx.bot.formatted_start_time}")
            return

        logging.info("start_wz invoked. Attempting to authenticate to the WZ API.")

        # create new API session and authenticate
        tracker_session = requests.Session()
        if not authenticate_session(tracker_session, ctx.bot.atkn, ctx.bot.sso):
            logging.error("API authentication failed three times. Tracker not started.")
            await ctx.channel.send("API authentication failed three times. Tracker not started.")
        else:
            logging.info(f"Starting Warzone session.")
            ctx.bot.warzone_session_tracker.start(tracker_session)
            ctx.bot.session_start_time = time.localtime()
            await ctx.channel.send("Warzone tracker started. Good luck, team.")

    # end a Warzone session and reset.
    # can only be invoked in private test server
    @command(name="end_wz")
    async def end_wz(ctx):
        if ctx.guild.name != "Bot Test Server":
            logging.info("end_wz command invoked in normal server. Ignoring.")
            return

        if ctx.bot.session_start_time is None:
            logging.info("end_wz command invoked, but there is currently no active session.")
            await ctx.channel.send("There is currently no active session to end.")
            return

        logging.info("Warzone session has ended. Stopping tracker.")
        ctx.bot.warzone_session_tracker.cancel()

        num_matches = ctx.bot.stats_dict["matches"]
        if num_matches == 0:
            await ctx.channel.send("Warzone tracker stopped. No matches were played.")
        else:
            await ctx.channel.send(f"Warzone tracker stopped. Good work out there.")

        # reset session variables
        ctx.bot.reset_session_variables()

    # return team's cumulative stats
    @command(name="session_stats")
    async def session_stats(ctx):
        if ctx.bot.session_start_time is None:
            logging.info("session_stats command invoked, but there is currently no active session.")
            await ctx.channel.send("There is currently no active session to report stats on.")
            return

        if ctx.bot.stats_dict["matches"] == 0:
            logging.info("session_stats command invoked, but no matches have been played.")
            await ctx.channel.send("No matches have been played.")
            return

        formatted_stats = format_session_stats(ctx.bot.stats_dict)
        logging.info("session_stats successfully invoked. Sending message.")
        await ctx.channel.send(formatted_stats)

    # return cumulative stats of an individual player
    @command(name="player_stats")
    async def player_stats(ctx, username_arg):
        if ctx.bot.session_start_time is None:
            logging.info("player_stats command invoked, but there is currently no active session.")
            await ctx.channel.send("There is no active session to report stats on.")
            return

        if ctx.bot.stats_dict["matches"] == 0:
            logging.info("player_stats command invoked, but no matches have been played.")
            await ctx.channel.send("No matches have been played.")
            return

        if username_arg == "--all" or username_arg == "-a": 
            formatted_stats = ""
            for player in ctx.bot.stats_dict["players"].keys():
                formatted_stats += format_individual_stats(ctx.bot.stats_dict, player) + "\n"
        elif username_arg in ctx.bot.stats_dict["players"]:
            formatted_stats = format_individual_stats(ctx.bot.stats_dict, username_arg)
        else:
            logging.info("player_stats command invoked, but no stats were found for inputted username.")
            await ctx.channel.send(f"{username_arg} has not played any matches. No stats to report.")
            return

        logging.info("player_stats successfully invoked. Sending message.")
        await ctx.channel.send(formatted_stats)

    @player_stats.error
    async def player_stats_error(ctx, error):
        if isinstance(error, MissingRequiredArgument):
            logging.error("No argument provided to player_stats command. Sending message to user.")
            await ctx.channel.send("Please specify a username to return stats for.")
            return

        raise error

    @command(name="awards")
    async def awards(ctx):
        if ctx.bot.session_start_time is None:
            logging.info("Awards command invoked, but there is currently no active session.")
            await ctx.channel.send("There is no active session to report stats on.")
            return

        if ctx.bot.stats_dict["matches"] == 0:
            logging.info("Awards command invoked, but no matches have been played.")
            await ctx.channel.send("No matches have been played.")
            return

        awards_message = format_awards(ctx.bot.stats_dict)
        logging.info("Awards successfully invoked. Sending message.")
        await ctx.channel.send(awards_message)

    @command(name="get_clip")
    async def get_clip(ctx, username_arg):
        logger.info("get_clip command not yet implemented.")
        return
    
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

    def reset_session_variables(self):
        self.session_start_time = None

        self.stats_dict["wins"] = 0
        self.stats_dict["team_placements"] = 0
        self.stats_dict["matches"] = 0
        self.stats_dict["single_game_max_kills"] = ("", 0)
        self.stats_dict["single_game_max_deaths"] = ("", 0)
        self.stats_dict["players"] = {}