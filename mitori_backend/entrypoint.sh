#!/bin/bash

# Exit immediately if any command fails
set -e

if [ "$3" = "runserver" ]; then
    echo "PostgreSQL is healthy! Running database migrations..."
    python manage.py migrate --noinput
else
    echo "PostgreSQL is healthy! Skipping migrations for background worker..."
fi

echo "Starting process: $@"
exec "$@"