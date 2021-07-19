import traceback

from database.dbc.DbcDatabaseManager import DbcDatabaseManager
from game.world.managers.maps.AreaInformation import AreaInformation
from game.world.managers.maps.Constants import SIZE, RESOLUTION_ZMAP, RESOLUTION_AREA_INFO, RESOLUTION_LIQUIDS
from game.world.managers.maps.Map import Map
from game.world.managers.maps.MapTile import MapTile
from utils.ConfigManager import config
from utils.Logger import Logger

MAPS = {}
MAP_LIST = DbcDatabaseManager.map_get_all_ids()
AREAS = {}
AREA_LIST = DbcDatabaseManager.area_get_all_ids()


class MapManager(object):
    @staticmethod
    def initialize_maps():
        for map_id in MAP_LIST:
            MAPS[map_id] = Map(map_id, MapManager.on_cell_turn_active)

    @staticmethod
    def initialize_area_tables():
        for area_id in AREA_LIST:
            AREAS[area_id] = DbcDatabaseManager.area_get_by_id(area_id)

    @staticmethod
    def get_area_number_by_zone_id(zone_id):
        if zone_id in AREAS:
            return AREAS[zone_id].AreaNumber
        return zone_id

    @staticmethod
    def get_parent_zone_id(zone_id, map_id):
        if zone_id in AREAS and AREAS[zone_id].ParentAreaNum > 0:
            parent = DbcDatabaseManager.area_get_by_area_number(AREAS[zone_id].ParentAreaNum, map_id)
            if parent:
                return parent.ID
        return zone_id

    @staticmethod
    def on_cell_turn_active(world_object):
        MapManager.load_map_tiles(world_object.map_, world_object.location.x, world_object.location.y)

    @staticmethod
    def load_map_tiles(map_id, x, y):
        if not config.Server.Settings.use_map_tiles:
            return False

        if map_id not in MAP_LIST:
            return False

        x = MapManager.get_tile_x(x)
        y = MapManager.get_tile_y(y)

        for i in range(-1, 1):
            for j in range(-1, 1):
                if -1 < x + i < 64 and -1 < y + j < 64:
                    # Avoid loading tiles information if we already did.
                    if not MAPS[map_id].tiles[x + i][y + j]:
                        MAPS[map_id].tiles[x + i][y + j] = MapTile(map_id, x + i, y + j)

        return True

    @staticmethod
    def get_tile(x, y):
        tile_x = int(32.0 - MapManager.validate_map_coord(x) / SIZE)
        tile_y = int(32.0 - MapManager.validate_map_coord(y) / SIZE)
        return [tile_x, tile_y]

    @staticmethod
    def get_tile_x(x):
        tile_x = int(32.0 - MapManager.validate_map_coord(x) / SIZE)
        return tile_x

    @staticmethod
    def get_tile_y(y):
        tile_y = int(32.0 - MapManager.validate_map_coord(y) / SIZE)
        return tile_y

    @staticmethod
    def get_submap_tile_x(x):
        tile_x = int((RESOLUTION_ZMAP - 1) * (
                32.0 - MapManager.validate_map_coord(x) / SIZE - int(32.0 - MapManager.validate_map_coord(x) / SIZE)))

        return tile_x

    @staticmethod
    def get_submap_tile_y(y):
        tile_y = int((RESOLUTION_ZMAP - 1) * (
                32.0 - MapManager.validate_map_coord(y) / SIZE - int(32.0 - MapManager.validate_map_coord(y) / SIZE)))

        return tile_y

    @staticmethod
    def calculate_z_for_object(world_object):
        return MapManager.calculate_z(world_object.map_, world_object.location.x, world_object.location.y,
                                      world_object.location.z)

    # noinspection PyBroadException
    @staticmethod
    def calculate_z(map_id, x, y, current_z=0.0):
        try:
            if map_id not in MAPS:
                Logger.warning(f'Wrong map, {map_id} not found.')
                return current_z if current_z else 0.0

            map_tile_x, map_tile_y, tile_local_x, tile_local_y = MapManager.calculate_tile(x, y, (RESOLUTION_ZMAP - 1))
            x_normalized = (RESOLUTION_ZMAP - 1) * (32.0 - (x / SIZE) - map_tile_x) - tile_local_x
            y_normalized = (RESOLUTION_ZMAP - 1) * (32.0 - (y / SIZE) - map_tile_y) - tile_local_y

            if not MapManager._check_tile_load(map_id, x, y, map_tile_x, map_tile_y):
                return current_z if current_z else 0.0

            try:
                val_1 = MapManager.get_height(map_id, map_tile_x, map_tile_y, tile_local_x, tile_local_y)
                val_2 = MapManager.get_height(map_id, map_tile_x, map_tile_y, tile_local_x + 1, tile_local_y)
                top_height = MapManager._lerp(val_1, val_2, x_normalized)
                val_3 = MapManager.get_height(map_id, map_tile_x, map_tile_y, tile_local_x, tile_local_y + 1)
                val_4 = MapManager.get_height(map_id, map_tile_x, map_tile_y, tile_local_x + 1, tile_local_y + 1)
                bottom_height = MapManager._lerp(val_3, val_4, x_normalized)
                return MapManager._lerp(top_height, bottom_height, y_normalized)  # Z
            except:
                return MAPS[map_id].tiles[map_tile_x][map_tile_y].z_height_map[tile_local_x][tile_local_x]
        except:
            Logger.error(traceback.format_exc())
            return current_z if current_z else 0.0

    @staticmethod
    def get_area_information(map_id, x, y):
        try:
            if map_id not in MAPS:
                Logger.warning(f'Wrong map, {map_id} not found.')
                return None

            map_tile_x, map_tile_y, tile_local_x, tile_local_y = MapManager.calculate_tile(x, y, RESOLUTION_AREA_INFO - 1)

            if not MapManager._check_tile_load(map_id, x, y, map_tile_x, map_tile_y):
                return None

            if map_id not in MAPS or not MAPS[map_id].tiles[map_tile_x][map_tile_y]:
                return None
            return MAPS[map_id].tiles[map_tile_x][map_tile_y].area_information[tile_local_x][tile_local_y]
        except:
            Logger.error(traceback.format_exc())
            return None

    @staticmethod
    def get_liquid_information(map_id, x, y):
        try:
            if map_id not in MAPS:
                Logger.warning(f'Wrong map, {map_id} not found.')
                return None

            map_tile_x, map_tile_y, tile_local_x, tile_local_y = MapManager.calculate_tile(x, y, RESOLUTION_LIQUIDS - 1)

            if not MapManager._check_tile_load(map_id, x, y, map_tile_x, map_tile_y):
                return None

            if map_id not in MAPS or not MAPS[map_id].tiles[map_tile_x][map_tile_y]:
                return None
            return MAPS[map_id].tiles[map_tile_x][map_tile_y].liquid_information[tile_local_x][tile_local_y]
        except:
            Logger.error(traceback.format_exc())
            return None

    @staticmethod
    def _check_tile_load(map_id, location_x, location_y, map_tile_x, map_tile_y):
        tile_loaded = MAPS[map_id].tiles[map_tile_x][map_tile_y] is not None

        if tile_loaded:
            return True

        # Load the tile if it hasn't been loaded yet.
        if not tile_loaded:
            tile_loaded = MapManager.load_map_tiles(map_id, location_x, location_y)

        # If invalid map or tile information not present (even after loading attempt), return None.
        if not tile_loaded:
            Logger.warning(f'Tile [{map_tile_x},{map_tile_y}] information not found.')

        return tile_loaded is not None

    @staticmethod
    def calculate_tile(x, y, resolution):
        x = MapManager.validate_map_coord(x)
        y = MapManager.validate_map_coord(y)
        map_tile_x = int(32.0 - (x / SIZE))
        map_tile_y = int(32.0 - (y / SIZE))
        tile_local_x = int(resolution * (32.0 - (x / SIZE) - map_tile_x))
        tile_local_y = int(resolution * (32.0 - (y / SIZE) - map_tile_y))
        return map_tile_x, map_tile_y, tile_local_x, tile_local_y

    @staticmethod
    def get_height(map_id, map_tile_x, map_tile_y, map_tile_local_x, map_tile_local_y):
        if map_tile_local_x > RESOLUTION_ZMAP:
            map_tile_x = int(map_tile_x + 1)
            map_tile_local_x = int(map_tile_local_x - RESOLUTION_ZMAP)
        elif map_tile_local_x < 0:
            map_tile_x = int(map_tile_x - 1)
            map_tile_local_x = int(-map_tile_local_x - 1)

        if map_tile_local_y > RESOLUTION_ZMAP:
            map_tile_y = int(map_tile_y + 1)
            map_tile_local_y = int(map_tile_local_y - RESOLUTION_ZMAP)
        elif map_tile_local_y < 0:
            map_tile_y = int(map_tile_y - 1)
            map_tile_local_y = int(-map_tile_local_y - 1)

        return MAPS[map_id].tiles[map_tile_x][map_tile_y].z_height_map[map_tile_local_x][map_tile_local_y]

    @staticmethod
    def validate_map_coord(coord):
        if coord > 32.0 * SIZE:
            return 32.0 * SIZE
        elif coord < -32.0 * SIZE:
            return -32 * SIZE
        else:
            return coord

    @staticmethod
    def get_grid_manager_by_map_id(map_id):
        if map_id in MAPS:
            return MAPS[map_id].grid_manager
        return None

    @staticmethod
    def _lerp(value1, value2, amount):
        return value1 + (value2 - value1) * amount

    # Object methods (wrappers around GridManager methods)

    @staticmethod
    def should_relocate(world_object, destination, destination_map):
        grid_manager = MapManager.get_grid_manager_by_map_id(destination_map)
        destination_cells = grid_manager.get_surrounding_cells_by_location(destination.x, destination.y, destination_map)
        current_cell = grid_manager.get_cells()[world_object.current_cell]
        return current_cell in destination_cells

    @staticmethod
    def update_object(world_object):
        grid_manager = MapManager.get_grid_manager_by_map_id(world_object.map_)
        grid_manager.update_object(world_object)

    @staticmethod
    def remove_object(world_object):
        MapManager.get_grid_manager_by_map_id(world_object.map_).remove_object(world_object)

    @staticmethod
    def send_surrounding(packet, world_object, include_self=True, exclude=None, use_ignore=False):
        MapManager.get_grid_manager_by_map_id(world_object.map_).send_surrounding(
            packet, world_object, include_self, exclude, use_ignore)

    @staticmethod
    def send_surrounding_in_range(packet, world_object, range_, include_self=True, exclude=None, use_ignore=False):
        MapManager.get_grid_manager_by_map_id(world_object.map_).send_surrounding_in_range(
            packet, world_object, range_, include_self, exclude, use_ignore)

    @staticmethod
    def get_surrounding_objects(world_object, object_types):
        return MapManager.get_grid_manager_by_map_id(world_object.map_).get_surrounding_objects(world_object, object_types)

    @staticmethod
    def get_surrounding_players(world_object):
        return MapManager.get_grid_manager_by_map_id(world_object.map_).get_surrounding_players(world_object)

    @staticmethod
    def get_surrounding_units(world_object, include_players=False):
        return MapManager.get_grid_manager_by_map_id(world_object.map_).get_surrounding_units(world_object, include_players)

    @staticmethod
    def get_surrounding_units_by_location(vector, target_map, range_, include_players=False):
        grid_mgr = MapManager.get_grid_manager_by_map_id(target_map)
        if not grid_mgr:
            return [{}, {}]
        return grid_mgr.get_surrounding_units_by_location(vector, target_map, range_, include_players)

    @staticmethod
    def get_surrounding_gameobjects(world_object):
        return MapManager.get_grid_manager_by_map_id(world_object.map_).get_surrounding_gameobjects(world_object)

    @staticmethod
    def get_surrounding_player_by_guid(world_object, guid):
        return MapManager.get_grid_manager_by_map_id(world_object.map_).get_surrounding_player_by_guid(world_object, guid)

    @staticmethod
    def get_surrounding_unit_by_guid(world_object, guid, include_players=False):
        return MapManager.get_grid_manager_by_map_id(world_object.map_).get_surrounding_unit_by_guid(world_object, guid, include_players)

    @staticmethod
    def get_surrounding_gameobject_by_guid(world_object, guid):
        return MapManager.get_grid_manager_by_map_id(world_object.map_).get_surrounding_gameobject_by_guid(world_object, guid)

    @staticmethod
    def update_creatures():
        for map_id, map_ in MAPS.items():
            map_.grid_manager.update_creatures()

    @staticmethod
    def update_gameobjects():
        for map_id, map_ in MAPS.items():
            map_.grid_manager.update_gameobjects()

    @staticmethod
    def deactivate_cells():
        for map_id, map_ in MAPS.items():
            map_.grid_manager.deactivate_cells()
