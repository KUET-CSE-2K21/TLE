import os
import subprocess
import sys
import time
import textwrap
import logging
import json
import discord
from discord.ext import commands

from math import *
from tle.util import codeforces_common as cf_common
from tle.util import codeforces_api as cf
from tle import constants
from tle.util import discord_common
from tle.cogs.handles import HandleCogError
from tle.cogs.handles import CODECHEF_RATED_RANKS
from tle.util.codeforces_api import RATED_RANKS as CODEFORCES_RATED_RANKS
from discord.ext import commands
from tle.util.codeforces_common import pretty_time_format
from tle.util import clist_api

async def _create_roles(ctx, ranks):
    for rank in ranks[::-1]:
        guild = ctx.guild
        await guild.create_role(name=rank.title, colour=discord.Colour(rank.color_embed))

class Moderator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.converter = commands.MemberConverter()

    @commands.Cog.listener()
    @discord_common.once
    async def on_ready(self):
        pass

    @commands.group(brief='Bot control', invoke_without_command=True)
    async def meta(self, ctx):
        """Command the bot or get information about the bot."""
        await ctx.send_help(ctx.command)

    @meta.command(brief='Restarts TLE')
    @commands.is_owner()
    async def restart(self, ctx):
        """Restarts the bot."""
        await ctx.send('TLE is restarting :arrows_clockwise:')
        os._exit(42)

    @meta.command(brief='Kill TLE')
    @commands.is_owner()
    async def kill(self, ctx):
        """Restarts the bot."""
        await ctx.send('TLE has been slained :skull:')
        os._exit(0)

    @meta.command(brief='Is TLE up?')
    async def ping(self, ctx):
        """Replies to a ping."""
        start = time.perf_counter()
        message = await ctx.send(':ping_pong: Pong!')
        end = time.perf_counter()
        duration = (end - start) * 1000
        await message.edit(content=f'REST API latency: {int(duration)}ms\n'
                                   f'Gateway API latency: {int(self.bot.latency * 1000)}ms')

    @meta.command(brief='Prints bot uptime')
    async def uptime(self, ctx):
        """Replies with how long TLE has been up."""
        await ctx.send('TLE has been running for ' +
                       pretty_time_format(time.time() - self.start_time))

    @meta.command(brief='Print bot guilds')
    @commands.is_owner()
    async def guilds(self, ctx):
        "Replies with info on the bot's guilds"
        await ctx.send('I\'m in ' + str(len(self.bot.guilds)) + ' servers!')
        # msg = [f'Guild ID: {guild.id} | Name: {guild.name} | Owner: {guild.owner.id} | Icon: {guild.icon_url}'
        msg = []

        glen = 0
        for guild in self.bot.guilds:
            glen = max(glen, len(guild.name))
        glen = min(glen, 34)

        for guild in self.bot.guilds:
            guildname = guild.name
            if len(guildname) > glen:
                guildname = guildname[:glen - 3] + '...'
            else:
                guildname = guildname + (glen - len(guildname))*' '

            ownername = guild.owner.name
            if len(ownername) > glen:
                ownername = ownername[:glen - 3] + '...'
            else:
                ownername = ownername + (glen - len(ownername))*' '

            msg.append(f'Name: {guildname} | Owner: {ownername}')
        await ctx.send('```' + '\n'.join(msg) + '```')
    
    @meta.command(brief='Reset contest cache')
    @commands.is_owner()
    async def resetcache(self, ctx):
        "Reset contest cache."
        try:
            clist_api.cache(True)
            await ctx.send('```Cache reset completed. '
                           'Restart to reschedule all contest reminders.'
                           '```')
        except BaseException:
            await ctx.send('```' + 'Cache reset failed.' + '```')

    @commands.command(brief='(unofficial) Calculate math expressions', usage='[expression]')
    @commands.is_owner()
    async def calc(self, ctx, *args):
        """Calculate a math expression (in python format).
        This function is owner-only command due to technical reason.
        Note that ALL CONSTANTS and the ANSWER must be 1000 or fewer in LENGTH.

        e.g ;calc (10**9 + 7) % 17
        The bot should respond with 14"""
        try:
            if args[0] == 'sum':
                await ctx.send(eval('+'.join(args[1:])))
            elif args[0] == 'prod':
                await ctx.send(eval('*'.join(args[1:])))
            else:
                await ctx.send(eval(' '.join(args)))
        except TypeError as e:
            await ctx.send(e)
        except SyntaxError as e:
            await ctx.send('Invalid math expression. Please try again!')

    @commands.command(brief='Ban users from accessing the bot')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def ban(self, ctx, member: discord.Member):
        cf_common.user_db.ban_user(member.id)
        return await ctx.send("```"+str(member.display_name)+" banned from TLE!!!```")
    
    @commands.command(brief='Unban users from accessing the bot')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def unban(self, ctx, member: discord.Member):
        cf_common.user_db.unban_user(member.id)
        return await ctx.send("```"+str(member.display_name)+" unbanned!!! ```")
    
    @commands.group(brief='Create roles for codeforces/codechef', invoke_without_command=True)
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def createroles(self, ctx):
        await ctx.send_help(ctx.command)
    
    @createroles.command(brief='Create roles for codeforces ranks')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def codeforces(self, ctx):
        wait_msg = await ctx.channel.send("Creating Roles...")
        await _create_roles(ctx, CODEFORCES_RATED_RANKS)
        await wait_msg.delete()
        await ctx.send(embed=discord_common.embed_success('Roles created successfully.'))

    @createroles.command(brief='Create roles for codechef stars')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def codechef(self, ctx):
        wait_msg = await ctx.channel.send("Creating Roles...")
        await _create_roles(ctx, CODECHEF_RATED_RANKS)
        await wait_msg.delete()
        await ctx.send(embed=discord_common.embed_success('Roles created successfully.'))

    @discord_common.send_error_if(HandleCogError, cf_common.HandleIsVjudgeError)
    async def cog_command_error(self, ctx, error):
        pass


def setup(bot):
    bot.add_cog(Moderator(bot))