web: gunicorn eduportal.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 3 --worker-class gthread --timeout 90 --max-requests 500 --max-requests-jitter 50
