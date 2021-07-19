from struct import unpack, error

from game.world.managers.maps.MapManager import MapManager
from game.world.managers.objects import MovementManager
from network.packet.PacketReader import *
from network.packet.PacketWriter import *
from utils.Logger import Logger
from utils.constants.MiscCodes import MoveFlags
from utils.constants.OpCodes import OpCode
from utils.constants.UnitCodes import StandState


class MovementHandler(object):

    @staticmethod
    def handle_movement_status(world_session, socket, reader: PacketReader) -> int:
        # Avoid handling malformed movement packets, or handling them while no player or player teleporting.
        if world_session.player_mgr and len(reader.data) >= 48:
            try:
                transport_guid, transport_x, transport_y, transport_z, transport_o, x, y, z, o, pitch, flags = \
                    unpack('<Q9fI', reader.data[:48])

                # Hacky way to prevent random teleports when colliding with elevators
                # Also acts as a rudimentary teleport cheat detection
                if not world_session.player_mgr.pending_taxi_destination and world_session.player_mgr.location.distance(
                        x=x, y=y, z=z) > 64:
                    Logger.anticheat(f'Preventing coordinate desync from player {world_session.player_mgr.player.name} ({world_session.player_mgr.guid}).')
                    world_session.player_mgr.teleport(world_session.player_mgr.map_,
                                                      world_session.player_mgr.location)

                    return 0

                # Send movement info to SpellManager until movement handling is merged to update system
                if flags & 0xF != 0:  # MoveFlags.MOVEFLAG_MOVE_MASK | MoveFlags.MOVEFLAG_STRAFE_MASK
                    world_session.player_mgr.spell_manager.flag_as_moved()

                world_session.player_mgr.transport_id = transport_guid

                world_session.player_mgr.transport.x = transport_x
                world_session.player_mgr.transport.y = transport_y
                world_session.player_mgr.transport.z = transport_z
                world_session.player_mgr.transport.o = transport_o

                world_session.player_mgr.location.x = x
                world_session.player_mgr.location.y = y
                world_session.player_mgr.location.z = z
                world_session.player_mgr.location.o = o

                world_session.player_mgr.pitch = pitch
                world_session.player_mgr.movement_flags = flags

                if flags & MoveFlags.MOVEFLAG_SPLINE_MOVER:
                    world_session.player_mgr.movement_spline = MovementManager.MovementSpline.from_bytes(
                        reader.data[48:])

                movement_data = pack(f'<Q{len(reader.data)}s',
                                     world_session.player_mgr.guid,
                                     reader.data)

                MapManager.send_surrounding(PacketWriter.get_packet(OpCode(reader.opcode), movement_data),
                                            world_session.player_mgr, include_self=False)
                MapManager.update_object(world_session.player_mgr)
                world_session.player_mgr.sync_player()

                # Update player swimming state.
                if world_session.player_mgr.is_swimming() and not world_session.player_mgr.liquid_information:
                    world_session.player_mgr.update_swimming_state(True)
                elif not world_session.player_mgr.is_swimming() and world_session.player_mgr.liquid_information:
                    world_session.player_mgr.update_swimming_state(False)

                # Get up if you jump while not standing.
                if reader.opcode == OpCode.MSG_MOVE_JUMP and \
                        world_session.player_mgr.stand_state != StandState.UNIT_DEAD and \
                        world_session.player_mgr.stand_state != StandState.UNIT_STANDING:
                    world_session.player_mgr.stand_state = StandState.UNIT_STANDING
                    world_session.player_mgr.set_dirty()

            except (AttributeError, error):
                Logger.error(f'Error while handling {OpCode(reader.opcode).name}, skipping. Data: {reader.data}')

        return 0
