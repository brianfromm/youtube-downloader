#!/bin/sh

# Default to false if USE_DEV_SERVER is not set or empty
if [ "${USE_DEV_SERVER}" = "true" ]; then
  echo "Starting Flask development server (FLASK_ENV=development)..."
  export FLASK_ENV=development # Set for Flask dev server
  # server.py handles host/port configuration for the dev server.
  python server.py
else
  echo "Starting Gunicorn server..."
  # Execute Gunicorn with command-line arguments, using environment variables for configuration
  gunicorn \
    --workers ${GUNICORN_WORKERS:-1} \
    --threads ${GUNICORN_THREADS:-4} \
    --bind 0.0.0.0:${APP_PORT:-8080} \
    --log-level ${GUNICORN_LOGLEVEL:-info} \
    --timeout ${GUNICORN_TIMEOUT:-300} \
    server:app
fi
