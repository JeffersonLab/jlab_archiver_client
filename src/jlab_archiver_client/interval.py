"""Query and retrieve historical EPICS PV data from the MYA archiver using the interval endpoint.

This module provides the Interval class for querying the MYA archiver's interval endpoint,
which retrieves all archived events for specified PVs over a given time range. The module
supports both single-channel queries and parallel multi-channel queries, returning data as
pandas Series or DataFrames with datetime indices.

The interval endpoint returns all archived events (value updates, disconnections, etc.) within
the specified time range. Non-update events (like network disconnections) are handled separately
to maintain data integrity and type consistency. The disconnects field contains both events where
no data is available (e.g., NETWORK_DISCONNECTION) and special events that do have data
(e.g., CHANNELS_PRIOR_DATA_DISCARDED).

Examples:
    These examples are designed to work with the container environment in the development repo.
    First set the config to use the myquery container.

        >>> from jlab_archiver_client.config import config
        >>> config.set(myquery_server = "localhost:8080", protocol = "http")

    Query a single channel and access the data:

    Example::
        >>> from datetime import datetime
        >>> from jlab_archiver_client import IntervalQuery
        >>> from jlab_archiver_client import Interval
        >>>
        >>> # Create a query for a single channel
        >>> query = IntervalQuery(
        ...             channel="channel100",
        ...             begin=datetime(2018, 4, 24),
        ...             end=datetime(2018, 5, 1),
        ...             deployment="docker"
        ...         )
        >>>
        >>> # Execute the query
        >>> interval = Interval(query)
        >>> interval.run()
        >>>
        >>> # Access the data as a pandas Series with datetime index
        >>> print(interval.data)
        2018-04-24 06:25:01    0.000
        2018-04-24 06:25:05    5.911
        2018-04-24 11:18:19    5.660
        2018-04-24 12:19:44      NaN
        2018-04-24 12:31:11    5.657
        2018-04-25 02:39:29    0.000
        2018-04-25 02:39:34    5.657
        2018-04-26 10:31:39    0.000
        2018-04-26 10:31:42    0.031
        2018-04-26 10:31:43    2.466
        2018-04-26 10:31:44    5.657
        2018-04-27 14:29:41    0.000
        2018-04-27 14:29:45    1.418
        2018-04-27 14:29:46    5.657
        2018-04-29 01:52:04    0.000
        2018-04-29 01:52:08    5.657
        2018-04-30 10:15:21    0.000
        2018-04-30 10:15:26    5.658
        Name: channel100, dtype: float64
        >>>
        >>> # Access disconnect events separately
        >>> print(interval.disconnects)
        2018-04-24 12:19:44    NETWORK_DISCONNECTION
        Name: channel100, dtype: object
        >>>
        >>> # Access metadata about the channel
        >>> print(interval.metadata)
        {'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True, 'sampled': False, 'returnCount': 18}

    Query multiple channels in parallel and get a combined DataFrame:

        >>> from datetime import datetime
        >>> from jlab_archiver_client.interval import Interval
        >>> out = Interval.run_parallel(pvlist=["channel2", "channel3"],
                            begin=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                            end=datetime.strptime("2019-08-12 01:20:45.002",
                                                  "%Y-%m-%d %H:%M:%S.%f"),
                            deployment="docker",
                            prior_point=True,
                            )
        >>> data, disconnects, metadata = out
        >>> data.head()
                             channel2                                           channel3
        2019-08-12 00:00:01       NaN  [1565580000.0, 1565580000.0, 1565580000.0, 156...
        2019-08-12 00:43:56       0.0  [1565580000.0, 1565580000.0, 1565580000.0, 156...
        2019-08-12 00:44:11       3.0  [1565580000.0, 1565580000.0, 1565580000.0, 156...
        2019-08-12 01:00:01       3.0  [1565590000.0, 1565580000.0, 1565580000.0, 156...
        2019-08-12 01:14:06       0.0  [1565590000.0, 1565580000.0, 1565580000.0, 156...
""" # noqa: E501
import concurrent
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests

from jlab_archiver_client import utils
from jlab_archiver_client.config import config
from jlab_archiver_client.exceptions import MyqueryException
from jlab_archiver_client.query import IntervalQuery

__all__ = ["Interval"]

class Interval:
    """A class for running calls to myquery's interval endpoint.

    Values of the PV updates are stored as a pandas Series object in the data
    field.  Non-update events are stored as None to allow better automatic type
    detection by pandas.  Diconnect events are stored as a pandas Series in the
    disconnects field.  The disconnects field contains both events where no data
    is available (e.g., NETWORK_DISCONNECTION) and special events that do have
    data (e.g., CHANNELS_PRIOR_DATA_DISCARDED).  Other response metadata is
    available in the metadata field.

    The interval endpoint is intended for retrieving the mya events over the
    requested time interval.
    """

    def __init__(self, query: IntervalQuery, url: Optional[str] = None):
        """Construct an instance for running a myquery interval.

        Args:
            query: The query to run
            url: The location of the myquery/interval endpoint. Generated from config if None supplied.
        """
        self.query = query
        self.url = url
        if url is None:
            self.url = f"{config.protocol}://{config.myquery_server}{config.interval_path}"

        self.data: Optional[pd.Series] = None
        self.disconnects: Optional[pd.Series] = None
        self.metadata: Optional[Dict[str, object]] = None

    def run(self):
        """Run a web-based myquery interval query.  This supports querying only one PV at a time.

        Raises:
            RequestException when a problem making the query has occurred
        """

        opts = self.query.to_web_params()
        r = requests.get(self.url, params=opts)

        utils.check_response(r)

        content = r.json()
        # Data values
        values = []
        # Timestamps for all events
        ts = []
        # Timestamps for disconnect events
        disconnect_ts = []
        # Values for disconnect events (strings like "NETWORK_DISCONNECTION")
        disconnect_values = []
        for item in content['data']:
            ts.append(item['d'])
            if 't' in item:
                disconnect_values.append(item['t'])
                disconnect_ts.append(item['d'])
            if 'v' in item:
                values.append(item['v'])
            else:
                # Should be identical to x=True in JSON response
                values.append(None)

        # Default value for empty series is in flux.  Future will have dtype of object.  Skips a deprecation warning.
        if len(disconnect_values) == 0:
            disconnects = pd.Series(disconnect_values, index=disconnect_ts, name=self.query.channel, dtype=object)
        else:
            disconnects = pd.Series(disconnect_values, index=disconnect_ts, name=self.query.channel)

        metadata = {}
        for key, value in content.items():
            if key != "data":
                metadata[key] = value

        self.data = utils.convert_data_to_series(values, ts, self.query.channel, metadata, self.query.enums_as_strings)
        self.disconnects = disconnects
        self.metadata = metadata

    @staticmethod
    def create_queries() -> List[IntervalQuery]:
        """Create a list of IntervalQueries, one per PV, with otherwise identical parameters.

        See IntervalQuery for required parameters.
        """

    @staticmethod
    def run_parallel(pvlist: List[str], max_workers: int = 4, **kwargs) -> Tuple[
        pd.DataFrame, Dict[str, pd.Series], dict]:
        """Run multiple IntervalQueries in parallel.  The web endpoint does not support multiple PVs in a single query.

        All queries will have the same options other than channel, which is pulled from pvlist.  prior_point is forced
        to True to ensure that we can intelligently fill NaN values from merging the disparate time stamps.

        Args:
            pvlist: A list of PVs to queries
            max_workers: The maximum number of concurrent queries to run in parallel.

        Raises:
            MyqueryException when a problem with one or more queries has occurred

        Returns:
            A Pandas DataFrame of the combined PVs, a dictionry of per-channel disconnect series (keyed on channels),
            and a dictionary of per-channel metadata (keyed on channel)
        """
        if "channel" in kwargs.keys():
            del kwargs["channel"]
        kwargs["prior_point"] = True

        queries = []
        for pv in pvlist:
            queries.append(IntervalQuery(pv, **kwargs))

        out = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for query in queries:
                out[query.channel] = Interval(query)
                futures.append(executor.submit(out[query.channel].run))

            # The futures won't hold results, only the status of the jobs.  Look at out for future.
            done, not_done = concurrent.futures.wait(futures, return_when=concurrent.futures.ALL_COMPLETED)

        if len(not_done) > 0:
            raise MyqueryException("Some PV queries did not complete.")

        data = Interval._combine_series([out[channel].data for channel in out.keys()])
        disconnects = {channel: out[channel].disconnects for channel in out.keys()}
        metadata = {channel: out[channel].metadata for channel in out.keys()}

        return data, disconnects, metadata

    @staticmethod
    def _combine_series(series: List[pd.Series]) -> pd.DataFrame:
        """Combine multiple series of PV history into a single DataFrame with shared DateTime Index.

        The series are concat'ed together and sorted so that rows appear in chronological order.  Missing values are
        forward filled, but NaNs in the original data are preserved and forward filled as well.  The names of the
        Series are used as column names in the resulting DataFrame.

        Note: Series are assumed to have a DateTime index.

        Args:
            series: A list of Series objects to combine

        Return:
            A DataFrame of the combined Series objects.
        """
        df = pd.concat(series, axis=1).sort_index().ffill()

        for s in series:
            # Find where there is non-update values (None/NaN)
            nan_mask = s.isnull()

            # Add back any missing NaNs from the original data
            if sum(nan_mask) > 0:
                # This identifies all the timestamps following an NaN.  If the last value is NaN, then the following
                # timestamp will be pd.NaT (not a time)
                next_ts = s.index.to_series().shift(-1)

                # For each row, check if it was originally an NaN, then add back in the NaNs.
                for idx, is_true in nan_mask.items():
                    if is_true:
                        # idx is the last row so we go to the end
                        if next_ts[idx] is pd.NaT:
                            df.loc[df.index >= idx, s.name] = np.nan
                        else:
                            # Fill in any value between "here" and the next "real" update.
                            df.loc[(df.index >= idx) & (df.index < next_ts[idx]), s.name] = np.nan

        return df
