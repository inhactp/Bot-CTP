import json
import discord
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from datetime import datetime


DATA_FILE = "data.json"
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = (SCRIPT_DIR / "data.json").resolve()
DEBUGLEVEL = 0 # 0 is silent
def DEBUG(*args):
    if DEBUGLEVEL == 0:
        return
    print(*args)
    pass


def load_data():
    """
    ### loads data.json
    - makes & returns basic data with no entries if data.json isnt present
    """
    
    basic = {"botid":""}
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

def addUser2db(member: discord.Member,serverId:str,data:dict):
    if serverId not in data.keys():
        data[serverId] = {"users":dict()}
    user_id = str(member.id)

    # Create the user entry if it doesn't exist
    if user_id not in data[serverId]["users"]:
        data[serverId]["users"][user_id] = {
            "name": member.display_name,
            "roles": [],
            "currentMember": True
        }
    else:
        data[serverId]["users"][user_id]["name"] = member.display_name
        data[serverId]["users"][user_id]["currentMember"] = True
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
    DEBUG(f"Logged in as {bot.user} (ID: {bot.user.id})")

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
    DEBUG("> Running add_member")
    DEBUG(f"target : {member.display_name}")
    DEBUG(f"loading db data")
    data = load_data()
    
    serverId = str(interaction.guild.id)
    curMemberRole = await getCurrentMemberRole(interaction.guild)
    if curMemberRole in member.roles:
        DEBUG(f"error : already a member")
        await interaction.response.send_message(
            f"{member.mention}님은 이미 멤버입니다.",
        )
        return
    
    addUser2db(member,serverId,data)
    await member.add_roles(curMemberRole)
    DEBUG(f"saving db data")
    save_data(data)
    
    DEBUG(f"succesfully added : {member.display_name}")
    await interaction.response.send_message(
        f"{member.mention}님을 멤버로 추가했습니다.",
        
    )
    pass

@bot.tree.command(
    name="분기역할적용",
    description="새로운 분기역할를 만들며 멤버역할을 가진 사람 기준으로 부여합니다. 멤버역할을 모두 부여한 후 실행하는 것이 권장됩니다"
)
@app_commands.describe(
    period="2026-2 와 같은 새로운 분기의 이름을 입력세요. 빈칸이면 현재 날짜에 따라 생성됩니다."
    
)
@app_commands.checks.has_permissions(administrator=True)
async def create_period(interaction: discord.Interaction,period:str=""):
    DEBUG("> Running create_period")
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    serverId = str(guild.id)
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
        DEBUG(f"loading db data")
        data = load_data()
        for user in allUsers:
            userId = user.id
            member = guild.get_member(userId)
            if member.bot:
                continue
            #print(member.display_name)
            if curMember in member.roles:
                if str(userId) not in data[serverId]["users"].keys():
                    DEBUG(f"user {user.display_name} - not in db. creating reference and adding <{period}> role")
                    reason["Not in db"].append(user.display_name)
                    addUser2db(member,serverId,data)
                    await addMemberRoleToUser(interaction,member)
                    data[serverId]["users"][str(userId)]["roles"].append(period)
                    addedCnt+=1
                    await member.add_roles(newRole)
                elif newRole in user.roles:
                    DEBUG(f"user {user.display_name} - already has <{period}> role. skipping..")
                    skippedCnt += 1
                    reason["Already Has Role"].append(user.display_name)
                else:
                    DEBUG(f"user {user.display_name} - adding <{period}> role")
                    data[serverId]["users"][str(userId)]["roles"].append(period)
                    addedCnt += 1
                    await member.add_roles(newRole)
                    pass
            else:
                DEBUG(f"user {user.display_name} - does not have member role. removing <{period}> role if there is one")
                if str(userId) not in data[serverId]["users"].keys():
                    addUser2db(member,serverId,data)
                data[serverId]["users"][str(userId)]["currentMember"] = False
                skippedCnt+=1
                await member.remove_roles(newRole)
                reason["Not A Member"].append(user.display_name)
            pass
        DEBUG(f"saving db data")
        save_data(data)
        #print(">>>>",reason['Already Has Role'],reason['Already Has Role'][:4])
        memberstr = ' '.join(reason['Already Has Role'][:4]) + ("..." if len(reason['Already Has Role'])>4 else "")
        nmemberstr = ' '.join(reason['Not A Member'][:4]) + ("..." if len(reason['Not A Member'])>4 else "")
        #print(">>>>",memberstr)
        # Result
        await interaction.followup.send(
            content=f"역할생성 - `{period}`.\n"+
            f"추가한인원 ({addedCnt}), 건너뛴인원 ({skippedCnt}) / 총인원({userCnt}).\n"+
            f"""{f"<{period}>역할소유자 - {memberstr} ({len(reason['Already Has Role'])}명)\n" if len(reason['Already Has Role']) else ""}"""+
            f"""{f"<{period}>멤버이외 - {nmemberstr} ({len(reason['Not A Member'])}명)" if len(reason['Not A Member']) else ""}""",ephemeral=False
        )
        pass
    
    async def confirm_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="확인! ✅",
            view=None
        )

        await addRoles(period)
        pass
    async def cancel_callback(interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="취소됨.",
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
    if not period:
        DEBUG(f"no given period")
        today = datetime.today()

        year = today.year
        pd = 1 if today.month <= 6 else 2

        period = f"{year}-{pd}"
        DEBUG(f"<{period}> waiting confirmation")
        view = confirmAutoPeriod()

        await interaction.followup.send(f"자동으로 {period} 역할을 사용합니다",view=view,ephemeral=True)
        return
    DEBUG(f"given period - <{period}>")
    await addRoles(period)
    pass

@bot.tree.command(
    name="현재멤버재부여",
    description="db에 따라 디스코드 멤버 역할을 재부여합니다. 반대의 경우는 분기역할적용 커맨드를 사용해주세요"
)
@app_commands.checks.has_permissions(administrator=True)
async def reditribute_current_member(interaction: discord.Interaction,member: discord.Member):
    DEBUG("> Running reditribute_current_member")
    await interaction.response.defer()
    
    guild = interaction.guild
    DEBUG(f"loading db data")
    data = load_data()
    curMember = await getCurrentMemberRole(guild)
    
    addedCnt = 0
    removedCnt = 0
    usersNotIndb = []

    # compare every discord user with data.json to get the intersection
    allUsers = guild.members
    userCnt = len([x for x in allUsers if not x.bot])
    data = load_data()
    for user in allUsers:
        userId = user.id
        member = guild.get_member(userId)
        if member.bot:
            continue
        if str(userId) not in data[serverId]["users"].keys():
            usersNotIndb.append(user.display_name)
        pass
    
    for userId,userdata in data:
        userId = int(userId)
        member = guild.get_member(userId)
        if userdata["currentMember"] and curMember not in member.roles:
            DEBUG(f"user {member.display_name} - adding role on discord")
            addedCnt+=1
            member.add_roles(curMember)
        elif not userdata["currentMember"] and curMember in member.roles:
            DEBUG(f"user {member.display_name} - removing role on discord")
            removedCnt+=1
            member.remove_roles(curMember)
            pass
        pass
    

    # Result
    await interaction.followup.send(
        content=f"추가인원 ({addedCnt}), 제거한인원 ({removedCnt}) / 총인원({userCnt}).\n"+
        f"""{f"db에 없음 -\n{' '.join(usersNotIndb)}\n" if len(usersNotIndb) else ""}"""
    )
    pass

@bot.tree.command(
    name="이름업데이트",
    description="db에 현재 디스코드 닉네임들로 업데이트합니다"
)
@app_commands.describe(
    member="업데이트할 멤버. 비워놓으면 모든 멤버를 업데이트합니다."
)
@app_commands.checks.has_permissions(administrator=True)
async def update_displayname(interaction: discord.Interaction,member: discord.Member=None):
    if type(member) != discord.Member:
        await interaction.response.send_message(
            f"{str(member)}는 멤버가 아닙니다.",
            ephemeral=True
        )
        return
    DEBUG("> Running update_displayname")
    
    serverId = serverId = str(interaction.guild.id)
    
    DEBUG(f"loading db data")
    data = load_data()
    if member != None:
        if str(member.id) not in data[serverId]["users"].keys():
            addUser2db(member,serverId,data)
            data[serverId]["users"][str(member.id)]["currentMember"] = False
        data[serverId]["users"][str(member.id)]["name"] = member.display_name
        return
    
    guild = interaction.guild
    allUsers = guild.members
    for user in allUsers:
        if str(user.id) not in data[serverId]["users"].keys():
            addUser2db(member,serverId,data)
            data[serverId]["users"][str(user.id)]["currentMember"] = False
        data[serverId]["users"][str(user.id)]["name"] = user.display_name
        return
        pass
    DEBUG(f"saving db data")
    data = save_data(data)
    await interaction.response.send_message(
        f"{member.mention}님을 멤버로 추가했습니다.",
    )
    pass



async def defaultErrorHandling(interaction,error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        message = "현재 커맨드를 사용하기 위해서는 운영진 역할이 필요합니다"
    else:
        message = f"An error occurred: `{error}`"

    if interaction.response.is_done():
        await interaction.followup.send(message, )
    else:
        await interaction.response.send_message(message, )
    pass

# Error handling
@add_member.error
async def add_member_error(interaction: discord.Interaction,error):
    await defaultErrorHandling(interaction,error)
@create_period.error
async def create_period_error(interaction: discord.Interaction,error):
    await defaultErrorHandling(interaction,error)
@reditribute_current_member.error
async def reditribute_current_member_error(interaction: discord.Interaction,error):
    await defaultErrorHandling(interaction,error)
@update_displayname.error
async def reditribute_current_member_error(interaction: discord.Interaction,error):
    await defaultErrorHandling(interaction,error)
    pass


# Start bot 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라 제발되라
DEBUGLEVEL = 1
bot.run(TOKEN)

