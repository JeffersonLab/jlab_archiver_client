"""Statistical aggregation module for archived channel data.

This module provides functionality for querying the Jefferson Lab Archiver's
mystats endpoint, which returns statistical aggregations (min, max, mean, count,
etc.) of Process Variable (PV) values over regularly spaced time bins. This is
useful for analyzing trends and patterns in archived data without retrieving
every individual event.

The mystats endpoint bins data into time intervals and computes statistics for
each bin, making it efficient for analyzing large time ranges.

Key Features:
    * Query multiple PVs with a single request
    * Statistical metrics per time bin (min, max, mean, count, etc.)
    * Data organized in a MultiIndex DataFrame (timestamp, stat)
    * Separate metadata storage for each channel
    * Configurable time range and number of time bins

Classes:
    MyStats: Main class for executing mystats queries and storing results.

Example::

    >>> from jlab_archiver_client.config import config
    >>> config.set(myquery_server="localhost:8080", protocol="http")
    >>>
    >>> from jlab_archiver_client import MyStats, MyStatsQuery
    >>> from datetime import datetime
    >>> query = MyStatsQuery(
    ...     start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
    ...     end=datetime.strptime("2019-08-13 00:00:00", "%Y-%m-%d %H:%M:%S"),
    ...     num_bins=24,      # 24 bin (one hour per bin)
    ...     pvlist=["channel1", "channel100"],
    ...     deployment="docker"
    ... )
    >>> mystats = MyStats(query)
    >>> mystats.run()
    >>> mystats.data  # MultiIndex DataFrame with (timestamp, stat)
                                          channel1    channel100
    timestamp           stat
    2019-08-12 00:00:00 duration       3594.421033   3600.000000
                        eventCount     1716.000000      2.000000
                        integration  341342.201073  20368.799973
                        max              96.952400      5.658000
                        mean             94.964400      5.658000
    ...                                        ...           ...
    2019-08-12 23:00:00 mean             92.036600      5.658000
                        min               0.000000      5.658000
                        rms              93.545500      5.658000
                        stdev            16.733800      0.000000
                        updateCount    1606.000000      1.000000
    >>> mystats.data.loc['2019-08-12 00:00:00'] # Query all stats at a specific time
                      channel1    channel100
    stat
    duration       3594.421033   3600.000000
    eventCount     1716.000000      2.000000
    integration  341342.201073  20368.799973
    max              96.952400      5.658000
    mean             94.964400      5.658000
    min               0.000000      5.658000
    rms              95.267500      5.658000
    >>> mystats.data.loc[(pd.Timestamp('2019-08-12 00:00:00'), 'mean'), 'channel1'] # Query a specific stat at a specific time
    94.9644
    >>> idx = pd.IndexSlice  # Setup to query a slice of times and stats
    >>> mystats.data.loc[idx['2019-08-12 00:00:00':'2019-08-12 12:00:00', ['mean', 'max']], :]
                              channel1  channel100
    timestamp           stat
    2019-08-12 00:00:00 max    96.9524       5.658
                        mean   94.9644       5.658
    2019-08-12 01:00:00 max    96.1750       5.658
                        mean   84.4616       5.658
    2019-08-12 02:00:00 max    96.2040       5.658
                        mean   85.8309       5.658
    2019-08-12 03:00:00 max    96.6146       5.658
                        mean   91.1273       5.658
    2019-08-12 04:00:00 max    97.7953       5.658
                        mean   94.3502       5.658
    2019-08-12 05:00:00 max    98.8530       5.658
                        mean   95.6387       5.658
    2019-08-12 06:00:00 max    98.5217       5.658
                        mean   71.1526       5.658
    2019-08-12 07:00:00 max    98.9699       5.658
                        mean   89.9230       5.658
    2019-08-12 08:00:00 max    96.5996       5.658
                        mean   38.1108       5.658
    2019-08-12 09:00:00 max    95.3031       5.658
                        mean   56.5888       5.658
    2019-08-12 10:00:00 max    97.7024       5.658
                        mean   94.0369       5.658
    2019-08-12 11:00:00 max    97.6824       5.658
                        mean   77.0781       5.658
    2019-08-12 12:00:00 max    38.3621       5.658
                        mean   32.7660       5.658
    >>> mystats.metadata  # Channel metadata dictionary
    {'channel1': {'name': 'channel1', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True}, 'channel100': {'name': 'channel100', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True}}

Note:
    Only float-type PVs are currently supported by the mystats endpoint.
    The data DataFrame uses a MultiIndex with (timestamp, stat) for efficient
    access to specific statistics across time bins.  Other PV types are will
    be skipped and print a warning from myquery.

See Also:
    jlab_archiver_client.query.MyStatsQuery: Query builder for mystats requests
    jlab_archiver_client.config: Configuration settings for archiver endpoints
"""# noqa: E501
import warnings
from typing import Optional, Dict, Any

import pandas as pd
import requests

from jlab_archiver_client import utils
from jlab_archiver_client.query import MyStatsQuery
from jlab_archiver_client.config import config

__all__ = ["MyStats"]


class MyStats:
    """A class for running a myquery mystats request and holding the results.  Only float PVs supported.

    Statistics are stored in the data field.  This is a DataFrame with a MultiIndex on the start of the bin and the
    metric name.

    Metadata is stored in a dictionary key on each channel.

    The mystats endpoint is intended to provide the value of a set of PVs at regularly spaced time intervals.
    """

    def __init__(self, query: MyStatsQuery, url: Optional[str] = None):
        """Construct an instance for running a mystats query.

        Args:
            query: The query to run
            url: The location of the mystats endpoint.  Generated from config if None supplied.
        """
        self.query = query
        self.url = url
        if url is None:
            self.url = f"{config.protocol}://{config.myquery_server}{config.mystats_path}"

        self.data: Optional[pd.DataFrame] = None
        self.metadata: Optional[Dict[str, object]] = None

    @staticmethod
    def _channel_series(channel_obj: Dict[str, Any]):
        """Return a Series indexed by (timestamp, stat) holding the metric values."""
        tuples, vals = [], []

        # Look at the first entry to determine what metrics to include
        metrics = []
        for key in channel_obj["data"][0].keys():
            if key != "begin":
                metrics.append(key)
        metrics = sorted(metrics)

        for rec in channel_obj["data"]:
            ts = pd.to_datetime(rec["begin"])
            for m in metrics:
                tuples.append((ts, m))
                vals.append(rec.get(m))
        idx = pd.MultiIndex.from_tuples(tuples, names=["timestamp", "stat"])
        return pd.Series(vals, index=idx)

    def run(self):
        """Run a web-based mysampler query.

        Results will be stored in the data and metadata fields.

        Raises:
            RequestException when a problem making the query has occurred
        """

        # Make the request
        opts = self.query.to_web_params()
        r = requests.get(self.url, params=opts)

        utils.check_response(r)

        # Single top level key is channels
        channels = r.json()['channels']

        # Process one channel at a time, then concat Series into a DataFrame
        series_by_channel = {}
        self.metadata = {}
        for ch_name, ch_obj in channels.items():
            if "error" in ch_obj.keys():
                warnings.warn(f"Error querying {ch_name}: {ch_obj['error']}")
            else:
                series_by_channel[ch_name] = self._channel_series(ch_obj)
                self.metadata[ch_name] = ch_obj['metadata']

        self.data = pd.concat(series_by_channel, axis=1).sort_index()
