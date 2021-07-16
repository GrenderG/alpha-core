from enum import IntEnum


class CharList(IntEnum):
    CHAR_LIST_RETRIEVING = 0x24
    CHAR_LIST_RETRIEVED = 0x25
    CHAR_LIST_FAILED = 0x26


class CharCreate(IntEnum):
    CHAR_CREATE_IN_PROGRESS = 0x27
    CHAR_CREATE_SUCCESS = 0x28
    CHAR_CREATE_ERROR = 0x29
    CHAR_CREATE_FAILED = 0x2A
    CHAR_CREATE_NAME_IN_USE = 0x2B
    CHAR_CREATE_DISABLED = 0x2C


class CharDelete(IntEnum):
    CHAR_DELETE_IN_PROGRESS = 0x2D
    CHAR_DELETE_SUCCESS = 0x2E
    CHAR_DELETE_FAILED = 0x2F


class CharLogin(IntEnum):
    CHAR_LOGIN_IN_PROGRESS = 0x30
    CHAR_LOGIN_SUCCESS = 0x31
    CHAR_LOGIN_NO_WORLD = 0x32
    CHAR_LOGIN_DUPLICATE_CHARACTER = 0x33
    CHAR_LOGIN_NO_INSTANCES = 0x34
    CHAR_LOGIN_FAILED = 0x35
    CHAR_LOGIN_DISABLED = 0x36


class TutorialFlags(IntEnum):
    TUTORIAL_QUESTGIVERS = 0
    TUTORIAL_MOVEMENT = 1
    TUTORIAL_CAMERA = 2
    TUTORIAL_TARGETING = 3
    TUTORIAL_TARGETING_ENEMY = 4
    TUTORIAL_COMBAT = 5
    TUTORIAL_LOOTING = 6
    TUTORIAL_ITEMS = 7
    TUTORIAL_USABLE_ITEMS = 8
    TUTORIAL_BAGS = 9
    TUTORIAL_FOOD = 10
    TUTORIAL_DRINK = 11
    TUTORIAL_TALENTS = 12
    TUTORIAL_SKILLS = 13
    TUTORIAL_ABILITIES = 14
    TUTORIAL_REPUTATION = 15
    TUTORIAL_TELLS = 16
    TUTORIAL_GROUPING = 17
    NUM_TUTORIALS = 18
