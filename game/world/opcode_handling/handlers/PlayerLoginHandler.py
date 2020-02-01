import time

from struct import pack, unpack

from network.packet.PacketWriter import *
from game.world.managers.PlayerManager import PlayerManager
from database.realm.RealmDatabaseManager import *
from utils.Logger import Logger
from game.world.managers.ObjectManager import ObjectManager
from game.world.managers.PlayerManager import PlayerManager
from utils.constants.ObjectCodes import ObjectTypes
from utils.ConfigManager import config
from utils.constants.ObjectCodes import UpdateTypes
from game.world.managers.ChatManager import ChatManager


class PlayerLoginHandler(object):

    @staticmethod
    def handle(world_session, socket, reader):
        guid = unpack('<Q', reader.data)[0]

        world_session.player_mgr = PlayerManager(RealmDatabaseManager.character_get_by_guid(guid))
        if not world_session.player_mgr.player:
            Logger.error('Character with wrong guid (%u) tried to login.' % guid)
            return -1

        socket.sendall(PacketWriter.get_packet(OpCode.SMSG_LOGIN_SETTIMESPEED,
                                               PlayerLoginHandler._get_login_timespeed()))

        socket.sendall(world_session.player_mgr.get_tutorial_packet())
        socket.sendall(world_session.player_mgr.get_initial_spells())
        socket.sendall(world_session.player_mgr.get_query_details())
        # MotD
        ChatManager.send_system_message(world_session, config.Server.General.motd)

        socket.sendall(PacketWriter.get_packet(
            OpCode.SMSG_UPDATE_OBJECT,
            world_session.player_mgr.create_update_packet(UpdateTypes.UPDATE_IN_RANGE.value) +
            world_session.player_mgr.get_update_packet()))

        world_session.player_mgr.complete_login()

        return 0

    @staticmethod
    def _get_login_timespeed():
        data = pack(
            '<If',
            PlayerLoginHandler._get_secs_to_time_bit_fields(),  # game time (secs) to bit
            config.World.Gameplay.game_speed
        )
        return data

    @staticmethod
    def _get_secs_to_time_bit_fields():
        local = time.localtime()

        year = local.tm_year - 2000
        month = local.tm_mon - 1
        day = local.tm_mday - 1
        day_of_week = local.tm_wday
        hour = local.tm_hour
        minute = local.tm_min

        return ((((minute | (hour << 6)) | (day_of_week << 11)) | (day << 14)) | (month << 20)) | (year << 24)