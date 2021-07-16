from enum import IntEnum
from struct import pack, unpack
from typing import NamedTuple

from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from database.realm.RealmDatabaseManager import RealmDatabaseManager
from database.realm.RealmModels import CharacterSkill
from game.world.managers.objects.player.StatManager import UnitStats
from network.packet.PacketWriter import PacketWriter
from utils.constants.MiscCodes import SkillCategories, Languages
from utils.constants.OpCodes import OpCode
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


class ProficiencyAcquireMethod(IntEnum):
    ON_TRAINER_LEARN = 0
    ON_CHAR_CREATE = 1


class Proficiency(NamedTuple):
    min_level: int
    acquire_method: int
    item_class: int
    item_subclass_mask: int


class SkillManager(object):
    def __init__(self, player_mgr):
        self.player_mgr = player_mgr
        self.skills = {}
        self.proficiencies = {}

    def load_skills(self):
        for skill in RealmDatabaseManager.character_get_skills(self.player_mgr.guid):
            self.skills[skill.skill] = skill
        self.update_skills_max_value()
        self.build_update()

    def load_proficiencies(self):
        base_info = DbcDatabaseManager.CharBaseInfoHolder.char_base_info_get(self.player_mgr.player.race, self.player_mgr.player.class_)
        if not base_info:
            return

        chr_proficiency = base_info.proficiency
        for x in range(1, 17):
            acquire_method = eval(f'chr_proficiency.Proficiency_AcquireMethod_{x}')
            if acquire_method == -1:
                break

            # TODO: Only loading proficiencies acquired on char creation for now
            if acquire_method != ProficiencyAcquireMethod.ON_CHAR_CREATE:
                continue

            item_class = eval(f'chr_proficiency.Proficiency_ItemClass_{x}')
            self.proficiencies[item_class] = Proficiency(
                    eval(f'chr_proficiency.Proficiency_MinLevel_{x}'),
                    acquire_method,
                    item_class,
                    eval(f'chr_proficiency.Proficiency_ItemSubClassMask_{x}'),
            )

    def send_set_proficiency(self, proficiency):
        packet = PacketWriter.get_packet(OpCode.SMSG_SET_PROFICIENCY, pack('<bI', proficiency.item_class, proficiency.item_subclass_mask))
        self.player_mgr.session.enqueue_packet(packet)

    def init_proficiencies(self):
        for proficiency in self.proficiencies.values():
            self.send_set_proficiency(proficiency)

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

    def can_use_equipment(self, item_class, item_subclass):
        if item_class not in self.proficiencies:
            return False
        return self.proficiencies[item_class].item_subclass_mask & (1 << item_subclass) != 0

    def get_total_skill_value(self, skill_id):
        if skill_id not in self.skills:
            return None
        skill = self.skills[skill_id]
        bonus_skill = self.player_mgr.stat_manager.get_total_stat(UnitStats.SKILL, misc_value=skill_id)
        return skill.value + bonus_skill

    def get_skill_value_for_spell_id(self, spell_id):
        skill_line_ability = DbcDatabaseManager.SkillLineAbilityHolder.skill_line_ability_get_by_spell(spell_id)
        if not skill_line_ability:
            return None

        skill_id = skill_line_ability.SkillLine
        if skill_id not in self.skills:
            return None
        return self.get_total_skill_value(skill_id)

    @staticmethod
    def get_all_languages():
        return LANG_DESCRIPTION.items()

    @staticmethod
    def get_skill_by_language(language_id):
        if language_id in LANG_DESCRIPTION:
            return LANG_DESCRIPTION[language_id].skill_id
        return -1

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
            total_value = self.get_total_skill_value(skill_id)
            self.player_mgr.set_uint32(PlayerFields.PLAYER_SKILL_INFO_1_1 + (count * 3),
                                       unpack('<I', pack('<2H', skill_id, skill.value))[0])
            self.player_mgr.set_uint32(PlayerFields.PLAYER_SKILL_INFO_1_1 + (count * 3) + 1,
                                       unpack('<I', pack('<2H', skill.max, total_value - skill.value))[0])  # max_rank, skill_mod
            self.player_mgr.set_uint32(PlayerFields.PLAYER_SKILL_INFO_1_1 + (count * 3) + 2,
                                       unpack('<I', pack('<2H', 0, 0))[0])  # skill_step, padding
            count += 1
