from enum import IntEnum
from struct import pack, unpack
from typing import NamedTuple

from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from database.realm.RealmDatabaseManager import RealmDatabaseManager
from database.realm.RealmModels import CharacterSkill
from database.world.WorldDatabaseManager import WorldDatabaseManager
from game.world.managers.objects.player.proficiencies.proficiency import Proficiency
from network.packet.PacketWriter import PacketWriter
from utils.constants.ItemCodes import ItemClasses, ItemSubClasses
from utils.constants.ObjectCodes import SkillCategories, Languages
from utils.constants.OpCodes import OpCode
from utils.constants.UnitCodes import Classes
from utils.constants.UpdateFields import PlayerFields


class SkillTypes(IntEnum):
    NONE = 0
    FROSTMAGIC = 0x6
    FIREMAGIC = 0x8
    COMBATMANEUVERS = 0x1A
    STREETFIGHTING = 0x26
    DECEPTION = 0x27
    POISONS = 0x28
    SWORDS = 0x2B
    AXES = 0x2C
    BOWS = 0x2D
    GUNS = 0x2E
    BEASTHANDLING = 0x32
    TRACKING = 0x33
    MACES = 0x36
    TWOHANDEDSWORDS = 0x37
    HOLYMAGIC = 0x38
    FEIGNDEATH = 0x4A
    SHADOWMAGIC = 0x4E
    DEFENSE = 0x5F
    NATUREMAGIC = 0x60
    LANGUAGE_COMMON = 0x62
    LANGUAGE_COMMON_TEMP = 0x63
    DWARVENRACIAL = 0x65
    LANGUAGE_ORCISH = 0x6D
    LANGUAGE_ORCISH_TEMP = 0x6E
    LANGUAGE_DWARVEN = 0x6F
    LANGUAGE_DWARVEN_TEMP = 0x70
    LANGUAGE_DARNASSIAN = 0x71
    LANGUAGE_DARNASSIAN_TEMP = 0x72
    LANGUAGE_TAURAHE = 0x73
    LANGUAGE_TAURAHE_TEMP = 0x74
    DUALWIELD = 0x76
    SUMMONING = 0x78
    TAURENRACIAL = 0x7C
    ORCRACIAL = 0x7D
    NIGHTELFRACIAL = 0x7E
    FIRSTAID = 0x81
    CONJURATION = 0x82
    SHAPESHIFTING = 0x86
    STAVES = 0x88
    THALASSIAN = 0x89
    DRACONIC = 0x8A
    DEMONTONGUE = 0x8B
    TITAN = 0x8C
    OLDTONGUE = 0x8D
    SURVIVAL = 0x8E
    HORSERIDING = 0x94
    WOLFRIDING = 0x95
    TIGERRIDING = 0x96
    NIGHTMARERIDING = 0x97
    RAMRIDING = 0x98
    SWIMMING = 0x9B
    TWOHANDEDMACES = 0xA0
    UNARMED = 0xA2
    COMBATSHOTS = 0xA3
    BLACKSMITHING = 0xA4
    LEATHERWORKING = 0xA5
    ALCHEMY = 0xAB
    TWOHANDEDAXES = 0xAC
    DAGGERS = 0xAD
    THROWN = 0xB0
    LOCKPICKING_TEMP = 0xB5
    HERBALISM = 0xB6
    GENERIC = 0xB7
    HOLYSTRIKES = 0xB8
    COOKING = 0xB9
    MINING = 0xBA
    PET_IMP = 0xBC
    PET_FELHUNTER = 0xBD
    TAILORING = 0xC5
    SEALS = 0xC6
    SPIRITCOMBAT = 0xC7
    ENGINEERING = 0xCA
    PET_SPIDER = 0xCB
    PET_VOIDWALKER = 0xCC
    PET_SUCCUBUS = 0xCD
    PET_INFERNAL = 0xCE
    PET_DOOMGUARD = 0xCF
    PET_WOLF = 0xD0
    PET_CAT = 0xD1
    PET_BEAR = 0xD2
    PET_BOAR = 0xD3
    PET_CROCILISK = 0xD4
    PET_CARRIONBIRD = 0xD5
    PET_CRAB = 0xD6
    PET_GORILLA = 0xD7
    PET_HORSE = 0xD8
    PET_RAPTOR = 0xD9
    PET_TALLSTRIDER = 0xDA
    RACIAL_UNDEAD = 0xDC
    WEAPONTALENTS = 0xDE
    CROSSBOWS = 0xE2
    SPEARS = 0xE3
    WANDS = 0xE4
    POLEARMS = 0xE5
    ATTRIBUTEENHANCEMENTS = 0xE6
    SLAYERTALENTS = 0xE7
    MAGICTALENTS = 0xE9
    DEFENSIVETALENTS = 0xEA
    PET_SCORPION = 0xEC
    ARCANEMAGIC = 0xED
    PICKPOCKETS = 0xEE
    STEALTH = 0xEF
    DISARMTRAPS = 0xF1
    LOCKPICKING = 0xF2
    STANCES = 0xF3
    SHOUTS = 0xF4
    ADVANCEDCOMBAT = 0xF5
    UNDEADMASTERY = 0xF6
    SNEAKING = 0xF7
    DISENGAGE = 0x111
    FORAGE = 0xF9
    PET_TURTLE = 0xFB
    RANGEDCOMBAT = 0xFC
    ASSASSINATION = 0xFD
    ACROBATICS = 0xFE
    DUELING = 0xFF
    SAVAGECOMBAT = 0x100
    SHIELDS = 0x101
    TAUNT = 0x102
    TOTEMS = 0x103
    MENDPET = 0x104
    BEASTTRAINING = 0x105
    EXPERTSHOTS = 0x106
    FIRESHOTS = 0x107
    FROSTSHOTS = 0x108
    PLATEMAIL = 0x125
    AURAS = 0x10B
    BLOCK = 0x10C
    JUSTICE = 0x10D
    PET_TALENTS = 0x10E
    MAGICUNLOCK = 0x10F
    GROWL = 0x110
    LANGUAGE_GNOMISH = 0x139
    LANGUAGE_GNOMISH_TEMP = 0x13A
    LANGUAGE_TROLL = 0x13B
    LANGUAGE_TROLL_TEMP = 0x13C
    ENCHANTING = 0x14D
    SOULCRAFT = 0x161
    DEMONMASTERY = 0x162
    CURSES = 0x163
    FISHING = 0x164


class LanguageDesc(NamedTuple):
    lang_id: int
    spell_id: int
    skill_id: int


LANG_DESCRIPTION = {
    Languages.LANG_UNIVERSAL: LanguageDesc(Languages.LANG_UNIVERSAL, 0, SkillTypes.NONE),
    Languages.LANG_ORCISH: LanguageDesc(Languages.LANG_ORCISH, 669, SkillTypes.LANGUAGE_ORCISH.value),
    Languages.LANG_DARNASSIAN: LanguageDesc(Languages.LANG_DARNASSIAN, 671, SkillTypes.LANGUAGE_DARNASSIAN.value),
    Languages.LANG_TAURAHE: LanguageDesc(Languages.LANG_TAURAHE, 670, SkillTypes.LANGUAGE_TAURAHE.value),
    Languages.LANG_DWARVISH: LanguageDesc(Languages.LANG_DWARVISH, 672, SkillTypes.LANGUAGE_DWARVEN.value),
    Languages.LANG_COMMON: LanguageDesc(Languages.LANG_COMMON, 668, SkillTypes.LANGUAGE_COMMON.value),
    Languages.LANG_DEMONIC: LanguageDesc(Languages.LANG_DEMONIC, 815, SkillTypes.DEMONTONGUE.value),
    Languages.LANG_TITAN: LanguageDesc(Languages.LANG_TITAN, 816, SkillTypes.TITAN.value),
    Languages.LANG_THALASSIAN: LanguageDesc(Languages.LANG_THALASSIAN, 813, SkillTypes.THALASSIAN.value),
    Languages.LANG_DRACONIC: LanguageDesc(Languages.LANG_DRACONIC, 814, SkillTypes.DRACONIC.value),
    Languages.LANG_KALIMAG: LanguageDesc(Languages.LANG_KALIMAG, 817, SkillTypes.OLDTONGUE.value),
    Languages.LANG_GNOMISH: LanguageDesc(Languages.LANG_GNOMISH, 7340, SkillTypes.LANGUAGE_GNOMISH.value),
    Languages.LANG_TROLL: LanguageDesc(Languages.LANG_TROLL, 7341, SkillTypes.LANGUAGE_TROLL.value)
}


class SpellSkillDesc(NamedTuple):
    spell_id: int
    skill_id: int


EQUIPMENT_DESCRIPTION = {
    ItemClasses.ITEM_CLASS_WEAPON: {
        ItemSubClasses.ITEM_SUBCLASS_AXE: SpellSkillDesc(196, SkillTypes.AXES.value),
        ItemSubClasses.ITEM_SUBCLASS_TWOHAND_AXE: SpellSkillDesc(197, SkillTypes.TWOHANDEDAXES.value),
        ItemSubClasses.ITEM_SUBCLASS_BOW: SpellSkillDesc(264, SkillTypes.BOWS.value),
        ItemSubClasses.ITEM_SUBCLASS_GUN: SpellSkillDesc(266, SkillTypes.GUNS.value),
        ItemSubClasses.ITEM_SUBCLASS_MACE: SpellSkillDesc(198, SkillTypes.MACES.value),
        ItemSubClasses.ITEM_SUBCLASS_TWOHAND_MACE: SpellSkillDesc(199, SkillTypes.TWOHANDEDMACES.value),
        ItemSubClasses.ITEM_SUBCLASS_POLEARM: SpellSkillDesc(3386, SkillTypes.POLEARMS.value),
        ItemSubClasses.ITEM_SUBCLASS_SWORD: SpellSkillDesc(201, SkillTypes.SWORDS.value),
        ItemSubClasses.ITEM_SUBCLASS_TWOHAND_SWORD: SpellSkillDesc(202, SkillTypes.TWOHANDEDSWORDS.value),
        ItemSubClasses.ITEM_SUBCLASS_STAFF: SpellSkillDesc(227, SkillTypes.STAVES.value),
        ItemSubClasses.ITEM_SUBCLASS_DAGGER: SpellSkillDesc(1180, SkillTypes.DAGGERS.value),
        ItemSubClasses.ITEM_SUBCLASS_THROWN: SpellSkillDesc(2567, SkillTypes.THROWN.value),
        ItemSubClasses.ITEM_SUBCLASS_CROSSBOW: SpellSkillDesc(5011, SkillTypes.CROSSBOWS.value),
        ItemSubClasses.ITEM_SUBCLASS_WAND: SpellSkillDesc(5009, SkillTypes.WANDS.value),
        ItemSubClasses.ITEM_SUBCLASS_FIST_WEAPON: SpellSkillDesc(0, SkillTypes.UNARMED.value),
        ItemSubClasses.ITEM_SUBCLASS_FISHING_POLE: SpellSkillDesc(0, SkillTypes.NONE)
    },
    ItemClasses.ITEM_CLASS_ARMOR: {
        ItemSubClasses.ITEM_SUBCLASS_PLATE: SpellSkillDesc(750, SkillTypes.PLATEMAIL.value),
        ItemSubClasses.ITEM_SUBCLASS_CLOTH: SpellSkillDesc(0, -1),
        ItemSubClasses.ITEM_SUBCLASS_LEATHER: SpellSkillDesc(0, -1),
        ItemSubClasses.ITEM_SUBCLASS_MAIL: SpellSkillDesc(0, -1),
        ItemSubClasses.ITEM_SUBCLASS_MISC: SpellSkillDesc(0, SkillTypes.NONE),
        ItemSubClasses.ITEM_SUBCLASS_BUCKLER: SpellSkillDesc(107, SkillTypes.BLOCK),
        ItemSubClasses.ITEM_SUBCLASS_SHIELD: SpellSkillDesc(107, SkillTypes.BLOCK)
    }
}


class SkillManager(object):
    def __init__(self, player_mgr):
        self.player_mgr = player_mgr
        self.skills = {}
        self.proficiencies = []

    def load_skills(self):
        for skill in RealmDatabaseManager.character_get_skills(self.player_mgr.guid):
            self.skills[skill.skill] = skill
        self.build_update()

    def load_proficiencies(self):
        proficiency = DbcDatabaseManager.char_get_proficiency(self.player_mgr.player.race, self.player_mgr.player.class_)
        self.proficiencies = Proficiency.build_from_chr_proficiency(proficiency)

    def get_proficiencies_packets(self):
        packets = []
        for proficiency in self.proficiencies:
            # TODO: Should check skill rank against proficiency.min_level, not sure how to map itemsubclass to the skill
            if proficiency.acquire_method == 0:  # and player skill rank > proficiency.min_level
                continue
            if proficiency.acquire_method == 1 and self.player_mgr.level < proficiency.min_level:
                continue
            if proficiency.acquire_method < 0:  # Not sure what this means '-1'.
                continue
            data = pack('<bI', proficiency.item_class, proficiency.item_subclass_mask)
            packets.append(PacketWriter.get_packet(OpCode.SMSG_SET_PROFICIENCY, data))
        return packets

    def add_skill(self, skill_id):
        # Skill already learnt
        if skill_id in self.skills:
            return

        skill = DbcDatabaseManager.SkillHolder.skill_get_by_id(skill_id)
        if not skill:
            return

        start_rank_value = 1
        if skill.CategoryID == SkillCategories.MAX_SKILL:
            start_rank_value = skill.MaxRank

        skill_to_set = CharacterSkill()
        skill_to_set.guid = self.player_mgr.guid
        skill_to_set.skill = skill_id
        skill_to_set.value = start_rank_value
        skill_to_set.max = skill.MaxRank

        RealmDatabaseManager.character_add_skill(skill_to_set)

        self.skills[skill_id] = skill_to_set

    def set_skill(self, skill_id, current_value, max_value=-1):
        if skill_id not in self.skills:
            return

        skill = self.skills[skill_id]
        skill.value = current_value
        if max_value > 0:
            skill.max = max_value

        RealmDatabaseManager.character_update_skill(skill)

    def update_skills_max_value(self):
        for skill_id, skill in self.skills.items():
            # For cases like non-default languages, they should remain at max 1 unless forcefully set
            if skill.max == 1:
                new_max = 1
            else:
                new_max = SkillManager.get_max_rank(self.player_mgr.level, skill_id)

            self.set_skill(skill_id, skill.value, new_max)

    def _class_can_use_armor_type(self, armor_type):
        player_class = self.player_mgr.player.class_
        if armor_type == ItemSubClasses.ITEM_SUBCLASS_CLOTH:
            return True

        if armor_type == ItemSubClasses.ITEM_SUBCLASS_LEATHER:
            return player_class != Classes.CLASS_MAGE and player_class != Classes.CLASS_PRIEST and player_class != Classes.CLASS_WARLOCK

        if armor_type == ItemSubClasses.ITEM_SUBCLASS_MAIL:
            if self.player_mgr.level >= 40 and (player_class == Classes.CLASS_HUNTER or player_class == Classes.CLASS_SHAMAN):
                return True

            if player_class == Classes.CLASS_WARRIOR or player_class == Classes.CLASS_PALADIN:
                return True

            return False

        if armor_type == ItemSubClasses.ITEM_SUBCLASS_PLATE:
            return SkillTypes.PLATEMAIL in self.skills

        return False

    # TODO: Use ChrProficiency.dbc
    def can_use_equipment(self, item_class, item_subclass):
        # No Cloth, Leather or Mail spells / skills exist in 0.5.3, but according to Ziggurat armor restrictions existed.
        if item_class == ItemClasses.ITEM_CLASS_ARMOR and \
                (item_subclass == ItemSubClasses.ITEM_SUBCLASS_CLOTH or
                 item_subclass == ItemSubClasses.ITEM_SUBCLASS_LEATHER or item_subclass == ItemSubClasses.ITEM_SUBCLASS_MAIL):
            return self._class_can_use_armor_type(item_subclass)
        # Special case, don't let Hunters and Rogues use shields even if they have the Block skill (just bucklers).
        elif item_class == ItemClasses.ITEM_CLASS_ARMOR and item_subclass == ItemSubClasses.ITEM_SUBCLASS_SHIELD:
            if self.player_mgr.player.class_ == Classes.CLASS_HUNTER or self.player_mgr.player.class_ == Classes.CLASS_ROGUE:
                return False

        skill = SkillManager.get_skill_by_item_class(item_class, item_subclass)
        if skill == -1:
            return False

        # No skill requirement
        if skill == SkillTypes.NONE:
            return True

        return skill in self.skills

    def get_skill_for_spell_id(self, spell_id):
        skill_line_ability = DbcDatabaseManager.SkillLineAbilityHolder.skill_line_ability_get_by_spell(spell_id)
        if not skill_line_ability:
            return None

        skill_id = skill_line_ability.SkillLine
        if skill_id not in self.skills:
            return None
        return self.skills[skill_id]

    @staticmethod
    def get_all_languages():
        return LANG_DESCRIPTION.items()

    @staticmethod
    def get_skill_by_language(language_id):
        if language_id in LANG_DESCRIPTION:
            return LANG_DESCRIPTION[language_id].skill_id
        return -1

    @staticmethod
    def get_skill_by_item_class(item_class, item_subclass):
        if item_class in EQUIPMENT_DESCRIPTION:
            class_ = EQUIPMENT_DESCRIPTION[item_class]
            if item_subclass in class_:
                return class_[item_subclass].skill_id
            return -1
        return 0

    @staticmethod
    def get_max_rank(player_level, skill_id):
        skill = DbcDatabaseManager.SkillHolder.skill_get_by_id(skill_id)
        if not skill:
            return 0

        # Weapon, Defense, Spell
        if skill.SkillType == 0:
            return player_level * 5
        # Language, Riding, Secondary profs
        elif skill.SkillType == 4:
            # Language, Riding
            if skill.CategoryID == SkillCategories.MAX_SKILL:
                return skill.MaxRank
            else:
                return (player_level * 5) + 25

        return 0

    def can_dual_wield(self):
        return SkillTypes.DUALWIELD in self.skills and self.player_mgr.level >= 10

    def build_update(self):
        count = 0
        for skill_id, skill in self.skills.items():
            self.player_mgr.set_uint32(PlayerFields.PLAYER_SKILL_INFO_1_1 + (count * 3),
                                       unpack('<I', pack('<2H', skill_id, skill.value))[0])
            self.player_mgr.set_uint32(PlayerFields.PLAYER_SKILL_INFO_1_1 + (count * 3) + 1,
                                       unpack('<I', pack('<2H', skill.max, 0))[0])  # max_rank, skill_mod
            self.player_mgr.set_uint32(PlayerFields.PLAYER_SKILL_INFO_1_1 + (count * 3) + 2,
                                       unpack('<I', pack('<2H', 0, 0))[0])  # skill_step, padding
            count += 1
