# LumberBot
Simple Discord bot

[Warzone API Authentication Reference](https://github.com/sdiepend/cod_api) (does not work anymore b/c of captcha)  
[Warzone API Endpoint Reference](https://documenter.getpostman.com/view/5519582/SzzgAefq)

## Warzone Session Tracking

The main feature of this bot is tracking matches of Call of Duty: Warzone.  

Once a tracking session is activated, it is backed by a Discord task that runs every 8 minutes (this was originally 15 minutes, but it was reduced due to a new map that was released with much shorter match lengths). For each iteration, the bot will first collect all recent matches played by my account (a limitation is that the tracker will only work for games that I specifically play in), then for each new match that has not yet been processed in that list, the bot will make another call to collect more detailed info on the game and then update the stat tracking.

If a first place finish is detected, the bot will automatically send a message to our server with a congrats message, our match stats, and a random GIF picked from the salutes directory. The bot will also specifically congratulate anyone who achieves 10+ kills in a game (regardless of team placement), as well as a special note every three wins.

```
Congratulations on a recent Warzone win!
Match Start Time: 11/03 22:47:44
Match Duration: 14.17 minutes
Map: Rebirth
Team Stats:
    • @Player1: 7-3 (2.33 K/D), 2879 damage.
    • @Player2: 9-4 (2.25 K/D), 3713 damage.
    • @Player3: 6-1 (6.0 K/D), 2438 damage.
    • @Player4: 8-1 (8.0 K/D), 3284 damage.
<random salute gif>
```

Known gamertags are hardcoded to their corresponding Discord message IDs so that players can be mentioned directly by their Discord usernames in the message.

## Available Commands

Sessions are managed via the `start_wz` and `end_wz` commands, but these are currently only invokable by me.

### `session_stats`

Formats and returns the cumulative team stats. Requires active session.
```
!session_stats
Session Start: 11/03 21:20:59
Matches Played: 12
Team K/D: 159-124 (1.28)
Average Team Placement: 5 (2 wins)
Max Kills: 11 (Player1, Player2)
Max Deaths: 7 (Player3)
Total Session Duration: 151.03 minutes
```

### `player_stats {gamertag}`

Formats and returns an individual player's cumulative stats. If gamertag is not provided, it will return stats for all players that have participated in at least one game during the session. Requires active session.

```
!player_stats Player1
Stats for Player1:
Matches Played: 12
K/D: 32-28 (1.14)
Average Kills: 3.0 (Max: 6)
Average Deaths: 2.0 (Max: 4)
Average Damage: 1206.5 (14478 total)
```

### `awards`

Calculates and returns the following commendations based on the cumulative stats at the time of invocation.
* MVP - best kill/death ratio
* Carried - worst kill/death ratio 
* Bloodthirsty - most kills
* Cannon Fodder - most deaths
* Commando - best damage ratio (damage given / damage taken)

Ties are awarded to all players involved. Any known gamertag -> Discord ID mappings will be mentioned with their Discord username. Requires active session.

```
!awards
Awards
    •MVP: @Player1 (3.43 K/D)
    •Carried: Player2 (0.67 K/D)
    •Bloodthirsty: @Player1, @Player3 (39 kills)
    •Cannon Fodder: Player2 (36 deaths)
    •Commando: @Player4 (3.96 damage ratio)
```

### `clear_channel`

Clear out all messages in the channel of invocation

## WZ API Authentication
The first step of authentication is to send a GET request to the Call of Duty login page to set an XSRF token that is used in subsequent API requests.

After this, the original method was to send a POST request with username and password to the site login. Upon success, this would set a few required cookies that would be used to authenticate any API requests. In 2021, Activision added a reCaptcha to the login, presumably to prevent tools like this from accessing their APIs. I have a hacky workaround that keeps this working - if you are building a similar project reach out to me and I can share the details. I was also looking into a method using Selenium and 2captcha to bypass the captcha and login programmatically, but I may or may not pursue it.
