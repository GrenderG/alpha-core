from struct import pack
from game.world.managers.objects.player.guild.GuildManager import GuildManager
from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from game.world import WorldManager
from game.world.WorldSessionStateHandler import WorldSessionStateHandler
from game.world.managers.GridManager import GridManager
from game.world.managers.abstractions.Vector import Vector
from network.packet.PacketWriter import PacketWriter, OpCode
from game.world.managers.ChatManager import ChatManager
from database.world.WorldDatabaseManager import WorldDatabaseManager
from database.realm.RealmDatabaseManager import RealmDatabaseManager
from utils.ConfigManager import config
from utils.TextUtils import GameTextFormatter
from utils.constants.ObjectCodes import HighGuid, ObjectTypes
from utils.constants.UpdateFields import PlayerFields
from utils.Logger import Logger


class CommandManager(object):

    @staticmethod
    def handle_command(world_session, command_msg):
        terminator_index = command_msg.find(' ') if ' ' in command_msg else len(command_msg)

        command = command_msg[1:terminator_index].strip()
        args = command_msg[terminator_index:].strip()

        if command in PLAYER_COMMAND_DEFINITIONS:
            command_func = PLAYER_COMMAND_DEFINITIONS.get(command)
        elif command in GM_COMMAND_DEFINITIONS and world_session.player_mgr.is_gm:
            command_func = GM_COMMAND_DEFINITIONS.get(command)
        else:
            ChatManager.send_system_message(world_session, 'Command not found, type .help for help.')
            return

        if command_func:
            code, res = command_func(world_session, args)
            if code != 0:
                ChatManager.send_system_message(world_session, 'Wrong arguments for <%s> command: %s' % (command, res))
            elif res:
                ChatManager.send_system_message(world_session, res)

    @staticmethod
    def _target_or_self(world_session, only_players=False):
        if world_session.player_mgr.current_selection \
                and world_session.player_mgr.current_selection != world_session.player_mgr.guid:
            if only_players:
                unit = GridManager.get_surrounding_player_by_guid(world_session.player_mgr,
                                                                  world_session.player_mgr.current_selection)
            else:
                unit = GridManager.get_surrounding_unit_by_guid(world_session.player_mgr,
                                                                world_session.player_mgr.current_selection,
                                                                include_players=True)
            if unit:
                return unit

        return world_session.player_mgr

    @staticmethod
    def help(world_session, args):
        help_str = ''

        if world_session.player_mgr.is_gm:
            gm_commands = [k for k in GM_COMMAND_DEFINITIONS.keys()]
            help_str += '[GM Commands]: \n%s\n\n' % ', '.join(gm_commands)

        player_commands = [k for k in PLAYER_COMMAND_DEFINITIONS.keys()]
        help_str += '[Player Commands]: \n%s' % ', '.join(player_commands)

        return 0, help_str

    @staticmethod
    def speed(world_session, args):
        try:
            speed = config.Unit.Defaults.run_speed * float(args)
            player_mgr = CommandManager._target_or_self(world_session, only_players=True)
            player_mgr.change_speed(speed)

            return 0, ''
        except ValueError:
            return -1, 'wrong speed value.'

    @staticmethod
    def swim_speed(world_session, args):
        try:
            speed = config.Unit.Defaults.swim_speed * float(args)
            player_mgr = CommandManager._target_or_self(world_session, only_players=True)
            player_mgr.change_swim_speed(speed)

            return 0, ''
        except ValueError:
            return -1, 'wrong speed value.'

    @staticmethod
    def gps(world_session, args):
        Logger.info('.port %f %f %f %u' % (
            world_session.player_mgr.location.x,
            world_session.player_mgr.location.y,
            world_session.player_mgr.location.z,
            world_session.player_mgr.map_,
        ))

        return 0, 'Map: %u, Zone: %u, X: %f, Y: %f, Z: %f, O: %f' % (
            world_session.player_mgr.map_,
            world_session.player_mgr.zone,
            world_session.player_mgr.location.x,
            world_session.player_mgr.location.y,
            world_session.player_mgr.location.z,
            world_session.player_mgr.location.o
        )

    @staticmethod
    def tel(world_session, args):
        try:
            tel_name = args.split()[0]
        except IndexError:
            return -1, 'please specify a location name.'
        location = WorldDatabaseManager.worldport_get_by_name(tel_name)

        if location:
            tel_location = Vector(location.x, location.y, location.z, location.o)
            success = world_session.player_mgr.teleport(location.map, tel_location)

            if success:
                return 0, 'Teleported to "%s".' % location.name
            return -1, 'map not found (%u).' % location.map
        return -1, '"%s" not found.' % tel_name

    @staticmethod
    def stel(world_session, args):
        try:
            tel_name = args.split()[0]
        except IndexError:
            return -1, 'please specify a location name to start searching.'
        locations = WorldDatabaseManager.worldport_get_by_name(tel_name, return_all=True)

        for location in locations:
            port_text = '|cFF00FFFF[Map %s]|r - %s' % (location.map, location.name)
            ChatManager.send_system_message(world_session, port_text)
        return 0, '%u worldports found.' % len(locations)

    @staticmethod
    def sitem(world_session, args):
        item_name = args.strip()
        if not item_name:
            return -1, 'please specify an item name to start searching.'
        items = WorldDatabaseManager.item_template_get_by_name(item_name, return_all=True)

        for item in items:
            item_link = GameTextFormatter.generate_item_link(item.entry, item.name, item.quality)
            item_text = '%u - %s' % (item.entry, item_link)
            ChatManager.send_system_message(world_session, item_text)
        return 0, '%u items found.' % len(items)

    @staticmethod
    def sspell(world_session, args):
        spell_name = args.strip()
        if not spell_name:
            return -1, 'please specify a spell name to start searching.'
        spells = DbcDatabaseManager.spell_get_by_name(spell_name)

        for spell in spells:
            spell_text = '%u - |cFF00FFFF[%s]|r' % (spell.ID, spell.Name_enUS.replace('\\', ''))
            spell_text += ' (%s)' % spell.NameSubtext_enUS if spell.NameSubtext_enUS else ''
            ChatManager.send_system_message(world_session, spell_text)
        return 0, '%u spells found.' % len(spells)

    @staticmethod
    def port(world_session, args):
        try:
            x, y, z, map_ = args.split()
            tel_location = Vector(float(x), float(y), float(z))
            success = world_session.player_mgr.teleport(int(map_), tel_location)

            if success:
                return 0, ''
            return -1, 'map not found (%u).' % int(map_)
        except ValueError:
            return -1, 'please use the "x y z map" format.'

    @staticmethod
    def tickets(world_session, args):
        tickets = RealmDatabaseManager.ticket_get_all()
        for ticket in tickets:
            ticket_text = '%s[%s]|r %s: %s from %s.' % ('|cFFFF0000' if ticket.is_bug else '|cFF00FFFF',
                                                        ticket.id,
                                                        ticket.submit_time,
                                                        'Bug report' if ticket.is_bug else 'Suggestion',
                                                        ticket.character_name)
            ChatManager.send_system_message(world_session, ticket_text)
        return 0, '%u tickets shown.' % len(tickets)

    @staticmethod
    def rticket(world_session, args):
        try:
            ticket_id = int(args)
            ticket = RealmDatabaseManager.ticket_get_by_id(ticket_id)
            if ticket:
                return 0, '%s[%s] %s:|r %s' % ('|cFFFF0000' if ticket.is_bug else '|cFF00FFFF', ticket_id,
                                               ticket.character_name, ticket.text_body)
            return -1, 'ticket not found.'
        except ValueError:
            return -1, 'please specify a valid ticket id.'

    @staticmethod
    def dticket(world_session, args):
        try:
            ticket_id = int(args)
            if RealmDatabaseManager.ticket_delete(ticket_id) == 0:
                return 0, 'Ticket %u deleted.' % ticket_id
            return -1, 'ticket not found.'

        except ValueError:
            return -1, 'please specify a valid ticket id.'

    @staticmethod
    def goplayer(world_session, args):
        player_name = args
        is_online = True

        player = WorldSessionStateHandler.find_player_by_name(player_name)
        player_location = None
        map_ = 0

        if player:
            player_location = player.location
            map_ = player.map_
        else:
            is_online = False
            player = RealmDatabaseManager.character_get_by_name(player_name)

        if player:
            if not is_online:
                player_location = Vector(float(player.position_x), float(player.position_y), float(player.position_z))
                map_ = player.map
        else:
            return -1, 'player not found.'

        world_session.player_mgr.teleport(int(map_), player_location)

        return 0, 'Teleported to player %s (%s).' % (player_name.capitalize(), 'Online' if is_online else 'Offline')

    @staticmethod
    def summon(world_session, args):
        player_name = args
        is_online = True

        player = WorldSessionStateHandler.find_player_by_name(player_name)

        if player:
            player.teleport(world_session.player_mgr.map_, world_session.player_mgr.location)
        else:
            is_online = False
            player = RealmDatabaseManager.character_get_by_name(player_name)

        if player:
            if not is_online:
                player.map = world_session.player_mgr.map_
                player.zone = world_session.player_mgr.zone
                player.position_x = world_session.player_mgr.location.x
                player.position_y = world_session.player_mgr.location.y
                player.position_z = world_session.player_mgr.location.z
                RealmDatabaseManager.character_update(player)
        else:
            return -1, 'player not found.'

        return 0, 'Summoned player %s (%s).' % (player_name.capitalize(), 'Online' if is_online else 'Offline')

    @staticmethod
    def ann(world_session, args):
        ann = str(args)

        for session in WorldSessionStateHandler.get_world_sessions():
            if session.player_mgr and session.player_mgr.is_online:
                ChatManager.send_system_message(session, '[SERVER] %s' % ann)

        return 0, ''

    @staticmethod
    def mount(world_session, args):
        try:
            mount_display_id = int(args)
            player_mgr = CommandManager._target_or_self(world_session, only_players=True)
            player_mgr.mount(mount_display_id)
            return 0, ''
        except ValueError:
            return -1, 'please specify a valid mount display id.'

    @staticmethod
    def unmount(world_session, args):
        player_mgr = CommandManager._target_or_self(world_session, only_players=True)
        player_mgr.unmount()
        return 0, ''

    @staticmethod
    def morph(world_session, args):
        try:
            display_id = int(args)
            unit = CommandManager._target_or_self(world_session)
            unit.set_display_id(display_id)
            return 0, ''
        except ValueError:
            return -1, 'please specify a valid display id.'

    @staticmethod
    def demorph(world_session, args):
        unit = CommandManager._target_or_self(world_session)
        unit.demorph()
        return 0, ''

    @staticmethod
    def additem(world_session, args):
        try:
            entry = int(args)
            player_mgr = CommandManager._target_or_self(world_session, only_players=True)
            item_mgr = player_mgr.inventory.add_item(entry)
            if item_mgr:
                return 0, ''
            else:
                return -1, 'unable to find and / or add that item.'
        except ValueError:
            return -1, 'please specify a valid item entry.'

    @staticmethod
    def creature_info(world_session, args):
        creature = GridManager.get_surrounding_unit_by_guid(world_session.player_mgr,
                                                            world_session.player_mgr.current_selection)

        if creature:
            return 0, '[%s] - Guid: %u, Entry: %u, Display ID: %u, X: %f, Y: %f, Z: %f, O: %f, Map: %u' % (
                creature.creature_template.name,
                creature.guid & ~HighGuid.HIGHGUID_UNIT,
                creature.creature_template.entry,
                creature.display_id,
                creature.location.x,
                creature.location.y,
                creature.location.z,
                creature.location.o,
                creature.map_
            )
        return -1, 'error retrieving creature info.'

    @staticmethod
    def player_info(world_session, args):
        # Because you can select party members on different maps, we search in the entire session pool
        player_mgr = CommandManager._target_or_self(world_session, only_players=True)

        if player_mgr:
            return 0, '[%s] - Guid: %u, Account ID: %u, Account name: %s' % (
                player_mgr.player.name,
                player_mgr.guid & ~HighGuid.HIGHGUID_PLAYER,
                player_mgr.session.account_mgr.account.id,
                player_mgr.session.account_mgr.account.name
            )
        return -1, 'error retrieving player info.'

    @staticmethod
    def gobject_info(world_session, args):
        try:
            if args:
                max_distance = int(args)
            else:
                max_distance = 10
            found_count = 0
            for guid, gobject in list(GridManager.get_surrounding_gameobjects(world_session.player_mgr).items()):
                distance = world_session.player_mgr.location.distance(gobject.location)
                if distance <= max_distance:
                    found_count += 1
                    ChatManager.send_system_message(world_session,'[%s] - Guid: %u, Entry: %u, Display ID: %u, X: %f, Y: %f, Z: %f, O: %f, Map: %u, Distance: %f' % (
                        gobject.gobject_template.name,
                        gobject.guid & ~HighGuid.HIGHGUID_GAMEOBJECT,
                        gobject.gobject_template.entry,
                        gobject.display_id,
                        gobject.location.x,
                        gobject.location.y,
                        gobject.location.z,
                        gobject.location.o,
                        gobject.map_,
                        distance
                    ))
            return 0, '%u game objects found within %u distance units.' % (found_count, max_distance)
        except ValueError:
            return -1, 'please specify a valid distance.'

    @staticmethod
    def level(world_session, args):
        try:
            input_level = int(args)
            player_mgr = CommandManager._target_or_self(world_session, only_players=True)
            player_mgr.xp = 0
            player_mgr.set_uint32(PlayerFields.PLAYER_XP, 0)
            player_mgr.mod_level(input_level)

            return 0, ''
        except ValueError:
            return -1, 'please specify a valid level.'

    @staticmethod
    def money(world_session, args):
        try:
            money = int(args)
            player_mgr = CommandManager._target_or_self(world_session, only_players=True)
            player_mgr.mod_money(money)

            return 0, ''
        except ValueError:
            return -1, 'please specify a money amount.'

    @staticmethod
    def suicide(world_session, args):
        world_session.player_mgr.deal_damage(world_session.player_mgr, world_session.player_mgr.health)

        return 0, ''

    @staticmethod
    def guildcreate(world_session, args):
        GuildManager.create_guild(world_session.player_mgr, args)

        return 0, ''

    @staticmethod
    def die(world_session, args):
        unit = CommandManager._target_or_self(world_session)
        world_session.player_mgr.deal_damage(unit, unit.health)

        return 0, ''

    @staticmethod
    def kick(world_session, args):
        player = CommandManager._target_or_self(world_session, only_players=True)
        if player:
            player.session.keep_alive = False

        return 0, ''

    @staticmethod
    def worldoff(world_session, args):
        confirmation = str(args)

        if confirmation.strip() != 'confirm':
            return -1, 'this command is DANGEROUS, it will shutdown the server. Write \'.worldoff confirm\' to do it.'

        # Prevent more sockets to be opened
        WorldManager.WORLD_ON = False

        # Kick all players
        for session in WorldSessionStateHandler.get_world_sessions():
            if session.player_mgr and session.player_mgr.is_online:
                session.keep_alive = False

        return 0, ''

    @staticmethod
    def summon_npc(world_session, args):
        creature = GridManager.get_surrounding_unit_by_guid(world_session.player_mgr,
                                                    world_session.player_mgr.current_selection)
        if creature:
            creature.respawn_time = 1

            creature.map_ = world_session.player_mgr.map_
            creature.zone = world_session.player_mgr.zone
            creature.location.x = world_session.player_mgr.location.x
            creature.location.y = world_session.player_mgr.location.y
            creature.location.z = world_session.player_mgr.location.z
            creature.location.o = world_session.player_mgr.location.o

            creature.set_dirty()
            creature.respawn()

            return 0, ''

        return -1, 'error retrieving creature info.'

    @staticmethod
    def generate_sql(world_session, args):
        creature = GridManager.get_surrounding_unit_by_guid(world_session.player_mgr,
                                                            world_session.player_mgr.current_selection)

        if creature:
            try:
                Logger.sql("UPDATE creature_template as ct, spawns_creatures as sc SET ct.display_id1='%u' WHERE sc.spawn_entry1=ct.entry AND sc.spawn_id='%u';" % (creature.display_id, creature.guid & ~HighGuid.HIGHGUID_UNIT))
                Logger.sql("UPDATE spawns_creatures SET position_x='%f', position_y='%f', position_z='%f', orientation='%f' WHERE spawn_id='%u';" % (creature.location.x, creature.location.y, creature.location.z, creature.location.o, creature.guid & ~HighGuid.HIGHGUID_UNIT))
            except TypeError:
                return -1, 'not enough arguments for format string'
            except ValueError:
                return -1, 'wrong input value'

        return 0, ''


PLAYER_COMMAND_DEFINITIONS = {
    'help': CommandManager.help,
    'suicide': CommandManager.suicide,
    'guildcreate': CommandManager.guildcreate,
}

GM_COMMAND_DEFINITIONS = {
    'speed': CommandManager.speed,
    'swimspeed': CommandManager.swim_speed,
    'gps': CommandManager.gps,
    'tel': CommandManager.tel,
    'stel': CommandManager.stel,
    'sitem': CommandManager.sitem,
    'sspell': CommandManager.sspell,
    'port': CommandManager.port,
    'tickets': CommandManager.tickets,
    'rticket': CommandManager.rticket,
    'dticket': CommandManager.dticket,
    'goplayer': CommandManager.goplayer,
    'summon': CommandManager.summon,
    'ann': CommandManager.ann,
    'mount': CommandManager.mount,
    'unmount': CommandManager.unmount,
    'morph': CommandManager.morph,
    'demorph': CommandManager.demorph,
    'additem': CommandManager.additem,
    'cinfo': CommandManager.creature_info,
    'pinfo': CommandManager.player_info,
    'goinfo': CommandManager.gobject_info,
    'level': CommandManager.level,
    'money': CommandManager.money,
    'die': CommandManager.die,
    'kick': CommandManager.kick,
    'worldoff': CommandManager.worldoff,
    'snpc': CommandManager.summon_npc,
    'sql': CommandManager.generate_sql
}
