"""Backward-compatible Gmail poll wrapper — prefer services.email_poll."""

from app.services.email_poll import poll_and_process

__all__ = ["poll_and_process"]
