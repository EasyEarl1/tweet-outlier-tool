"""
Vercel serverless function entry point for Flask app
"""
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel Python runtime expects the app variable to be exported
# Flask app is WSGI-compatible, so we just export it directly

