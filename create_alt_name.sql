alter table coverage_provinces add column alt_name varchar(128);

create index on coverage_provinces(alt_name);

alter table coverage_communes add column alt_name varchar(128);

create index on coverage_communes(alt_name);

alter table coverage_streets add column alt_name varchar(128);

create index on coverage_streets(alt_name);

