#!/usr/bin/env python3
"""
Simple script to run the CMBAgent backend server
"""

import logging
import os
import uvicorn
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in parent directory
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path)

# Add the parent directory to the path to import cmbagent
sys.path.append(str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting CMBAgent Backend Server")
    port = int(os.getenv("PORT", 8000))
    logger.info("Server: http://localhost:%d | WebSocket: ws://localhost:%d/ws/{task_id} | Docs: http://localhost:%d/docs", port, port, port)

    # Get log directory from environment or use default
    work_dir = os.getenv("CMBAGENT_DEFAULT_WORK_DIR", "~/Desktop/cmbdir")
    work_dir = os.path.expanduser(work_dir)
    log_dir = Path(work_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Logs will be written to %s/backend.log", log_dir)

    # Determine if we should enable auto-reload (development mode only)
    # Set CMBAGENT_DEBUG=true or CMBAGENT_ENABLE_RELOAD=true to enable reload
    debug_mode = os.getenv("CMBAGENT_DEBUG", "false").lower() == "true"
    enable_reload_env = os.getenv("CMBAGENT_ENABLE_RELOAD", "false").lower() == "true"
    enable_reload = debug_mode or enable_reload_env

    # Configure reload exclusions to prevent server restart when agent creates files
    # These patterns are relative to the backend directory
    reload_excludes = [
        "cmbdir*/**",           # Exclude all cmbdir_* work directories
        "cmbagent*/**",         # Exclude all cmbagent_* work directories  
        "**/sessions/**",       # Exclude session directories anywhere
        "**/tasks/**",          # Exclude task directories anywhere
        "**/chats/**",          # Exclude chat directories
        "**/data/**",           # Exclude data directories
        "**/database/**",       # Exclude database directories
        "**/planning/**",       # Exclude planning directories
        "**/control/**",        # Exclude control directories
        "*.log",                # Exclude log files
        "*.db",                 # Exclude database files
        "*.sqlite",             # Exclude SQLite files
        "*.sqlite3",            # Exclude SQLite3 files
        "**/__pycache__/**",    # Exclude Python cache
        "**/*.pyc",             # Exclude compiled Python
        "**/.cache/**",         # Exclude cache directories
    ]

    if enable_reload:
        logger.info("Auto-reload ENABLED (development mode)")
        logger.warning("Auto-reload should be disabled in production. Set CMBAGENT_DEBUG=false")
    else:
        logger.info("Auto-reload DISABLED (production mode)")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=enable_reload,
        reload_excludes=reload_excludes if enable_reload else None,
        log_level="info",
        log_config=None,  # Don't override app's logging configuration
    )
