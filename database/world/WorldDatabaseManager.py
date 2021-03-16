import os

from sqlalchemy import create_engine, func
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import sessionmaker, scoped_session
from difflib import SequenceMatcher

from database.world.WorldModels import *
from utils.ConfigManager import *
from utils.constants.ObjectCodes import HighGuid

world_db_engine = create_engine('mysql+pymysql://%s:%s@%s/%s?charset=utf8mb4' % (
                    os.getenv('MYSQL_USERNAME', config.Database.Connection.username),
                    os.getenv('MYSQL_PASSWORD', config.Database.Connection.password),
                    os.getenv('MYSQL_HOST', config.Database.Connection.host),
                    config.Database.DBNames.world_db
                ), pool_pre_ping=True)
SessionHolder = scoped_session(sessionmaker(bind=world_db_engine, autocommit=True, autoflush=True))


class WorldDatabaseManager(object):
    # Player stuff

    @staticmethod
    def player_create_info_get(race, class_):
        world_db_session = SessionHolder()
        res = world_db_session.query(Playercreateinfo).filter_by(race=race, _class=class_).first()
        world_db_session.close()
        return res

    @staticmethod
    def player_create_spell_get(race, class_):
        world_db_session = SessionHolder()
        res = world_db_session.query(PlayercreateinfoSpell).filter_by(race=race, _class=class_).all()
        world_db_session.close()
        return res

    @staticmethod
    def player_create_skill_get(race, class_):
        world_db_session = SessionHolder()
        res = world_db_session.query(PlayercreateinfoSkill).filter_by(race=race, _class=class_).all()
        world_db_session.close()
        return res

    @staticmethod
    def player_create_item_get(race, class_):
        world_db_session = SessionHolder()
        res = world_db_session.query(PlayercreateinfoItem).filter_by(race=race, _class=class_).all()
        world_db_session.close()
        return res

    @staticmethod
    def player_get_class_level_stats(class_, level):
        world_db_session = SessionHolder()
        res = world_db_session.query(PlayerClasslevelstats).filter_by(level=level, _class=class_).first()
        world_db_session.close()
        return res

    @staticmethod
    def player_get_level_stats(class_, level, race):
        world_db_session = SessionHolder()
        res = world_db_session.query(PlayerLevelstats).filter_by(level=level, _class=class_, race=race).first()
        world_db_session.close()
        return res

    # Area trigger stuff

    @staticmethod
    def area_trigger_teleport_get_by_id(trigger_id):
        world_db_session = SessionHolder()
        res = world_db_session.query(AreatriggerTeleport).filter_by(id=trigger_id).first()
        world_db_session.close()
        return res

    # Area Template stuff

    @staticmethod
    def area_get_by_id(area_id):
        world_db_session = SessionHolder()
        res = world_db_session.query(AreaTemplate).filter_by(entry=area_id).first()
        world_db_session.close()
        return res

    # Worldport stuff

    @staticmethod
    def worldport_get_by_name(name, return_all=False):
        world_db_session = SessionHolder()
        best_matching_location = None
        best_matching_ratio = 0
        locations = world_db_session.query(Worldports).filter(Worldports.name.like('%' + name + '%')).all()
        world_db_session.close()

        if return_all:
            return locations

        for location in locations:
            ratio = SequenceMatcher(None, location.name.lower(), name.lower()).ratio()
            if ratio > best_matching_ratio:
                best_matching_ratio = ratio
                best_matching_location = location
        return best_matching_location

    # Item stuff

    @staticmethod
    def item_template_get_by_entry(entry):
        world_db_session = SessionHolder()
        res = world_db_session.query(ItemTemplate).filter_by(entry=entry).first()
        world_db_session.close()
        return res

    @staticmethod
    def item_template_get_by_name(name, return_all=False):
        world_db_session = SessionHolder()
        best_matching_item = None
        best_matching_ratio = 0
        items = world_db_session.query(ItemTemplate).filter(ItemTemplate.name.like('%' + name + '%')).all()
        world_db_session.close()

        if return_all:
            return items

        for item in items:
            ratio = SequenceMatcher(None, item.name.lower(), name.lower()).ratio()
            if ratio > best_matching_ratio:
                best_matching_ratio = ratio
                best_matching_item = item
        return best_matching_item

    # Page text stuff

    @staticmethod
    def page_text_get_by_id(page_id):
        world_db_session = SessionHolder()
        res = world_db_session.query(PageText).filter_by(entry=page_id).first()
        world_db_session.close()
        return res

    # Gameobject stuff

    @staticmethod
    def gameobject_get_all_spawns():
        world_db_session = SessionHolder()
        res = world_db_session.query(SpawnsGameobjects).filter_by(ignored=0).all()
        return res, world_db_session

    @staticmethod
    def gameobject_spawn_get_by_guid(guid):
        world_db_session = SessionHolder()
        res = world_db_session.query(SpawnsGameobjects).filter_by(spawn_id=guid & ~HighGuid.HIGHGUID_GAMEOBJECT).first()
        return res, world_db_session

    # Creature stuff

    @staticmethod
    def creature_get_by_entry(entry):
        world_db_session = SessionHolder()
        res = world_db_session.query(CreatureTemplate).filter_by(entry=entry).first()
        world_db_session.close()
        return res

    @staticmethod
    def creature_get_all_spawns():
        world_db_session = SessionHolder()
        res = world_db_session.query(SpawnsCreatures).filter_by(ignored=0).all()
        return res, world_db_session

    @staticmethod
    def creature_spawn_get_by_guid(guid):
        world_db_session = SessionHolder()
        res = world_db_session.query(SpawnsCreatures).filter_by(spawn_id=guid & ~HighGuid.HIGHGUID_UNIT).first()
        return res, world_db_session

    @staticmethod
    def creature_get_model_info(display_id):
        world_db_session = SessionHolder()
        res = world_db_session.query(CreatureModelInfo).filter_by(modelid=display_id).first()
        world_db_session.close()
        return res

    @staticmethod
    def creature_get_loot_template():
        world_db_session = SessionHolder()
        res = world_db_session.query(CreatureLootTemplate).all()
        return res, world_db_session

    @staticmethod
    def creature_get_vendor_data(entry):
        world_db_session = SessionHolder()
        res = world_db_session.query(NpcVendor).filter_by(entry=entry).all()
        return res, world_db_session

    @staticmethod
    def creature_get_vendor_data_by_item(entry, item):
        world_db_session = SessionHolder()
        res = world_db_session.query(NpcVendor).filter_by(entry=entry, item=item).first()
        return res, world_db_session

    @staticmethod
    def creature_get_equipment_by_id(equipment_id):
        world_db_session = SessionHolder()
        res = world_db_session.query(CreatureEquipTemplate).filter_by(entry=equipment_id).first()
        world_db_session.close()
        return res
