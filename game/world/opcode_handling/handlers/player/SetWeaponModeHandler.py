from network.packet.PacketReader import *
from struct import unpack


class SetWeaponModeHandler(object):

    @staticmethod
    def handle(world_session, socket: int, reader: PacketReader) -> int:
        if len(reader.data) >= 1:  # Avoid handling empty set weapon mode packet.
            weapon_mode: bool = unpack('<B', reader.data[:1])[0]
            world_session.player_mgr.set_weapon_mode(weapon_mode)
            world_session.player_mgr.set_dirty()

        return 0
