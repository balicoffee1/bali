#! /bin/bash

set -e

psql -v ON_ERROR_STOP=1 --username "postgres" --dbname "island_bali" <<-EOSQL
  CREATE DATABASE island_bali;
    CREATE USER postgres WITH ENCRYPTED PASSWORD '12345';
    GRANT ALL PRIVILEGES ON DATABASE postgres TO island_bali;
EOSQL