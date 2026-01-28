"""
Vercel serverless function entry point for Flask app
"""
from app import app

# Vercel expects the app to be accessible as a WSGI application
# Flask app is already WSGI-compatible, so we just export it
__all__ = ['app']

