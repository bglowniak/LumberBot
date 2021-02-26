import os
import sys
from LumberBot import LumberBot
from dotenv import load_dotenv
from discord.ext import commands

if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")

    debug = len(sys.argv) == 1 or not (sys.argv[1] == "--active" or sys.argv[1] == "-a") # lol

    bot = LumberBot(command_prefix=commands.when_mentioned_or("!"), debug=debug)
    bot.run(TOKEN)