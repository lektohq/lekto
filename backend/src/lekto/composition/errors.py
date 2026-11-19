"""Errors raised while starting up: invalid configuration."""


class ConfigurationError(Exception):
    """The configuration is invalid or contradictory. The message is meant for operators."""
