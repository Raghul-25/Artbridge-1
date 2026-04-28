"""
wsgi.py — Gunicorn entry point for production.

Run with:
    gunicorn --workers 4 --bind 127.0.0.1:5000 wsgi:app
"""
from app import create_app

app = create_app()
