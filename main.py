import json
import discord
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from datetime import datetime


DATA_FILE = "data.json"
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = (SCRIPT_DIR / "data.json").resolve()


def load_data():
    """
    ### loads data.json
    - makes & returns basic data with no entries if data.json isnt present
    """
    
    basic = {"botid":"","users":{}}
    if not DATA_FILE.exists():
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(basic, file, indent=4, ensure_ascii=False)
            return basic
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)
        if data["botid"] == "":
            print("No botid present! Please input the discord bot id in data.json!")
            raise
        return data
    pass


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


# Bot setup

data = load_data()

TOKEN = data["botid"]

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="/",
    intents=intents
)


# Utility functions

async def createRole(guild: discord.Guild, role_name: str):
    """
    Gets an existing role or creates it if it doesn't exist.
    """
    role = discord.utils.get(guild.roles, name=role_name)

    if role is None:
        role = await guild.create_role(
            name=role_name,
            reason="Automatically created by the BotCTP"
        )

    return role
async def getCurrentMemberRole(guild: discord.Guild):
    """
    Gets the '멤버' Discord role.

    If it doesn't exist, create it.
    """
    role = discord.utils.get(guild.roles, name="멤버")

    if role is None:
        role = await guild.create_role(
            name="멤버",
            reason="Automatically created by the bot"
        )

    return role

def addUser2db(member: discord.Member,data:dict):
    user_id = str(member.id)

    # Create the user entry if it doesn't exist
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "name": member.name,
            "roles": [],
            "currentMember": True
        }
    else:
        data["users"][user_id]["name"] = member.name
        data["users"][user_id]["currentMember"] = True
    pass

async def addMemberRoleToUser(interaction: discord.Interaction,member: discord.Member):
    curMemberRole = await getCurrentMemberRole(interaction.guild)
    await member.add_roles(
        curMemberRole,
        reason="Member added through bot"
    )
    pass


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(
    name="멤버추가",
    description="현재 멤버역할에 멤버를 추가합니다"
)
@app_commands.describe(
    member="추가할 멤버"
)
@app_commands.checks.has_permissions(administrator=True)
async def add_member(
    interaction: discord.Interaction,
    member: discord.Member
):
    data = load_data()
    await addUser2db(interaction,member,data)

    save_data(data)
    
    await interaction.response.send_message(
        f"{member.mention}님을 멤버로 추가했습니다.",
        ephemeral=True
    )

@bot.tree.command(
    name="분기역할적용",
    description="새로운 분기역할를 만들며 멤버역할을 가진 사람 기준으로 부여합니다. 멤버역할을 부여한 후 실행하는 것이 권장됩니다"
)
@app_commands.describe(
    period="2026-2 와 같은 새로운 분기의 이름을 입력세요. 빈칸이면 현재 날짜에 따라 생성됩니다."
    
)
@app_commands.checks.has_permissions(administrator=True)
async def create_period(interaction: discord.Interaction,period:str=""):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild

    if guild is None:
        await interaction.followup.send(
            "This command can only be used inside a server."
        )
        return
    async def addRoles(period:str):
        # Create/get the new Discord role
        newRole = await createRole(guild, period)
        curMember = await getCurrentMemberRole(guild)

        addedCnt = 0
        skippedCnt = 0
        reason={"Not in db":[],"Already Has Role":[],"Not A Member":[]}

        # Process every user and compare with data.json
        allUsers = guild.members
        userCnt = len([x for x in allUsers if not x.bot])
        data = load_data()
        for user in allUsers:
            userId = user.id
            member = guild.get_member(userId)
            if member.bot:
                continue
            #print(member.name)
            if curMember in member.roles:
                if str(userId) not in data["users"].keys():
                    reason["Not in db"].append(user.name)
                    addUser2db(member,data)
                    await addMemberRoleToUser(interaction,member)
                    data["users"][str(userId)]["roles"].append(period)
                    addedCnt+=1
                    await member.add_roles(newRole)
                elif newRole in user.roles:
                    skippedCnt += 1
                    reason["Already Has Role"].append(user.name)
                else:
                    data["users"][str(userId)]["roles"].append(period)
                    addedCnt += 1
                    await member.add_roles(newRole)
                    pass
            else:
                print(4)
                skippedCnt+=1
                await member.remove_roles(newRole)
                reason["Not A Member"].append(user.name)
            pass
        save_data(data)

        # Result
        await interaction.followup.send(
            content=f"역할생성 - `{period}`.\n"+
            f"추가인원 ({addedCnt}), 스킵한인원 ({skippedCnt}) / 총인원({userCnt}).\n"+
            f"""{f"이미 현재역할이 있음 -\n{' '.join(reason['Already Has Role'])}\n" if len(reason['Already Has Role']) else ""}"""+
            f"""{f"멤버가 아님 -\n{' '.join(reason['Not A Member'])}" if len(reason['Not A Member']) else ""}"""
        )
    
    async def confirm_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="확인! ✅",
            view=None
        )

        await addRoles(period)
        pass
    async def cancel_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="취소됨. ❌",
            view=None
        )

    def confirmAutoPeriod():
        view = discord.ui.View()

        confirm = discord.ui.Button(
            label="확인",
            style=discord.ButtonStyle.green
        )
        cancel = discord.ui.Button(
            label="취소",
            style=discord.ButtonStyle.red
        )

        confirm.callback = confirm_callback
        cancel.callback = cancel_callback

        view.add_item(confirm)
        view.add_item(cancel)

        return view
    
    # Validate period
    period = str(period.strip())
    print(period)
    if not period:
        today = datetime.today()

        year = today.year
        pd = 1 if today.month <= 6 else 2

        period = f"{year}-{pd}"
        view = confirmAutoPeriod()

        await interaction.followup.send(
            f"자동으로 {period} 역할을 사용합니다",
            view=view,
            ephemeral=True
        )
        return
    await addRoles(period)
    pass

@bot.tree.command(
    name="현재멤버재부여",
    description="db에 따라 현재멤버 역할을 재부여합니다"
)
@app_commands.describe(
    member="추가할 멤버"
)
@app_commands.checks.has_permissions(administrator=True)
async def add_member(
    interaction: discord.Interaction,
    member: discord.Member
):
    data = load_data()
    await addUser2db(interaction,member,data)

    save_data(data)
    
    await interaction.response.send_message(
        f"{member.mention}님을 멤버로 추가했습니다.",
        ephemeral=True
    )

# Error handling
@add_member.error
async def add_member_error(
    interaction: discord.Interaction,
    error
):
    if isinstance(error, app_commands.errors.MissingPermissions):
        message = "현재 커맨드를 사용하기 위해서는 운영진 역할이 필요합니다"
    else:
        message = f"An error occurred: `{error}`"

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@create_period.error
async def create_period_error(
    interaction: discord.Interaction,
    error
):
    if isinstance(error, app_commands.errors.MissingPermissions):
        message = "현재 커맨드를 사용하기 위해서는 운영진 역할이 필요합니다"
    else:
        message = f"An error occurred: `{error}`"

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


# Start bot 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라
bot.run(TOKEN)

