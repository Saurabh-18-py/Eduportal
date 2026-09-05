web: gunicorn eduportal.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --worker-class gthread --timeout 30 --max-requests 500 --max-requests-jitter 50
