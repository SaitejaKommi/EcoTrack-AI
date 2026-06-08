"""
Entrypoint Script for CarbonWise AI.
Instantiates and runs the Flask application server.
"""

from app import create_app
from app.config import Config

# Create application instance using factory pattern
app = create_app()

if __name__ == '__main__':
    # Start web server
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
