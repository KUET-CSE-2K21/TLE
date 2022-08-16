import disnake
from disnake.ext import commands

_EMBED_COLOR = 0xff8c00

def donate_embed(avatar_url):
    embed = disnake.Embed(color = _EMBED_COLOR)
    embed.description = 'Thank you for choosing <@968509913531809862> bot!\nHere is the donate information in case you want to support and make the bot thrives even more in the future! All means of support are appreciated :smiling_face_with_3_hearts::kissing_heart:'

    embed.set_author(name = 'Donate Information', icon_url = avatar_url)
    embed.set_thumbnail(url = avatar_url)
    embed.add_field(name = 'Momo', value = '`0794568992`', inline = False)
    embed.add_field(name = 'Playerduo', value = 'https://playerduo.com/glowcheese', inline = False)
    embed.add_field(name = 'Banking', value = '`1029910129 DAO LE BAO MINH Vietcombank`', inline = False)

    return embed

class Donate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed = donate_embed(bot.user.display_avatar.url)

    @commands.slash_command(description='Show donate information')
    async def donate(self, inter):
        await inter.response.send_message(embed = self.embed)

def setup(bot):
    bot.add_cog(Donate(bot))