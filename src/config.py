"""
Shared Neo4j connection config. Reads credentials from environment
variables (via a local .env file) instead of hardcoding them in every
script — this is the standard, secure approach.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file in the project root

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_PASSWORD:
    raise ValueError(
        "NEO4J_PASSWORD not set. Copy .env.example to .env and fill in your password."
    )