"""ASGI entrypoint for the internal Vercel API service."""

from .app import create_app

app = create_app()
