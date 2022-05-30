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
from tle.cogs.handles import HandleCogError,_CLIST_RESOURCE_SHORT_FORMS,_SUPPORTED_CLIST_RESOURCES
from tle.cogs.handles import CODECHEF_RATED_RANKS
from tle.util.codeforces_api import RATED_RANKS as CODEFORCES_RATED_RANKS

from discord.ext import commands

from tle import constants
from tle.util.codeforces_common import pretty_time_format
from tle.util import clist_api

RESTART = 42


# Adapted from numpy sources.
# https://github.com/numpy/numpy/blob/master/setup.py#L64-85
def git_history():
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout = subprocess.PIPE, env=env).communicate()[0]
        return out
    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        branch = out.strip().decode('ascii')
        out = _minimal_ext_cmd(['git', 'log', '--oneline', '-5'])
        history = out.strip().decode('ascii')
        return (
            'Branch:\n' +
            textwrap.indent(branch, '  ') +
            '\nCommits:\n' +
            textwrap.indent(history, '  ')
        )
    except OSError:
        return "Fetching git info failed"

async def _create_roles(ctx, ranks):
    for rank in ranks[::-1]:
        guild = ctx.guild
        await guild.create_role(name=rank.title, colour=discord.Colour(rank.color_embed))

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

    @commands.group(brief='Command to create roles for codeforces/codechef', invoke_without_command=True)
    @commands.check_any(commands.has_any_role('Admin', constants.TLE_MODERATOR), commands.is_owner())
    async def createroles(self, ctx):
        await ctx.send_help(ctx.command)
    
    @createroles.command(brief='Create roles for codeforces ranks')
    async def codeforces(self, ctx):
        wait_msg = await ctx.channel.send("Creating Roles...")
        await _create_roles(ctx, CODEFORCES_RATED_RANKS)
        await wait_msg.delete()
        await ctx.send(embed=discord_common.embed_success('Roles created successfully.'))

    @createroles.command(brief='Create roles for codechef stars')
    async def codechef(self, ctx):
        wait_msg = await ctx.channel.send("Creating Roles...")
        await _create_roles(ctx, CODECHEF_RATED_RANKS)
        await wait_msg.delete()
        await ctx.send(embed=discord_common.embed_success('Roles created successfully.'))

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

    @meta.command(brief='Get git information')
    async def git(self, ctx):
        """Replies with git information."""
        await ctx.send('```yaml\n' + git_history() + '```')

    @meta.command(brief='Prints bot uptime')
    async def uptime(self, ctx):
        """Replies with how long TLE has been up."""
        await ctx.send('TLE has been running for ' +
                       pretty_time_format(time.time() - self.start_time))

    @meta.command(brief='Print bot guilds')
    @commands.is_owner()
    async def guilds(self, ctx):
        "Replies with info on the bot's guilds"
        msg = [f'Guild ID: {guild.id} | Name: {guild.name} | Owner: {guild.owner.id} | Icon: {guild.icon_url}'
                for guild in self.bot.guilds]
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
