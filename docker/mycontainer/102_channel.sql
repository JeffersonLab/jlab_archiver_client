-- channel103 is a scaler double floating point type
-- loosely based on IPM5R02.BCSP using channel101 as a guide
INSERT INTO channels
(chan_id, name, type, adel, size, clip, active, request, alert, host, backup, ioc)
VALUES (102, 'channel102', 1, null, 11, NULL, 1, 1, 0, 'mya', '6197335468200165376', NULL);


-- hstmya1: copied from similar PV in mycontainer.  Matches `show create` from mysql CLI tool
CREATE TABLE `table_102`
(
    `time`  bigint(20)          NOT NULL,
    `code`  tinyint(3) unsigned NOT NULL DEFAULT '0',
    `val1`  smallint(6)         NOT NULL DEFAULT '0',
    `val2`  smallint(6)         NOT NULL DEFAULT '0',
    `val3`  smallint(6)         NOT NULL DEFAULT '0',
    `val4`  smallint(6)         NOT NULL DEFAULT '0',
    `val5`  smallint(6)         NOT NULL DEFAULT '0',
    `val6`  smallint(6)         NOT NULL DEFAULT '0',
    `val7`  smallint(6)         NOT NULL DEFAULT '0',
    `val8`  smallint(6)         NOT NULL DEFAULT '0',
    `val9`  smallint(6)         NOT NULL DEFAULT '0',
    `val10` smallint(6)         NOT NULL DEFAULT '0',
    `val11` smallint(6)         NOT NULL DEFAULT '0',
    PRIMARY KEY (`time`)
);

-- pulled from opsmyafb0 originally mya time 454410045243747746 - 460877218000666623, but updated to match channel 101
INSERT INTO archive.table_102 (time, code, val1, val2, val3, val4, val5, val6, val7, val8, val9, val10, val11)
VALUES (409252071947660845, 48, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5),
       (409252072551402631, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
       (409252072789858057, 0, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5),
       (409252159417281676, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
       (409253148943048969, 0, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5),
       (409253358329564799, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
       (409359951810995171, 0, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5),
       (409359952347866064, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
       (409359952508927331, 0, 3, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5),
       (409359952607355665, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
