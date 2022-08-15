import asyncio
import random
import functools
import json
import pickle
import logging
import time
import datetime as dt
from pathlib import Path
from recordtype import recordtype
import pytz
import copy

from collections import defaultdict
from collections import namedtuple

import disnake
from disnake.ext import commands
import os
from os import environ
from tle.util.rounds import Round
from tle.util import discord_common
from tle.util import paginator
from tle import constants
from tle.util import clist_api as clist
from tle.util import codeforces_common as cf_common
from tle.cogs.handles import _CLIST_RESOURCE_SHORT_FORMS, _SUPPORTED_CLIST_RESOURCES, _CP_PLATFORMS

_CONTESTS_PER_PAGE = 5
_CONTEST_PAGINATE_WAIT_TIME = 5 * 60
_FINISHED_CONTESTS_LIMIT = 10
_CONTEST_REFRESH_PERIOD = 10 * 60  # seconds

class RemindersCogError(commands.CommandError):
    pass


def _contest_start_time_format(contest, tz):
    start = contest.start_time.replace(tzinfo=dt.timezone.utc).astimezone(tz)
    tz = str(tz)
    if tz == 'Asia/Kolkata': tz = 'IST'
    if tz == 'Asia/Ho_Chi_Minh': tz = 'ICT'
    return f'{start.strftime("%d %b %y, %H:%M")} {tz}'


def _contest_duration_format(contest):
    duration_days, duration_hrs, duration_mins, _ = discord_common.time_format(
        contest.duration.total_seconds())
    duration = f'{duration_hrs}h {duration_mins}m'
    if duration_days > 0:
        duration = f'{duration_days}d ' + duration
    return duration


def _get_formatted_contest_desc(
        start,
        duration,
        url,
        max_duration_len):
    em = '\N{EN SPACE}'
    sq = '\N{WHITE SQUARE WITH UPPER RIGHT QUADRANT}'
    desc = (f'`{em}{start}{em}|'
            f'{em}{duration.rjust(max_duration_len, em)}{em}|'
            f'{em}`[`link {sq}`]({url} "Link to contest page")')
    return desc


def _get_embed_fields_from_contests(contests, localtimezone):
    infos = [(contest.name,
              _contest_start_time_format(contest,
                                         localtimezone),
              _contest_duration_format(contest),
              contest.url) for contest in contests]
    max_duration_len = max(len(duration) for _, _, duration, _ in infos)

    fields = []
    for name, start, duration, url in infos:
        value = _get_formatted_contest_desc(
            start, duration, url, max_duration_len)
        fields.append((name, value))
    return fields


async def _send_reminder_at(channel, role, contests, before_secs, send_time,
                            localtimezone: pytz.timezone):
    delay = send_time - dt.datetime.utcnow().timestamp()
    if delay <= 0:
        return
    await asyncio.sleep(delay)
    values = discord_common.time_format(before_secs)

    def make(value, label):
        tmp = f'{value} {label}'
        return tmp if value == 1 else tmp + 's'

    labels = 'day hr min sec'.split()
    before_str = ' '.join(make(value, label)
                          for label, value in zip(labels, values) if value > 0)
    desc = f'About to start in {before_str}'
    embed = discord_common.color_embed(description=desc)
    for name, value in _get_embed_fields_from_contests(
            contests, localtimezone):
        embed.add_field(name=name, value=value)
    await channel.send(role.mention, embed=embed)

_WEBSITE_ALLOWED_PATTERNS = defaultdict(list)
_WEBSITE_ALLOWED_PATTERNS['codeforces.com'] = ['']
_WEBSITE_ALLOWED_PATTERNS['codechef.com'] = [
    'lunch', 'cook', 'rated']
_WEBSITE_ALLOWED_PATTERNS['atcoder.jp'] = [
    'abc:', 'arc:', 'agc:', 'grand', 'beginner', 'regular']
_WEBSITE_ALLOWED_PATTERNS['codingcompetitions.withgoogle.com'] = ['']
_WEBSITE_ALLOWED_PATTERNS['facebook.com/hackercup'] = ['']
_WEBSITE_ALLOWED_PATTERNS['leetcode.com'] = ['']
_WEBSITE_ALLOWED_PATTERNS['codedrills.io'] = ['icpc']


_WEBSITE_DISALLOWED_PATTERNS = defaultdict(list)
_WEBSITE_DISALLOWED_PATTERNS['codeforces.com'] = [
    'wild', 'fools', 'kotlin', 'unrated']
_WEBSITE_DISALLOWED_PATTERNS['codechef.com'] = ['unrated']
_WEBSITE_DISALLOWED_PATTERNS['atcoder.jp'] = []
_WEBSITE_DISALLOWED_PATTERNS['codingcompetitions.withgoogle.com'] = [
    'registration']
_WEBSITE_DISALLOWED_PATTERNS['facebook.com/hackercup'] = []
_WEBSITE_DISALLOWED_PATTERNS['leetcode.com'] = []
_WEBSITE_DISALLOWED_PATTERNS['codedrills.io'] = []

_SUPPORTED_WEBSITES = [
    'codeforces.com',
    'codechef.com',
    'atcoder.jp',
    'codingcompetitions.withgoogle.com',
    'facebook.com/hackercup',
    'leetcode.com',
    'codedrills.io'
]

_RESOURCE_NAMES = {
    'codeforces.com': 'CodeForces',
    'codechef.com': 'CodeChef', 
    'atcoder.jp': 'AtCoder',
    'codingcompetitions.withgoogle.com': 'Google', 
    'facebook.com/hackercup': 'Facebook', 
    'leetcode.com': 'LeetCode',
    'codedrills.io': 'CodeDrills'
}

GuildSettings = recordtype(
    'GuildSettings', [
        ('channel_id', None), ('role_id', None),
        ('before', None),
        ('website_allowed_patterns', defaultdict(list)),
        ('website_disallowed_patterns', defaultdict(list))])


def get_default_guild_settings():
    allowed_patterns = copy.deepcopy(_WEBSITE_ALLOWED_PATTERNS)
    disallowed_patterns = copy.deepcopy(_WEBSITE_DISALLOWED_PATTERNS)
    settings = GuildSettings()
    settings.website_allowed_patterns = allowed_patterns
    settings.website_disallowed_patterns = disallowed_patterns
    return settings


class Reminders(commands.Cog, description = "Follow upcoming CP contests with our contest reminders"):
    def __init__(self, bot):
        self.bot = bot
        self.future_contests = None
        self.contest_cache = None
        self.active_contests = None
        self.finished_contests = None
        self.start_time_map = defaultdict(list)
        self.task_map = defaultdict(list)

        self.member_converter = commands.MemberConverter()
        self.role_converter = commands.RoleConverter()

        self.logger = logging.getLogger(self.__class__.__name__)

    @commands.Cog.listener()
    @discord_common.once
    async def on_ready(self):
        asyncio.create_task(self._update_task())

    async def _update_task(self):
        self.logger.info(f'Updating reminder tasks.')
        self._generate_contest_cache()
        contest_cache = self.contest_cache
        current_time = dt.datetime.utcnow()

        self.future_contests = [
            contest for contest in contest_cache
            if contest.start_time > current_time
        ]
        self.finished_contests = [
            contest for contest in contest_cache
            if contest.start_time +
            contest.duration < current_time
        ]
        self.active_contests = [
            contest for contest in contest_cache
            if contest.start_time <= current_time <=
            contest.start_time + contest.duration
        ]

        self.active_contests.sort(key=lambda contest: contest.start_time)
        self.finished_contests.sort(
            key=lambda contest: contest.start_time +
            contest.duration,
            reverse=True
        )
        self.future_contests.sort(key=lambda contest: contest.start_time)
        # Keep most recent _FINISHED_LIMIT
        self.finished_contests = \
            self.finished_contests[:_FINISHED_CONTESTS_LIMIT]
        self.start_time_map.clear()
        for contest in self.future_contests:
            self.start_time_map[time.mktime(
                contest.start_time.timetuple())].append(contest)
        self._reschedule_all_tasks()
        await asyncio.sleep(_CONTEST_REFRESH_PERIOD)
        asyncio.create_task(self._update_task())

    def _generate_contest_cache(self):
        clist.cache(forced=False)
        db_file = Path(constants.CONTESTS_DB_FILE_PATH)
        with db_file.open() as f:
            data = json.load(f)
        contests = [Round(contest) for contest in data['objects']]
        self.contest_cache = [
            contest for contest in contests if contest.is_desired(
                _WEBSITE_ALLOWED_PATTERNS,
                _WEBSITE_DISALLOWED_PATTERNS)]

    def get_guild_contests(self, contests, guild_id, resources=None):
        settings = cf_common.user_db.get_reminder_settings(guild_id)
        if settings:
            _, _, _, website_allowed_patterns, website_disallowed_patterns = settings
        website_allowed_patterns = json.loads(website_allowed_patterns) if settings else _WEBSITE_ALLOWED_PATTERNS
        website_disallowed_patterns = json.loads(website_disallowed_patterns) if settings else _WEBSITE_DISALLOWED_PATTERNS
        contests = [contest for contest in contests if contest.is_desired(
            website_allowed_patterns, website_disallowed_patterns, resources)]
        return contests

    def get_all_contests(self, contests, guild_id, resources=None):
        website_allowed_patterns = _WEBSITE_ALLOWED_PATTERNS
        website_disallowed_patterns = _WEBSITE_DISALLOWED_PATTERNS
        contests = [contest for contest in contests if contest.is_desired(
            website_allowed_patterns, website_disallowed_patterns, resources)]
        return contests

    def _reschedule_all_tasks(self):
        for guild in self.bot.guilds:
            self._reschedule_tasks(guild.id)

    def _reschedule_tasks(self, guild_id):
        for task in self.task_map[guild_id]:
            task.cancel()
        self.task_map[guild_id].clear()
        self.logger.info(f'Tasks for guild {guild_id} cleared')
        if not self.start_time_map:
            return
        settings = cf_common.user_db.get_reminder_settings(guild_id)
        if settings is None or any(setting is None for setting in settings):
            return
        channel_id, role_id, before, \
            website_allowed_patterns, website_disallowed_patterns = settings

        channel_id, role_id, before = int(channel_id), int(role_id), json.loads(before)
        website_allowed_patterns = json.loads(website_allowed_patterns)
        website_disallowed_patterns = json.loads(website_disallowed_patterns)

        localtimezone = cf_common.user_db.get_guildtz(guild_id)
        localtimezone = pytz.timezone(localtimezone or 'Asia/Kolkata')

        guild = self.bot.get_guild(guild_id)
        channel, role = guild.get_channel(channel_id), guild.get_role(role_id)
        for start_time, contests in self.start_time_map.items():
            contests = self.get_guild_contests(contests, guild_id)
            if not contests:
                continue
            for before_mins in before:
                before_secs = 60 * before_mins
                task = asyncio.create_task(
                    _send_reminder_at(
                        channel,
                        role,
                        contests,
                        before_secs,
                        start_time -
                        before_secs, localtimezone)
                )
                self.task_map[guild_id].append(task)
        self.logger.info(
            f'{len(self.task_map[guild_id])} '
            f'tasks scheduled for guild {guild_id}')

    @staticmethod
    def _make_contest_pages(contests, title, localtimezone):
        pages = []
        chunks = paginator.chunkify(contests, _CONTESTS_PER_PAGE)
        for chunk in chunks:
            embed = discord_common.color_embed()
            for name, value in _get_embed_fields_from_contests(
                    chunk, localtimezone):
                embed.add_field(name=name, value=value, inline=False)
            pages.append((title, embed))
        return pages

    async def _send_contest_list(self, inter, contests, *, title, empty_msg):
        if contests is None:
            return await inter.edit_original_message('Contest list not present')
        if len(contests) == 0:
            return await inter.edit_original_message(embed=discord_common.embed_neutral(empty_msg))

        zone = cf_common.user_db.get_guildtz(inter.guild.id)
        zone = pytz.timezone(zone or 'Asia/Kolkata')

        pages = self._make_contest_pages(contests, title, zone)
        await paginator.paginate(self.bot, 'edit', inter, pages,
            message=await inter.original_message(),
            wait_time=_CONTEST_PAGINATE_WAIT_TIME, set_pagenum_footers=True)

    @commands.slash_command(description='Commands for contest reminders')
    async def remind(self, inter):
        pass

    @remind.sub_command(description='Set contest reminder to current channel')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def here(self, inter, role: disnake.Role, before: commands.Range[0, ...] = 300):
        """
        Sets reminder channel to current channel, role to the given role, and reminder times to the given values in minutes.

        Parameters
        ----------
        role: Member role to be mentioned when a new contest release
        before: Number of minutes to remind before a contest starts
        """
        await inter.response.defer(ephemeral = True)

        if not role.mentionable:
            return await inter.edit_original_message('The role for reminders must be mentionable.')
        if inter.channel.type != disnake.ChannelType.text:
            return await inter.edit_original_message(f'{inter.channel.mention} is not text channel.')
        before = [before]
        before = sorted(before, reverse=True)
        _, _, _, default_allowed_patterns, default_disallowed_patterns = \
            get_default_guild_settings()
        cf_common.user_db.set_reminder_settings( \
            inter.guild.id, inter.channel.id, role.id, json.dumps(before), \
                json.dumps(default_allowed_patterns), \
                json.dumps(default_disallowed_patterns)
            )
        message = f'Contest reminder has been enabled in this channel {inter.channel.mention}.'
        await inter.edit_original_message(embed=discord_common.embed_success(message))
        self._reschedule_tasks(inter.guild.id)

    @remind.sub_command(description='Set contest reminder in a specified channel')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def inchannel(self, inter, channel: disnake.TextChannel, role: disnake.Role, before: commands.Range[0, ...] = 300):
        """
        Sets reminder channel to a specified channel, role to the given role, and reminder times to the given values in minutes.

        Parameters
        ----------
        channel: Channel to set contest reminder in
        role: Member role to be mentioned when a new contest release
        before: Number of minutes to remind before a contest starts
        """
        await inter.response.defer(ephemeral = True)

        if not role.mentionable:
            return await inter.edit_original_message('The role for reminders must be mentionable')
        if channel.type != disnake.ChannelType.text:
            return await inter.edit_original_message(f'{channel.mention} is not a text channel.')
        before = [before]
        before = sorted(before, reverse=True)
        _, _, _, default_allowed_patterns, default_disallowed_patterns = \
            get_default_guild_settings()
        cf_common.user_db.set_reminder_settings( \
            inter.guild.id, channel.id, role.id, json.dumps(before), \
                json.dumps(default_allowed_patterns), \
                json.dumps(default_disallowed_patterns)
            )
        message = f'Contest reminder has been enabled in channel {channel.mention}.'
        await inter.edit_original_message(embed=discord_common.embed_success(message))
        self._reschedule_tasks(inter.guild.id)

    def _set_guild_setting(
            self,
            guild_id,
            websites,
            allowed_patterns,
            disallowed_patterns):
        # load settings
        settings = cf_common.user_db.get_reminder_settings(guild_id)
        channel_id, role_id, before, \
            website_allowed_patterns, website_disallowed_patterns = settings
        channel_id, role_id, before = int(channel_id), int(role_id), json.loads(before)
        website_allowed_patterns = json.loads(website_allowed_patterns)
        website_disallowed_patterns = json.loads(website_disallowed_patterns)
        # modify settings
        supported_websites, unsupported_websites = [], []
        for website in websites:
            if website not in _SUPPORTED_WEBSITES:
                unsupported_websites.append(website)
                continue
            website_allowed_patterns[website] = \
                allowed_patterns[website]
            website_disallowed_patterns[website] = \
                disallowed_patterns[website]
            supported_websites.append(website)
        # save settings
        cf_common.user_db.set_reminder_settings( \
            guild_id, channel_id, role_id, json.dumps(before), \
                json.dumps(website_allowed_patterns), \
                json.dumps(website_disallowed_patterns)
            )
        return supported_websites, unsupported_websites

    async def subscribe(self, guild_id, websites):
        """Start contest reminders from websites."""
        self._set_guild_setting(guild_id, websites, _WEBSITE_ALLOWED_PATTERNS, _WEBSITE_DISALLOWED_PATTERNS)

    async def unsubscribe(self, guild_id, websites):
        """Stop contest reminders from websites."""
        self._set_guild_setting(guild_id, websites, defaultdict(list), defaultdict(lambda: ['']))

    @remind.sub_command(description='Configure contest reminder settings')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def config(self, inter):
        await inter.response.defer(ephemeral = True)

        settings = cf_common.user_db.get_reminder_settings(inter.guild.id)
        if settings is None:
            return await inter.edit_original_message(embed=discord_common.embed_neutral(
                'You have to set a contest reminder in a channel in advance.'
                'Set a contest reminder by using `/remind here` or `/remind inchannel`.'
            ))
        channel_id, role_id, before, \
            website_allowed_patterns, website_disallowed_patterns = settings
        channel = inter.guild.get_channel(int(channel_id))
        role = inter.guild.get_role(int(role_id))
        website_allowed_patterns = json.loads(website_allowed_patterns)
        website_disallowed_patterns = json.loads(website_disallowed_patterns)
        if channel is None:
            return await inter.edit_original_message('Reminder channel missing. Please set another contest reminder.')
        if role is None:  
            return await inter.edit_original_message('Reminder role missing. Please set another contest reminder.')

        select = disnake.ui.Select(max_values = len(_SUPPORTED_WEBSITES),
            options = [disnake.SelectOption(
                value = website,
                description = website,
                label = _RESOURCE_NAMES[website],
                default = website_allowed_patterns[website] != None
            ) for website in _SUPPORTED_WEBSITES])
        async def select_callback(_):
            await self.unsubscribe(inter.guild.id, _SUPPORTED_WEBSITES)
            await self.subscribe(inter.guild.id, select.values)
            await self._settings(inter)
        select.callback = select_callback

        select_all = disnake.ui.Button(label = 'Select all', style = disnake.ButtonStyle.blurple)
        async def select_all_callback(_):
            await self.subscribe(inter.guild.id, _SUPPORTED_WEBSITES)
            await self._settings(inter)
        select_all.callback = select_all_callback

        unselect_all = disnake.ui.Button(label = 'Unselect all', style = disnake.ButtonStyle.red)
        async def unselect_all_callback(_):
            await self.unsubscribe(inter.guild.id, _SUPPORTED_WEBSITES)
            await self._settings(inter)
        unselect_all.callback = unselect_all_callback

        view = disnake.ui.View()
        view.add_item(select)
        view.add_item(select_all)
        view.add_item(unselect_all)

        content = 'Select the websites you want to set contest reminder for:'
        await inter.edit_original_message(content = content, view = view)

    async def _settings(self, inter):
        settings = cf_common.user_db.get_reminder_settings(inter.guild.id)
        if settings is None:
            return await inter.edit_original_message(embed=discord_common.embed_neutral('Contest reminder hasn\'t been set.'))
        channel_id, role_id, before, \
            website_allowed_patterns, website_disallowed_patterns = settings
        channel_id, role_id, before = int(channel_id), int(role_id), json.loads(before)
        website_allowed_patterns = json.loads(website_allowed_patterns)
        website_disallowed_patterns = json.loads(website_disallowed_patterns)
        
        channel = inter.guild.get_channel(channel_id)
        role = inter.guild.get_role(role_id)
        if channel is None:
            return await inter.edit_original_message('Reminder channel missing. Please set another contest reminder.', view = None)
        if role is None:  
            return await inter.edit_original_message('Reminder role missing. Please set another contest reminder.', view = None)

        subscribed_websites_str = ", ".join(
            _RESOURCE_NAMES[website] for website, patterns
            in website_allowed_patterns.items() if patterns)
        if subscribed_websites_str == '':
            subscribed_websites_str = 'No website is subscribed'

        before_str = ', '.join(str(before_mins) for before_mins in before)
        embed = discord_common.embed_success('Current reminder settings')
        embed.add_field(name='Channel', value=channel.mention)
        embed.add_field(name='Role', value=role.mention)
        embed.add_field(name='Before',
                        value=f'At {before_str} mins before contest')
        embed.add_field(name='Subscribed websites',
                        value=f'{subscribed_websites_str}')
        await inter.edit_original_message(content = '', embed=embed, view = None)

    @remind.sub_command(description='Show reminder settings')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def settings(self, inter):
        """
        Shows the reminders role, channel, times, and timezone settings."""
        # load settings
        await inter.response.defer()
        await self._settings(inter)

    async def _get_remind_role(self, inter):
        # load settings
        settings = cf_common.user_db.get_reminder_settings(inter.guild.id)
        if settings is None:
            await inter.edit_original_message(embed=discord_common.embed_neutral('Contest reminder hasn\'t been set.'))
            return
        channel_id, role_id, before, \
            website_allowed_patterns, website_disallowed_patterns = settings
        role = inter.guild.get_role(int(role_id))
        if role is None:
            await inter.edit_original_message('Reminder role missing. Please set another contest reminder.')
            return
        return role

    @remind.sub_command(description='Clear all reminder settings')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def disable(self, inter):
        await inter.response.defer()

        cf_common.user_db.clear_reminder_settings(inter.guild.id)
        await inter.edit_original_message(embed=discord_common.embed_success('Reminder settings cleared'))
        self._reschedule_tasks(inter.guild.id)

    @commands.slash_command(description='Set the server\'s timezone', usage=' <timezone>')
    @commands.check_any(commands.has_permissions(administrator = True), commands.is_owner())
    async def settz(self, inter, timezone: str):
        """
        Sets the server's timezone to the given timezone.

        Parameters
        ----------
        timezone: Find your timezone here: pastebin.com/cydNeAyr
        """
        await inter.response.defer()

        if not (timezone in pytz.all_timezones):
            desc = 'The given timezone is invalid\n'
            desc += 'All valid timezones can be found [here](https://pastebin.com/cydNeAyr)\n\n'
            desc += 'Examples of valid timezones:\n'
            desc += '```\n' + '\n'.join(random.sample(pytz.all_timezones, 5)) + '\n```'
            return await inter.edit_original_message(embed=discord_common.embed_alert(desc))
        cf_common.user_db.set_guildtz(inter.guild.id, str(pytz.timezone(timezone)))
        await inter.edit_original_message(embed=discord_common.embed_success(
            f'Succesfully set the server timezone to {timezone}'))

    @commands.slash_command(description='Commands for listing contests')
    async def clist(self, inter):
        pass

    @clist.sub_command(description='List future contests')
    async def future(self, inter, resource: _CP_PLATFORMS = "codeforces.com"):
        """List future contests."""
        await inter.response.defer()

        filter = [resource]
        contests = self.get_all_contests(self.future_contests, inter.guild.id, resources=filter)
        await self._send_contest_list(inter, contests, title='Future contests',
                                      empty_msg='No future contests scheduled')

    @clist.sub_command(description='List active contests')
    async def active(self, inter):
        """List active contests."""
        await inter.response.defer()

        contests = self.get_all_contests(self.active_contests, inter.guild.id)
        await self._send_contest_list(inter, contests, title='Active contests',
                                      empty_msg='No contests currently active')

    @clist.sub_command(description='List recent finished contests')
    async def finished(self, inter):
        """List recently concluded contests."""
        await inter.response.defer()

        contests = copy.deepcopy(self.get_all_contests(
            self.finished_contests, inter.guild.id))
        for contest in contests:
            contest.name += " (ID : "+str(contest.id)+")"
        await self._send_contest_list(inter, contests, title='Recently finished contests',
                                      empty_msg='No finished contests found')

    @discord_common.send_error_if(RemindersCogError)
    async def cog_slash_command_error(self, inter, error):
        pass


def setup(bot):
    bot.add_cog(Reminders(bot))
