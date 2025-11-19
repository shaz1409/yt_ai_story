#!/usr/bin/env python3
"""
Main CLI entrypoint for AI Story Shorts Factory.

This is a convenience wrapper that imports and runs the main pipeline orchestrator.
"""

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.pipelines.run_full_pipeline import main

if __name__ == "__main__":
    sys.exit(main())

