import discord
from discord.ext import tasks
from discord.ext.commands import Bot, command, CommandNotFound
from dotenv import load_dotenv
import os
import random
import re
import requests
import logging

class LumberBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.greetings = ["hello", "hi", "hiya", "hey", "howdy",
                          "sup", "hola", "privet", "salve", "ciao",
                           "konnichiwa", "shalom"]
        load_dotenv()
        self.mention_id = os.getenv("BOT_MENTION_ID")
        self.salute_directory = os.getenv("SALUTE_DIRECTORY")
        self.cod_email = os.getenv("COD_EMAIL")
        self.cod_username = os.getenv("COD_USERNAME")
        self.cod_pw = os.getenv("COD_AUTH")

        self.most_recent_match_id = None # used for warzone win tracking

        # eventually add loop in init to add all commands regardless of number (to avoid having to hardcode)
        self.add_command(self.clip)

        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')

    #################################    EVENTS    #################################

    async def on_ready(self):
        logging.info(f'{self.user} has connected to Discord')
        self.general_channels = self.collect_general_channels()
        self.check_warzone_wins.start()

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

    # TO-DO: set up retries if API calls fail
    @tasks.loop(minutes=15.0)
    async def check_warzone_wins(self):
        logging.info("Running Warzone Win Tracker")
        api_session = self.authenticate_warzone_api(self.cod_email, self.cod_pw)

        # if API session is not successfully set up, don't proceed
        # TO-DO: set up retries if session setup fails
        if api_session is None:
            return

        base_URL = "https://my.callofduty.com/api/papi-client/"
        req_URL = base_URL + "crm/cod/v2/title/mw/platform/uno/gamer/" + self.cod_username + "/matches/wz/start/0/end/0/details"

        # this API request will return Warzone matches played in the last week. Although there is a start and end in the
        # URL, they don't work as expected and there is very little documentation as to what these attributes do.
        recent_matches = api_session.get(req_URL).json()["data"]["matches"]
        matches_checked = 0

        # the purpose of most_recent_match_id is to make sure we only process new matches added to the list (despite
        # pulling the full list each time)
        if self.most_recent_match_id == None:
            self.most_recent_match_id = recent_matches[0]["matchID"]
        elif recent_matches[0]["matchID"] != self.most_recent_match_id: # there are new matches to process
            for match in recent_matches:
                current_ID = match["matchID"]
                if current_ID == self.most_recent_match_id: # we have processed all new matches in the list
                    break

                placement = match["playerStats"]["teamPlacement"]
                if placement == 1: # we won a match
                    logging.info(f"Warzone win found with ID {current_ID}. Creating stats message.")
                    team = match["player"]["team"]
                    match_url = base_URL + "crm/cod/v2/title/mw/platform/uno/fullMatch/wz/" + current_ID + "/en"
                    match_data = api_session.get(match_url).json()

                    team_stats = {}

                    for player in match_data["data"]["allPlayers"]:
                        if player["player"]["team"] == team:
                            playerStats = player["playerStats"]
                            team_stats[player["player"]["username"]] = [playerStats["kills"], playerStats["deaths"], playerStats["damageDone"]]

                    duration = round((match["utcEndSeconds"] - match["utcStartSeconds"]) / 60, 2)
                    stats = self.format_stats(team_stats)
                    await self.general_channels["Bot Test Server"].send(f"Congratulations on a recent Warzone win!\n**Match Duration**: {duration} minutes\n**Team Stats**:\n{stats}")

                matches_checked += 1

            self.most_recent_match_id = recent_matches[0]["matchID"]

        logging.info(f"Win tracker run complete. {matches_checked} recent matches checked.")

    #################################    COMMANDS    #################################
    # eventually add command descriptions/help command?
    @command(name="clip")
    async def clip(ctx, args):
        pass

    #################################    HELPERS    #################################

    def check_for_big(self, message):
        words = message.split(" ")
        for index, word in enumerate(words):
            if word == "big" and index + 1 != len(words):
                return words[index + 1]

    def collect_general_channels(self):
        channels = {}
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == "general":
                    channels[guild.name] = channel

        return channels

    # returns formatted list of players and their match stats
    # player_dict format is expected to be {gamertag: [kills, deaths, damage]}
    def format_stats(self, player_dict):
        format = ""
        for player, stats in player_dict.items():
            kills = stats[0]
            deaths = stats[1]
            kd_ratio = kills if deaths == 0 else kills / deaths
            damage = stats[2]

            # hardcode known gamertags to Discord message IDs
            if player == "bglowniak":
                player = "<@!250017966928691211>"
            elif player == "triplexlink":
                player = "<@!273518554517602305>"
            elif player == "funny_monkey998":
                player = "<@!479298269110075433>"
            elif player == "MisterDuV":
                player = "<@!425035767350296578>"

            format += f"    • {player}: {int(kills)}-{int(deaths)} ({kd_ratio} K/D), {int(damage)} damage.\n"

        return format

    # TO-DO: Add checks + retries for when these requests don't return a status code of 200
    def authenticate_warzone_api(self, email, password):
        api_session = requests.Session()

        # Get CSRF Token for subsequent requests
        r = api_session.get("https://profile.callofduty.com/cod/login")
        XSRF_TOKEN = api_session.cookies["XSRF-TOKEN"]

        # Authenticate to the COD API
        login_url = "https://profile.callofduty.com/do_login?new_SiteId=cod"
        payload = {
            "username": email,
            "password": password,
            "remember_me": "true",
            "_csrf": XSRF_TOKEN
        }

        # a successful post request will set the atkn and rtkn cookies in the Session variable
        # this authenticates future API requests made with the same Session
        response = api_session.post(login_url, data=payload)

        if response.status_code == 200:
            logging.info("API Session successfully authenticated")
            return api_session
        else:
            logging.error(f"API session unable to be established with error code {response.status_code}")
            return None