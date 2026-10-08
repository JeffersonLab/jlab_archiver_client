"""Configuration management for the jlab_archiver_client package.

This module provides a thread-safe configuration singleton for managing connection
settings and endpoint paths for the Jefferson Lab Archiver myquery server. The
configuration can be modified at runtime and supports safe concurrent access from
multiple threads.

The configuration uses a singleton pattern to ensure that all parts of the application
share the same configuration state. The 'from' import pattern is supported through
a mutate-in-place API, so imported references never go stale.

Key Features:
    * Thread-safe configuration updates and reads
    * Singleton pattern for global configuration state
    * Support for multiple myquery endpoints (mysampler, interval, channel, point, mystats)
    * Runtime configuration changes without restart
    * Consistent snapshots for atomic reads

Attributes:
    config (_Config): The global configuration singleton instance.

Example::

    >>> from jlab_archiver_client.config import config
    >>> # Configure for local development server
    >>> config.set(myquery_server="localhost:8080", protocol="http")
    >>>
    >>> # Configure for production server
    >>> config.set(myquery_server="epicsweb.jlab.org", protocol="https")
    >>>
    >>> # Get a consistent snapshot of current configuration
    >>> current_config = config.snapshot()
    >>> print(current_config['myquery_server'])
    epicsweb.jlab.org

See Also:
    jlab_archiver_client.query: Query classes that use config for endpoint URLs
"""
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock

# Used to support thread-safe reads and coherent snapshots of configuration
_lock = RLock()

@dataclass
class _Config:
    """A basic config file class that handles thread-safety and issues with name binding ('from' imports)"""
    protocol: str = "http"
    """The protocol used by the myquery server"""

    myquery_server: str = "epicsweb.jlab.org"
    """The fully qualified domain name of the myquery server.  Can include port number."""

    mysampler_path: str = "/myquery/mysampler"
    """The path to the mysampler endpoint"""

    interval_path: str = "/myquery/interval"
    """The path to the interval endpoint"""

    channel_path: str = "/myquery/channel"
    """The path to the channel endpoint"""

    point_path: str = "/myquery/point"
    """The path to the point endpoint"""

    mystats_path: str = "/myquery/mystats"
    """The path to the mystats endpoint"""

    server_timezone: str = "America/New_York"
    """The IANA timezone of the myquery server.  Used to present timestamps transferred from myquery as millis since
    unix epoch in the server's local time."""

    def set(self, **kwargs) -> None:
        """mutate-in-place API so imports never go stale"""
        with _lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self) -> dict:
        """Get a consistent (thread-safe) snapshot of the config."""
        with _lock:
            return {
                "protocol": self.protocol,
                "myquery_server": self.myquery_server,
                "mysampler_path": self.mysampler_path,
                "interval_path": self.interval_path,
                "channel_path": self.channel_path,
                "point_path": self.point_path,
                "mystats_path": self.point_path,
                "server_timezone": self.server_timezone,
            }

config = _Config()  # singleton
