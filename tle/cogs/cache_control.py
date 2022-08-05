import functools
import time
import traceback

import disnake
from disnake.ext import commands

from tle import constants
from tle.util import codeforces_common as cf_common

def timed_command(coro):
    @functools.wraps(coro)
    async def wrapper(cog, inter, *args):
        await inter.send('Running...')
        begin = time.time()
        await coro(cog, inter, *args)
        elapsed = time.time() - begin
        await inter.channel.send(f'Completed in {elapsed:.2f} seconds')

    return wrapper


class CacheControl(commands.Cog):
    """Cog to manually trigger update of cached data. Intended for dev/admin use."""

    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description='Commands to force reload of cache')
    @commands.is_owner()
    async def cache(self, inter):
        pass

    @cache.sub_command(description='Reload contests cache')
    @commands.is_owner()
    @timed_command
    async def contests(self, inter):
        await cf_common.cache2.contest_cache.reload_now()

    @cache.sub_command(description='Reload problems cache')
    @commands.is_owner()
    @timed_command
    async def problems(self, inter):
        await cf_common.cache2.problem_cache.reload_now()

    @cache.sub_command(description='Reload rating changes cache')
    @commands.is_owner()
    @timed_command
    async def ratingchanges(self, inter, contest_id: int):
        """
        Defaults to 'missing'. Mode 'all' clears existing cached changes.
        Mode 'contest_id' clears existing changes with the given contest id.
        """
        count = await cf_common.cache2.rating_changes_cache.fetch_contest(contest_id)
        await inter.send(f'Done, fetched {count} changes and recached handle ratings')

    @cache.sub_command(description='Reload problemsets cache')
    @commands.is_owner()
    @timed_command
    async def problemsets(self, inter, contest_id: int = None):
        """
        Mode 'all' clears all existing cached problems. Mode 'contest_id'
        clears existing problems with the given contest id.
        """
        if contest_id == None:
            inter.channel.send('This will take a while...')
            count = await cf_common.cache2.problemset_cache.update_for_all()
        else:
            try:
                contest_id = int(contest_id)
            except ValueError:
                return inter.send('Invalid contest ID')
            count = await cf_common.cache2.problemset_cache.update_for_contest(contest_id)
        await inter.send(f'Done, fetched {count} problems')

def setup(bot):
    bot.add_cog(CacheControl(bot))
