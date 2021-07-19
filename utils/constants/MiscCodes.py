from enum import IntEnum


class ObjectTypes(IntEnum):
    TYPE_OBJECT = 1
    TYPE_ITEM = 2
    TYPE_CONTAINER = 4
    TYPE_UNIT = 8
    TYPE_PLAYER = 16
    TYPE_GAMEOBJECT = 32
    TYPE_DYNAMICOBJECT = 64
    TYPE_CORPSE = 128
    TYPE_AIGROUP = 256
    TYPE_AREATRIGGER = 512
    HIER_TYPE_OBJECT = 1
    HIER_TYPE_ITEM = 3
    HIER_TYPE_CONTAINER = 7
    HIER_TYPE_UNIT = 9
    HIER_TYPE_PLAYER = 25
    HIER_TYPE_GAMEOBJECT = 33
    HIER_TYPE_DYNAMICOBJECT = 65
    HIER_TYPE_CORPSE = 129
    HIER_TYPE_AIGROUP = 257
    HIER_TYPE_AREATRIGGER = 513


class ObjectTypeIds(IntEnum):
    ID_OBJECT = 0
    ID_ITEM = 1
    ID_CONTAINER = 2
    ID_UNIT = 3
    ID_PLAYER = 4
    ID_GAMEOBJECT = 5
    ID_DYNAMICOBJECT = 6
    ID_CORPSE = 7
    NUM_CLIENT_OBJECT_TYPES = 8
    ID_AIGROUP = 8
    ID_AREATRIGGER = 9
    NUM_OBJECT_TYPES = 10


class UpdateTypes(IntEnum):
    PARTIAL = 0
    MOVEMENT = 1
    CREATE_OBJECT = 2
    FAR_OBJECTS = 3
    NEAR_OBJECTS = 4


# Some might be unused on Alpha
class HighGuid(IntEnum):
    HIGHGUID_PLAYER = 0x0000 << 48
    HIGHGUID_ITEM = 0x4000 << 48
    HIGHGUID_CONTAINER = 0x4000 << 48
    HIGHGUID_GAMEOBJECT = 0xF110 << 48
    HIGHGUID_TRANSPORT = 0xF120 << 48
    HIGHGUID_UNIT = 0xF130 << 48
    HIGHGUID_PET = 0xF140 << 48
    HIGHGUID_VEHICLE = 0xF150 << 48
    HIGHGUID_DYNAMICOBJECT = 0xF100 << 48
    HIGHGUID_CORPSE = 0xF101 << 48
    HIGHGUID_MO_TRANSPORT = 0x1FC0 << 48
    HIGHGUID_GROUP = 0x1F50 << 48
    HIGHGUID_GUILD = 0x1FF6 << 48


class Factions(IntEnum):
    ALLIANCE = 4
    HORDE = 6


class NpcFlags(IntEnum):
    NPC_FLAG_NONE = 0x0
    NPC_FLAG_GOSSIP = 0x1
    NPC_FLAG_QUESTGIVER = 0x2
    NPC_FLAG_VENDOR = 0x3
    NPC_FLAG_FLIGHTMASTER = 0x4
    NPC_FLAG_TRAINER = 0x8
    NPC_FLAG_BINDER = 0x10  # Binders were used to bind players to a meeting stone. You appeared there on death respawn.
    NPC_FLAG_BANKER = 0x20
    NPC_FLAG_TABARDDESIGNER = 0x40
    NPC_FLAG_PETITIONER = 0x80

    NPC_FLAG_SPIRITHEALER = 0x00000020
    NPC_FLAG_SPIRITGUIDE = 0x00000040
    NPC_FLAG_INNKEEPER = 0x00000080


# COMBAT INFORMATION
class HitInfo(IntEnum):
    DAMAGE = 0x00000000
    MISS = 0x00000001
    SUCCESS = 0x00000002
    UNIT_DEAD = 0x00000004  # unit died because of this attack
    CRITICAL_HIT = 0x00000008
    STUN = 0x00000010
    PARRY = 0x00000020
    DODGE = 0x00000040
    BLOCK = 0x00000080
    COOLDOWN = 0x00000100  # ?
    OFFHAND = 0x00000200
    CRUSHING = 0x0000400
    UNKNOWN1 = 0x0000800
    DEFERRED_LOGGING = 0x0001000
    ADVANCED_LOGGING = 0x0002000
    PREVENT_LOGGING = 0x0004000  # receives no damage and voids attack?
    OFFHAND_FAILED = 0x0008000  # uncertain
    ABSORBED = 0x0010000
    HIDE_MISSED_TEXT = 0x0020000  # ? CGUnit_C::ShowWorldText
    DEFLECT = 0x0040000  # ? CGUnit_C::ShowWorldText

    """
    HandleGeneralCombatLogging (ATTACKROUNDINFO) - NOTE: 0x2000 and 0x4000 both supress player logs
    HandleGeneralCombatLoggingMissed = 0x1 : any misses
    HandleGeneralCombatOrSpellHitLogging = VS_WOUND, 0x8 for crits : standard successful combat/combat spell log
    HandleGeneralCombatEvadeLogging = uses VictimState : use for everything else
    """


class AttackSwingError(IntEnum):
    NONE = 0x0000
    # NOTE: it appears you can't melee attack whilst moving - Blizz was initially very anti-kiting so may be the reason
    # the client prevents attack animations whilst moving and there's always a delay in Blizzcon 2003 gameplay footage.
    # This is just a guess though.
    MOVING = 0x0001
    NOTINRANGE = 0x0138
    BADFACING = 0x0139
    NOTSTANDING = 0x013A
    DEADTARGET = 0x013B
    CANTATTACK = 0x013C


class VictimStates(IntEnum):
    VS_NONE = 0  # set when attacker misses
    VS_WOUND = 1  # victim got clear/blocked hit
    VS_DODGE = 2
    VS_PARRY = 3
    VS_INTERRUPT = 4
    VS_BLOCK = 5  # unused? not set when blocked even on full block
    VS_EVADE = 6
    VS_IMMUNE = 7
    VS_DEFLECT = 8


class ProcFlags(IntEnum):
    NONE = 0x0
    DEAL_COMBAT_DMG = 0x1
    TAKE_COMBAT_DMG = 0x2
    KILL = 0x4
    HEARTBEAT = 0x8
    DODGE = 0x10
    PARRY = 0x20
    BLOCK = 0x40
    SWING = 0x80
    SPELL_CAST = 0x100  # Only used by zzOLDMind Bomb
    SPELL_CAST_SCHOOL = 0x200  # Not yet implemented by the client
    SPELL_HIT = 0x400
    SPELL_HIT_SCHOOL = 0x800  # Not yet implemented by the client


class ProcFlagsExLegacy(IntEnum):
    NONE = 0x0000000  # If none can tigger on Hit/Crit only (passive spells MUST defined by SpellFamily flag)
    NORMAL_HIT = 0x0000001  # If set only from normal hit (only damage spells)
    CRITICAL_HIT = 0x0000002
    MISS = 0x0000004
    RESIST = 0x0000008
    DODGE = 0x0000010
    PARRY = 0x0000020
    BLOCK = 0x0000040
    EVADE = 0x0000080
    IMMUNE = 0x0000100
    DEFLECT = 0x0000200
    ABSORB = 0x0000400
    REFLECT = 0x0000800
    INTERRUPT = 0x0001000  # Melee hit result can be Interrupt (not used)
    FULL_BLOCK = 0x0002000  # block al attack damage
    RESERVED2 = 0x0004000
    NOT_ACTIVE_SPELL = 0x0008000  # Spell mustn't do damage/heal to proc
    EX_TRIGGER_ALWAYS = 0x0010000  # If set trigger always no matter of hit result
    EX_ONE_TIME_TRIGGER = 0x0020000  # If set trigger always but only one time (not implemented yet)
    ONLY_ACTIVE_SPELL = 0x0040000  # Spell has to do damage/heal to proc

    # Flags for internal use - do not use these in db!
    INTERNAL_CANT_PROC = 0x0800000
    INTERNAL_DOT = 0x1000000
    INTERNAL_HOT = 0x2000000
    INTERNAL_TRIGGERED = 0x4000000
    INTERNAL_REQ_FAMILY = 0x8000000


class AttackTypes(IntEnum):
    BASE_ATTACK = 0
    OFFHAND_ATTACK = 1
    RANGED_ATTACK = 2


class TradeSkillCategories(IntEnum):
    TRADESKILL_OPTIMAL = 0x0
    TRADESKILL_MEDIUM = 0x1
    TRADESKILL_EASY = 0x2
    TRADESKILL_TRIVIAL = 0x3
    NUM_TRADESKILL_CATEGORIES = 0x4


class TradeStatus(IntEnum):
    TRADE_STATUS_PLAYER_BUSY = 0x0
    TRADE_STATUS_PROPOSED = 0x1
    TRADE_STATUS_INITIATED = 0x2
    TRADE_STATUS_CANCELLED = 0x3
    TRADE_STATUS_ACCEPTED = 0x4
    TRADE_STATUS_ALREADY_TRADING = 0x5
    TRADE_STATUS_PLAYER_NOT_FOUND = 0x6
    TRADE_STATUS_STATE_CHANGED = 0x7
    TRADE_STATUS_COMPLETE = 0x8
    TRADE_STATUS_UNACCEPTED = 0x9
    TRADE_STATUS_TOO_FAR_AWAY = 0xA
    TRADE_STATUS_WRONG_FACTION = 0xB
    TRADE_STATUS_FAILED = 0xC
    TRADE_STATUS_DEAD = 0xD
    TRADE_STATUS_PETITION = 0xE
    TRADE_STATUS_PLAYER_IGNORED = 0xF


class CraftLevelCategories(IntEnum):
    CRAFT_NONE = 0x0
    CRAFT_OPTIMAL = 0x1
    CRAFT_MEDIUM = 0x2
    CRAFT_EASY = 0x3
    CRAFT_TRIVIAL = 0x4
    NUM_CRAFT_CATEGORIES = 0x5


class TrainerServices(IntEnum):
    TRAINER_SERVICE_AVAILABLE = 0x0
    TRAINER_SERVICE_UNAVAILABLE = 0x1
    TRAINER_SERVICE_USED = 0x2
    TRAINER_SERVICE_NOT_SHOWN = 0x3
    TRAINER_SERVICE_NEVER = 0x4
    TRAINER_SERVICE_NO_PET = 0x5
    NUM_TRAINER_SERVICE_TYPES = 0x6


class TrainerTypes(IntEnum):
    TRAINER_TYPE_GENERAL = 0x0
    TRAINER_TYPE_TALENTS = 0x1
    TRAINER_TYPE_TRADESKILLS = 0x2
    TRAINER_TYPE_PET = 0x3


class TrainingFailReasons(IntEnum):
    TRAIN_FAIL_UNAVAILABLE = 0x0
    TRAIN_FAIL_NOT_ENOUGH_MONEY = 0x1
    TRAIN_FAIL_NOT_ENOUGH_SKILL = 0x2


class UnitDynamicTypes(IntEnum):
    UNIT_DYNAMIC_NONE = 0x0000
    UNIT_DYNAMIC_LOOTABLE = 0x0001
    UNIT_DYNAMIC_TRACK_UNIT = 0x0002
    UNIT_DYNAMIC_TAPPED = 0x0004  # Lua_UnitIsTapped - Indicates the target as grey for the client.
    UNIT_DYNAMIC_ROOTED = 0x0008
    UNIT_DYNAMIC_SPECIALINFO = 0x0010
    UNIT_DYNAMIC_DEAD = 0x0020


class LootTypes(IntEnum):
    LOOT_TYPE_NOTALLOWED = 0
    LOOT_TYPE_CORPSE = 1
    LOOT_TYPE_SKINNING = 2
    LOOT_TYPE_FISHING = 3


class ReputationFlag(IntEnum):
    HIDDEN = 0
    VISIBLE = 1
    ATWAR = 2


class QuestMethod(IntEnum):
    QUEST_AUTOCOMPLETE = 0
    QUEST_DISABLED = 1
    QUEST_ENABLED = 2


class QuestState(IntEnum):
    QUEST_GREETING = 0
    QUEST_OFFER = 1
    QUEST_ACCEPTED = 2
    QUEST_REWARD = 3
    QUEST_STATE_NUM_TYPES = 4


class QuestGiverStatus(IntEnum):
    QUEST_GIVER_NONE = 0
    QUEST_GIVER_TRIVIAL = 1
    QUEST_GIVER_FUTURE = 2
    QUEST_GIVER_REWARD = 3
    QUEST_GIVER_QUEST = 4
    QUEST_GIVER_NUMITEMS = 5


class QuestFlags(IntEnum):
    QUEST_FLAGS_NONE = 0x00000000
    QUEST_FLAGS_STAY_ALIVE = 0x00000001  # Not used currently
    QUEST_FLAGS_PARTY_ACCEPT = 0x00000002  # If player in party, all players that can accept this quest will receive confirmation box to accept quest CMSG_QUEST_CONFIRM_ACCEPT/SMSG_QUEST_CONFIRM_ACCEPT
    QUEST_FLAGS_EXPLORATION = 0x00000004  # Not used currently
    QUEST_FLAGS_SHARABLE = 0x00000008  # Can be shared: Player::CanShareQuest()
    QUEST_FLAGS_EPIC = 0x00000020  # Not used currently: Unsure of content
    QUEST_FLAGS_RAID = 0x00000040  # Not used currently
    QUEST_FLAGS_HIDDEN_REWARDS = 0x00000200  # Items and money rewarded only sent in SMSG_QUESTGIVER_OFFER_REWARD (not in SMSG_QUESTGIVER_QUEST_DETAILS or in client quest log(SMSG_QUEST_QUERY_RESPONSE))
    QUEST_FLAGS_AUTO_REWARDED = 0x00000400  # These quests are automatically rewarded on quest complete and they will never appear in quest log client side.


class QuestFailedReasons(IntEnum):
    QUEST_MISSING_REQ = 0  # Missing requirements
    QUEST_FAILED_LOW_LEVEL = 1  # You are not high enough level for that quest.
    QUEST_FAILED_WRONG_RACE = 6  # That quest is not available to your race.
    QUEST_ONLY_ONE_TIMED = 12  # You can only be on one timed quest at a time.
    QUEST_ALREADY_ON = 13  # You are already on that quest
    QUEST_FAILED_MISSING_ITEMS = 21  # You don't have the required items with you. Check storage.
    QUEST_FAILED_NOT_ENOUGH_MONEY = 23  # You don't have enough money for that quest.


class SkillCategories(IntEnum):
    MAX_SKILL = 1  # These are always max when added i.e. language/riding
    WEAPON_SKILL = 2
    CLASS_SKILL = 3
    SECONDARY_SKILL = 4


class GameObjectTypes(IntEnum):
    TYPE_DOOR = 0x0
    TYPE_BUTTON = 0x1
    TYPE_QUESTGIVER = 0x2
    TYPE_CHEST = 0x3
    TYPE_BINDER = 0x4
    TYPE_GENERIC = 0x5
    TYPE_TRAP = 0x6
    TYPE_CHAIR = 0x7
    TYPE_SPELL_FOCUS = 0x8
    TYPE_TEXT = 0x9
    TYPE_GOOBER = 0xA
    TYPE_TRANSPORT = 0xB
    TYPE_AREADAMAGE = 0xC
    TYPE_CAMERA = 0xD
    TYPE_MAP_OBJECT = 0xE
    TYPE_MO_TRANSPORT = 0xF
    TYPE_DUEL_ARBITER = 0x10
    TYPE_FISHINGNODE = 0x11
    TYPE_RITUAL = 0x12
    NUM_GAMEOBJECT_TYPE = 0x13


class GameObjectStates(IntEnum):
    GO_STATE_ACTIVE = 0  # show in world as used and not reset (closed door open)
    GO_STATE_READY = 1  # show in world as ready (closed door close)
    GO_STATE_ACTIVE_ALTERNATIVE = 2  # show in world as used in alt way and not reset (closed door open by cannon fire)


class Emotes(IntEnum):
    NONE = 0
    AGREE = 1
    AMAZE = 2
    ANGRY = 3
    APOLOGIZE = 4
    APPLAUD = 5
    BASHFUL = 6
    BECKON = 7
    BEG = 8
    BITE = 9
    BLEED = 10
    BLINK = 11
    BLUSH = 12
    BONK = 13
    BORED = 14
    BOUNCE = 15
    BRB = 16
    BOW = 17
    BURP = 18
    BYE = 19
    CACKLE = 20
    CHEER = 21
    CHICKEN = 22
    CHUCKLE = 23
    CLAP = 24
    CONFUSED = 25
    CONGRATULATE = 26
    COUGH = 27
    COWER = 28
    CRACK = 29
    CRINGE = 30
    CRY = 31
    CURIOUS = 32
    CURTSEY = 33
    DANCE = 34
    DRINK = 35
    DROOL = 36
    EAT = 37
    EYE = 38
    FART = 39
    FIDGET = 40
    FLEX = 41
    FROWN = 42
    GASP = 43
    GAZE = 44
    GIGGLE = 45
    GLARE = 46
    GLOAT = 47
    GREET = 48
    GRIN = 49
    GROAN = 50
    GROVEL = 51
    GUFFAW = 52
    HAIL = 53
    HAPPY = 54
    HELLO = 55
    HUG = 56
    HUNGRY = 57
    KISS = 58
    KNEEL = 59
    LAUGH = 60
    LAYDOWN = 61
    MASSAGE = 62
    MOAN = 63
    MOON = 64
    MOURN = 65
    NO = 66
    NOD = 67
    NOSEPICK = 68
    PANIC = 69
    PEER = 70
    PLEAD = 71
    POINT = 72
    POKE = 73
    PRAY = 74
    ROAR = 75
    ROFL = 76
    RUDE = 77
    SALUTE = 78
    SCRATCH = 79
    SEXY = 80
    SHAKE = 81
    SHOUT = 82
    SHRUG = 83
    SHY = 84
    SIGH = 85
    SIT = 86
    SLEEP = 87
    SNARL = 88
    SPIT = 89
    STARE = 90
    SURPRISED = 91
    SURRENDER = 92
    TALK = 93
    TALKEX = 94
    TALKQ = 95
    TAP = 96
    THANK = 97
    THREATEN = 98
    TIRED = 99
    VICTORY = 100
    WAVE = 101
    WELCOME = 102
    WHINE = 103
    WHISTLE = 104
    WORK = 105
    YAWN = 106
    BOGGLE = 107
    CALM = 108
    COLD = 109
    COMFORT = 110
    CUDDLE = 111
    DUCK = 112
    INSULT = 113
    INTRODUCE = 114
    JK = 115
    LICK = 116
    LISTEN = 117
    LOST = 118
    MOCK = 119
    PONDER = 120
    POUNCE = 121
    PRAISE = 122
    PURR = 123
    PUZZLE = 124
    RAISE = 125
    READY = 126
    SHIMMY = 127
    SHIVER = 128
    SHOO = 129
    SLAP = 130
    SMIRK = 131
    SNIFF = 132
    SNUB = 133
    SOOTHE = 134
    STINK = 135
    TAUNT = 136
    TEASE = 137
    THIRSTY = 138
    VETO = 139
    SNICKER = 140
    STAND = 141
    TICKLE = 142
    VIOLIN = 143
    SMILE = 163


class ChatMsgs(IntEnum):
    CHAT_MSG_SAY = 0x00
    CHAT_MSG_PARTY = 0x01
    CHAT_MSG_GUILD = 0x02
    CHAT_MSG_OFFICER = 0x03
    CHAT_MSG_YELL = 0x04
    CHAT_MSG_WHISPER = 0x05
    CHAT_MSG_WHISPER_INFORM = 0x06
    CHAT_MSG_EMOTE = 0x07
    CHAT_MSG_TEXT_EMOTE = 0x08
    CHAT_MSG_SYSTEM = 0x09
    CHAT_MSG_MONSTER_SAY = 0x0A
    CHAT_MSG_MONSTER_YELL = 0x0B
    CHAT_MSG_MONSTER_EMOTE = 0x0C
    CHAT_MSG_CHANNEL = 0x0D
    CHAT_MSG_CHANNEL_JOIN = 0x0E
    CHAT_MSG_CHANNEL_LEAVE = 0xF
    CHAT_MSG_CHANNEL_LIST = 0x10
    CHAT_MSG_CHANNEL_NOTICE = 0x11
    CHAT_MSG_CHANNEL_NOTICE_USER = 0x12
    CHAT_MSG_AFK = 0x13
    CHAT_MSG_DND = 0x14
    CHAT_MSG_IGNORED = 0x16
    CHAT_MSG_SKILL = 0x17
    CHAT_MSG_LOOT = 0x18


class ChatFlags(IntEnum):
    CHAT_TAG_NONE = 0
    CHAT_TAG_AFK = 1
    CHAT_TAG_DND = 2
    CHAT_TAG_GM = 3


class Languages(IntEnum):
    LANG_UNIVERSAL = 0
    LANG_ORCISH = 1
    LANG_DARNASSIAN = 2
    LANG_TAURAHE = 3
    LANG_DWARVISH = 6
    LANG_COMMON = 7
    LANG_DEMONIC = 8
    LANG_TITAN = 9
    LANG_THALASSIAN = 10
    LANG_DRACONIC = 11
    LANG_KALIMAG = 12
    LANG_GNOMISH = 13
    LANG_TROLL = 14


class MoveFlags(IntEnum):
    MOVEFLAG_NONE = 0x0
    MOVEFLAG_FORWARD = 0x1
    MOVEFLAG_BACKWARD = 0x2
    MOVEFLAG_STRAFE_LEFT = 0x4
    MOVEFLAG_STRAFE_RIGHT = 0x8
    MOVEFLAG_LEFT = 0x10
    MOVEFLAG_RIGHT = 0x20
    MOVEFLAG_PITCH_UP = 0x40
    MOVEFLAG_PITCH_DOWN = 0x80
    MOVEFLAG_WALK = 0x100
    MOVEFLAG_TIME_VALID = 0x200
    MOVEFLAG_IMMOBILIZED = 0x400
    MOVEFLAG_DONTCOLLIDE = 0x800
    MOVEFLAG_REDIRECTED = 0x1000
    MOVEFLAG_ROOTED = 0x2000
    MOVEFLAG_FALLING = 0x4000
    MOVEFLAG_FALLEN_FAR = 0x8000
    MOVEFLAG_PENDING_STOP = 0x10000
    MOVEFLAG_PENDING_UNSTRAFE = 0x20000
    MOVEFLAG_PENDING_FALL = 0x40000
    MOVEFLAG_PENDING_FORWARD = 0x80000
    MOVEFLAG_PENDING_BACKWARD = 0x100000
    MOVEFLAG_PENDING_STR_LEFT = 0x200000
    MOVEFLAG_PENDING_STR_RGHT = 0x400000
    MOVEFLAG_PEND_MOVE_MASK = 0x180000
    MOVEFLAG_PEND_STRAFE_MASK = 0x600000
    MOVEFLAG_PENDING_MASK = 0x7F0000
    MOVEFLAG_MOVED = 0x800000
    MOVEFLAG_SLIDING = 0x1000000
    MOVEFLAG_SWIMMING = 0x2000000
    MOVEFLAG_SPLINE_MOVER = 0x4000000
    MOVEFLAG_SPEED_DIRTY = 0x8000000
    MOVEFLAG_HALTED = 0x10000000
    MOVEFLAG_NUDGE = 0x20000000
    MOVEFLAG_FALL_MASK = 0x100C000
    MOVEFLAG_LOCAL = 0x500F400
    MOVEFLAG_MOVE_MASK = 0x3
    MOVEFLAG_TURN_MASK = 0x30
    MOVEFLAG_PITCH_MASK = 0xC0
    MOVEFLAG_STRAFE_MASK = 0xC
    MOVEFLAG_MOTION_MASK = 0xFF
    MOVEFLAG_STOPPED_MASK = 0x3100F


class BuyResults(IntEnum):
    BUY_ERR_CANT_FIND_ITEM = 0
    BUY_ERR_ITEM_ALREADY_SOLD = 1
    BUY_ERR_NOT_ENOUGH_MONEY = 2
    BUY_ERR_SELLER_DONT_LIKE_YOU = 4
    BUY_ERR_DISTANCE_TOO_FAR = 5
    BUY_ERR_ITEM_SOLD_OUT = 7
    BUY_ERR_CANT_CARRY_MORE = 8
    BUY_ERR_RANK_REQUIRE = 11
    BUY_ERR_REPUTATION_REQUIRE = 12


class SellResults(IntEnum):
    SELL_OK = 0
    SELL_ERR_CANT_FIND_ITEM = 1
    SELL_ERR_CANT_SELL_ITEM = 2  # merchant doesn't like that item
    SELL_ERR_CANT_FIND_VENDOR = 3  # merchant doesn't like you
    SELL_ERR_YOU_DONT_OWN_THAT_ITEM = 4  # you don't own that item
    SELL_ERR_UNK = 5  # nothing appears...
    SELL_ERR_ONLY_EMPTY_BAG = 6  # can only do with empty bags


class ItemBondingTypes(IntEnum):
    NO_BIND = 0
    BIND_WHEN_PICKED_UP = 1
    BIND_WHEN_EQUIPPED = 2
    BIND_WHEN_USE = 3
    BIND_QUEST_ITEM = 4


class LootMethods(IntEnum):
    LOOT_METHOD_FREEFORALL = 0x0
    LOOT_METHOD_ROUNDROBIN = 0x1
    LOOT_METHOD_MASTERLOOTER = 0x2
    LOOT_METHOD_MAX = 0x3


class ActionButtonTypes(IntEnum):
    ACTION_BUTTON_SPELL = 0x00
    ACTION_BUTTON_ITEM = 0xFF


class PlayerFlags(IntEnum):
    PLAYER_FLAGS_NONE = 0x0
    PLAYER_FLAGS_GROUP_LEADER = 0x1
    PLAYER_FLAGS_AFK = 0x4
    PLAYER_FLAGS_DND = 0x8
    PLAYER_FLAGS_GM = 0x10


class BankSlots(IntEnum):
    BANK_SLOT_ITEM_START = 39
    BANK_SLOT_ITEM_END = 63
    BANK_SLOT_BAG_START = 63
    BANK_SLOT_BAG_END = 69


class BankSlotErrors(IntEnum):
    BANKSLOT_ERROR_FAILED_TOO_MANY = 0
    BANKSLOT_ERROR_INSUFFICIENT_FUNDS = 1
    BANKSLOT_ERROR_NOTBANKER = 2
    BANKSLOT_ERROR_OK = 3


class ChannelMemberFlags(IntEnum):
    NONE = 0x0
    OWNER = 0x1
    MODERATOR = 0x2
    VOICE = 0x4


class ChannelNotifications(IntEnum):
    PLAYER_JOINED = 0x00
    PLAYER_LEFT = 0x01
    YOU_JOINED = 0x02
    YOU_LEFT = 0x03
    WRONG_PASSWORD = 0x04
    NOT_MEMBER = 0x05
    NOT_MODERATOR = 0x06
    PASSWORD_CHANGED = 0x07
    OWNER_CHANGED = 0x08
    PLAYER_NOT_FOUND = 0x09
    NOT_OWNER = 0x0A
    CHANNEL_OWNER = 0x0B
    MEMBER_FLAG_CHANGE = 0x0C
    MODERATOR = 0x0C
    ANNOUNCEMENTS_ON = 0x0D
    ANNOUNCEMENTS_OFF = 0x0E
    MODERATION_ON = 0x0F
    MODERATION_OFF = 0x10
    SELF_MUTED = 0x11
    KICKED = 0x12
    PLAYER_BANNED = 0x13
    BANNED = 0x14
    UNBANNED = 0x15
    PLAYER_NOT_BANNED = 0x16
    PLAYER_ALREADY_MEMBER = 0x17
    INVITE = 0x18
    INVITE_WRONG_FACTION = 0x19
    WRONG_FACTION = 0x1A


class GuildTypeCommand(IntEnum):
    GUILD_CREATE_S = 0x00
    GUILD_INVITE_S = 0x01
    GUILD_QUIT_S = 0x02
    GUILD_FOUNDER_S = 0x0C


class GuildCommandResults(IntEnum):
    GUILD_U_HAVE_INVITED = 0x00
    GUILD_INTERNAL = 0x01
    GUILD_ALREADY_IN_GUILD = 0x02
    ALREADY_IN_GUILD = 0x03
    INVITED_TO_GUILD = 0x04
    ALREADY_INVITED_TO_GUILD = 0x05
    GUILD_NAME_INVALID = 0x06
    GUILD_NAME_EXISTS = 0x07
    GUILD_LEADER_LEAVE = 0x08
    GUILD_PERMISSIONS = 0x08
    GUILD_PLAYER_NOT_IN_GUILD = 0x09
    GUILD_PLAYER_NOT_IN_GUILD_S = 0x0A
    GUILD_PLAYER_NOT_FOUND = 0x0B
    GUILD_NOT_ALLIED = 0x0C


class GuildEvents(IntEnum):
    GUILD_EVENT_PROMOTION = 0x0
    GUILD_EVENT_DEMOTION = 0x1
    GUILD_EVENT_MOTD = 0x2
    GUILD_EVENT_JOINED = 0x3
    GUILD_EVENT_LEFT = 0x4
    GUILD_EVENT_REMOVED = 0x5
    GUILD_EVENT_LEADER_IS = 0x6
    GUILD_EVENT_LEADER_CHANGED = 0x7
    GUILD_EVENT_DISBANDED = 0x8
    GUILD_EVENT_TABARDCHANGE = 0x9
    GUILD_EVENT_UNK1 = 0xA
    GUILD_EVENT_UNK2 = 0xB
    GUILD_EVENT_HASCOMEONLINE = 0xC
    GUILD_EVENT_HASGONEOFFLINE = 0xD


class GuildChatMessageTypes(IntEnum):
    G_MSGTYPE_ALL = 0
    G_MSGTYPE_ALLBUTONE = 1
    G_MSGTYPE_PUBLICCHAT = 2
    G_MSGTYPE_OFFICERCHAT = 3


class GuildRank(IntEnum):
    GUILDRANK_GUILD_MASTER = 0
    GUILDRANK_OFFICER = 1
    GUILDRANK_VETERAN = 2
    GUILDRANK_MEMBER = 3
    GUILDRANK_INITIATE = 4
    GUILDRANK_LOWEST = 9


class GuildEmblemResult(IntEnum):
    ERR_GUILDEMBLEM_SUCCESS = 0
    ERR_GUILDEMBLEM_INVALID_TABARD_COLORS = 1
    ERR_GUILDEMBLEM_NOGUILD = 2
    ERR_GUILDEMBLEM_NOTGUILDMASTER = 3
    ERR_GUILDEMBLEM_NOTENOUGHMONEY = 4
    ERR_GUILDEMBLEM_INVALIDVENDOR = 5


class FriendResults(IntEnum):
    FRIEND_DB_ERROR = 0x0
    FRIEND_LIST_FULL = 0x1
    FRIEND_ONLINE = 0x2
    FRIEND_OFFLINE = 0x3
    FRIEND_NOT_FOUND = 0x4
    FRIEND_REMOVED = 0x5
    FRIEND_ADDED_ONLINE = 0x6
    FRIEND_ADDED_OFFLINE = 0x7
    FRIEND_ALREADY = 0x8
    FRIEND_SELF = 0x9
    FRIEND_ENEMY = 0xA
    FRIEND_IGNORE_FULL = 0xB
    FRIEND_IGNORE_SELF = 0xC
    FRIEND_IGNORE_NOT_FOUND = 0xD
    FRIEND_IGNORE_ALREADY = 0xE
    FRIEND_IGNORE_ADDED = 0xF
    FRIEND_IGNORE_REMOVED = 0x10


class FriendStatus(IntEnum):
    FRIEND_STATUS_OFFLINE = 0
    FRIEND_STATUS_ONLINE = 1
    FRIEND_STATUS_AFK = 2
    FRIEND_STATUS_UNK3 = 3
    FRIEND_STATUS_DND = 4


class WhoPartyStatus(IntEnum):
    WHO_PARTY_STATUS_NOT_IN_PARTY = 0x0
    WHO_PARTY_STATUS_IN_PARTY = 0x1
    WHO_PARTY_STATUS_LFG = 0x2


class WhoSortTypes(IntEnum):
    WHO_SORT_ZONE = 0x0
    WHO_SORT_LEVEL = 0x1
    WHO_SORT_CLASS = 0x2
    WHO_SORT_GROUP = 0x3
    WHO_SORT_NAME = 0x4
    WHO_SORT_RACE = 0x5
    WHO_SORT_GUILD = 0x6


class ActivateTaxiReplies(IntEnum):
    ERR_TAXIOK = 0
    ERR_TAXIUNSPECIFIEDSERVERERROR = 1
    ERR_TAXINOSUCHPATH = 2
    ERR_TAXINOTENOUGHMONEY = 3
    ERR_TAXITOOFARAWAY = 4
    ERR_TAXINOVENDORNEARBY = 5
    ERR_TAXINOTVISITED = 6
    ERR_TAXIPLAYERBUSY = 7
    ERR_TAXIPLAYERALREADYMOUNTED = 8
    ERR_TAXIPLAYERSHAPESHIFTED = 9
    ERR_TAXIPLAYERMOVING = 10
    ERR_TAXISAMENODE = 11
    ERR_TAXINOTSTANDING = 12


class MirrorTimerTypes(IntEnum):
    FATIGUE = 0
    BREATH = 1
    FEIGNDEATH = 2
    ENVIRONMENTAL = 3


class MirrorTimerStatus(IntEnum):
    UNCHANGED = 0
    FULL_UPDATE = 1
    STATUS_UPDATE = 2


class LogoutResponseCodes(IntEnum):
    LOGOUT_CANCEL = 0
    LOGOUT_PROCEED = 1
