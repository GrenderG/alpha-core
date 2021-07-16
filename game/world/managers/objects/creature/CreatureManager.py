import time
from random import randint, choice
from struct import unpack, pack

from database.world.WorldModels import NpcTrainer, SpellChain
from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from database.world.WorldDatabaseManager import WorldDatabaseManager
from game.world.managers.abstractions.Vector import Vector
from game.world.managers.maps.MapManager import MapManager
from game.world.managers.objects.UnitManager import UnitManager
from game.world.managers.objects.creature.CreatureLootManager import CreatureLootManager
from game.world.managers.objects.item.ItemManager import ItemManager
from network.packet.PacketWriter import PacketWriter
from utils import Formulas
from utils.Logger import Logger
from utils.Formulas import UnitFormulas
from utils.constants.ItemCodes import InventoryTypes, ItemSubClasses
from utils.constants.MiscCodes import NpcFlags, ObjectTypes, ObjectTypeIds, UnitDynamicTypes, TrainerServices, \
    TrainerTypes, AttackTypes
from utils.constants.OpCodes import OpCode
from utils.constants.SpellCodes import SpellSchools
from utils.constants.UnitCodes import UnitFlags, WeaponMode, CreatureTypes, MovementTypes, SplineFlags
from utils.constants.UpdateFields import ObjectFields, UnitFields


class CreatureManager(UnitManager):

    def __init__(self,
                 creature_template,
                 creature_instance=None,
                 **kwargs):
        super().__init__(**kwargs)

        self.creature_template = creature_template
        self.creature_instance = creature_instance
        self.killed_by = None

        self.guid = self.generate_object_guid(creature_instance.spawn_id if creature_instance else 0)

        if self.creature_template:
            self.entry = self.creature_template.entry
            self.native_display_id = self.generate_display_id()
            self.current_display_id = self.native_display_id
            self.max_health = self.creature_template.health_max
            self.power_1 = self.creature_template.mana_min
            self.max_power_1 = self.creature_template.mana_max
            self.level = randint(self.creature_template.level_min, self.creature_template.level_max)
            self.resistance_0 = self.creature_template.armor
            self.resistance_1 = self.creature_template.holy_res
            self.resistance_2 = self.creature_template.fire_res
            self.resistance_3 = self.creature_template.nature_res
            self.resistance_4 = self.creature_template.frost_res
            self.resistance_5 = self.creature_template.shadow_res
            self.npc_flags = self.creature_template.npc_flags
            self.mod_cast_speed = 1.0
            self.base_attack_time = self.creature_template.base_attack_time
            self.unit_flags = self.creature_template.unit_flags
            self.faction = self.creature_template.faction
            self.creature_type = self.creature_template.type
            self.sheath_state = WeaponMode.NORMALMODE

            if 0 < self.creature_template.rank < 4:
                self.unit_flags = self.unit_flags | UnitFlags.UNIT_FLAG_PLUS_MOB

            self.fully_loaded = False
            self.is_evading = False
            self.wearing_offhand_weapon = False
            self.respawn_timer = 0
            self.is_spawned = True
            self.last_random_movement = 0
            self.random_movement_wait_time = randint(1, 12)

            self.loot_manager = CreatureLootManager(self)

        if self.creature_instance:
            self.health = int((self.creature_instance.health_percent / 100) * self.max_health)
            self.map_ = self.creature_instance.map
            self.spawn_position = Vector(self.creature_instance.position_x,
                                         self.creature_instance.position_y,
                                         self.creature_instance.position_z,
                                         self.creature_instance.orientation)
            self.location = self.spawn_position
            self.respawn_time = randint(self.creature_instance.spawntimesecsmin, self.creature_instance.spawntimesecsmax)

    def load(self):
        MapManager.update_object(self)

    def generate_display_id(self):
        display_id_list = list(filter((0).__ne__, [self.creature_template.display_id1,
                                                   self.creature_template.display_id2,
                                                   self.creature_template.display_id3,
                                                   self.creature_template.display_id4]))
        return choice(display_id_list) if len(display_id_list) > 0 else 4  # 4 = cube

    def send_inventory_list(self, world_session):
        vendor_data, session = WorldDatabaseManager.creature_get_vendor_data(self.entry)
        item_count = len(vendor_data) if vendor_data else 0

        data = pack(
            '<QB',
            self.guid,
            item_count
        )

        if item_count == 0:
            data += pack('<B', 0)
        else:
            for vendor_data_entry in vendor_data:
                data += pack(
                    '<7I',
                    1,  # mui
                    vendor_data_entry.item,
                    vendor_data_entry.item_template.display_id,
                    0xFFFFFFFF if vendor_data_entry.maxcount <= 0 else vendor_data_entry.maxcount,
                    vendor_data_entry.item_template.buy_price,
                    0,  # durability
                    0,  # stack count
                )
                world_session.enqueue_packet(ItemManager(item_template=vendor_data_entry.item_template).query_details())

        session.close()
        world_session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_LIST_INVENTORY, data))

    def send_trainer_list(self, world_session): # TODO Add skills (Two-Handed Swords etc.) to trainers for skill points https://i.imgur.com/tzyDDqL.jpg
        trainspell_bytes: bytes = b''
        trainspell_count: int = 0

        trainer_ability_list: list[NpcTrainer] = WorldDatabaseManager.TrainerSpellHolder.trainer_spells_get_by_trainer(self.entry)

        if not self.is_trainer():
            return

        if not self.is_trainer_for_class(world_session.player_mgr.player.class_):
            Logger.anticheat(f'send_trainer_list called from NPC {self.entry} by player with GUID {world_session.player_mgr.guid} but this unit does not train that player\'s class. Possible cheating')
            return

        if not trainer_ability_list or trainer_ability_list.count == 0:
            Logger.warning(f'send_trainer_list called from NPC {self.entry} but no trainer spells found!')
            return

        for ability in trainer_ability_list:
            ability_spell_chain: SpellChain = WorldDatabaseManager.SpellChainHolder.spell_chain_get_by_spell(ability.spell)

            spell_level: int = ability.reqlevel  # Use this and not spell data, as there are differences between data source (2003 Game Guide) and what is in spell table.
            spell_rank: int = ability_spell_chain.rank
            prev_spell: int = ability_spell_chain.prev_spell
            req_spell: int = ability_spell_chain.req_spell

            spell_is_too_high_level: bool = spell_level > world_session.player_mgr.level

            if ability.spell in world_session.player_mgr.spell_manager.spells:
                status = TrainerServices.TRAINER_SERVICE_USED
            else:
                if prev_spell in world_session.player_mgr.spell_manager.spells and spell_rank > 1 and not spell_is_too_high_level:
                    status = TrainerServices.TRAINER_SERVICE_AVAILABLE
                elif spell_rank == 1 and not spell_is_too_high_level:
                    status = TrainerServices.TRAINER_SERVICE_AVAILABLE
                else:
                    status = TrainerServices.TRAINER_SERVICE_UNAVAILABLE

            data: bytes = pack(
                '<IBI3B6I',
                ability.spell,  # Spell id
                status,  # Status
                ability.spellcost,  # Cost
                ability.talentpointcost,  # Talent Point Cost
                ability.skillpointcost,  # Skill Point Cost
                spell_level,  # Required Level
                ability.reqskill,  # Required Skill Line
                ability.reqskillvalue,  # Required Skill Rank
                0,  # Required Skill Step
                prev_spell,  # Required Ability (1)
                0,  # Required Ability (2)
                0  # Required Ability (3)
            )
            trainspell_bytes += data
            trainspell_count += 1

        # TODO: Temp placeholder.
        greeting: str = f'Hello, {world_session.player_mgr.player.name}! Ready for some training?'
        greeting_bytes = PacketWriter.string_to_bytes(greeting)
        greeting_bytes = pack(
                    f'<{len(greeting_bytes)}s', 
                    greeting_bytes
        )

        data = pack('<Q2I', self.guid, TrainerTypes.TRAINER_TYPE_GENERAL, trainspell_count) + trainspell_bytes + greeting_bytes
        world_session.player_mgr.session.enqueue_packet(PacketWriter.get_packet(OpCode.SMSG_TRAINER_LIST, data))

    def finish_loading(self):
        if self.creature_template and self.creature_instance:
            if not self.fully_loaded:
                creature_model_info = WorldDatabaseManager.creature_get_model_info(self.current_display_id)
                if creature_model_info:
                    self.bounding_radius = creature_model_info.bounding_radius
                    self.combat_reach = creature_model_info.combat_reach
                    self.gender = creature_model_info.gender

                if self.creature_template.scale == 0:
                    display_scale = DbcDatabaseManager.creature_display_info_get_by_id(self.current_display_id)
                    if display_scale and display_scale.CreatureModelScale > 0:
                        self.native_scale = display_scale.CreatureModelScale
                    else:
                        self.native_scale = 1
                else:
                    self.native_scale = self.creature_template.scale
                self.current_scale = self.native_scale

                if self.creature_template.equipment_id > 0:
                    creature_equip_template = WorldDatabaseManager.creature_get_equipment_by_id(
                        self.creature_template.equipment_id
                    )
                    if creature_equip_template:
                        self.set_virtual_item(0, creature_equip_template.equipentry1)
                        self.set_virtual_item(1, creature_equip_template.equipentry2)
                        self.set_virtual_item(2, creature_equip_template.equipentry3)

                self.fully_loaded = True

    def set_virtual_item(self, slot, item_entry):
        if item_entry == 0:
            self.set_uint32(UnitFields.UNIT_VIRTUAL_ITEM_SLOT_DISPLAY + slot, 0)
            self.set_uint32(UnitFields.UNIT_VIRTUAL_ITEM_INFO + (slot * 2) + 0, 0)
            self.set_uint32(UnitFields.UNIT_VIRTUAL_ITEM_INFO + (slot * 2) + 1, 0)
            return

        item_template = WorldDatabaseManager.ItemTemplateHolder.item_template_get_by_entry(item_entry)
        if item_template:
            self.set_uint32(UnitFields.UNIT_VIRTUAL_ITEM_SLOT_DISPLAY + slot, item_template.display_id)
            virtual_item_info = unpack('<I', pack('<4B',
                                                  item_template.class_,
                                                  item_template.subclass,
                                                  item_template.material,
                                                  item_template.inventory_type)
                                       )[0]
            self.set_uint32(UnitFields.UNIT_VIRTUAL_ITEM_INFO + (slot * 2) + 0, virtual_item_info)
            self.set_uint32(UnitFields.UNIT_VIRTUAL_ITEM_INFO + (slot * 2) + 1, item_template.sheath)

            # Main hand
            if slot == 0:
                # This is a TOTAL guess, I have no idea about real weapon reach values.
                # The weapon reach unit field was removed in patch 0.10.
                if item_template.inventory_type == InventoryTypes.TWOHANDEDWEAPON:
                    self.weapon_reach = 1.5
                elif item_template.subclass == ItemSubClasses.ITEM_SUBCLASS_DAGGER:
                    self.weapon_reach = 0.5
                elif item_template.subclass != ItemSubClasses.ITEM_SUBCLASS_FIST_WEAPON:
                    self.weapon_reach = 1.0

            # Offhand
            if slot == 1:
                self.wearing_offhand_weapon = (item_template.inventory_type == InventoryTypes.WEAPON or
                                               item_template.inventory_type == InventoryTypes.WEAPONOFFHAND)
        elif slot == 0:
            self.weapon_reach = 0.0

    def is_quest_giver(self) -> bool:
        return self.npc_flags & NpcFlags.NPC_FLAG_QUESTGIVER

    def is_trainer(self) -> bool:
        return self.npc_flags & NpcFlags.NPC_FLAG_TRAINER

    def is_trainer_for_class(self, player_class: int) -> bool:
        if not self.is_trainer():
            return False

        if self.creature_template.trainer_class == player_class:
            return True
        return False

    def trainer_has_spell(self, spell_id: int) -> bool:
        if not self.is_trainer():
            return False
        
        trainer_spells: list[NpcTrainer] = WorldDatabaseManager.TrainerSpellHolder.trainer_spells_get_by_trainer(self.entry)

        for trainer_spell in trainer_spells:
            if trainer_spell.spell == spell_id:
                return True

        return False

    # override
    def get_full_update_packet(self, is_self=True):
        self.finish_loading()

        # race, class, gender, power_type
        self.bytes_0 = unpack('<I', pack('<4B', 0, self.creature_template.unit_class, self.gender, 0))[0]
        # stand_state, npc_flags, shapeshift_form, visibility_flag
        self.bytes_1 = unpack('<I', pack('<4B', self.stand_state, self.npc_flags, self.shapeshift_form, 0))[0]
        # sheath_state, misc_flags, pet_flags, unknown
        self.bytes_2 = unpack('<I', pack('<4B', self.sheath_state, 0, 0, 0))[0]
        self.damage = unpack('<I', pack('<2H', int(self.creature_template.dmg_min),
                                        int(self.creature_template.dmg_max)))[0]

        # Object fields
        self.set_uint64(ObjectFields.OBJECT_FIELD_GUID, self.guid)
        self.set_uint32(ObjectFields.OBJECT_FIELD_TYPE, self.get_object_type_value())
        self.set_uint32(ObjectFields.OBJECT_FIELD_ENTRY, self.entry)
        self.set_float(ObjectFields.OBJECT_FIELD_SCALE_X, self.current_scale)

        # Unit fields
        self.set_uint32(UnitFields.UNIT_CHANNEL_SPELL, self.channel_spell)
        self.set_uint64(UnitFields.UNIT_FIELD_CHANNEL_OBJECT, self.channel_object)
        self.set_uint32(UnitFields.UNIT_FIELD_HEALTH, self.health)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXHEALTH, self.max_health)
        self.set_uint32(UnitFields.UNIT_FIELD_POWER1, self.power_1)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXHEALTH, self.max_health)
        self.set_uint32(UnitFields.UNIT_FIELD_MAXPOWER1, self.max_power_1)
        self.set_uint32(UnitFields.UNIT_FIELD_LEVEL, self.level)
        self.set_uint32(UnitFields.UNIT_FIELD_FACTIONTEMPLATE, self.faction)
        self.set_uint32(UnitFields.UNIT_FIELD_FLAGS, self.unit_flags)
        self.set_uint32(UnitFields.UNIT_FIELD_COINAGE, self.coinage)
        self.set_float(UnitFields.UNIT_FIELD_BASEATTACKTIME, self.base_attack_time)
        self.set_float(UnitFields.UNIT_FIELD_BASEATTACKTIME + 1, 0)
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
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_0, self.bytes_0)
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_1, self.bytes_1)
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_2, self.bytes_2)
        self.set_float(UnitFields.UNIT_MOD_CAST_SPEED, self.mod_cast_speed)
        self.set_uint32(UnitFields.UNIT_DYNAMIC_FLAGS, self.dynamic_flags)
        self.set_uint32(UnitFields.UNIT_FIELD_DAMAGE, self.damage)

        return self.get_object_create_packet(is_self)

    def query_details(self):
        name_bytes = PacketWriter.string_to_bytes(self.creature_template.name)
        subname_bytes = PacketWriter.string_to_bytes(self.creature_template.subname)
        data = pack(
            f'<I{len(name_bytes)}ssss{len(subname_bytes)}s3I',
            self.entry,
            name_bytes, b'\x00', b'\x00', b'\x00',
            subname_bytes,
            self.creature_template.type_flags,
            self.creature_type,
            self.creature_template.beast_family
        )
        return PacketWriter.get_packet(OpCode.SMSG_CREATURE_QUERY_RESPONSE, data)

    def _perform_random_movement(self, now):
        if not self.in_combat and self.creature_instance.movement_type == MovementTypes.WANDER:
            if len(self.movement_manager.pending_waypoints) == 0:
                if now > self.last_random_movement + self.random_movement_wait_time:
                    self.movement_manager.move_random(self.spawn_position,
                                                      self.creature_instance.wander_distance)
                    self.random_movement_wait_time = randint(1, 12)
                    self.last_random_movement = now

    def _perform_combat_movement(self, now):
        if self.combat_target:
            current_distance = self.location.distance(self.combat_target.location)
            interactable_distance = UnitFormulas.interactable_distance(self, self.combat_target)

            # If target is within interactable distance, don't move yet.
            if current_distance <= interactable_distance:
                return

            # TODO: Find better formula?
            combat_position_distance = interactable_distance * 0.5
            combat_location = self.combat_target.location.get_point_in_between(combat_position_distance, vector=self.location)

            # If already going to the correct spot, don't do anything.
            if len(self.movement_manager.pending_waypoints) > 0 and self.movement_manager.pending_waypoints[0].location == combat_location:
                return

            self.movement_manager.send_move_to([combat_location], self.running_speed, SplineFlags.SPLINEFLAG_RUNMODE)

    # override
    def update(self):
        now = time.time()
        if now > self.last_tick > 0:
            elapsed = now - self.last_tick

            if self.is_alive:
                # Spell/aura updates
                self.spell_manager.update(now, elapsed)
                self.aura_manager.update(now)
                # Movement Updates
                self.movement_manager.update_pending_waypoints(elapsed)
                # Random Movement
                self._perform_random_movement(now)
                # Combat movement
                self._perform_combat_movement(now)
                # Attack update
                if self.combat_target and self.is_within_interactable_distance(self.combat_target):
                    self.attack_update(elapsed)
            # Dead
            else:
                self.respawn_timer += elapsed
                if self.respawn_timer >= self.respawn_time:
                    self.respawn()
                # Destroy body when creature is about to respawn
                elif self.is_spawned and self.respawn_timer >= self.respawn_time * 0.8:
                    self.is_spawned = False
                    MapManager.send_surrounding(self.get_destroy_packet(), self, include_self=False)

            # Check "dirtiness" to determine if this creature object should be updated yet or not.
            if self.dirty:
                MapManager.send_surrounding(self.generate_proper_update_packet(create=False), self, include_self=False)
                MapManager.update_object(self)
                if self.reset_fields_older_than(now):
                    self.set_dirty(is_dirty=False)

        self.last_tick = now

    # override
    def respawn(self):
        super().respawn()

        self.set_health(self.max_health)
        self.set_mana(self.max_power_1)

        self.loot_manager.clear()
        self.set_lootable(False)

        if self.killed_by and self.killed_by.group_manager:
            self.killed_by.group_manager.clear_looters_for_victim(self)
        self.killed_by = None

        self.is_spawned = True
        self.respawn_timer = 0
        self.respawn_time = randint(self.creature_instance.spawntimesecsmin, self.creature_instance.spawntimesecsmax)

        MapManager.send_surrounding(self.generate_proper_update_packet(create=True), self, include_self=False)

    # override
    def die(self, killer=None):
        super().die(killer)
        self.loot_manager.generate_loot(killer)

        if killer and killer.get_type() == ObjectTypes.TYPE_PLAYER:
            self.reward_kill_xp(killer)
            self.killed_by = killer
            # If the player/group requires the kill, reward it to them.
            if self.killed_by.group_manager:
                self.killed_by.group_manager.reward_group_creature_or_go(self.killed_by, self)
            elif self.killed_by.quest_manager.reward_creature_or_go(self):
                self.killed_by.send_update_self()
            # If the player is in a group, set the group as allowed looters if needed.
            if self.killed_by.group_manager and self.loot_manager.has_loot():
                self.killed_by.group_manager.set_allowed_looters(self)

        if self.loot_manager.has_loot():
            self.set_lootable(True)

        self.set_dirty()
        return True

    def reward_kill_xp(self, player):
        # Critters don't award XP
        if self.creature_type == CreatureTypes.AMBIENT:
            return

        is_elite = 0 < self.creature_template.rank < 4

        if player.group_manager:
            player.group_manager.reward_group_xp(player, self, is_elite)
        else:
            player.give_xp([Formulas.CreatureFormulas.xp_reward(self.level, player.level, is_elite)], self)

    def calculate_min_max_damage(self, attack_type: AttackTypes, attack_school: SpellSchools, target_creature_type: CreatureTypes):
        min_damage, max_damage = unpack('<2H', pack('<I', self.damage))
        return int(min_damage), int(max_damage)

    def set_lootable(self, flag=True):
        if flag:
            self.dynamic_flags |= UnitDynamicTypes.UNIT_DYNAMIC_LOOTABLE
        else:
            self.dynamic_flags &= ~UnitDynamicTypes.UNIT_DYNAMIC_LOOTABLE
        self.set_uint32(UnitFields.UNIT_DYNAMIC_FLAGS, self.dynamic_flags)

    # override
    def has_offhand_weapon(self):
        return self.wearing_offhand_weapon

    # override
    def set_weapon_mode(self, weapon_mode):
        super().set_weapon_mode(weapon_mode)
        self.bytes_2 = unpack('<I', pack('<4B', self.sheath_state, 0, 0, 0))[0]

        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_2, self.bytes_2)

    # override
    def set_stand_state(self, stand_state):
        super().set_stand_state(stand_state)
        self.bytes_1 = unpack('<I', pack('<4B', self.stand_state, self.npc_flags, self.shapeshift_form, 0))[0]
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_1, self.bytes_1)

    # override
    def set_shapeshift_form(self, shapeshift_form):
        super().set_shapeshift_form(shapeshift_form)
        self.bytes_1 = unpack('<I', pack('<4B', self.stand_state, self.npc_flags, self.shapeshift_form, 0))[0]
        self.set_uint32(UnitFields.UNIT_FIELD_BYTES_1, self.bytes_1)

    # override
    def get_type(self):
        return ObjectTypes.TYPE_UNIT

    # override
    def get_type_id(self):
        return ObjectTypeIds.ID_UNIT
