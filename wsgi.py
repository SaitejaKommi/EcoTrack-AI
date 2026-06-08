"""
WSGI Entry Point for CarbonWise AI.
Exposes the Flask app instance for WSGI production servers (e.g. Gunicorn).
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
