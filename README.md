# LumberBot
Simple Discord bot

## Warzone Session Tracking

The main feature of this bot is tracking matches of Call of Duty: Warzone.  

The Discord task will run every 8 minutes (this was originally 15 minutes, but it was reduced due to a new map that was released with much shorter match lengths), and for each iteration, the bot will first collect all recent matches played by my account (a limitation of the bot is that the tracker will only work for games that I specifically play in). For each new matches in that list that has not yet been processed, the bot will make another call to collect more detailed info on the game and then update the stat tracking.

If a first place finish is detected, the bot will automatically send a message to our server with a congrats message, our match stats, and a random GIF picked from the salutes directory. The bot will also specifically congratulate anyone who achieves 10+ kills in a game (regardless of team placement), as well as a special note every three wins.

Known gamertags are hardcoded to their corresponding Discord message IDs so that players can be mentioned directly in the messages.

## Commands

### Warzone Stats Commands (requires active WZ session using start_wz command - currently only invokable by me)

session_stats - returns the cumulative team stats for a session

player_stats {gamertag} - returns an individual player's cumulative stats for a session. If username is not provided, it will return stats for all players that have participated in at least one game during the session.

awards - calculates and returns the following commendations based on the cumulative stats at the time of invocation.
- MVP - best kill/death ratio
- Carried - worst kill/death ratio 
- Bloodthirsty - most kills
- Cannon Fodder - most deaths
- Commando - best damage ratio (damage given / damage taken)

### Misc Commands

clear_channel - clear out all messages in the channel of invocation

## WZ API Authentication
Authentication was originally done by first sending a GET request to the Call of Duty login page to set an XSRF token. 
Warzone API Authentication Reference: https://github.com/sdiepend/cod_api (used device_id method)     
Warzone API Endpoint Reference: https://github.com/Lierrmm/Node-CallOfDuty/blob/master/index.js
