#!/bin/sh
set -e

echo "Waiting for the database..."
until pg_isready -h "${DB_HOST:-db}" -q; do
  sleep 1
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput -v 0

if [ -f data/ris_buildings.csv ]; then
  python manage.py load_buildings --if-empty
else
  echo "data/ris_buildings.csv not found - see data/README.md to prepare it."
fi

exec "$@"
