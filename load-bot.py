import os
from LumberBot import LumberBot
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")

    client = LumberBot()
    client.run(TOKEN)