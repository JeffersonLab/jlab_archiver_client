"""Point query module for retrieving single channel events.

This module provides functionality for querying the myquery point
endpoint, which returns a single event for a specified Process Variable (PV)
at or near a given timestamp. This is useful for finding the value of a channel
at a specific point in time or for navigating through events sequentially.

The point endpoint searches for the closest event before (inclusive) the specified
timestamp by default. Options exist to search forward in time and to exclude the
exact timestamp from the search, which is helpful for finding the next/previous
event relative to a known event.

Key Features:
    * Retrieve single event at or near a timestamp
    * Search backward (default) or forward in time
    * Option to exclude exact timestamp from search
    * Useful for sequential event navigation
    * Returns full event data including value and metadata

Classes:
    Point: Main class for executing point queries.

Example::

    >>> from jlab_archiver_client.config import config
    >>> config.set(myquery_server="localhost:8080", protocol="http")
    >>>
    >>> from jlab_archiver_client import Point, PointQuery
    >>> from datetime import datetime
    >>> # Get the event at or before a specific time
    >>> query = PointQuery(
    ...     channel="channel1",
    ...     time=datetime.strptime("2019-08-12 12:00:00", "%Y-%m-%d %H:%M:%S"),
    ...     deployment="docker"
    ... )
    >>> point = Point(query)
    >>> point.run()
    >>> point.event  # Dictionary containing event data
    {'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'data': {'d': '2019-08-12 11:55:22', 'v': 6.20794}}

See Also:
    jlab_archiver_client.query.PointQuery: Query builder for point requests
    jlab_archiver_client.config: Configuration settings for archiver endpoints
"""
from typing import Optional, Dict, Any

import requests

from jlab_archiver_client import utils
from jlab_archiver_client.config import config
from jlab_archiver_client.query import PointQuery

__all__ = ["Point"]


class Point:
    """A class for running calls to myquery's point endpoint.

    This endpoint returns a single channel event.  The user supplies the channel name and a timestamp, and myquery
    return the closest event before (inclusive) the timestamp.

    Options exists to look into the future and exclude
    the given timestamp from search space.  That is helpful in the scenario that you want to know the next event
    before/after an event you already know of.
    """

    def __init__(self, query: PointQuery, url: Optional[str] = None):
        """Construct an instance for running a myquery interval.

        Args:
            query: The query to run
            url: The location of the myquery/interval endpoint. Generated from config if None supplied.
        """
        self.query = query
        self.url = url
        if url is None:
            self.url = f"{config.protocol}://{config.myquery_server}{config.point_path}"

        self.event: Optional[Dict[str, Any]] = None

    def run(self):
        """Run a web-based myquery interval query.  This supports querying only one PV at a time.

        Raises:
            RequestException when a problem making the query has occurred
        """

        opts = self.query.to_web_params()
        r = requests.get(self.url, params=opts)

        utils.check_response(r)

        self.event = r.json()
        self.event['name'] = self.query.channel
