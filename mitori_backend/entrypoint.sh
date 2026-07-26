
echo "Waiting for PostgreSQL to start..."
while ! python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(('$POSTGRES_HOST', $POSTGRES_PORT))" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL started!"

if [ "$3" = "runserver" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput
else
    echo "Skipping migrations for background worker..."
fi

echo "Starting process: $@"
exec "$@"