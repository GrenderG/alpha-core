delimiter $
begin not atomic
	-- 15/05/2021 1
	if (select count(*) from applied_updates where id='150520211') = 0 then
		DROP TABLE IF EXISTS `character_reputation`;
		CREATE TABLE IF NOT EXISTS `character_reputation` (
		`character` int(11) unsigned NOT NULL DEFAULT 0,
		`faction` int(11) unsigned NOT NULL DEFAULT 0,
		`standing` int(11) NOT NULL DEFAULT 0,
		`flags` tinyint(1) unsigned NOT NULL DEFAULT 0,
		`index` int(5) NOT NULL,
		PRIMARY KEY (`character`,`faction`),
		CONSTRAINT `fk_character_reputation_character` FOREIGN KEY (`character`) REFERENCES `characters` (`guid`) ON DELETE CASCADE ON UPDATE CASCADE
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;	
		insert into applied_updates values ('150520211');
    end if;
end $
delimiter ;