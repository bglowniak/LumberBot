import discord
import os
from dotenv import load_dotenv
import random
import re

class LumberBot(discord.Client):
    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        load_dotenv()
        self.mention_id = os.getenv("BOT_MENTION_ID")
        self.greetings = ["hello", "hi", "hiya", "hey", "howdy",
                          "sup", "hola", "privet", "salve", "ciao",
                           "konnichiwa", "shalom"]

    async def on_message(self, message):
        # first check if the message author is our LumberBot or another bot
        if message.author == self.user or message.author.bot:
            return

        content = message.content.strip().lower()
        author_mention = "<@!" + str(message.author.id) + ">"

        # check if the message @s our bot
        if content.startswith(self.mention_id):
            # check for greeting
            greeting_patterns = "|".join(self.greetings)
            if re.search(rf'\b({greeting_patterns})\b', content):
                random_greeting = random.choice(self.greetings)
                response = author_mention + " " + random_greeting + "!"
                await message.channel.send(response)

        # check if the message includes "big _______" and respond accordingly
        next_word = self.check_for_big(content)
        if next_word != None:
            response = author_mention + " what kind of " + next_word + "?"
            await message.channel.send(response)
        else:
            print("No Big Detected")

    # HELPERS
    def check_for_big(self, message):
        words = message.split(" ")
        for index, word in enumerate(words):
            if word == "big" and index + 1 != len(words):
                return words[index + 1]
