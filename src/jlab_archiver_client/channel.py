"""Channel lookup module for querying archived channel names.

This module provides functionality for searching and discovering Process Variable (PV)
channel names in the Jefferson Lab Archiver using SQL-style pattern matching. The
channel endpoint is useful for finding what channels are available in the archive
without needing to know exact channel names.

The channel query supports SQL LIKE patterns (%, _) for flexible searching.

Classes:
    Channel: Main class for executing channel lookup queries.

Example::

    >>> from jlab_archiver_client.config import config
    >>> config.set(myquery_server="localhost:8080", protocol="http")
    >>>
    >>> from jlab_archiver_client import Channel, ChannelQuery
    >>> # Search for all channels starting with "channel10"
    >>> query = ChannelQuery(pattern="channel10%", deployment="docker")
    >>> channel = Channel(query)
    >>> channel.run()
    >>> channel.matches
    [{'name': 'channel100', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True}, {'name': 'channel101', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True}]

See Also:
    jlab_archiver_client.query.ChannelQuery: Query builder for channel searches
    jlab_archiver_client.config: Configuration settings for archiver endpoints
""" # noqa: E501
from typing import Optional, List, Any, Dict

import requests

from jlab_archiver_client import utils
from jlab_archiver_client.config import config
from jlab_archiver_client.query import ChannelQuery


__all__ = ["Channel"]


class Channel:
    """A class for running calls to myquery's channel endpoint.

    This class allows for the user to lookup channels in the archive by name using SQL patterns
    """

    def __init__(self, query: ChannelQuery, url: Optional[str] = None):
        """Construct an instance for running a myquery channel call.

        Args:
            query: The query to run
            url: The location of the myquery/interval endpoint. Generated from config if None supplied.
        """
        self.query = query
        self.url = url
        if url is None:
            self.url = f"{config.protocol}://{config.myquery_server}{config.channel_path}"

        self.matches: Optional[List[Dict:str, Any]] = None

    def run(self):
        """Run a web-based myquery channel query."""

        opts = self.query.to_web_params()
        r = requests.get(self.url, params=opts)

        utils.check_response(r)
        self.matches = r.json()
