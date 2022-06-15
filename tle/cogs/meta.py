import os
import subprocess
import sys
import time
import textwrap
import logging
import json
import discord

from tle.util import codeforces_common as cf_common
from tle.util import codeforces_api as cf
from tle import constants
from tle.util import discord_common
from tle.cogs.handles import HandleCogError

from discord.ext import commands

from tle import constants
from tle.util.codeforces_common import pretty_time_format
from tle.util import clist_api

RESTART = 42

class Meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.converter = commands.MemberConverter()

    @commands.Cog.listener()
    @discord_common.once
    async def on_ready(self):
        pass

    @commands.command(brief='(unofficial) Calculate a math expression', usage='[expression]')
    @commands.is_owner()
    async def calc(self, ctx, *args):
        """Calculate a math expression (in python format).
        This function is owner-only command due to technical reason.
        Note that ALL CONSTANTS and the ANSWER must be 1000 or fewer in LENGTH.

        e.g ;calc (10**9 + 7) % 17
        The bot should respond with 14"""
        await ctx.send(eval(' '.join(args)))

    @discord_common.send_error_if(HandleCogError, cf_common.HandleIsVjudgeError)
    async def cog_command_error(self, ctx, error):
        pass

    @commands.group(brief='Bot control', invoke_without_command=True)
    async def meta(self, ctx):
        """Command the bot or get information about the bot."""
        await ctx.send_help(ctx.command)

    @meta.command(brief='Restarts TLE')
    @commands.is_owner()
    async def restart(self, ctx):
        """Restarts the bot."""
        await ctx.send('Restarting...')
        os._exit(RESTART)

    @meta.command(brief='Kill TLE')
    @commands.is_owner()
    async def kill(self, ctx):
        """Restarts the bot."""
        await ctx.send('Dying...')
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
    
    @meta.command(brief='Forcefully reset contests')
    @commands.is_owner()
    async def resetcache(self, ctx):
        "Resets contest cache."
        try:
            clist_api.cache(True)
            await ctx.send('```Cache reset completed. '
                           'Restart to reschedule all contest reminders.'
                           '```')
        except BaseException:
            await ctx.send('```' + 'Cache reset failed.' + '```')


def setup(bot):
    bot.add_cog(Meta(bot))
