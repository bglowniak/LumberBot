import os
import sys
from LumberBot import LumberBot
from dotenv import load_dotenv
from discord.ext import commands
import argparse
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')

if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")

    parser = argparse.ArgumentParser(description="Lumber Bot")
    parser.add_argument('-a', '--active', action='store_true', help="Marks this as an active session (will send messages to public discord)")
    args = parser.parse_args()

    debug = not args.active

    bot = LumberBot(command_prefix=commands.when_mentioned_or("!"), debug=debug)
    bot.run(TOKEN)