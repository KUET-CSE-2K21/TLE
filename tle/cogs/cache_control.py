import functools
import time
import traceback

import discord
from discord.ext import commands

from tle import constants
from tle.util import codeforces_common as cf_common

from os import environ
from firebase_admin import storage

bucket = None
STORAGE_BUCKET = str(environ.get('STORAGE_BUCKET'))
if STORAGE_BUCKET!='None':
    bucket = storage.bucket()

_SUCCESS_GREEN = 0x28A745
_ALERT_AMBER = 0xFFBF00

def embed_success(desc):
    return discord.Embed(description=str(desc), color=_SUCCESS_GREEN)

def embed_alert(desc):
    return discord.Embed(description=str(desc), color=_ALERT_AMBER)

def timed_command(coro):
    @functools.wraps(coro)
    async def wrapper(cog, ctx, *args):
        await ctx.send('Running...')
        begin = time.time()
        await coro(cog, ctx, *args)
        elapsed = time.time() - begin
        await ctx.send(f'Completed in {elapsed:.2f} seconds')

    return wrapper


class CacheControl(commands.Cog):
    """Cog to manually trigger update of cached data. Intended for dev/admin use."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(brief='Commands to force reload of cache',
                    invoke_without_command=True, hidden=True)
    @commands.is_owner()
    async def cache(self, ctx):
        await ctx.send_help('cache')

    @cache.command()
    @commands.is_owner()
    @timed_command
    async def upload(self, ctx):
        """Upload cache database to Googe Firebase"""
        if bucket==None:
            return await ctx.send(embed=embed_alert('Cannot find storage bucket.'))
        await ctx.send('Caching database, please wait...')
        try:
            begin = time.time()
            cache = bucket.blob('tle_cache.db')
            cache.upload_from_filename(constants.CACHE_DB_FILE_PATH)
            elapsed = time.time() - begin
            await ctx.send(embed=embed_success(f'Uploaded cache database.'))
        except Exception as e:
            await ctx.send(embed=embed_alert(f'Cache database upload failed: {e!r}'))

    @cache.command()
    @commands.is_owner()
    @timed_command
    async def contests(self, ctx):
        await cf_common.cache2.contest_cache.reload_now()

    @cache.command()
    @commands.is_owner()
    @timed_command
    async def problems(self, ctx):
        await cf_common.cache2.problem_cache.reload_now()

    @cache.command(usage='[missing|all|contest_id]')
    @commands.is_owner()
    @timed_command
    async def ratingchanges(self, ctx, contest_id='missing'):
        """Defaults to 'missing'. Mode 'all' clears existing cached changes.
        Mode 'contest_id' clears existing changes with the given contest id.
        """
        if contest_id not in ('all', 'missing'):
            try:
                contest_id = int(contest_id)
            except ValueError:
                return
        if contest_id == 'all':
            await ctx.send('This will take a while')
            count = await cf_common.cache2.rating_changes_cache.fetch_all_contests()
        elif contest_id == 'missing':
            await ctx.send('This may take a while')
            count = await cf_common.cache2.rating_changes_cache.fetch_missing_contests()
        else:
            count = await cf_common.cache2.rating_changes_cache.fetch_contest(contest_id)
        await ctx.send(f'Done, fetched {count} changes and recached handle ratings')

    @cache.command(usage='[contest_id|all]')
    @commands.is_owner()
    @timed_command
    async def problemsets(self, ctx, contest_id):
        """Mode 'all' clears all existing cached problems. Mode 'contest_id'
        clears existing problems with the given contest id.
        """
        if contest_id == 'all':
            await ctx.send('This will take a while')
            count = await cf_common.cache2.problemset_cache.update_for_all()
        else:
            try:
                contest_id = int(contest_id)
            except ValueError:
                return
            count = await cf_common.cache2.problemset_cache.update_for_contest(contest_id)
        await ctx.send(f'Done, fetched {count} problems')


def setup(bot):
    bot.add_cog(CacheControl(bot))
