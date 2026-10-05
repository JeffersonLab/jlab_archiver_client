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
    * Streaming of large queries to parquet files in time chunks (MySampler.run_to_parquet, requires pyarrow)

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
import copy
import importlib.metadata
import json
import os
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple, List
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import ijson
from requests import RequestException

from jlab_archiver_client import utils
from jlab_archiver_client.query import MySamplerQuery
from jlab_archiver_client.config import config

__all__ = ["MySampler", "DEFAULT_PARQUET_CHUNK_SIZE", "PARQUET_QUERY_KEY", "PARQUET_METADATA_KEY",
           "PARQUET_VERSION_KEY", "default_disconnects_path"]

from jlab_archiver_client.utils import convert_multivalue_sample

DEFAULT_PARQUET_CHUNK_SIZE = 100_000
"""Default maximum number of samples requested at once by MySampler.run_to_parquet"""

PARQUET_QUERY_KEY = "jlab_archiver_client.query"
"""Parquet key-value metadata key holding the JSON description of the query that generated the file"""

PARQUET_METADATA_KEY = "jlab_archiver_client.metadata"
"""Parquet key-value metadata key holding the JSON channel metadata (data file only)"""

PARQUET_VERSION_KEY = "jlab_archiver_client.version"
"""Parquet key-value metadata key holding the JSON jlab_archiver_client version that wrote the file"""


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
        self.data, self.metadata, self.disconnects = self._fetch(self.query)

    def run_to_parquet(self, path: str, chunk_size: int = DEFAULT_PARQUET_CHUNK_SIZE,
                       disconnects_path: Optional[str] = None) -> None:
        """Run the mysampler query in time chunks, streaming the results to parquet files.

        The query is split into consecutive requests of at most chunk_size samples each, so memory usage is bounded by
        the size of one chunk across all PVs rather than by the size of the full query.  Each chunk is written to the
        data file as one row group, and its disconnect events are appended to the disconnects sidecar file.  Problems
        with the query (e.g., unknown PVs) are reported by the first request, before most of the data is requested.

        The data file has a "Date" column (stored as the pandas index) and one column per PV, matching the layout of
        the data field produced by run().  The disconnects sidecar is in long format with columns "pv", "Date", and
        "event".  Both files carry key-value metadata, each value a JSON string:

            * jlab_archiver_client.query: the query that generated the file (both files)
            * jlab_archiver_client.version: the jlab_archiver_client version that wrote the file (both files)
            * jlab_archiver_client.metadata: channel metadata as found in the metadata field (data file only)

        Files are written to temporary ".partial" paths and moved into place only once the whole query succeeds.  On
        success, the metadata field holds the channel metadata.  The data and disconnects fields are left as None.

        Args:
            path: The output path of the data parquet file.
            chunk_size: The maximum number of samples requested from the server at once.
            disconnects_path: The output path of the disconnects sidecar parquet file.  Defaults to
                              "<path stem>-disconnects.parquet".

        Raises:
            RequestException when a problem making the query has occurred
            ImportError if pyarrow is not installed
            ValueError if the arguments are invalid
        """
        pa, pq = _import_pyarrow()
        disconnects_path = self._validate_parquet_args(path, chunk_size, disconnects_path)

        server_timezone = config.server_timezone
        chunk_queries = _chunk_queries(self.query, chunk_size, server_timezone)
        common_metadata = {
            PARQUET_QUERY_KEY: json.dumps(self._describe_query(chunk_size, server_timezone), default=str),
            PARQUET_VERSION_KEY: json.dumps(_package_version()),
        }

        date_type = pa.int64() if self.query.unix_timestamps_ms else pa.timestamp("ns")
        disconnects_schema = pa.schema([("pv", pa.string()), ("Date", date_type), ("event", pa.string())],
                                       metadata=common_metadata)

        data_tmp = f"{path}.partial"
        disconnects_tmp = f"{disconnects_path}.partial"
        data_writer = None
        disconnects_writer = None
        metadata = None
        success = False
        try:
            disconnects_writer = pq.ParquetWriter(disconnects_tmp, disconnects_schema)
            data_schema = None
            for chunk_query in chunk_queries:
                df, chunk_metadata, chunk_disconnects = self._fetch(chunk_query)

                if data_schema is None:
                    data_schema = _data_schema(pa, df, chunk_metadata, self.query)
                table = pa.Table.from_pandas(df, schema=data_schema, preserve_index=True)
                if data_writer is None:
                    data_writer = pq.ParquetWriter(data_tmp,
                                                   table.schema.with_metadata({**table.schema.metadata,
                                                                               **common_metadata}))
                data_writer.write_table(table)

                disconnects_table = _disconnects_table(pa, chunk_disconnects, disconnects_schema,
                                                       self.query.unix_timestamps_ms)
                if disconnects_table.num_rows > 0:
                    disconnects_writer.write_table(disconnects_table)

                metadata = _merge_metadata(metadata, chunk_metadata)

            # Channel metadata is complete only after the last chunk.  Note that pyarrow exposes metadata added here via
            # pq.read_metadata(path).metadata, but not via pq.read_schema(path).metadata.
            data_writer.add_key_value_metadata({
                PARQUET_METADATA_KEY: json.dumps(utils.json_normalize(metadata), default=str),
            })
            success = True
        finally:
            for writer in (data_writer, disconnects_writer):
                if writer is not None:
                    writer.close()
            if not success:
                for tmp in (data_tmp, disconnects_tmp):
                    if os.path.exists(tmp):
                        os.remove(tmp)

        os.replace(data_tmp, path)
        os.replace(disconnects_tmp, disconnects_path)
        self.metadata = metadata

    def _validate_parquet_args(self, path: str, chunk_size: int, disconnects_path: Optional[str]) -> str:
        """Check the run_to_parquet arguments and return the disconnects sidecar path to use."""
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1")
        if self.query.num_samples < 1:
            raise ValueError("num_samples must be at least 1 to write parquet output")
        if disconnects_path is None:
            disconnects_path = default_disconnects_path(path)
        if os.path.abspath(path) == os.path.abspath(disconnects_path):
            raise ValueError("path and disconnects_path must be different files")
        return disconnects_path

    def _fetch(self, query: MySamplerQuery) -> Tuple[pd.DataFrame, Dict[str, dict], Dict[str, pd.Series]]:
        """Make a single mysampler request and parse the response.

        Args:
            query: The query to run.  May differ from self.query when a query is split into chunks.

        Raises:
            RequestException when a problem making the query has occurred
        """
        opts = query.to_web_params()
        sig_figs = int(opts["v"]) if "v" in opts else 6
        with requests.get(self.url, params=opts, stream=True) as r:
            if r.status_code != requests.codes.ok:
                raise RequestException(r.status_code)
            return _parse_json_iteratively(
                r,
                num_samples=int(opts["n"]),
                enums_as_strings=query.enums_as_strings,
                sig_figs=sig_figs,
                unix_timestamps_ms=query.unix_timestamps_ms,
            )

    def _describe_query(self, chunk_size: int, server_timezone: str) -> Dict[str, object]:
        """Describe the query and how it was run for storing alongside output files."""
        with warnings.catch_warnings():
            # to_web_params warns about extra_opts, which the user has already been warned about.
            warnings.simplefilter("ignore")
            web_params = self.query.to_web_params()
        return {
            "endpoint": "mysampler",
            "url": self.url,
            "query": self.query.to_dict(),
            "web_params": web_params,
            "chunk_size": chunk_size,
            "server_timezone": server_timezone,
        }


def default_disconnects_path(path: str) -> str:
    """Get the default disconnects sidecar path for a data file path, i.e., <path stem>-disconnects.parquet"""
    stem, ext = os.path.splitext(path)
    if ext.lower() != ".parquet":
        stem = path
    return f"{stem}-disconnects.parquet"


def _import_pyarrow():
    """Import pyarrow, which is only needed for parquet output."""
    try:
        import pyarrow as pa  # noqa: PLC0415
        import pyarrow.parquet as pq  # noqa: PLC0415
    except ImportError as e:
        raise ImportError("Parquet output requires pyarrow.  Install it with "
                          "'pip install jlab_archiver_client[parquet]'.") from e
    return pa, pq


def _package_version() -> Optional[str]:
    """Get the installed jlab_archiver_client version."""
    try:
        return importlib.metadata.version("jlab_archiver_client")
    except importlib.metadata.PackageNotFoundError:
        return None


def _format_start(wall_time: datetime) -> str:
    """Format a wall-clock time as a MySamplerQuery start string, keeping milliseconds only when needed."""
    if wall_time.microsecond:
        return wall_time.isoformat(sep=" ", timespec="milliseconds")
    return wall_time.isoformat(sep=" ")


def _chunk_queries(query: MySamplerQuery, chunk_size: int, server_timezone: str) -> List[MySamplerQuery]:
    """Split a mysampler query into consecutive queries of at most chunk_size samples.

    myquery takes the start time as a wall-clock time in the server's timezone and places samples at fixed intervals
    of absolute time.  Chunk start times are therefore computed in absolute time and converted back to wall-clock time
    so that the chunks reproduce the sample times of the original query across daylight saving time transitions.

    When clocks fall back, wall-clock times are repeated and myquery interprets them as their first occurrence, so a
    chunk can not start during the second occurrence.  Chunk boundaries that land there are pushed forward to the
    first sample that can be requested, making the chunk before it larger than chunk_size.

    Args:
        query: The query to split
        chunk_size: The maximum number of samples per chunk (except as noted above)
        server_timezone: The IANA timezone the myquery server uses to interpret start times
    """
    tz = ZoneInfo(server_timezone)
    num_samples = query.num_samples
    # myquery interprets ambiguous start times as their first occurrence, the same as fold=0.
    start_utc = datetime.fromisoformat(query.start).replace(tzinfo=tz).astimezone(timezone.utc)
    step = timedelta(milliseconds=query.interval)

    # (first sample index, start string) of each chunk
    bounds = [(0, query.start)]
    idx = chunk_size
    while idx < num_samples:
        local = (start_utc + idx * step).astimezone(tz)
        if local.fold == 1 and local.replace(fold=0).utcoffset() != local.utcoffset():
            # Second occurrence of a repeated wall-clock time - not something myquery can be asked for.
            idx += 1
            continue
        bounds.append((idx, _format_start(local.replace(tzinfo=None))))
        idx += chunk_size

    out = []
    for i, (first, start) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else num_samples
        chunk = copy.copy(query)
        chunk.start = start
        chunk.num_samples = end - first
        out.append(chunk)
    return out


def _data_schema(pa, df: pd.DataFrame, metadata: Dict[str, dict], query: MySamplerQuery):
    """Build the arrow schema for the data file from channel metadata.

    The schema is fixed from metadata rather than inferred from the data so that every chunk has the same schema, even
    when a chunk only contains missing values for a PV.  The Date index field goes last, where pandas places index
    columns.  Otherwise, pyarrow records the wrong pandas dtypes and nullable integer columns are not restored on read.
    """
    sig_figs = int(query.sig_figs) if query.sig_figs is not None else 6
    fields = []
    for name in df.columns:
        channel_metadata = metadata[name]["metadata"]
        new_type = utils.get_data_types(metadata=channel_metadata, enums_as_strings=query.enums_as_strings,
                                        sig_figs=sig_figs)
        arrow_type = pa.string() if new_type is str else pa.from_numpy_dtype(np.dtype(new_type))
        if channel_metadata["datasize"] != 1:
            arrow_type = pa.list_(arrow_type)
        fields.append(pa.field(name, arrow_type))
    fields.append(pa.field("Date", pa.int64() if query.unix_timestamps_ms else pa.timestamp("ns")))
    return pa.schema(fields)


def _disconnects_table(pa, disconnects: Dict[str, pd.Series], schema, unix_timestamps_ms: bool):
    """Convert a chunk's disconnects into a long-format arrow table with pv, Date, and event columns."""
    pvs = []
    dates = []
    events = []
    for pv, series in disconnects.items():
        pvs.extend([pv] * len(series))
        dates.extend(series.index)
        events.extend(series.values)

    if unix_timestamps_ms:
        date_values = np.asarray(dates, dtype="int64")
    else:
        date_values = pd.to_datetime(dates).to_numpy(dtype="datetime64[ns]")

    return pa.table({
        "pv": pa.array(pvs, type=pa.string()),
        "Date": pa.array(date_values, type=schema.field("Date").type),
        "event": pa.array(events, type=pa.string()),
    }, schema=schema)


def _merge_metadata(merged: Optional[Dict[str, dict]], chunk: Dict[str, dict]) -> Dict[str, dict]:
    """Combine channel metadata from one chunk into the metadata of the chunks before it.

    returnCount is summed across chunks, and enum label sets are combined without duplicates.
    """
    if merged is None:
        return copy.deepcopy(chunk)

    for name, channel in chunk.items():
        target = merged[name]
        target["returnCount"] = target.get("returnCount", 0) + channel.get("returnCount", 0)
        if "labels" in channel:
            labels = target.setdefault("labels", [])
            known = [json.dumps(label, sort_keys=True, default=str) for label in labels]
            for label in channel["labels"]:
                key = json.dumps(label, sort_keys=True, default=str)
                if key not in known:
                    labels.append(copy.deepcopy(label))
                    known.append(key)
    return merged


def _parse_json_iteratively(response: requests.Response, num_samples: int, # noqa: PLR0912, PLR0915
                            enums_as_strings: bool, sig_figs: int | None, unix_timestamps_ms: bool,
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
    if unix_timestamps_ms:
        dates = np.empty(num_samples, dtype="int64")
    else:
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
                    if unix_timestamps_ms:
                        dates[v_idx] = sample_d
                    else:
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
