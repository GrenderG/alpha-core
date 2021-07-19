import time
from struct import unpack

from bitarray import bitarray
from database.dbc.DbcDatabaseManager import *
from database.realm.RealmDatabaseManager import RealmDatabaseManager
from database.world.WorldDatabaseManager import WorldDatabaseManager
from game.world.WorldSessionStateHandler import WorldSessionStateHandler
from game.world.managers.abstractions.Vector import Vector
from game.world.managers.maps.MapManager import MapManager
from game.world.managers.objects.UnitManager import UnitManager
from game.world.managers.objects.player.ChannelManager import ChannelManager
from game.world.managers.objects.player.FriendsManager import FriendsManager
from game.world.managers.objects.player.InventoryManager import InventoryManager
from game.world.managers.objects.player.TaxiManager import TaxiManager
from game.world.managers.objects.player.quest.QuestManager import QuestManager
from game.world.managers.objects.player.ReputationManager import ReputationManager
from game.world.managers.objects.player.SkillManager import SkillManager
from game.world.managers.objects.player.StatManager import StatManager
from game.world.managers.objects.player.TalentManager import TalentManager
from game.world.managers.objects.player.TradeManager import TradeManager
from game.world.managers.objects.timers.MirrorTimersManager import MirrorTimersManager
from game.world.opcode_handling.handlers.player.NameQueryHandler import NameQueryHandler
from network.packet.PacketWriter import *
from network.packet.update.UpdatePacketFactory import UpdatePacketFactory
from utils import Formulas
from utils.Logger import Logger
from utils.constants.DuelCodes import *
from utils.constants.MiscCodes import ChatFlags, LootTypes
from utils.constants.MiscCodes import ObjectTypes, ObjectTypeIds, PlayerFlags, WhoPartyStatus, HighGuid, \
    AttackTypes, MoveFlags
from utils.constants.SpellCodes import ShapeshiftForms
from utils.constants.UnitCodes import Classes, PowerTypes, Races, Genders, UnitFlags, Teams, SplineFlags
from utils.constants.UpdateFields import *

MAX_ACTION_BUTTONS = 120
MAX_EXPLORED_AREAS = 488


class PlayerManager(UnitManager):
    def __init__(self,
                 player=None,
                 session=None,
                 num_inv_slots=0x89,  # Paperdoll + Bag slots + Bag space
                 player_bytes=0,  # skin, face, hair style, hair color
                 xp=0,
                 next_level_xp=0,
                 player_bytes_2=0,  # player flags, facial hair, bank slots, 0
                 block_percentage=0,
                 dodge_percentage=0,
                 parry_percentage=0,
                 base_hp=0,
                 base_mana=0,
                 combo_points=0,
                 combo_target=0,
                 chat_flags=0,
                 online=False,
                 current_selection=0,
                 deathbind=None,
                 **kwargs):
        super().__init__(**kwargs)

        self.session = session
        self.update_lock = False
        self.teleport_destination = None
        self.teleport_destination_map = -1
        self.is_relocating = False
        self.objects_in_range = dict()

        self.player = player
        self.online = online
        self.num_inv_slots = num_inv_slots
        self.xp = xp
        self.next_level_xp = next_level_xp
        self.block_percentage = block_percentage
        self.dodge_percentage = dodge_percentage
        self.parry_percentage = parry_percentage
        self.base_hp = base_hp
        self.base_mana = base_mana
        self.combo_points = combo_points
        self.combo_target = combo_target

        self.current_selection = current_selection
        self.current_loot_selection = current_selection

        self.chat_flags = chat_flags
        self.group_status = WhoPartyStatus.WHO_PARTY_STATUS_NOT_IN_PARTY
        self.race_mask = 0
        self.class_mask = 0
        self.deathbind = deathbind
        self.team = Teams.TEAM_NONE  # Set at set_player_variables().
        self.trade_data = None
        self.last_regen = 0
        self.spirit_release_timer = 0
        self.logout_timer = -1
        self.dirty_inventory = False
        self.pending_taxi_destination = None
        self.explored_areas = bitarray(MAX_EXPLORED_AREAS, 'little')
        self.explored_areas.setall(0)
        self.liquid_information = None

        if self.player:
            self.set_player_variables()
            self.guid = self.generate_object_guid(self.player.guid)
            self.inventory = InventoryManager(self)
            self.level = self.player.level
            self.player_bytes = unpack('<I', pack('<4B', self.player.skin, self.player.face, self.player.hairstyle, self.player.haircolour))[0]
            self.player_bytes_2 = unpack('<I', pack('<4B', self.player.extra_flags, self.player.facialhair, self.player.bankslots, 0))[0]
            self.xp = player.xp
            self.talent_points = self.player.talentpoints
            self.skill_points = self.player.skillpoints
            self.map_ = self.player.map
            self.zone = self.player.zone
            self.location.x = self.player.position_x
            self.location.y = self.player.position_y
            self.location.z = self.player.position_z
            self.location.o = self.player.orientation
            self.health = self.player.health
            self.max_health = self.player.health
            self.max_power_1 = self.player.power1
            self.power_1 = self.player.power1
            self.max_power_2 = 1000
            self.power_2 = self.player.power2
            self.max_power_3 = 100
            self.power_3 = self.player.power3
            self.max_power_4 = 100
            self.power_4 = self.player.power4
            self.coinage = self.player.money
            self.online = self.player.online

            # GM checks
            self.is_god = False
            self.is_gm = self.session.account_mgr.account.gmlevel > 0
            if self.is_gm:
                self.set_gm()

            # Update exploration data.
            if self.player.explored_areas and len(self.player.explored_areas) > 0:
                self.explored_areas = bitarray(self.player.explored_areas, 'little')

            self.next_level_xp = Formulas.PlayerFormulas.xp_to_level(self.level)
            self.is_alive = self.health > 0

            self.object_type.append(ObjectTypes.TYPE_PLAYER)
            self.update_packet_factory.init_values(PlayerFields.PLAYER_END)

            self.stat_manager = StatManager(self)
            self.talent_manager = TalentManager(self)
            self.skill_manager = SkillManager(self)
            self.quest_manager = QuestManager(self)
            self.friends_manager = FriendsManager(self)
            self.reputation_manager = ReputationManager(self)
            self.taxi_manager = TaxiManager(self)
            self.duel_manager = None
            self.guild_manager = None
            self.has_pending_group_invite = False
            self.group_manager = None
            self.mirror_timers_manager = MirrorTimersManager(self)

    def get_native_display_id(self, is_male, race_data=None):
        if not race_data:
            race_data = DbcDatabaseManager.chr_races_get_by_race(self.player.race)
        return race_data.MaleDisplayId if is_male else race_data.FemaleDisplayId

    def set_player_variables(self):
        race = DbcDatabaseManager.chr_races_get_by_race(self.player.race)

        self.faction = race.FactionID
        self.creature_type = race.CreatureType

        self.gender = self.player.gender
        is_male = self.gender == Genders.GENDER_MALE

        self.native_display_id = self.get_native_display_id(is_male, race)
        self.current_display_id = self.native_display_id

        # Power type
        if self.player.class_ == Classes.CLASS_WARRIOR:
            self.power_type = PowerTypes.TYPE_RAGE
        elif self.player.class_ == Classes.CLASS_HUNTER:
            self.power_type = PowerTypes.TYPE_FOCUS
        elif self.player.class_ == Classes.CLASS_ROGUE:
            self.power_type = PowerTypes.TYPE_ENERGY
        else:
            self.power_type = PowerTypes.TYPE_MANA

        if self.player.race == Races.RACE_HUMAN:
            self.bounding_radius = 0.306 if is_male else 0.208
            self.combat_reach = 1.5
        elif self.player.race == Races.RACE_ORC:
            self.bounding_radius = 0.372 if is_male else 0.236
            self.combat_reach = 1.5
        elif self.player.race == Races.RACE_DWARF:
            self.bounding_radius = 0.347
            self.combat_reach = 1.5
        elif self.player.race == Races.RACE_NIGHT_ELF:
            self.bounding_radius = 0.389 if is_male else 0.306
            self.combat_reach = 1.5
        elif self.player.race == Races.RACE_UNDEAD:
            self.bounding_radius = 0.383
            self.combat_reach = 1.5
        elif self.player.race == Races.RACE_TAUREN:
            self.bounding_radius = 0.9747 if is_male else 0.8725
            self.combat_reach = 4.05 if is_male else 3.75
            self.native_scale = 1.35 if is_male else 1.25
        elif self.player.race == Races.RACE_GNOME:
            self.bounding_radius = 0.3519
            self.combat_reach = 1.725
            self.native_scale = 1.15
        elif self.player.race == Races.RACE_TROLL:
            self.bounding_radius = 0.306
            self.combat_reach = 1.5

        self.current_scale = self.native_scale
        self.race_mask = 1 << self.player.race - 1
        self.class_mask = 1 << self.player.class_ - 1
        self.team = PlayerManager.get_team_for_race(self.player.race)

    def set_gm(self, on=True):
        self.player.extra_flags |= PlayerFlags.PLAYER_FLAGS_GM
        self.chat_flags = ChatFlags.CHAT_TAG_GM

    def complete_login(self):
        self.online = True

        # Place player in world and update surroundings.
        MapManager.update_object(self)
        self.send_update_surrounding(self.generate_proper_update_packet(create=True), include_self=False, create=True)

        # Join default channels.
        ChannelManager.join_default_channels(self)

        # Init faction status.
        self.reputation_manager.send_initialize_factions()

        # Notify friends about player login.
        self.friends_manager.send_online_notification()  # Notify our friends

        # If guild, send guild Message of the Day.
        if self.guild_manager:
            self.guild_manager.send_motd(player_mgr=self)

        # If group, notify group members.
        if self.group_manager:
            self.group_manager.send_update()

    def logout(self):
        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LOGOUT_COMPLETE))
        self.online = False
        self.logout_timer = -1

        if self.duel_manager:
            self.duel_manager.force_duel_end(self)

        self.spell_manager.remove_all_casts()
        self.aura_manager.remove_all_auras()
        self.leave_combat(force=True)

        # Channels weren't saved on logout until Patch 0.5.5
        ChannelManager.leave_all_channels(self, logout=True)

        if self.group_manager:
            self.group_manager.send_update()

        self.friends_manager.send_offline_notification()
        self.session.save_character()
        MapManager.remove_object(self)
        WorldSessionStateHandler.pop_active_player(self)
        self.session.player_mgr = None
        self.session = None

    def get_tutorial_packet(self):
        return PacketWriter.get_packet(OpCode.SMSG_TUTORIAL_FLAGS, pack('<18I', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                                                        0, 0, 0, 0, 0))

    def get_action_buttons(self):
        data = b''
        player_buttons = RealmDatabaseManager.character_get_buttons(self.player.guid)
        for x in range(0, MAX_ACTION_BUTTONS):
            if player_buttons and x in player_buttons:
                data += pack('<i', player_buttons[x])
            else:
                data += pack('<i', 0)
        return PacketWriter.get_packet(OpCode.SMSG_ACTION_BUTTONS, data)

    def get_deathbind_packet(self):
        data = b''
        if self.deathbind:
            data = pack(
                '<3fI',
                self.deathbind.deathbind_position_x,
                self.deathbind.deathbind_position_y,
                self.deathbind.deathbind_position_z,
                self.deathbind.deathbind_map
            )
        return PacketWriter.get_packet(OpCode.SMSG_BINDPOINTUPDATE, data)

    def update_surrounding_on_me(self):
        players, creatures, gobjects = MapManager.get_surrounding_objects(self, [ObjectTypes.TYPE_PLAYER,
                                                                                 ObjectTypes.TYPE_UNIT,
                                                                                 ObjectTypes.TYPE_GAMEOBJECT])

        # At this point, all objects aren't synced unless proven otherwise
        for guid, object_info in list(self.objects_in_range.items()):
            self.objects_in_range[guid]['synced'] = False

        for guid, player in players.items():
            if self.guid != guid:
                if guid not in self.objects_in_range:
                    update_packet = player.generate_proper_update_packet(create=True)
                    self.session.enqueue_packet(update_packet)
                    self.session.enqueue_packet(NameQueryHandler.get_query_details(player.player))
                self.objects_in_range[guid] = {'object': player, 'synced': True}

        for guid, creature in creatures.items():
            if creature.is_spawned:
                if guid not in self.objects_in_range:
                    update_packet = UpdatePacketFactory.compress_if_needed(
                        PacketWriter.get_packet(OpCode.SMSG_UPDATE_OBJECT,
                                                creature.get_full_update_packet(is_self=False)))
                    self.session.enqueue_packet(update_packet)
                    self.session.enqueue_packet(creature.query_details())
            self.objects_in_range[guid] = {'object': creature, 'synced': True}

        for guid, gobject in gobjects.items():
            if guid not in self.objects_in_range:
                update_packet = UpdatePacketFactory.compress_if_needed(
                    PacketWriter.get_packet(OpCode.SMSG_UPDATE_OBJECT,
                                            gobject.get_full_update_packet(is_self=False)))
                self.session.enqueue_packet(update_packet)
                self.session.enqueue_packet(gobject.query_details())
            self.objects_in_range[guid] = {'object': gobject, 'synced': True}

        for guid, object_info in list(self.objects_in_range.items()):
            if not object_info['synced']:
                self.destroy_near_object(guid, skip_check=True)

    def destroy_near_object(self, guid, skip_check=False):
        if skip_check or guid in self.objects_in_range:
            self.session.enqueue_packet(self.objects_in_range[guid]['object'].get_destroy_packet())
            del self.objects_in_range[guid]
            return True
        return False

    def sync_player(self):
        if self.player:
            self.player.level = self.level
            self.player.xp = self.xp
            self.player.talentpoints = self.talent_points
            self.player.skillpoints = self.skill_points
            self.player.position_x = self.location.x
            self.player.position_y = self.location.y
            self.player.position_z = self.location.z
            self.player.map = self.map_
            self.player.orientation = self.location.o
            self.player.zone = self.zone
            self.player.explored_areas = self.explored_areas.to01()
            self.player.taximask = self.taxi_manager.available_taxi_nodes.to01()
            self.player.health = self.health
            self.player.power1 = self.power_1
            self.player.power2 = self.power_2
            self.player.power3 = self.power_3
            self.player.power4 = self.power_4
            self.player.money = self.coinage
            self.player.online = self.online

    # TODO: teleport system needs a complete rework
    def teleport(self, map_, location):
        if not DbcDatabaseManager.map_get_by_id(map_):
            return False

        # From here on, the update is blocked until the player teleports to a new location.
        # If another teleport triggers from a client message, then it will proceed once this TP is done.
        self.update_lock = True

        # New destination we will use when we receive an acknowledge message from client.
        self.teleport_destination_map = map_
        self.teleport_destination = Vector(location.x, location.y, location.z, location.o)

        # Same map and not inside instance
        if self.map_ == map_ and self.map_ <= 1:
            if MapManager.should_relocate(self, self.teleport_destination, map_):
                self.is_relocating = True

            data = pack(
                '<Q9fI',
                self.transport_id,
                self.transport.x,
                self.transport.y,
                self.transport.z,
                self.transport.o,
                location.x,
                location.y,
                location.z,
                location.o,
                0,  # ?
                MoveFlags.MOVEFLAG_NONE,
            )

            self.session.enqueue_packet(PacketWriter.get_packet(OpCode.MSG_MOVE_TELEPORT_ACK, data))

        # Loading screen
        else:
            self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_TRANSFER_PENDING))

            data = pack(
                '<B4f',
                map_,
                location.x,
                location.y,
                location.z,
                location.o
            )

            self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_NEW_WORLD, data))

        return True

    def spawn_player_from_teleport(self):
        if not self.is_relocating:
            # Remove ourselves from the old location.
            for guid, player in list(MapManager.get_surrounding_players(self).items()):
                if self.guid == guid:
                    continue

                # Always make sure self is destroyed for others
                if not player.destroy_near_object(self.guid):
                    player.session.enqueue_packet(self.get_destroy_packet())

        # Update new coordinates and map.
        if self.teleport_destination_map != -1 and self.teleport_destination:
            self.map_ = self.teleport_destination_map
            self.location = Vector(self.teleport_destination.x, self.teleport_destination.y, self.teleport_destination.z, self.teleport_destination.o)

        # Get us in a new grid.
        MapManager.update_object(self)

        # Get us in world again.
        self.send_update_self(create=True if not self.is_relocating else False,
                              force_inventory_update=True if not self.is_relocating else False,
                              reset_fields=False)

        self.send_update_surrounding(self.generate_proper_update_packet(
            create=True if not self.is_relocating else False),
            include_self=False,
            create=True if not self.is_relocating else False,
            force_inventory_update=True if not self.is_relocating else False)

        self.reset_fields_older_than(time.time())
        self.update_lock = False
        self.teleport_destination_map = -1
        self.teleport_destination = None
        self.is_relocating = False

        # Update managers.
        self.friends_manager.send_update_to_friends()
        if self.group_manager and self.group_manager.is_party_formed():
            self.group_manager.send_update()
        if self.duel_manager:
            self.duel_manager.force_duel_end(self)

    def set_root(self, active):
        if not self.session:
            return

        if active:
            opcode = OpCode.SMSG_FORCE_MOVE_ROOT
        else:
            opcode = OpCode.SMSG_FORCE_MOVE_UNROOT
        self.session.enqueue_packet(PacketWriter.get_packet(opcode))

    # TODO Maybe merge all speed changes in one method
    def change_speed(self, speed=0):
        if speed <= 0:
            speed = config.Unit.Defaults.run_speed
        elif speed >= 56:
            speed = 56  # Max speed without glitches
        self.running_speed = speed
        data = pack('<f', speed)
        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_FORCE_SPEED_CHANGE, data))

        MapManager.send_surrounding(PacketWriter.get_packet(OpCode.SMSG_UPDATE_OBJECT,
                                                            self.get_movement_update_packet()), self)

    def change_swim_speed(self, swim_speed=0):
        if swim_speed <= 0:
            swim_speed = config.Unit.Defaults.swim_speed
        elif swim_speed >= 56:
            swim_speed = 56  # Max possible swim speed
        self.swim_speed = swim_speed
        data = pack('<f', swim_speed)
        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_FORCE_SWIM_SPEED_CHANGE, data))

        MapManager.send_surrounding(PacketWriter.get_packet(OpCode.SMSG_UPDATE_OBJECT,
                                                            self.get_movement_update_packet()), self)

    def change_walk_speed(self, walk_speed=0):
        if walk_speed <= 0:
            walk_speed = config.Unit.Defaults.walk_speed
        elif walk_speed >= 56:
            walk_speed = 56  # Max speed without glitches
        self.walk_speed = walk_speed
        data = pack('<f', walk_speed)
        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.MSG_MOVE_SET_WALK_SPEED, data))

        MapManager.send_surrounding(PacketWriter.get_packet(OpCode.SMSG_UPDATE_OBJECT,
                                                            self.get_movement_update_packet()), self)

    def change_turn_speed(self, turn_speed=0):
        if turn_speed <= 0:
            turn_speed = config.Unit.Player.Defaults.turn_speed
        self.turn_rate = turn_speed
        data = pack('<f', turn_speed)
        # TODO NOT WORKING
        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.MSG_MOVE_SET_TURN_RATE_CHEAT, data))

        MapManager.send_surrounding(PacketWriter.get_packet(OpCode.SMSG_UPDATE_OBJECT,
                                                            self.get_movement_update_packet()), self)

    def loot_money(self):
        if self.current_selection > 0:
            enemy = MapManager.get_surrounding_unit_by_guid(self, self.current_selection)
            if enemy and enemy.loot_manager.has_money():
                # If party is formed, try to split money.
                if self.group_manager and self.group_manager.is_party_formed():
                    # Try to split money and finish on success.
                    if self.group_manager.reward_group_money(self, enemy):
                        return
                    else:  # Not able to split, notify the whole amount to the sole player.
                        data = pack('<I', enemy.loot_manager.current_money)
                        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LOOT_MONEY_NOTIFY, data))

                # Not able to split money or no group, loot money to self only.
                self.mod_money(enemy.loot_manager.current_money)
                enemy.loot_manager.clear_money()
                packet = PacketWriter.get_packet(OpCode.SMSG_LOOT_CLEAR_MONEY)
                for looter in enemy.loot_manager.get_active_looters():
                    looter.session.enqueue_packet(packet)

    def loot_item(self, slot):
        if self.current_loot_selection > 0:
            high_guid: HighGuid = self.extract_high_guid(self.current_loot_selection)
            world_obj_target = None
            if high_guid == HighGuid.HIGHGUID_UNIT:
                world_obj_target = MapManager.get_surrounding_unit_by_guid(self, self.current_loot_selection, include_players=False)
            elif high_guid == HighGuid.HIGHGUID_GAMEOBJECT:
                world_obj_target = MapManager.get_surrounding_gameobject_by_guid(self, self.current_loot_selection)

            if world_obj_target and world_obj_target.loot_manager.has_loot():
                loot = world_obj_target.loot_manager.get_loot_in_slot(slot)
                if loot and loot.item:
                    if self.inventory.add_item(item_template=loot.item.item_template, count=loot.quantity, looted=True):
                        world_obj_target.loot_manager.do_loot(slot)
                        data = pack('<B', slot)
                        packet = PacketWriter.get_packet(OpCode.SMSG_LOOT_REMOVED, data)
                        for looter in world_obj_target.loot_manager.get_active_looters():
                            looter.session.enqueue_packet(packet)

    def send_loot_release(self, guid):
        self.unit_flags &= ~UnitFlags.UNIT_FLAG_LOOTING
        self.set_uint32(UnitFields.UNIT_FIELD_FLAGS, self.unit_flags)

        high_guid: HighGuid = self.extract_high_guid(self.current_loot_selection)
        data = pack('<QB', guid, 1)  # Must be 1 otherwise client keeps the loot window open
        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LOOT_RELEASE_RESPONSE, data))

        if high_guid == HighGuid.HIGHGUID_UNIT:
            # If this release comes from the loot owner and has no party, set killed_by to None to allow FFA loot.
            enemy = MapManager.get_surrounding_unit_by_guid(self, guid, include_players=False)
            if enemy:
                if enemy.killed_by and enemy.killed_by == self and not enemy.killed_by.group_manager:
                    enemy.killed_by = None
                # If in party, check if this player has rights to release the loot for FFA.
                elif enemy.killed_by and enemy.killed_by.group_manager:
                    if self in enemy.killed_by.group_manager.get_allowed_looters(enemy):
                        if not enemy.loot_manager.has_loot():  # Flush looters for this enemy.
                            enemy.killed_by.group_manager.clear_looters_for_victim(enemy)
                        enemy.killed_by = None

                if not enemy.loot_manager.has_loot():
                    enemy.set_lootable(False)
                    enemy.set_dirty()
                    enemy.loot_manager.clear()

                enemy.loot_manager.remove_active_looter(self)
        elif high_guid == HighGuid.HIGHGUID_GAMEOBJECT:
            game_object = MapManager.get_surrounding_gameobject_by_guid(self, self.current_loot_selection)
            if game_object:
                game_object.set_ready()
        else:
            Logger.warning(f'Unhandled loot release for type {HighGuid(high_guid).name}')

        self.current_loot_selection = 0
        self.set_dirty()

    def send_loot(self, world_object):
        self.current_loot_selection = world_object.guid
        loot_type = world_object.loot_manager.get_loot_type(self, world_object)
        data = pack(
            '<QBIB',
            world_object.guid,
            loot_type,
            world_object.loot_manager.current_money,
            len(world_object.loot_manager.current_loot)
         )

        # Do not send loot if player has no permission.
        if loot_type != LootTypes.LOOT_TYPE_NOTALLOWED:
            slot = 0
            # Slot should match real current_loot indexes.
            for loot in world_object.loot_manager.current_loot:
                if loot:
                    # If this is a quest item and player does not need it, don't show it to this player.
                    if loot.is_quest_item() and not self.player_or_group_require_quest_item(
                            loot.get_item_entry(), only_self=True):
                        slot += 1
                        continue

                    # Send item query information
                    self.session.enqueue_packet(loot.item.query_details())

                    data += pack(
                        '<B3I',
                        slot,
                        loot.item.item_template.entry,
                        loot.quantity,
                        loot.item.item_template.display_id
                    )
                slot += 1

            # At this point, this player have access to the loot window, add him to the active looters.
            world_object.loot_manager.add_active_looter(self)

        packet = PacketWriter.get_packet(OpCode.SMSG_LOOT_RESPONSE, data)
        self.session.enqueue_packet(packet)

        return loot_type != LootTypes.LOOT_TYPE_NOTALLOWED

    def give_xp(self, amounts, victim=None, notify=True):
        if self.level >= config.Unit.Player.Defaults.max_level or not self.is_alive:
            return

        new_xp = self.xp
        """
        0.5.3 supports multiple amounts of XP and then combines them all

        uint64_t victim,
        uint32_t count

        loop (for each count):
            uint64_t guid,
            int32_t xp
        """

        amount_bytes = b''
        for amount in amounts:
            # Adjust XP gaining rates using config
            amount = int(amount * config.Server.Settings.xp_rate)

            new_xp += amount
            amount_bytes += pack('<QI', self.guid, amount)

        if notify:
            data = pack('<QI',
                        victim.guid if victim else self.guid,
                        len(amounts)
                        )
            data += amount_bytes
            self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LOG_XPGAIN, data))

        if new_xp >= self.next_level_xp:  # Level up!
            self.xp = (new_xp - self.next_level_xp)  # Set the overload xp as current
            self.set_uint32(PlayerFields.PLAYER_XP, self.xp)
            self.mod_level(self.level + 1)
        else:
            self.xp = new_xp
            self.set_uint32(PlayerFields.PLAYER_XP, self.xp)
            self.send_update_self()

    def mod_level(self, level):
        if level != self.level:
            max_level = 255 if self.is_gm else config.Unit.Player.Defaults.max_level
            if 0 < level <= max_level:
                should_send_info = level > self.level

                self.level = level
                self.set_uint32(UnitFields.UNIT_FIELD_LEVEL, self.level)
                self.player.leveltime = 0

                self.stat_manager.init_stats()
                hp_diff, mana_diff = self.stat_manager.apply_bonuses()
                self.set_health(self.max_health)
                self.set_mana(self.max_power_1)

                self.skill_manager.update_skills_max_value()
                self.skill_manager.build_update()

                if should_send_info:
                    data = pack('<3I',
                                level,
                                hp_diff,
                                mana_diff if self.power_type == PowerTypes.TYPE_MANA else 0
                                )
                    self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LEVELUP_INFO, data))

                    # Add Talent and Skill points
                    self.add_talent_points(Formulas.PlayerFormulas.talent_points_gain_per_level(self.level))
                    self.add_skill_points(1)

                self.next_level_xp = Formulas.PlayerFormulas.xp_to_level(self.level)
                self.set_uint32(PlayerFields.PLAYER_NEXT_LEVEL_XP, self.next_level_xp)
                self.quest_manager.update_surrounding_quest_status()
                self.friends_manager.send_update_to_friends()

                self.set_dirty()

    def player_or_group_require_quest_item(self, item_entry, only_self=False):
        if not self.group_manager or only_self:
            return self.quest_manager.item_is_still_needed_by_any_quest(item_entry)
        else:
            for member in self.group_manager.members.values():
                player_mgr = WorldSessionStateHandler.find_player_by_guid(member.guid)
                if player_mgr and player_mgr.quest_manager.item_is_still_needed_by_any_quest(item_entry):
                    return True
        return False

    def add_bank_slot(self, slot_cost):
        self.player.bankslots += 1
        self.player_bytes_2 = unpack('<I', pack('<4B', self.player.extra_flags, self.player.facialhair, self.player.bankslots, 0))[0]
        self.set_uint32(PlayerFields.PLAYER_BYTES_2, self.player_bytes_2)
        self.mod_money(-slot_cost, reload_items=True)

    def mod_money(self, amount, reload_items=False):
        if self.coinage + amount < 0:
            amount = -self.coinage

        # Gold hard cap: 214748 gold, 36 silver and 47 copper
        if self.coinage + amount > 2147483647:
            self.coinage = 2147483647
        else:
            self.coinage += amount

        self.set_uint32(UnitFields.UNIT_FIELD_COINAGE, self.coinage)

        self.send_update_self(self.generate_proper_update_packet(is_self=True), force_inventory_update=reload_items)

    def on_zone_change(self, new_zone):
        # Update player zone.
        self.zone = new_zone
        # Update friends and group.
        self.friends_manager.send_update_to_friends()
        if self.group_manager:
            self.group_manager.send_update()

        # Checks below this condition can only happen if map loading is enabled.
        if not config.Server.Settings.use_map_tiles:
            return

        # Exploration handling (only if player is not flying).
        if not self.movement_spline or self.movement_spline.flags != SplineFlags.SPLINEFLAG_FLYING:
            area_information = MapManager.get_area_information(self.map_, self.location.x, self.location.y)
            if area_information:
                # Check if we need to set this zone as explored.
                if area_information.explore_bit >= 0 and not self.has_area_explored(area_information.explore_bit):
                    self.set_area_explored(area_information)

    def has_area_explored(self, area_explore_bit):
        return self.explored_areas[area_explore_bit]

    # TODO, Trigger quest explore requirement checks.
    def set_area_explored(self, area_information):
        self.explored_areas[area_information.explore_bit] = True
        if area_information.level > 0:
            if self.level < config.Unit.Player.Defaults.max_level:
                # The following calculations are taken from VMaNGOS core.
                xp_rate = int(config.Server.Settings.xp_rate)
                diff = self.level - area_information.level
                if diff < -5:
                    xp_gain = WorldDatabaseManager.exploration_base_xp_get_by_level(self.level + 5) * xp_rate
                elif diff > 5:
                    exploration_percent = (100 - ((diff - 5) * 5))
                    if exploration_percent > 100:
                        exploration_percent = 100
                    elif exploration_percent < 0:
                        exploration_percent = 0
                    xp_gain = WorldDatabaseManager.exploration_base_xp_get_by_level(area_information.level) * exploration_percent / 100 * xp_rate
                else:
                    xp_gain = WorldDatabaseManager.exploration_base_xp_get_by_level(area_information.level) * xp_rate
                self.give_xp([xp_gain], notify=False)
            else:
                xp_gain = 0

            # Notify client new discovered zone + xp gain.
            data = pack('<2I', area_information.zone_id, xp_gain)
            packet = PacketWriter.get_packet(OpCode.SMSG_EXPLORATION_EXPERIENCE, data)
            self.session.enqueue_packet(packet)

    def update_swimming_state(self, state):
        if state:
            self.liquid_information = MapManager.get_liquid_information(self.map_, self.location.x, self.location.y)
            if not self.liquid_information:
                Logger.warning(f'Unable to retrieve liquid information.')
        else:
            self.liquid_information = None

    def is_swimming(self):
        return self.movement_flags & MoveFlags.MOVEFLAG_SWIMMING

    def is_under_water(self):
        if self.liquid_information is None or not self.is_swimming():
            return False
        return self.location.z + (self.current_scale * 2) < self.liquid_information.height

    # override
    def get_full_update_packet(self, is_self=True):
        self.bytes_0 = unpack('<I', pack('<4B', self.player.race, self.player.class_, self.gender, self.power_type))[0]
        self.bytes_1 = unpack('<I', pack('<4B', self.stand_state, 0, self.shapeshift_form, self.sheath_state))[0]
        self.bytes_2 = unpack('<I', pack('<4B', self.combo_points, 0, 0, 0))[0]
        self.player_bytes_2 = unpack('<I', pack('<4B', self.player.extra_flags, self.player.facialhair, self.player.bankslots, 0))[0]

        # Object fields
        self.set_uint64(ObjectFields.OBJECT_FIELD_GUID, self.player.guid)
        self.set_uint32(ObjectFields.OBJECT_FIELD_TYPE, self.get_object_type_value())
        self.set_uint32(ObjectFields.OBJECT_FIELD_ENTRY, self.entry)
        self.set_float(ObjectFields.OBJECT_FIELD_SCALE_X, self.current_scale)

        # Unit fields
        self.set_uint32(UnitFields.UNIT_CHANNEL_SPELL, self.channel_spell)
        self.set_uint64(UnitFields.UNIT_FIELD_CHANNEL_OBJECT, self.channel_object)
        self.set_uint32(UnitFields.UNIT_FIELD_HEALTH, self.health)
        self.set_uint32(UnitFields.UNIT_FIELD_POWER1, self.power_1)
        self.set_uint32(UnitFields.UNIT_FIELD_POWER2, self.power_2)
        self.set_uint32(UnitFields.UNIT_FIELD_POWER3, self.power_3)
        self.set_uint32(UnitFields.UNIT_FIELD_POWER4, self.power_4)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXHEALTH, self.max_health)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXPOWER1, self.max_power_1)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXPOWER2, self.max_power_2)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXPOWER3, self.max_power_3)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXPOWER4, self.max_power_4)
        self.set_uint32(UnitFields.UNIT_FIELD_LEVEL, self.level)
        self.set_uint32(UnitFields.UNIT_FIELD_FACTIONTEMPLATE, self.faction)
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_0, self.bytes_0)
        self.set_uint32(UnitFields.UNIT_FIELD_STAT0, self.str)
        self.set_uint32(UnitFields.UNIT_FIELD_STAT1, self.agi)
        self.set_uint32(UnitFields.UNIT_FIELD_STAT2, self.sta)
        self.set_uint32(UnitFields.UNIT_FIELD_STAT3, self.int)
        self.set_uint32(UnitFields.UNIT_FIELD_STAT4, self.spi)
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT0, self.base_str)
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT1, self.base_agi)
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT2, self.base_sta)
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT3, self.base_int)
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT4, self.base_spi)
        self.set_uint32(UnitFields.UNIT_FIELD_FLAGS, self.unit_flags)
        self.set_uint32(UnitFields.UNIT_FIELD_COINAGE, self.coinage)
        self.set_uint32(UnitFields.UNIT_FIELD_BASEATTACKTIME, self.base_attack_time)
        self.set_uint32(UnitFields.UNIT_FIELD_BASEATTACKTIME + 1, self.offhand_attack_time)
        self.set_int64(UnitFields.UNIT_FIELD_RESISTANCES, self.resistance_0)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCES + 1, self.resistance_1)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCES + 2, self.resistance_2)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCES + 3, self.resistance_3)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCES + 4, self.resistance_4)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCES + 5, self.resistance_5)
        self.set_float(UnitFields.UNIT_FIELD_BOUNDINGRADIUS, self.bounding_radius)
        self.set_float(UnitFields.UNIT_FIELD_COMBATREACH, self.combat_reach)
        self.set_float(UnitFields.UNIT_FIELD_WEAPONREACH, self.weapon_reach)
        self.set_uint32(UnitFields.UNIT_FIELD_DISPLAYID, self.current_display_id)
        self.set_uint32(UnitFields.UNIT_FIELD_MOUNTDISPLAYID, self.mount_display_id)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSPOSITIVE, self.resistance_buff_mods_positive_0)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSPOSITIVE + 1, self.resistance_buff_mods_positive_1)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSPOSITIVE + 2, self.resistance_buff_mods_positive_2)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSPOSITIVE + 3, self.resistance_buff_mods_positive_3)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSPOSITIVE + 4, self.resistance_buff_mods_positive_4)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSPOSITIVE + 5, self.resistance_buff_mods_positive_5)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSNEGATIVE, self.resistance_buff_mods_negative_0)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSNEGATIVE + 1, self.resistance_buff_mods_negative_1)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSNEGATIVE + 2, self.resistance_buff_mods_negative_2)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSNEGATIVE + 3, self.resistance_buff_mods_negative_3)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSNEGATIVE + 4, self.resistance_buff_mods_negative_4)
        self.set_int32(UnitFields.UNIT_FIELD_RESISTANCEBUFFMODSNEGATIVE + 5, self.resistance_buff_mods_negative_5)
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_1, self.bytes_1)
        self.set_float(UnitFields.UNIT_MOD_CAST_SPEED, self.mod_cast_speed)
        self.set_uint32(UnitFields.UNIT_DYNAMIC_FLAGS, self.dynamic_flags)
        self.set_uint32(UnitFields.UNIT_FIELD_DAMAGE, self.damage)
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_2, self.bytes_2)

        # Player fields
        self.set_uint32(PlayerFields.PLAYER_FIELD_NUM_INV_SLOTS, self.num_inv_slots)
        self.set_uint32(PlayerFields.PLAYER_BYTES, self.player_bytes)
        self.set_uint32(PlayerFields.PLAYER_XP, self.xp)
        self.set_uint32(PlayerFields.PLAYER_NEXT_LEVEL_XP, self.next_level_xp)
        self.set_uint32(PlayerFields.PLAYER_BYTES_2, self.player_bytes_2)
        self.set_uint32(PlayerFields.PLAYER_CHARACTER_POINTS1, self.talent_points)
        self.set_uint32(PlayerFields.PLAYER_CHARACTER_POINTS2, self.skill_points)
        self.set_float(PlayerFields.PLAYER_BLOCK_PERCENTAGE, self.block_percentage)
        self.set_float(PlayerFields.PLAYER_DODGE_PERCENTAGE, self.dodge_percentage)
        self.set_float(PlayerFields.PLAYER_PARRY_PERCENTAGE, self.parry_percentage)
        self.set_uint32(PlayerFields.PLAYER_BASE_MANA, self.base_mana)

        # Skills
        self.skill_manager.build_update()

        # Guild
        if self.guild_manager:
            self.guild_manager.build_update(self)
        else:
            self.set_uint32(PlayerFields.PLAYER_GUILDID, 0)

        # Duel
        if self.duel_manager:
            self.duel_manager.build_update(self)

        # Inventory
        self.inventory.send_inventory_update(is_self)
        self.inventory.build_update()

        # Quests
        self.quest_manager.build_update()

        return self.get_object_create_packet(is_self)

    def set_current_selection(self, guid):
        self.current_selection = guid
        self.set_uint64(PlayerFields.PLAYER_SELECTION, guid)

    def set_weapon_reach(self, reach):
        self.weapon_reach = reach
        self.set_float(UnitFields.UNIT_FIELD_WEAPONREACH, reach)

    def set_base_str(self, str_):
        self.base_str = str_
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT0, str_)

    def set_base_agi(self, agi):
        self.base_agi = agi
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT1, agi)

    def set_base_sta(self, sta):
        self.base_sta = sta
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT2, sta)

    def set_base_int(self, int_):
        self.base_int = int_
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT3, int_)

    def set_base_spi(self, spi):
        self.base_spi = spi
        self.set_uint32(UnitFields.UNIT_FIELD_BASESTAT4, spi)

    def set_str(self, str_):
        self.str = str_
        self.set_uint32(UnitFields.UNIT_FIELD_STAT0, str_)

    def set_agi(self, agi):
        self.agi = agi
        self.set_uint32(UnitFields.UNIT_FIELD_STAT1, agi)

    def set_sta(self, sta):
        self.sta = sta
        self.set_uint32(UnitFields.UNIT_FIELD_STAT2, sta)

    def set_int(self, int_):
        self.int = int_
        self.set_uint32(UnitFields.UNIT_FIELD_STAT3, int_)

    def set_spi(self, spi):
        self.spi = spi
        self.set_uint32(UnitFields.UNIT_FIELD_STAT4, spi)

    def add_talent_points(self, talent_points):
        self.talent_points += talent_points
        self.set_uint32(PlayerFields.PLAYER_CHARACTER_POINTS1, self.talent_points)

    def add_skill_points(self, skill_points):
        self.skill_points += skill_points
        self.set_uint32(PlayerFields.PLAYER_CHARACTER_POINTS2, self.skill_points)

    def remove_talent_points(self, talent_points):
        self.talent_points -= talent_points
        self.set_uint32(PlayerFields.PLAYER_CHARACTER_POINTS1, self.talent_points)
    
    def remove_skill_points(self, skill_points):
        self.skill_points -= skill_points
        self.set_uint32(PlayerFields.PLAYER_CHARACTER_POINTS2, self.skill_points)

    def regenerate(self, current_time):
        if not self.is_alive or self.health == 0:
            return

        # Every 2 seconds
        if current_time > self.last_regen + 2:
            # Rate calculation per class

            should_update_health = self.health < self.max_health
            should_update_power = True

            health_regen = 0
            mana_regen = 0
            if self.player.class_ == Classes.CLASS_DRUID:
                health_regen = self.spi * 0.11 + 1
                mana_regen = (self.spi / 5 + 15) / 2
            elif self.player.class_ == Classes.CLASS_HUNTER:
                health_regen = self.spi * 0.43 - 5.5
            elif self.player.class_ == Classes.CLASS_PRIEST:
                health_regen = self.spi * 0.15 + 1.4
                mana_regen = (self.spi / 4 + 12.5) / 2
            elif self.player.class_ == Classes.CLASS_MAGE:
                health_regen = self.spi * 0.11 + 1
                mana_regen = (self.spi / 4 + 12.5) / 2
            elif self.player.class_ == Classes.CLASS_PALADIN:
                health_regen = self.spi * 0.25
                mana_regen = (self.spi / 5 + 15) / 2
            elif self.player.class_ == Classes.CLASS_ROGUE:
                health_regen = self.spi * 0.84 - 13
            elif self.player.class_ == Classes.CLASS_SHAMAN:
                health_regen = self.spi * 0.28 - 3.6
                mana_regen = (self.spi / 5 + 17) / 2
            elif self.player.class_ == Classes.CLASS_WARLOCK:
                health_regen = self.spi * 0.12 + 1.5
                mana_regen = (self.spi / 5 + 15) / 2
            elif self.player.class_ == Classes.CLASS_WARRIOR:
                health_regen = self.spi * 1.26 - 22.6

            # Health

            if should_update_health and not self.in_combat or self.player.race == Races.RACE_TROLL:
                if self.player.race == Races.RACE_TROLL:
                    health_regen *= 0.1 if self.in_combat else 1.1
                if self.is_sitting:
                    health_regen *= 0.33

                if health_regen < 1:
                    health_regen = 1
                if self.health + health_regen >= self.max_health:
                    self.set_health(self.max_health)
                elif self.health < self.max_health:
                    self.set_health(self.health + int(health_regen))
            else:
                should_update_health = False

            # Powers

            # Mana
            if self.power_type == PowerTypes.TYPE_MANA:
                if self.power_1 == self.max_power_1:
                    should_update_power = False
                else:
                    if self.in_combat:
                        # 1% per second (5% per 5 seconds)
                        mana_regen = self.base_mana * 0.02

                    if mana_regen < 1:
                        mana_regen = 1
                    if self.power_1 + mana_regen >= self.max_power_1:
                        self.set_mana(self.max_power_1)
                    elif self.power_1 < self.max_power_1:
                        self.set_mana(self.power_1 + int(mana_regen))
            # Rage decay
            elif self.power_type == PowerTypes.TYPE_RAGE:
                if self.power_2 == 0:
                    should_update_power = False
                else:
                    if not self.in_combat:
                        self.set_rage(self.power_2 - 20)
            # Focus
            elif self.power_type == PowerTypes.TYPE_FOCUS:
                # Apparently focus didn't regenerate while moving.
                # Note: Needs source, not 100% confirmed.
                if self.power_3 == self.max_power_3 or self.movement_flags & MoveFlags.MOVEFLAG_MOTION_MASK:
                    should_update_power = False
                else:
                    if self.power_3 + 5 >= self.max_power_3:
                        self.set_focus(self.max_power_3)
                    elif self.power_3 < self.max_power_3:
                        self.set_focus(self.power_3 + 5)
            # Energy
            elif self.power_type == PowerTypes.TYPE_ENERGY:
                if self.power_4 == self.max_power_4:
                    should_update_power = False
                else:
                    if self.power_4 + 20 >= self.max_power_4:
                        self.set_energy(self.max_power_4)
                    elif self.power_4 < self.max_power_4:
                        self.set_energy(self.power_4 + 20)

            if should_update_health or should_update_power:
                self.set_dirty()

            self.last_regen = current_time

    # override
    def calculate_min_max_damage(self, attack_type=0):
        # TODO: Using Vanilla formula, AP was not present in Alpha
        weapon = None
        base_min_dmg, base_max_dmg = unpack('<2H', pack('<I', self.damage))
        weapon_min_dmg = 0
        weapon_max_dmg = 0
        attack_power = 0
        dual_wield_penalty = 1

        if self.player.class_ == Classes.CLASS_WARRIOR or \
                self.player.class_ == Classes.CLASS_PALADIN:
            attack_power = (self.str * 2) + (self.level * 3) - 20
        elif self.player.class_ == Classes.CLASS_DRUID:
            attack_power = (self.str * 2) - 20
        elif self.player.class_ == Classes.CLASS_HUNTER:
            attack_power = self.str + self.agi + (self.level * 2) - 20
        elif self.player.class_ == Classes.CLASS_MAGE or \
                self.player.class_ == Classes.CLASS_PRIEST or \
                self.player.class_ == Classes.CLASS_WARLOCK:
            attack_power = self.str - 10
        elif self.player.class_ == Classes.CLASS_ROGUE:
            attack_power = self.str + ((self.agi * 2) - 20) + (self.level * 2) - 20
        elif self.player.class_ == Classes.CLASS_SHAMAN:
            attack_power = self.str - 10 + ((self.agi * 2) - 20) + (self.level * 2)

        if attack_type == AttackTypes.BASE_ATTACK:
            weapon = self.inventory.get_main_hand()
            dual_wield_penalty = 1.0
        elif attack_type == AttackTypes.OFFHAND_ATTACK:
            weapon = self.inventory.get_offhand()
            dual_wield_penalty = 0.5

        if weapon:
            weapon_min_dmg = weapon.item_template.dmg_min1
            weapon_max_dmg = weapon.item_template.dmg_max1

        # Disarmed
        if not self.can_use_attack_type(attack_type):
            weapon_min_dmg = base_min_dmg
            weapon_max_dmg = base_max_dmg

        min_damage = (weapon_min_dmg + attack_power / 14) * dual_wield_penalty
        max_damage = (weapon_max_dmg + attack_power / 14) * dual_wield_penalty

        return int(min_damage), int(max_damage)

    def generate_rage(self, damage_info, is_player=False):
        # Warriors or Druids in Bear form
        if self.player.class_ == Classes.CLASS_WARRIOR or (self.player.class_ == Classes.CLASS_DRUID and
                                                           self.has_form(ShapeshiftForms.SHAPESHIFT_FORM_BEAR)):
            self.set_rage(self.power_2 + Formulas.PlayerFormulas.calculate_rage_regen(damage_info, is_player=is_player))
            self.set_dirty()

    def _send_attack_swing_error(self, victim, opcode):
        data = pack('<2Q', self.guid, victim.guid if victim else 0)
        self.session.enqueue_packet(PacketWriter.get_packet(opcode, data))

    # override
    def send_attack_swing_not_in_range(self, victim):
        self._send_attack_swing_error(victim, OpCode.SMSG_ATTACKSWING_NOTINRANGE)

    # override
    def send_attack_swing_facing_wrong_way(self, victim):
        self._send_attack_swing_error(victim, OpCode.SMSG_ATTACKSWING_BADFACING)

    # override
    def send_attack_swing_cant_attack(self, victim):
        self._send_attack_swing_error(victim, OpCode.SMSG_ATTACKSWING_CANT_ATTACK)

    # override
    def send_attack_swing_dead_target(self, victim):
        self._send_attack_swing_error(victim, OpCode.SMSG_ATTACKSWING_DEADTARGET)

    # override
    def send_attack_swing_not_standing(self, victim):
        self._send_attack_swing_error(victim, OpCode.SMSG_ATTACKSWING_NOTSTANDING)

    # override
    def has_offhand_weapon(self):
        return self.inventory.has_offhand_weapon()

    # override
    def set_weapon_mode(self, weapon_mode):
        super().set_weapon_mode(weapon_mode)
        self.bytes_1 = unpack('<I', pack('<4B', self.stand_state, 0, self.shapeshift_form, self.sheath_state))[0]

        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_1, self.bytes_1)

    # override
    def set_stand_state(self, stand_state):
        super().set_stand_state(stand_state)
        self.bytes_1 = unpack('<I', pack('<4B', self.stand_state, 0, self.shapeshift_form, self.sheath_state))[0]
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_1, self.bytes_1)

    # override
    def set_shapeshift_form(self, shapeshift_form):
        super().set_shapeshift_form(shapeshift_form)
        self.bytes_1 = unpack('<I', pack('<4B', self.stand_state, 0, self.shapeshift_form, self.sheath_state))[0]
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_1, self.bytes_1)

    # override
    def add_combo_points_on_target(self, target, combo_points):
        if combo_points <= 0 or not target.is_alive:  # Killing a unit with a combo generator can generate a combo point after death
            return

        if target.guid != self.combo_target:
            self.combo_points = min(combo_points, 5)
            self.combo_target = target.guid
        else:
            self.combo_points = min(combo_points + self.combo_points, 5)

        self.bytes_2 = unpack('<I', pack('<4B', self.combo_points, 0, 0, 0))[0]
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_2, self.bytes_2)

        self.combo_target = target.guid
        self.set_uint64(UnitFields.UNIT_FIELD_COMBO_TARGET, self.combo_target)

        self.set_dirty()

    # override
    def remove_combo_points(self):
        self.combo_points = 0
        self.bytes_2 = unpack('<I', pack('<4B', self.combo_points, 0, 0, 0))[0]
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_2, self.bytes_2)

        self.combo_target = 0
        self.set_uint64(UnitFields.UNIT_FIELD_COMBO_TARGET, self.combo_target)

    # override
    def receive_damage(self, amount, source=None, is_periodic=False):
        if self.is_god:
            return

        super().receive_damage(amount, source, is_periodic=False)

    # override
    def receive_healing(self, amount, source=None):
        super().receive_healing(amount, source)

        data = pack('<IQ', amount, source.guid)
        self.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_HEALSPELL_ON_PLAYER, data))

    def set_dirty(self, is_dirty=True, dirty_inventory=False):
        self.dirty = is_dirty
        self.dirty_inventory = dirty_inventory

    # override
    def update(self):
        # Prevent updates if not online
        if not self.online:
            return

        # Specify that the player is being updated
        self.update_lock = True

        now = time.time()
        if now > self.last_tick > 0:
            elapsed = now - self.last_tick

            # Update played time
            self.player.totaltime += elapsed
            self.player.leveltime += elapsed

            # Regeneration
            self.regenerate(now)
            # Attack update
            self.attack_update(elapsed)
            # Waypoints (mostly flying paths) update
            self.movement_manager.update_pending_waypoints(elapsed)

            # SpellManager tick
            self.spell_manager.update(now, elapsed)
            # AuraManager tick
            self.aura_manager.update(now)

            # Duel tick
            if self.duel_manager:
                self.duel_manager.update(self, elapsed)

            # Release spirit timer
            if not self.is_alive:
                if self.spirit_release_timer < 300:  # 5 min
                    self.spirit_release_timer += elapsed
                else:
                    self.repop()

            # Swimming / Breathing
            if self.is_alive:
                self.mirror_timers_manager.update(elapsed)

            # Logout timer
            if self.logout_timer > 0:
                self.logout_timer -= elapsed
                if self.logout_timer < 0:
                    self.logout()

            # Check "dirtiness" to determine if this player object should be updated yet or not.
            if self.dirty and self.online:
                self.send_update_self(reset_fields=False)
                self.send_update_surrounding(self.generate_proper_update_packet())
                MapManager.update_object(self)
                if self.reset_fields_older_than(now):
                    self.set_dirty(is_dirty=False, dirty_inventory=False)

        self.last_tick = now

        # Player object finished being updated.
        self.update_lock = False

    def send_update_self(self, update_packet=None, create=False, force_inventory_update=False, reset_fields=True):
        if not create and (self.dirty_inventory or force_inventory_update):
            self.inventory.send_inventory_update(is_self=True)
            self.inventory.build_update()

        if not update_packet:
            update_packet = self.generate_proper_update_packet(is_self=True, create=create)

        self.session.enqueue_packet(update_packet)

        if reset_fields:
            self.reset_fields_older_than(time.time())

    def send_update_surrounding(self, update_packet, include_self=False, create=False, force_inventory_update=False):
        if not create and (self.dirty_inventory or force_inventory_update):
            self.inventory.send_inventory_update(is_self=False)
            self.inventory.build_update()

        MapManager.send_surrounding(update_packet, self, include_self=include_self)
        if create:
            MapManager.send_surrounding(NameQueryHandler.get_query_details(self.player), self, include_self=True)

    def teleport_deathbind(self):
        self.teleport(self.deathbind.deathbind_map, Vector(self.deathbind.deathbind_position_x,
                                                           self.deathbind.deathbind_position_y,
                                                           self.deathbind.deathbind_position_z))

    def get_deathbind_coordinates(self):
        return (self.deathbind.deathbind_map, Vector(self.deathbind.deathbind_position_x,
                                                     self.deathbind.deathbind_position_y,
                                                     self.deathbind.deathbind_position_z))

    # override
    def die(self, killer=None):
        if killer and self.duel_manager and self.duel_manager.player_involved(killer):
            self.duel_manager.end_duel(DuelWinner.DUEL_WINNER_KNOCKOUT, DuelComplete.DUEL_FINISHED, killer)
            self.set_health(1)
            return False

        if not super().die(killer):
            return False

        if killer and killer.get_type() == ObjectTypes.TYPE_PLAYER:
            death_notify_packet = PacketWriter.get_packet(OpCode.SMSG_DEATH_NOTIFY, pack('<Q', killer.guid))
            self.session.enqueue_packet(death_notify_packet)

        TradeManager.cancel_trade(self)
        self.spirit_release_timer = 0

        self.set_dirty()
        return True

    # override
    def respawn(self):
        super().respawn()

        self.set_health(int(self.max_health / 2))
        if self.power_type == PowerTypes.TYPE_MANA:
            self.set_mana(int(self.max_power_1 / 2))
        if self.power_type == PowerTypes.TYPE_RAGE:
            self.set_rage(0)
        if self.power_type == PowerTypes.TYPE_FOCUS:
            self.set_focus(int(self.max_power_3 / 2))
        if self.power_type == PowerTypes.TYPE_ENERGY:
            self.set_energy(int(self.max_power_4 / 2))

        self.spirit_release_timer = 0

    def repop(self):
        self.respawn()
        self.teleport_deathbind()

    # override
    def on_cell_change(self):
        self.update_surrounding_on_me()
        self.quest_manager.update_surrounding_quest_status()

    # override
    def get_type(self):
        return ObjectTypes.TYPE_PLAYER

    # override
    def get_type_id(self):
        return ObjectTypeIds.ID_PLAYER

    # override
    def generate_object_guid(self, low_guid):
        return low_guid | HighGuid.HIGHGUID_PLAYER

    @staticmethod
    def get_team_for_race(race):
        race_entry = DbcDatabaseManager.chr_races_get_by_race(race)
        if race_entry:
            if race_entry.BaseLanguage == 1:
                return Teams.TEAM_HORDE
            elif race_entry.BaseLanguage == 7:
                return Teams.TEAM_ALLIANCE

        return Teams.TEAM_NONE
