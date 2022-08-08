import os
import random
import re
import logging
import time
from discord import File
from discord.ext import tasks
from discord.ext.commands import Bot, command, CommandNotFound

from api_session import WarzoneApi
from stat_tracker import StatTracker

logger = logging.getLogger(__name__)


class LumberBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.greetings = ["hello", "hi", "hiya", "hey", "howdy",
                          "sup", "hola", "privet", "salve", "ciao",
                          "konnichiwa", "shalom"]

        self.mention_id = os.getenv("BOT_MENTION_ID")
        self.salute_directory = os.getenv("SALUTE_DIRECTORY")
        self.cod_username = os.getenv("COD_USERNAME")

        self.debug = kwargs["debug"]

        # self.most_recent_match_id = None # used for warzone win tracking
        self.most_recent_match_id = "12195181859429414966"
        self.session_active = False

        self.api = WarzoneApi()
        self.stat_tracker = StatTracker()

        # eventually add loop in init to add all commands regardless of number (to avoid having to hardcode)
        self.add_command(self.session_stats)
        self.add_command(self.player_stats)
        self.add_command(self.awards)
        self.add_command(self.start_wz)
        self.add_command(self.end_wz)
        self.add_command(self.clear_channel)

    def collect_default_channels(self):
        channels = {}
        for guild in self.guilds:
            for channel in guild.text_channels:
                if (guild.name == "lumber gang" and channel.name == "wz_bot") or (guild.name == "Bot Test Server" and channel.name == "general"):
                    channels[guild.name] = channel

        return channels

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

        if "trip" in content:
            logging.info("\"trip\" detected in message. Sending response.")
            salute = random.choice(os.listdir(self.salute_directory))
            await message.channel.send(content=author_mention + " trip? triple? triplexlink?",
                                       file=File(self.salute_directory + "/" + salute))

        # once we have checked the full message, process any commands that may be present
        await self.process_commands(message)

    # general command error catch-all
    async def on_command_error(self, ctx, error):
        if isinstance(error, CommandNotFound):
            logging.debug(f"Command in message \"{ctx.message.content}\" not found. Ignoring.")
            return
        else:
            raise error
            # TODO: include more info
            # logger.error("Error invoking command")

    #################################    TASKS    #################################

    # started and stopped via the start_wz and end_wz commands
    @tasks.loop(minutes=8.0)  # turned from 10 -> 8 to account for faster Rebirth matches
    async def warzone_session_tracker(self):
        logging.info("Running Warzone Win Tracker loop")

        try:
            recent_matches = self.api.get_matches(self.cod_username)
        except Exception as e:
            logger.error(f"Get Recent Matches call failed: {e}")
            return

        # uncomment to dump API data to debug
        # with open("dump.json", "w") as f:
        #   f.write(json.dumps(recent_matches, indent=4))
        # return

        matches_checked = 0

        # the purpose of most_recent_match_id is to make sure we only process new matches added to the list
        if self.most_recent_match_id is None:
            self.most_recent_match_id = recent_matches[0]["matchID"]
        elif recent_matches[0]["matchID"] != self.most_recent_match_id:  # there are new matches to process
            for match in recent_matches:
                current_ID = match["matchID"]
                if current_ID == self.most_recent_match_id:  # we have processed all new matches in the list
                    break

                # get basic match data
                placement = match["playerStats"]["teamPlacement"]
                self.stat_tracker.update_cumulative_match_stats(placement)
                team = match["player"]["team"]

                # no API auth or response checks here - if we don't get the expected data, just skip
                try:
                    all_player_stats = self.api.get_match_details(current_ID)
                except Exception as e:
                    logging.error(f"Match Details call failed: {e}")
                    continue

                # collect individual match stats to report in case of win
                match_stats_dict = {}

                # collect stats for all players on my Warzone team
                for player in all_player_stats:
                    if player["player"]["team"] == team:
                        player_stats = player["playerStats"]
                        username = player["player"]["username"]

                        self.stat_tracker.update_cumulative_player_stats(username, player_stats)

                        # format stats for individual match
                        kills = player_stats["kills"]
                        deaths = player_stats["deaths"]
                        damage = player_stats["damageDone"]
                        match_stats_dict[username] = {"kills": kills, "deaths": deaths, "damage": damage}

                        if kills >= 10:
                            logging.info(f"Found a 10+ kill game for {username}. Sending congrats message.")
                            # TODO: differently?
                            discord_handle = self.stat_tracker._map_player_name(username)
                            await self.default_channels[self.server].send(f"Congrats to {discord_handle} who has achieved **{int(kills)} kills** in a single Warzone match!")

                # if we won this match, send a congrats message to the channel
                if placement == 1:
                    logging.info(f"Warzone win found with ID {current_ID}. Creating stats message.")
                    salute = random.choice(os.listdir(self.salute_directory))
                    win_message = self.stat_tracker.format_win_message(match, match_stats_dict)

                    await self.default_channels[self.server].send(content=win_message,
                                                                  file=File(self.salute_directory + "/" + salute))
                    if self.stat_tracker.get_wins() % 3 == 0:
                        await self.default_channels[self.server].send("Ah shit, that's a triple dub. Good work team")
                matches_checked += 1

            # update most recent match ID to avoid re-processing any matches
            self.most_recent_match_id = recent_matches[0]["matchID"]

        logging.info(f"Win tracker run complete. {matches_checked} recent matches checked.")

    #################################    COMMANDS    #################################

    # start a new Warzone session
    # can only be invoked in private test server
    @command(name="start_wz")
    async def start_wz(ctx, use_existing_stats=None):
        if ctx.guild.name != "Bot Test Server":
            logging.info("start_wz command invoked in normal server. Ignoring.")
            return

        if ctx.bot.session_active:
            logging.info("start_wz command invoked, but there is already an active session.")
            await ctx.channel.send("There is already an active session.")
            return

        logging.info("Starting Warzone session.")

        if use_existing_stats != "-c":
            ctx.bot.stat_tracker = StatTracker()

        ctx.bot.warzone_session_tracker.start()
        ctx.bot.stat_tracker.set_start_time(time.localtime())
        ctx.bot.session_active = True
        await ctx.channel.send("Warzone tracker started. Good luck, team.")

    # end a Warzone session and reset.
    # can only be invoked in private test server
    @command(name="end_wz")
    async def end_wz(ctx):
        if ctx.guild.name != "Bot Test Server":
            logging.info("end_wz command invoked in normal server. Ignoring.")
            return

        if not ctx.bot.session_active:
            logging.info("end_wz command invoked, but there is currently no active session.")
            await ctx.channel.send("There is currently no active session to end.")
            return

        logging.info("Warzone session has ended. Stopping tracker.")
        ctx.bot.warzone_session_tracker.cancel()
        ctx.bot.session_active = False

        if ctx.bot.stat_tracker.get_num_matches() == 0:
            await ctx.channel.send("Warzone tracker stopped. No matches were played.")
        else:
            await ctx.channel.send("Warzone tracker stopped. Good work out there.")

    # return team's cumulative stats
    @command(name="session_stats")
    async def session_stats(ctx):
        if ctx.bot.stat_tracker.get_num_matches() == 0:
            logging.info("session_stats command invoked, but no matches have been played.")
            await ctx.channel.send("No matches have been played.")
            return

        formatted_stats = ctx.bot.stat_tracker.format_session_stats()
        logging.info("session_stats successfully invoked. Sending message.")
        await ctx.channel.send(formatted_stats)

    # return cumulative stats of an individual player
    @command(name="player_stats")
    async def player_stats(ctx, username_arg=None):
        if ctx.bot.stat_tracker.get_num_matches() == 0:
            logging.info("player_stats command invoked, but no matches have been played.")
            await ctx.channel.send("No matches have been played.")
            return

        # TODO: refactor, add this functionality to stattracker?
        # Handle case when username arg is None
        # if username_arg == None: # return all player stats
        #    formatted_stats = ""
        #    for player in ctx.bot.stats_dict["players"].keys():
        #        formatted_stats += format_individual_stats(ctx.bot.stats_dict, player) + "\n"

        formatted_stats = ctx.bot.stat_tracker.format_individual_stats(username_arg)

        if formatted_stats:
            logging.info("player_stats successfully invoked. Sending message.")
            await ctx.channel.send(formatted_stats)
        else:
            logging.info("player_stats command invoked, but no stats were found for inputted username.")
            await ctx.channel.send(f"{username_arg} has not played any matches. No stats to report.")

    @command(name="awards")
    async def awards(ctx):
        if ctx.bot.stat_tracker.get_num_matches() == 0:
            logging.info("Awards command invoked, but no matches have been played.")
            await ctx.channel.send("No matches have been played.")
            return

        awards_message = ctx.bot.stat_tracker.format_awards()
        logging.info("Awards successfully invoked. Sending message.")
        await ctx.channel.send(awards_message)

    @command(name="clear_channel")
    async def clear_channel(ctx):
        logging.info(f"Clearing #{ctx.channel} in {ctx.guild.name}")
        await ctx.channel.purge()
