import disnake

from disnake.ext import commands

class HelpCommand(commands.HelpCommand):
    def __init__(self, **options):
        super().__init__(**options)
        color = 0xff8c00 # Cheese's color XD
        title = 'Please use this command as a Slash Command!'
        description = 'This command can only be used as a Slash Command. Please use `/help` instead to execute this command. Non-slash commands will be disappearing as of **August 2022**.\n\nPlease note that **all bots** will be **required** to switch to Slash Commands by **August 2022**, so you better be getting used to them now!\n\nIf the server you are in is not showing TLE\'s slash commands you can ask an administrator of the server to invite the bot again by using [this link](https://j2c.cc/tle-bot). The bot **doesn\'t need to be kicked**, it just needs to be **invited again**!'
        avatar = "https://cdn.discordapp.com/avatars/968509913531809862/a739c2a4de74d91c17026daf7aadc7d8.png?size=1024"
        self.embed = disnake.Embed(color = color, title = title, description = description)
        self.embed.set_image(url = "https://cdn.discordapp.com/embed/avatars/0.png")
        self.embed.set_author(name = 'TLE Plugins Commands', icon_url = avatar)

    async def send_bot_help(self, mapping):
        await self.context.send(embed = self.embed)

    async def send_cog_help(self, cog):
        await self.context.send(embed = self.embed)

    async def send_command_help(self, command):
        await self.context.send(embed = self.embed)

    async def send_group_help(self, group):
        await self.context.send(embed = self.embed)

    async def send_error_message(self, group):
        await self.context.send(embed = self.embed)

class OldHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.help_command.cog = self
        bot.help_command = HelpCommand()

def setup(bot):
    bot.add_cog(OldHelp(bot))