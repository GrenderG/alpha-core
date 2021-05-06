from network.packet.PacketReader import *
from game.world.managers.objects.player.GroupManager import GroupManager
from database.realm.RealmDatabaseManager import RealmDatabaseManager
from utils.constants.GroupCodes import PartyOperations, PartyResults


class GroupSetLeaderHandler(object):

    @staticmethod
    def handle(world_session, socket, reader):
        target_name = PacketReader.read_string(reader.data, 0).strip()
        target_player_mgr = RealmDatabaseManager.character_get_by_name(target_name)

        if not world_session.player_mgr.group_manager:
            GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_LEAVE, '',
                                                     PartyResults.ERR_NOT_IN_GROUP)
        elif not target_player_mgr:
            GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_LEAVE, '',
                                                     PartyResults.ERR_BAD_PLAYER_NAME_S)
        else:
            world_session.player_mgr.group_manager.set_party_leader(world_session.player_mgr.guid, target_player_mgr.guid)

        return 0
