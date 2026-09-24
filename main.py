
try:
    from Python.tools.CTPDiscordBot.CTPBOT import bot,load_data # type: ignore
except:
    from CTPBOT import bot,load_data # type: ignore


data = load_data()
TOKEN = data["botid"]
bot.run(TOKEN)