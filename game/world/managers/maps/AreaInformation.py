class AreaInformation(object):
    def __init__(self, zone_id, area_number, area_flags, area_level, area_explore_bit, area_faction_mask):
        self.zone_id = zone_id
        self.area_number = area_number
        self.flags = area_flags
        self.level = area_level
        self.explore_bit = area_explore_bit
        self.faction_mask = area_faction_mask
