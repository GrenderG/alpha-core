from game.world.WorldSessionStateHandler import WorldSessionStateHandler
from game.world.managers.objects.player.GroupManager import GroupManager
from network.packet.PacketReader import *
from utils.constants.GroupCodes import PartyOperations, PartyResults


class GroupInviteHandler(object):

    @staticmethod
    def handle(world_session, socket, reader):
        if len(reader.data) > 1:  # Avoid handling empty Group Invite packet.
            target_name = PacketReader.read_string(reader.data, 0).strip()
            target_player_mgr = WorldSessionStateHandler.find_player_by_name(target_name)

            if world_session.player_mgr.has_pending_group_invite:
                GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_INVITE, '',
                                                         PartyResults.ERR_INVITE_RESTRICTED)
            elif world_session.player_mgr.group_manager and world_session.player_mgr.group_manager.is_full():
                GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_INVITE, '',
                                                         PartyResults.ERR_GROUP_FULL)
            elif not target_player_mgr:
                GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_INVITE,
                                                         target_name, PartyResults.ERR_BAD_PLAYER_NAME_S)
            elif target_player_mgr.friends_manager.has_ignore(world_session.player_mgr.guid):
                GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_INVITE,
                                                         target_name, PartyResults.ERR_IGNORING_YOU_S)
            elif target_player_mgr and (target_player_mgr.has_pending_group_invite or target_player_mgr.group_manager):
                GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_INVITE,
                                                         target_player_mgr.player.name, PartyResults.ERR_ALREADY_IN_GROUP_S)
            elif target_player_mgr and target_player_mgr.guid == world_session.player_mgr.guid:
                GroupManager.send_group_operation_result(world_session.player_mgr, PartyOperations.PARTY_OP_INVITE,
                                                         target_player_mgr.player.name, PartyResults.ERR_INVITE_RESTRICTED)
            else:
                GroupManager.invite_player(world_session.player_mgr, target_player_mgr)

        return 0
