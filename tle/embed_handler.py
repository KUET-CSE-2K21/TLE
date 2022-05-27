import discord, datetime

def error_handler(client, error, ctx):
    embed = discord.Embed(color = discord.Colour.random(), timestamp = datetime.datetime.now())
    embed.set_author(name = "Error", icon_url = client.user.avatar_url)
    embed.description = "Please try again. Error: {}".format(error)
    embed.set_footer(text = "Requested by {}".format(ctx.message.author.name), icon_url = ctx.message.author.avatar_url)
    return embed
    
def single_message(client, text, description = ""):
    embed = discord.Embed(color = discord.Colour.random(), timestamp = datetime.datetime.now())
    embed.set_author(name = text)
    if description != "":
        embed.description = description
    embed.set_footer(text = f'Sent by {client.user.name}', icon_url = client.user.avatar_url)

    return embed


# embedVar = discord.Embed(color=0x00ff00)
# embedVar.set_author(name="Now Playing", icon_url=client.user.avatar_url)
# embedVar.description = '[{}](https://www.youtube.com/watch?v=HHD9nLAn-Vo)'.format(txt.title()) + '\n' + "Loop: " + '`off` | ' + 'Volume: ' + '`100%` | ' + 'Duration: ' + '`00:04:00` | ' + 'Channel: ' + '`Music`'
# embedVar.set_footer(text = 'Requested by ' + ctx.message.author.name, icon_url = ctx.message.author.avatar_url)
# await ctx.send(embed=embedVar)