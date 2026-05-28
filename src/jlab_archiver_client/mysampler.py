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
"""  # noqa: E501
from typing import Optional, Dict, Tuple

import numpy as np
import pandas as pd
import requests
import ijson
from requests import RequestException

from jlab_archiver_client import utils
from jlab_archiver_client.query import MySamplerQuery
from jlab_archiver_client.config import config

__all__ = ["MySampler"]

from jlab_archiver_client.utils import convert_multivalue_sample


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
        n_samples = int(opts["n"])
        with requests.get(self.url, params=opts, stream=True) as r:
            if r.status_code is not requests.codes.ok:
                raise RequestException(r.status_code)
            if 'v' in opts:
                self.data, self.metadata, self.disconnects = _parse_json_iteratively(
                    r,
                    num_samples=n_samples,
                    enums_as_strings=self.query.enums_as_strings,
                    sig_figs=int(opts["v"]),
                )
            else:
                self.data, self.metadata, self.disconnects = _parse_json_iteratively(
                    r,
                    num_samples=n_samples,
                    enums_as_strings=self.query.enums_as_strings,
                    sig_figs=6,
                )

def _parse_json_iteratively(response: requests.Response, num_samples: int, # noqa: PLR0912, PLR0915
                            enums_as_strings: bool, sig_figs: int | None,
                            ) -> Tuple[pd.DataFrame, Dict[str, dict], Dict[str, pd.Series]]:
    """Stream-parse the mysampler JSON with a ijson.basic_parse approach and manual state machine.

    Note: basic_parse skips the per-event prefix-string construction that ijson.parse does, which is the dominant
    overhead for million-event streams.  This makes it noticeably more memory efficient than ijson.parse.

    Args:
        response: The Response object to parse.  Assumed to be from a "get" call with stream=True.
        num_samples: The number of samples we expect to have
        enums_as_strings: Are enumerated type variables expected as strings or ints.  strings if True
        sig_figs: How many significant figures did the end user want for numeric data.
    """

    response.raw.decode_content = True
    parser = ijson.basic_parse(response.raw, use_float=True)

    # Integer state constants — faster compares than strings, clearer than magic numbers.
    OUTSIDE = 0
    ROOT = 1  # inside the top-level {}
    CHANNELS = 2  # inside the "channels" map
    CHANNEL = 3  # inside one channel's map
    METADATA = 4  # inside a channel's "metadata" map
    DATA = 5  # inside a channel's "data" array
    SAMPLE = 6  # inside one sample's map within data
    SAMPLE_V_ARRAY = 7  # inside a sample's "v": [...] (multivalue PVs only)
    LABELS = 8 # inside a channels enumerated labels section (only for enum types).  Points to an array of label_sets
    LABEL_SET = 9 # inside a label_set object from an array of labels
    LABEL_VALUES = 10 # inside a map of ints to string labels from within a label_set

    state = OUTSIDE
    current_key = None
    metadata_key = None

    # Per-channel
    channel_name = None
    first_channel = None
    is_first_channel = False
    metadata = None
    new_type = None
    is_multivalue = False
    is_integer = False
    is_str = False
    v_array = None
    v_mask = None
    v_idx = 0
    dv = None
    dts = None
    labels = None # Array of label set objects ([{"d": <date>, "values": ["enum0", ...]}]

    # Per-label_set
    label_set_key = None # 'd' or 'values' within a label set
    label_date = None  # a date string
    label_values = None  # array of enum string labels, indexed by corresponding enum int

    # Per-sample (scalars, no dict)
    sample_d = None
    sample_v = None
    sample_t = None
    sample_v_set = False
    sample_v_list = None

    # Aggregates
    dates = np.empty(num_samples, dtype="datetime64[ns]")
    metadata_set: Dict[str, dict] = {}
    disconnects: Dict[str, pd.Series] = {}
    channel_arrays: Dict[str, np.ndarray] = {}

    # Hot-path local references — saves a LOAD_GLOBAL per event for tight inner work.
    nan = np.nan

    for event, value in parser:
        # Ordered by expected frequency in the hot path: value events first
        # (string/number per d/v/t), then map_key, then map/array delimiters.
        if event == "map_key":
            if state == SAMPLE:
                current_key = value
            elif state == METADATA:
                metadata_key = value
            elif state == CHANNEL:
                current_key = value
            elif state == LABELS:
                # should not happen as "labels" only maps to an array
                pass
            elif state == LABEL_SET:
                 label_set_key = value
            elif state == CHANNELS:
                channel_name = value
                if first_channel is None:
                    first_channel = channel_name
                is_first_channel = (channel_name == first_channel)
            # ROOT has only "channels" — no-op.

        elif event == "start_map":
            if state == DATA:
                # New sample — reset scalar slots.
                sample_d = None
                sample_v = None
                sample_t = None
                sample_v_set = False
                state = SAMPLE
            elif state == CHANNEL and current_key == "metadata":
                # This will include both "true" metadata, return count, and labels if they exist.
                metadata = {"metadata": {}}
                state = METADATA
            elif state == LABELS:
                state = LABEL_SET
            elif state == CHANNELS:
                state = CHANNEL
            elif state == ROOT:
                state = CHANNELS
            elif state == OUTSIDE:
                state = ROOT

        elif event == "end_map":
            if state == SAMPLE:
                if is_first_channel:
                    dates[v_idx] = np.datetime64(sample_d)
                if sample_t is not None:
                    dts.append(sample_d)
                    dv.append(sample_t)

                if sample_v_set:
                    if is_multivalue:
                        v_array[v_idx] = convert_multivalue_sample(sample_v, new_type)
                    else:
                        v_array[v_idx] = sample_v
                elif is_multivalue:
                    v_array[v_idx] = convert_multivalue_sample(None, new_type)
                # "v" not set and this is a single valued PV
                elif is_integer:
                    v_mask[v_idx] = True
                elif is_str:
                    v_array[v_idx] = None
                else:
                    v_array[v_idx] = nan

                v_idx += 1
                state = DATA

            elif state == METADATA:
                # End of one channel's metadata — set up its writer state.
                new_type = utils.get_data_types(
                    metadata=metadata["metadata"],
                    enums_as_strings=enums_as_strings,
                    sig_figs=sig_figs,
                )
                is_multivalue = metadata["metadata"]["datasize"] != 1
                # We only want to track if the dtype will be integer.  multivalued PVs will have an object dtype
                is_integer = np.issubdtype(new_type, np.integer) if not is_multivalue else False
                is_str = new_type is str if not is_multivalue else False
                metadata_set[metadata["metadata"]["name"]] = metadata

                if is_multivalue:
                    v_array = np.empty(num_samples, dtype=object)
                    v_mask = None
                elif is_integer:
                    v_array = np.zeros(num_samples, dtype=new_type)
                    v_mask = np.zeros(num_samples, dtype=bool)
                elif is_str:
                    v_array = [None] * num_samples
                    v_mask = None
                else: # float, etc.
                    v_array = np.empty(num_samples, dtype=new_type)
                    v_mask = None
                v_idx = 0
                dv = []
                dts = []
                state = CHANNEL

            elif state == LABEL_SET:
                labels.append({"d": label_date, "value": label_values})
                state = LABELS

            elif state == CHANNEL:
                # End of one channel — stash its array and disconnects.
                if is_integer:
                    column = pd.arrays.IntegerArray(v_array, v_mask, copy=False)
                else:
                    column = v_array
                channel_arrays[channel_name] = column
                disconnects[channel_name] = pd.Series(dv, index=dts, name=channel_name)
                state = CHANNELS

            elif state == CHANNELS:
                state = ROOT
            elif state == ROOT:
                state = OUTSIDE

        elif event == "start_array":
            if state == CHANNEL and current_key == "data":
                state = DATA
            elif state == SAMPLE and current_key == "v":
                sample_v_list = []
                state = SAMPLE_V_ARRAY
            elif state == CHANNEL and current_key == "labels":
                labels = []
                state = LABELS
            elif state == LABEL_SET and label_set_key == "value":
                label_values = []
                state = LABEL_VALUES
            elif state == LABELS:
                pass # no array in LABELS state

        elif event == "end_array":
            if state == DATA:
                state = CHANNEL
            elif state == SAMPLE_V_ARRAY:
                sample_v = sample_v_list
                sample_v_set = True
                sample_v_list = None
                state = SAMPLE
            elif state == LABEL_VALUES:
                state = LABEL_SET
            elif state == LABELS:
                metadata['labels'] = labels
                state = CHANNEL

        # Value event: string / number / integer / boolean / null.
        elif state == SAMPLE:
            if current_key == "d":
                sample_d = value
            elif current_key == "v":
                sample_v = value
                sample_v_set = True
            elif current_key == "t":
                sample_t = value
        elif state == METADATA:
            metadata["metadata"][metadata_key] = value
        elif state == SAMPLE_V_ARRAY:
            sample_v_list.append(value)
        elif state == LABEL_VALUES:
            label_values.append(value)
        elif state == LABEL_SET and label_set_key == "d":
            label_date = value
        elif state == CHANNEL:
            metadata[current_key] = value

    # Build the DataFrame once, no incremental column assignment.
    if first_channel is not None:
        df = pd.DataFrame(
            channel_arrays,
            index=dates,
            copy=False,
        )
    else:
        df = pd.DataFrame()
    df.index.name = "Date"

    return df, metadata_set, disconnects
