import os
import subprocess
import sys
import time
import textwrap
import logging
import json
import discord

from math import *
from os import environ
from firebase_admin import storage
from tle.util import table
from tle.util import paginator
from discord.ext import commands
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

_PAGINATE_WAIT_TIME = 5 * 60  # 5 minutes
_GUILDS_PER_PAGE = 10
_NAME_MAX_LEN = 30
_OWNER_MAX_LEN = 30
_SUCCESS_GREEN = 0x28A745
_ALERT_AMBER = 0xFFBF00

bucket = None
STORAGE_BUCKET = str(environ.get('STORAGE_BUCKET'))
if STORAGE_BUCKET!='None':
    bucket = storage.bucket()

async def _create_roles(ctx, ranks):
    roles = [role.name for role in ctx.guild.roles]
    for rank in ranks[::-1]:
        if rank.title not in roles:
            await ctx.guild.create_role(name=rank.title, colour=discord.Colour(rank.color_embed))

def embed_success(desc):
    return discord.Embed(description=str(desc), color=_SUCCESS_GREEN)

def embed_alert(desc):
    return discord.Embed(description=str(desc), color=_ALERT_AMBER)

def _make_pages(guilds, title):
    chunks = paginator.chunkify(guilds, _GUILDS_PER_PAGE)
    pages = []
    done = 1

    style = table.Style('{:>} {:<} {:<}')
    for chunk in chunks:
        t = table.Table(style)
        t += table.Header('#', 'Owner', 'Server')
        t += table.Line()
        for i, (name, owner) in enumerate(chunk):
            if len(name) > _NAME_MAX_LEN:
                name = name[:_NAME_MAX_LEN - 1] + '…'
            if len(owner) > _OWNER_MAX_LEN:
                owner = owner[:_OWNER_MAX_LEN - 1] + '…'
            t += table.Data(i + done, owner, name)
        table_str = '```\n'+str(t)+'\n```'
        embed = discord_common.cf_color_embed(description=table_str)
        pages.append((title, embed))
        done += len(chunk)

    return pages

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

    @meta.command(brief='Update database', usage='[all|user|cache]')
    @commands.is_owner()
    async def uploaddb(self, ctx, db = 'all'):
        """Upload database to Googe Firebase"""
        if bucket==None:
            await ctx.send(embed=embed_alert('Cannot find storage bucket.'))
        else:
            wait_msg = await ctx.channel.send('Uploading database, please wait...')
            try:
                if db == 'cache' or db == 'all':
                    cache = bucket.blob('tle_cache.db')
                    cache.upload_from_filename(constants.CACHE_DB_FILE_PATH)
                    await ctx.send(embed=embed_success('Cache database uploaded successfully.'))
            except Exception as e:
                await ctx.send(embed=embed_alert(f'Cache database upload failed: {e}'))
            try:
                if db == 'user' or db == 'all':
                    user = bucket.blob('tle.db')
                    user.upload_from_filename(constants.USER_DB_FILE_PATH)
                    await ctx.send(embed=embed_success('User database uploaded successfully.'))
            except Exception as e:
                await ctx.send(embed=embed_alert(f'User database upload failed: {e}'))
            await wait_msg.delete()

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
        guilds = [(guild.name, guild.owner.name) for guild in self.bot.guilds]
        guilds.sort(key=lambda x: (x[1]))
        title = f'I\'m in {len(guilds)} server!'

        pages = _make_pages(guilds, title)
        paginator.paginate(self.bot, ctx.channel, pages, wait_time=_PAGINATE_WAIT_TIME,
                   set_pagenum_footers=True)
    
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
    @commands.check_any(commands.has_any_role('Admin'), commands.is_owner())
    async def createroles(self, ctx):
        await ctx.send_help(ctx.command)
    
    @createroles.command(brief='Create roles for codeforces ranks')
    @commands.check_any(commands.has_any_role('Admin'), commands.is_owner())
    async def codeforces(self, ctx):
        wait_msg = await ctx.channel.send("Creating Roles...")
        await _create_roles(ctx, CODEFORCES_RATED_RANKS)
        await wait_msg.delete()
        await ctx.send(embed=discord_common.embed_success('Roles created successfully.'))

    @createroles.command(brief='Create roles for codechef stars')
    @commands.check_any(commands.has_any_role('Admin'), commands.is_owner())
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
