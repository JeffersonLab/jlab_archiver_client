"""MySampler module for querying regularly sampled archiver data.

This module provides functionality for querying the Jefferson Lab Archiver's
mysampler endpoint, which returns Process Variable (PV) values at regularly
spaced time intervals. The module handles data retrieval, processing, and
organization into pandas DataFrames for easy analysis.

The mysampler endpoint is designed for scenarios where you need synchronized
samples of multiple PVs at consistent time intervals, as opposed to retrieving
all archived events.

Key Features:
    * Query multiple PVs with a single request
    * Sampling strategies for different update rates (manual selection required)
    * Automatic handling of disconnect events and non-update events
    * Data organized in a single DataFrame with common time index
    * Separate tracking of disconnect events with original metadata
    * Configurable sampling intervals and time ranges
    * Support for enum-to-string conversion

Classes:
    MySampler: Main class for executing mysampler queries and storing results.

Typical Usage:
    Here is an example querying two channels from the containerized myquery
    bundled in the git project.

    Example::
        >>> from jlab_archiver_client.config import config
        >>> config.set(myquery_server = "localhost:8080", protocol = "http")

        >>> from jlab_archiver_client import MySampler
        >>> from jlab_archiver_client import MySamplerQuery
        >>> query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
        ...                        interval=1_800_000,  # 30 minutes
        ...                        num_samples=15,
        ...                        pvlist=["channel1", "channel2"],
        ...                        enums_as_strings=True,
        ...                        deployment="docker")
        >>> mysampler = MySampler(query)
        >>> mysampler.run()
        >>> mysampler.data
                             channel1      channel2
        Date
        2019-08-12 00:00:00       NaN          None
        2019-08-12 00:30:00   95.9706          None
        2019-08-12 01:00:00   95.3033  CW MODE (DC)
        2019-08-12 01:30:00   94.3594  CW MODE (DC)
        2019-08-12 02:00:00   94.8114  CW MODE (DC)
                >>> mysampler.disconnects
        {'channel1': 2019-08-12T00:00:00    UNDEFINED
        Name: channel1, dtype: object, 'channel2': 2019-08-12T00:00:00    UNDEFINED
        2019-08-12T00:30:00    UNDEFINED
        Name: channel2, dtype: object}
        >>> mysampler.metadata
        {'channel1': {'metadata': {'name': 'channel1', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True}, 'returnCount': 15}, 'channel2': {'metadata': {'name': 'channel2', 'datatype': 'DBR_ENUM', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True}, 'labels': [{'d': '2016-08-12T13:00:49', 'value': ['BEAM SYNC ONLY', 'PULSE MODE VL', 'TUNE MODE', 'CW MODE (DC)', 'USER MODE']}], 'returnCount': 15}}


Note:
    Non-update events (disconnects, network errors, etc.) are stored as None
    in the main data DataFrame to allow pandas automatic type detection to
    work correctly. The original disconnect event information is preserved
    in a separate disconnects dictionary. The disconnects field contains both
    events where no data is available (e.g., NETWORK_DISCONNECTION) and special
    events that do have data (e.g., CHANNELS_PRIOR_DATA_DISCARDED). Channel
    metadata is also stored in a separate dictionary object.

See Also:
    jlab_archiver_client.query.MySamplerQuery: Query builder for mysampler requests
    jlab_archiver_client.config: Configuration settings for archiver endpoints
""" # noqa: E501
from typing import Optional, Dict

import pandas as pd
import requests

from jlab_archiver_client import utils
from jlab_archiver_client.query import MySamplerQuery
from jlab_archiver_client.config import config


__all__ = ["MySampler"]


class MySampler:
    """A class for running a myquery mysampler request and holding the results.

    Data from all PVs are stored the data field as a single DataFrame as they
    share a common time index.  Non-update events are stored as None in the
    data field.  This should allow pandas automatic type detection to work
    in the case of non-update events.

    The diconnects field contains a dictionary that is keyed on each PV with
    values that are a Series of only the disconnect events.  The values of this
    Series contain the original text associated with the non-update events. The
    disconnects field contains both events where no data is available (e.g.,
    NETWORK_DISCONNECTION) and special events that do have data (e.g.,
    CHANNELS_PRIOR_DATA_DISCARDED).

    Additional metadata from the myquery/mysampler response is contained in a
    dictionary under the metadata field.

    The mysampler endpoint is intended to provide the value of a set of PVs at
    regularly spaced time intervals.
    """

    def __init__(self, query: MySamplerQuery, url: Optional[str] = None):
        """Construct an instance for running a mysampler query.

        Args:
            query: The query to run
            url: The location of the mysampler endpoint.  Generated from config if None supplied.
        """
        self.query = query
        self.url = url
        if url is None:
            self.url = f"{config.protocol}://{config.myquery_server}{config.mysampler_path}"

        self.data: Optional[pd.DataFrame] = None
        self.disconnects: Optional[Dict[str, pd.Series]] = None
        self.metadata: Optional[Dict[str, object]] = None

    def run(self):
        """Run a web-based mysampler query.

        Results will be stored in the data, disconnects, and metadata fields.

        Raises:
            RequestException when a problem making the query has occurred
        """

        # Make the request
        opts = self.query.to_web_params()
        r = requests.get(self.url, params=opts)

        # Check if we have any errors
        utils.check_response(r)

        # Single top level key is channels
        channels = r.json()['channels']

        # This will hold the information for the data, disconnects, and metadata fields respectively
        samples = {'Date': []}
        disconnects = {}
        metadata = {}

        # Process the response for each channel
        for idx, channel in enumerate(channels.keys()):
            for key in channels[channel].keys():
                if key == "data":
                    # Values, timestamps kep in shared list 'Date'
                    v = []
                    # Disconnect values (strings)
                    dv = []
                    # Disconnect timestamps
                    dts = []
                    for sample in channels[channel]['data']:
                        # Grab only one datetime series
                        if idx == 0:
                            samples['Date'].append(sample['d'])

                        # Handle disconnect events
                        if 't' in sample.keys():
                            dts.append(sample['d'])
                            dv.append(sample['t'])
                        if 'v' in sample.keys():
                            v.append(sample['v'])
                        else:
                            # Should be identical to x=True in JSON response
                            v.append(None)
                    samples[channel] = v

                    if len(dts) > 0:
                        disconnects[channel] = pd.Series(dv, index=dts, name=channel)

                else:
                    if channel not in metadata.keys():
                        metadata[channel] = {}
                    metadata[channel][key] = channels[channel][key]

        # Update the object with the processed response
        self.data = utils.convert_data_to_dataframe(samples, metadata, self.query.enums_as_strings)
        self.disconnects = disconnects
        self.metadata = metadata
