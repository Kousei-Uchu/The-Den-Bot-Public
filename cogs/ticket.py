import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import datetime
from utils.data_handler import DataHandler
from utils.config_manager import ConfigManager

TICKET_OPEN_CID = "ticket:open_ticket"
TICKET_CLOSE_PREFIX = "ticket:close_"
TICKET_ADD_PREFIX = "ticket:add_member_"
TICKET_REM_PREFIX = "ticket:remove_member_"

class OpenTicketView(View):
    """Persistent View for the main 'Open Ticket' button."""
    def __init__(self, cog: "Ticket"):
        super().__init__(timeout=None)
        self.cog = cog

        btn = Button(
            label=self.cog.config.get("panel_button_label", "🎫 Open Ticket"),
            style=discord.ButtonStyle.blurple,
            custom_id=TICKET_OPEN_CID
        )
        btn.callback = self.open_cb
        self.add_item(btn)

    async def open_cb(self, interaction: discord.Interaction):
        await self.cog._create_ticket(interaction)


class ManagementView(View):
    """Persistent View for each ticket’s Close / Add / Remove buttons."""
    def __init__(self, cog: "Ticket", channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

        btn_close = Button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id=f"{TICKET_CLOSE_PREFIX}{channel_id}")
        btn_close.callback = self.close_cb
        self.add_item(btn_close)

        btn_add = Button(label="Add Member", style=discord.ButtonStyle.green, custom_id=f"{TICKET_ADD_PREFIX}{channel_id}")
        btn_add.callback = self.add_cb
        self.add_item(btn_add)

        btn_rem = Button(label="Remove Member", style=discord.ButtonStyle.grey, custom_id=f"{TICKET_REM_PREFIX}{channel_id}")
        btn_rem.callback = self.rem_cb
        self.add_item(btn_rem)

    async def close_cb(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        await self.cog.close_ticket_cmd(interaction, channel)

    async def add_cb(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        await self.cog.add_member(interaction, channel)

    async def rem_cb(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        await self.cog.remove_member(interaction, channel)


class Ticket(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_handler = DataHandler('data/tickets.json')
        self.config_manager = ConfigManager('config.json')
        self.config = self.config_manager.load_config().get('ticket', {})

        # load or init our ticket store: { guild_id: { channel_id: {user_id, created_at, members[...] } } }
        self.store = self.data_handler.load_data()
        # ensure guild dicts
        for gid in list(self.store):
            self.store.setdefault(gid, {}).setdefault('open_tickets', {})

        # permission config
        self.command_configs = {
            'ticket':        {'enabled': True, 'required_roles': ['@everyone'], 'permissions': []},
            'ticket_button': {'enabled': True, 'required_roles': ['@everyone'], 'permissions': []},
            'addmember':     {'enabled': True, 'required_roles': self.config.get('staff_roles', []), 'permissions': []},
            'removemember':  {'enabled': True, 'required_roles': self.config.get('staff_roles', []), 'permissions': []},
            'close_ticket':  {'enabled': True, 'required_roles': self.config.get('staff_roles', []), 'permissions': []},
        }
        for name, cfg in self.config.get('commands', {}).items():
            if name in self.command_configs:
                self.command_configs[name].update(cfg)

        # register our persistent “open ticket” view
        bot.add_view(OpenTicketView(self))
        # register management views for every existing open ticket
        for gid, guild_data in self.store.items():
            for cid_str in guild_data.get('open_tickets', {}):
                bot.add_view(ManagementView(self, int(cid_str)))

    async def check_perms(self, interaction: discord.Interaction, name: str):
        cfg = self.command_configs.get(name, {})
        if not cfg.get('enabled', True):
            return False
        # roles
        req = cfg.get('required_roles', [])
        if req and '@everyone' not in req:
            user_roles = {str(r.id) for r in interaction.user.roles}
            if not user_roles.intersection(set(req)):
                return False
        # perms
        for p in cfg.get('permissions', []):
            if not getattr(interaction.user.guild_permissions, p, False):
                return False
        return True

    def _save(self):
        self.data_handler.save_data(self.store)

    async def _create_ticket(self, interaction: discord.Interaction):
        """Called by the OpenTicketView callback."""
        if not await self.check_perms(interaction, 'ticket_button'):
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

        gid = str(interaction.guild.id)
        uid = str(interaction.user.id)
        data = self.store.setdefault(gid, {'open_tickets': {}, 'transcripts': {}})
        # only 1 ticket per non-staff
        is_staff = any(str(r.id) in self.config.get('staff_roles', []) for r in interaction.user.roles)
        if not is_staff:
            for tinfo in data['open_tickets'].values():
                if tinfo['user_id'] == uid:
                    return await interaction.response.send_message(self.config.get('already_open_message', "You already have an open ticket."), ephemeral=True)

        # category
        cat = discord.utils.get(interaction.guild.categories, id=self.config.get('category_id'))
        if not cat:
            return await interaction.response.send_message("❌ Ticket category not configured.", ephemeral=True)

        # create channel
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.display_name}",
            category=cat,
            reason=f"Ticket opened by {interaction.user}"
        )
        # perms
        await channel.set_permissions(interaction.guild.default_role, read_messages=False)
        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        for rid in self.config.get('staff_roles', []):
            role = interaction.guild.get_role(rid)
            if role:
                await channel.set_permissions(role, read_messages=True, send_messages=True)

        # store
        data['open_tickets'][str(channel.id)] = {
            'user_id': uid,
            'created_at': datetime.datetime.utcnow().isoformat(),
            'members': [uid]
        }
        self._save()

        # send the management panel
        embed = discord.Embed(
            title=self.config.get('ticket_embed_title', "Support Ticket"),
            description=self.config.get('ticket_embed_desc', "Please describe your issue."),
            color=discord.Color.blue()
        )
        view = ManagementView(self, channel.id)
        await channel.send(embed=embed, view=view)

        # register this view so it survives restarts
        self.bot.add_view(view)

        return await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    @app_commands.command(name="ticket", description="Create a new support ticket.")
    async def ticket_cmd(self, interaction: discord.Interaction):
        if not await self.check_perms(interaction, 'ticket'):
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        # shorthand to call the same logic:
        await self._create_ticket(interaction)

    @app_commands.command(name="ticket_button", description="Post the ticket panel embed.")
    async def ticket_button_cmd(self, interaction: discord.Interaction):
        if not await self.check_perms(interaction, 'ticket_button'):
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

        panel_ch = interaction.guild.get_channel(self.config.get('panel_channel_id'))
        if not panel_ch:
            return await interaction.response.send_message("❌ Panel channel not found.", ephemeral=True)

        embed = discord.Embed(
            title=self.config.get('panel_embed_title', "Open a Ticket"),
            description=self.config.get('panel_embed_description', "Click below to open a ticket."),
            color=discord.Color.green()
        )
        view = OpenTicketView(self)
        await panel_ch.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Panel posted in {panel_ch.mention}", ephemeral=True)

    async def close_ticket_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not await self.check_perms(interaction, 'close_ticket'):
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        # delete and clean up store
        gid = str(channel.guild.id)
        cid = str(channel.id)
        await channel.delete(reason="Ticket closed")
        self.store[gid]['open_tickets'].pop(cid, None)
        self._save()
        # no need to remove view: once channel is gone, interactions won’t fire

    async def add_member(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not await self.check_perms(interaction, 'addmember'):
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

        class AddModal(Modal, title="Add Member"):
            member_id = TextInput(label="Member ID or Mention")

            async def on_submit(modal_self, modal_inter: discord.Interaction):
                try:
                    m = await commands.MemberConverter().convert(modal_inter, modal_self.member_id.value)
                    await channel.set_permissions(m, read_messages=True, send_messages=True)
                    # save in store
                    gid = str(channel.guild.id)
                    tid = str(channel.id)
                    tinfo = self.store[gid]['open_tickets'][tid]
                    if str(m.id) not in tinfo['members']:
                        tinfo['members'].append(str(m.id))
                        self._save()
                    await modal_inter.response.send_message(f"✅ Added {m.mention}", ephemeral=True)
                except:
                    await modal_inter.response.send_message("❌ Invalid member.", ephemeral=True)

        await interaction.response.send_modal(AddModal())

    async def remove_member(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not await self.check_perms(interaction, 'removemember'):
            return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)

        class RemModal(Modal, title="Remove Member"):
            member_id = TextInput(label="Member ID or Mention")

            async def on_submit(modal_self, modal_inter: discord.Interaction):
                try:
                    m = await commands.MemberConverter().convert(modal_inter, modal_self.member_id.value)
                    await channel.set_permissions(m, overwrite=None)
                    # update store
                    gid = str(channel.guild.id)
                    tid = str(channel.id)
                    tinfo = self.store[gid]['open_tickets'][tid]
                    if str(m.id) in tinfo['members']:
                        tinfo['members'].remove(str(m.id))
                        self._save()
                    await modal_inter.response.send_message(f"✅ Removed {m.mention}", ephemeral=True)
                except:
                    await modal_inter.response.send_message("❌ Invalid member.", ephemeral=True)

        await interaction.response.send_modal(RemModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(Ticket(bot))
