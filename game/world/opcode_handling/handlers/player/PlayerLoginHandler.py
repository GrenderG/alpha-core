from network.packet.PacketReader import PacketReader
import time
from struct import unpack

from database.dbc.DbcDatabaseManager import *
from database.realm.RealmDatabaseManager import *
from game.world.WorldSessionStateHandler import WorldSessionStateHandler
from game.world.managers.objects.player.ChatManager import ChatManager
from game.world.managers.objects.player.GroupManager import GroupManager
from game.world.managers.objects.player.PlayerManager import PlayerManager
from game.world.managers.objects.player.guild.GuildManager import GuildManager
from game.world.managers.objects.player.guild.PetitionManager import PetitionManager
from network.packet.PacketWriter import *
from utils.ConfigManager import config
from utils.Logger import Logger
from utils.constants.CharCodes import CharLogin
from utils.constants.UnitCodes import PowerTypes


class PlayerLoginHandler(object):

    @staticmethod
    def handle(world_session, socket, reader: PacketReader) -> int:
        if len(reader.data) < 8:  # Avoid handling wrong player login packet.
            return -1

        guid = unpack('<Q', reader.data[:8])[0]

        world_session.player_mgr = PlayerManager(
            RealmDatabaseManager.character_get_by_guid(guid), world_session)
        world_session.player_mgr.session = world_session
        if not world_session.player_mgr.player:
            Logger.anticheat(f'Character with wrong guid ({guid}) tried to login.')
            return -1
        else:
            WorldSessionStateHandler.push_active_player_session(world_session)

        # Disabled race & class checks (only if not a GM)
        if not world_session.player_mgr.is_gm:
            disabled_race_mask = config.Server.General.disabled_race_mask
            disabled = disabled_race_mask & world_session.player_mgr.race_mask == world_session.player_mgr.race_mask

            if not disabled:
                disabled_class_mask = config.Server.General.disabled_class_mask
                disabled = disabled_class_mask & world_session.player_mgr.class_mask == world_session.player_mgr.class_mask

            if disabled:
                # Not 100% sure if CHAR_LOGIN_DISABLED matters here, but I don't know where else to send it
                data = pack(
                    '<B', CharLogin.CHAR_LOGIN_DISABLED
                )
                world_session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_CHARACTER_LOGIN_FAILED, data))
                return 0

        # Class & race allowed, continue with the login process

        world_session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LOGIN_SETTIMESPEED,
                                                             PlayerLoginHandler._get_login_timespeed()))

        world_session.player_mgr.skill_manager.load_proficiencies()
        world_session.player_mgr.spell_manager.load_spells()

        world_session.player_mgr.deathbind = RealmDatabaseManager.character_get_deathbind(world_session.player_mgr.guid)
        world_session.player_mgr.friends_manager.load_from_db(RealmDatabaseManager.character_get_social(world_session.player_mgr.guid))

        world_session.enqueue_packet(world_session.player_mgr.get_deathbind_packet())
        # Tutorials aren't implemented in 0.5.3
        # world_session.enqueue_packet(world_session.player_mgr.get_tutorial_packet())
        world_session.player_mgr.skill_manager.init_proficiencies()
        world_session.enqueue_packet(world_session.player_mgr.spell_manager.get_initial_spells())
        world_session.enqueue_packet(world_session.player_mgr.get_action_buttons())

        # MotD
        ChatManager.send_system_message(world_session, config.Server.General.motd)

        world_session.player_mgr.inventory.load_items()
        world_session.player_mgr.talent_manager.apply_talent_auras()
        world_session.player_mgr.stat_manager.init_stats()
        world_session.player_mgr.stat_manager.apply_bonuses()
        world_session.player_mgr.skill_manager.load_skills()
        world_session.player_mgr.quest_manager.load_quests()
        world_session.player_mgr.reputation_manager.load_reputations()
        GuildManager.set_character_guild(world_session.player_mgr)
        GroupManager.set_character_group(world_session.player_mgr)
        PetitionManager.load_petition(world_session.player_mgr)

        # First login
        if world_session.player_mgr.player.totaltime == 0:
            # Replenish health, and mana if needed.
            world_session.player_mgr.set_health(world_session.player_mgr.max_health)
            if world_session.player_mgr.power_type == PowerTypes.TYPE_MANA:
                world_session.player_mgr.set_mana(world_session.player_mgr.max_power_1)

            # Load self before sending cinematic
            PlayerLoginHandler._load_self(world_session.player_mgr)

            # Send cinematic
            PlayerLoginHandler._send_cinematic(world_session, world_session.player_mgr.player, socket)
        else:
            PlayerLoginHandler._load_self(world_session.player_mgr)

        world_session.player_mgr.complete_login()

        return 0

    @staticmethod
    def _load_self(player):
        player.send_update_self(create=True)

    @staticmethod
    def _send_cinematic(world_session, player, socket):
        # Sadly, ONLY undeads have intro cinematic.
        cinematic_id = DbcDatabaseManager.chr_races_get_by_race(player.race).CinematicSequenceID
        if cinematic_id != 0:
            data = pack('<I', cinematic_id)
            world_session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_TRIGGER_CINEMATIC, data))

    @staticmethod
    def _get_login_timespeed() -> bytes:
        data = pack(
            '<If',
            PlayerLoginHandler._get_secs_to_time_bit_fields(),  # game time (secs) to bit
            config.World.Gameplay.game_speed
        )
        return data

    @staticmethod
    def _get_secs_to_time_bit_fields() -> int:
        local = time.localtime()

        year = local.tm_year - 2000  # "Blizz Time" starts at year 2000
        month = local.tm_mon - 1
        day = local.tm_mday - 1
        day_of_week = local.tm_wday
        hour = local.tm_hour
        minute = local.tm_min

        return minute | (hour << 6) | (day_of_week << 11) | (day << 14) | (month << 20) | (year << 24)
