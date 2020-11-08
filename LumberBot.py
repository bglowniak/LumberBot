import discord
from discord.ext import tasks
from discord.ext.commands import Bot, command
from dotenv import load_dotenv
import os
import random
import re
import requests

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

        self.add_command(self.tell)
        self.add_command(self.clip)

    # EVENTS
    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
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
            salute = random.choice(os.listdir(self.salute_directory))
            await message.channel.send(content=author_mention + " trip? triple? triplexlink?",
                                       file=discord.File(self.salute_directory + "/" + salute))

        # once we have checked the full message, process any commands that may be present
        await self.process_commands(message)


    @tasks.loop(minutes=30.0)
    async def check_warzone_wins(self):
        api_session = self.authenticate_warzone_api(self.cod_email, self.cod_pw)

        base_URL = "https://my.callofduty.com/api/papi-client/"
        req_URL = base_URL + "crm/cod/v2/title/mw/platform/uno/gamer/" + self.cod_username + "/matches/wz/start/0/end/0/details"

        #most_recent_match_id = None
        most_recent_match_id = "6359357863122988582"

        # TO-DO: Add loop so the code below executes every 15 (or 30?) minutes
        # TO-DO: Add better logging (checking matches, number of matches checked, etc.)

        # this API request will return Warzone matches played in the last week. Although there is a start and end in the
        # URL, they don't work as expected and there is very little documentation as to what these attributes do.
        recent_matches = api_session.get(req_URL).json()["data"]["matches"]

        # the purpose of most_recent_match_id is to make sure we only process new matches added to the list (despite
        # pulling the full list each time)
        if most_recent_match_id == None:
            most_recent_match_id = recent_matches[0]["matchID"]
        elif recent_matches[0]["matchID"] != most_recent_match_id: # there are new matches to process
            for match in recent_matches:
                current_ID = match["matchID"]
                if current_ID == most_recent_match_id: # we have processed all new matches in the list and thus can stop
                    break

                placement = match["playerStats"]["teamPlacement"]
                if placement == 1: # we won a match
                    print("Win spotted!")
                    team = match["player"]["team"]
                    match_url = base_URL + "crm/cod/v2/title/mw/platform/uno/fullMatch/wz/" + current_ID + "/en"
                    match_data = api_session.get(match_url).json()

                    team_stats = {}

                    for player in match_data["data"]["allPlayers"]:
                        if player["player"]["team"] == team:
                            team_stats[player["player"]["username"]] = player["playerStats"]["kills"]

                    stats = self.format_stats(team_stats)
                    await self.general_channels["Bot Test Server"].send("Congratulations on your recent win!  \nMatch Time:  \nTeam Kills:  \n" + stats)

            most_recent_match_id = recent_matches[0]["matchID"]

    # COMMANDS
    @command(name="tell")
    async def tell(ctx, arg1, *args):
        pass

    @command(name="clip")
    async def clip(ctx, args):
        pass

    # HELPERS
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

    # returns markdown formatted list of players and their match kills
    def format_stats(self, player_dict):
        format = ""
        for player, kills in player_dict.items():
            format += "    • " + player + ": " + str(int(kills)) + " kills  \n"

        return format

    # TO-DO: Add checks for when these requests don't return a status code of 200
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
            print("API Session successfully authenticated")

        return api_session