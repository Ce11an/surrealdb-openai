USE NS test; USE DB test;

DEFINE TABLE chat SCHEMAFULL;

DEFINE FIELD title ON TABLE chat TYPE string;
DEFINE FIELD created_at ON TABLE chat TYPE datetime
   VALUE time::now() READONLY;
DEFINE FIELD updated_at ON TABLE chat TYPE datetime
   VALUE time::now();

