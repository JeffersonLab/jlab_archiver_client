# jlab_archiver_client

A Python client library for querying the Jefferson Lab EPICS archiver (MYA) via the myquery web service.

It is intended for non-mission critical applications such as data analysis and uses the CEBAF read-only archiver deployment by default.  CEBAF mission critical applications should use internal libraries that provide direct access to the operations-oriented deployment.

## Overview
This package provides a convenient Python interface to the myquery web service, making archived EPICS Process Variable (PV) data easily accessible for analysis. Data is returned in familiar pandas data structures (Series and DataFrames) with datetime indices for time-series analysis.

The package supports multiple myquery endpoints:
- **interval**: Retrieve all archived events for a PV over a time range
- **mysampler**: Get regularly-spaced samples across multiple PVs
- **mystats**: Compute statistical aggregations over time bins
- **point**: Retrieve a single event at a specific time
- **channel**: Search and discover available channel names

## Key Features
- **Pandas Integration**: All data returned as pandas Series, DataFrames, and simple dictionaries
- **Datetime Indexing**: Time-series data with proper datetime indices
- **Disconnect Handling**: Non-update events tracked separately
- **Parallel Queries**: Limited support for multi-channel queries with concurrent execution
- **Type Safety**: Query builder classes with parameter validation
- **Enum Support**: Option to convert enum values to strings
- **Thread-Safe Config**: Runtime configuration changes supported
- **History Deployment**: Defaults to Jefferson Lab's read-only history deployment
- **Command Line Interface**: Command-line tools for quick queries
- **Parquet Streaming**: Stream large mysampler queries to parquet files in time chunks with bounded memory use

## API Documentation
Documentation can be found [here](https://jeffersonlab.github.io/jlab_archiver_client/)

## See Also
- [PyPI](https://pypi.org/project/jlab-archiver-client)
- [myquery](https://github.com/JeffersonLab/myquery)
- [jmyapi](https://github.com/JeffersonLab/jmyapi)
- [wave](https://github.com/JeffersonLab/wave)

## Installation

```bash
pip install jlab_archiver_client

# Include optional support for streaming mysampler results to parquet files
pip install jlab_archiver_client[parquet]
```

## Developer Quick Start Guide
Download the repo, create a virtual environment using pythong 3.11+, and install the package in editable mode with 
development dependencies.  Then develop using your preferred IDE, etc.

*Linux (bash)*
```bash
git clone https://github.com/JeffersonLab/jlab_archiver_client
cd jlab_archiver_client
python3.11 -m venv venv
# bash
source venv/bin/activate
pip install -e .[dev]
```

*Linux (tcsh / csh)*
```csh
git clone https://github.com/JeffersonLab/jlab_archiver_client
cd jlab_archiver_client
python3.11 -m venv venv
# tcsh / csh
source venv/bin/activate.csh
pip install -e '.[dev]'
```

*Windows (PowerShell)*
```PowerShell
git clone https://github.com/JeffersonLab/jlab_archiver_client
cd jlab_archiver_client
\path\to\python3 -m venv venv
venv\Scripts\activate.ps1
pip install -e .[dev]
```

To start the provided database.
```
docker compose up
```

### Testing
This application supports testing using `pytest` and code coverage using `coverage`.  Configuration in `pyproject.toml`.
Integration tests required that the provided docker container(s) are running.  [Tests](https://github.com/JeffersonLab/jlab_archiver_client/.github/workflows/test.yml) are automatically run on appropriate triggers.

| Test Type            | Command                                  |
|----------------------|------------------------------------------|
| Unit                 | `pytest test/unit`                       |
| Integration          | `pytest test/integration`                |
| Unit & Integration   | `pytest`                                 |
| Code Coverage Report | `pytest --cov-report=html`               |
| Linting              | `ruff  check [--fix]`                    |

### Documentation
Documentation is done in Sphinx and automatically built and published to GitHub Pages when triggering a new [release](https://github.com/JeffersonLab/jlab_archiver_client/.github/workflows/release.yml).  To build documentation, run this commands from the project root.
```
sphinx-build -b html docsrc/source build/docs
```

### Release
Release are generated automatically when the VERSION file receives a commit on the main branch.  Artifacts (packages) are deployed to PyPI automatically as this is intended for a broader audience.  Build artifacts are automatically attached to the releases when generated along with the python dependency information for the build (requirements.txt).











## Configuration (Optional)

The package come pre-configured for use with CEBAF's production myquery service.  This requires authentication when used offsite, which this package does not currently support.

If you need to access a non-standard myquery or the development container bundled in this repo, then configure the myquery server first.

```python
from jlab_archiver_client.config import config

# For production
config.set(myquery_server="epicsweb.jlab.org", protocol="https")

# For local development/testing
config.set(myquery_server="localhost:8080", protocol="http")
```

## Usage Examples

### MySampler - Regularly Sampled Data

Query multiple PVs at regularly spaced time intervals. Useful for synchronized sampling across channels.

```python
from jlab_archiver_client import MySampler, MySamplerQuery
from datetime import datetime

# Query two channels with 30-minute intervals
query = MySamplerQuery(
    start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
    interval=1_800_000,  # 30 minutes in milliseconds
    num_samples=15,
    pvlist=["R12XGMES", "R13XGMES"],
)

mysampler = MySampler(query)
mysampler.run()

# Access the data as a DataFrame with datetime index
print(mysampler.data)
                     R12XGMES  R13XGMES
Date                                   
2019-08-12 00:00:00    57.265    44.813
2019-08-12 00:30:00    57.265    44.811
2019-08-12 01:00:00    57.265    44.811
2019-08-12 01:30:00    57.265    44.811
...

# Access disconnect events - dictionary of chanel_names: pd.Series
print(mysampler.disconnects)
{}

# Access channel metadata
print(mysampler.metadata)
{'R12XGMES': {'metadata': {'name': 'R12XGMES', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'hstmya3', 'ioc': None, 'active': True}, 'returnCount': 15}, 'R13XGMES': {'metadata': {'name': 'R13XGMES', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'hstmya0', 'ioc': None, 'active': True}, 'returnCount': 15}}

```

### MySampler - Streaming to Parquet

`MySampler.run()` holds the full result in memory.  For large queries, `MySampler.run_to_parquet()` instead splits
the query into time chunks of at most `chunk_size` samples, requests them one at a time, and writes each chunk to disk
before requesting the next.  Memory use is bounded by one chunk across all PVs, and problems such as an unknown PV are
reported by the first request rather than after most of the data has been transferred.  This requires `pyarrow`
(`pip install jlab_archiver_client[parquet]`).

```python
from jlab_archiver_client import MySampler, MySamplerQuery
from datetime import datetime

query = MySamplerQuery(
    start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
    interval=1_800_000,  # 30 minutes in milliseconds
    num_samples=15,
    pvlist=["channel1", "channel2"],
)

# Writes samples.parquet and samples-disconnects.parquet
MySampler(query).run_to_parquet("samples.parquet", chunk_size=100_000)
```

Two files are written.  Files are only moved into place once the whole query succeeds, so a failed query leaves no
partial output.

| File                          | Contents                                                                                                                          |
|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| `samples.parquet`             | The same table as `MySampler.data`: a `Date` index and one column per PV.  Each chunk is one row group.                           |
| `samples-disconnects.parquet` | Disconnect events (the contents of `MySampler.disconnects`) in long format, with `pv`, `Date`, and `event` columns.                |

Both files include key-value metadata entries whose values are JSON strings.

| Key                              | Data file | Disconnects file | Contents                                                                                |
|----------------------------------|-----------|------------------|-----------------------------------------------------------------------------------------|
| `jlab_archiver_client.query`     | Yes       | Yes              | The query that generated the file: query parameters, web parameters, URL, chunk size    |
| `jlab_archiver_client.version`   | Yes       | Yes              | The jlab_archiver_client version that wrote the file                                    |
| `jlab_archiver_client.metadata`  | Yes       | No               | Channel metadata, the same as `MySampler.metadata`                                      |

Read the files back with pandas, and read their metadata with `pyarrow.parquet.read_metadata`.  Use `read_metadata`
rather than `read_schema`, since the channel metadata is added when the data file is closed and is not part of the
stored arrow schema.

```python
import json
import pandas as pd
import pyarrow.parquet as pq

# Data - the dtypes match MySampler.data (e.g., float32, nullable Int16 for enums)
data = pd.read_parquet("samples.parquet")
print(data.head())
                      channel1  channel2
Date                                    
2019-08-12 00:00:00        NaN      <NA>
2019-08-12 00:30:00  95.970596      <NA>
2019-08-12 01:00:00  95.303299         3
2019-08-12 01:30:00  94.359398         3
2019-08-12 02:00:00  94.811401         3

# Disconnect events from the sidecar file
disconnects = pd.read_parquet("samples-disconnects.parquet")
print(disconnects)
         pv                Date      event
0  channel1 2019-08-12 00:00:00  UNDEFINED
1  channel2 2019-08-12 00:00:00  UNDEFINED
2  channel2 2019-08-12 00:30:00  UNDEFINED

# Disconnect events for a single PV
print(disconnects[disconnects.pv == "channel2"].set_index("Date").event)

# Metadata from the data file
data_kv = pq.read_metadata("samples.parquet").metadata
query_info = json.loads(data_kv[b"jlab_archiver_client.query"])
channel_metadata = json.loads(data_kv[b"jlab_archiver_client.metadata"])
version = json.loads(data_kv[b"jlab_archiver_client.version"])

print(query_info["query"])
{'start': '2019-08-12 00:00:00', 'interval': 1800000, 'num_samples': 15, 'pvlist': ['channel1', 'channel2'], 'deployment': 'history', 'sample_strategy': 'stream', 'frac_time_digits': 9, 'sig_figs': 6, 'data_updates_only': False, 'enums_as_strings': False, 'unix_timestamps_ms': False, 'adjust_time_to_server_offset': False, 'extra_opts': {}}
print(query_info["web_params"])
{'c': 'channel1,channel2', 'b': '2019-08-12T00:00:00', 'n': 15, 'm': 'history', 's': 1800000, 'x': 's', 'f': 9, 'v': 6}
print(channel_metadata["channel2"])
{'metadata': {'name': 'channel2', 'datatype': 'DBR_ENUM', 'datasize': 1, 'datahost': 'mya', 'ioc': None, 'active': True}, 'labels': [{'d': '2016-08-12 13:00:49.000000000', 'value': ['BEAM SYNC ONLY', 'PULSE MODE VL', 'TUNE MODE', 'CW MODE (DC)', 'USER MODE']}], 'returnCount': 15}

# Metadata from the disconnects file - the same query description
sidecar_kv = pq.read_metadata("samples-disconnects.parquet").metadata
sidecar_query_info = json.loads(sidecar_kv[b"jlab_archiver_client.query"])
print(sidecar_query_info == query_info)
True
```

Chunk start times are computed in absolute time so that chunked queries return the same sample times as a single
query across daylight saving time transitions.  This uses the timezone of the myquery server, which defaults to
`America/New_York` and can be changed with `config.set(server_timezone=...)`.  myquery cannot be asked to start a
query during the repeated hour when clocks fall back, so a chunk boundary that lands there is moved to the end of that
hour.


### Interval - All Events in Time Range

Retrieve all archived events for a single PV. Best for detailed event history.  Also includes option to run multiple interval queries in parallel and return combined results.  This results in a single DataFrame with a row for each timestamp that any *single* channel updated.

**Note:** Example assumes you are running the provided docker container.

```python
from jlab_archiver_client import Interval, IntervalQuery
from datetime import datetime

# Query a single channel for all events
query = IntervalQuery(
    channel="channel100",
    begin=datetime(2018, 4, 24),
    end=datetime(2018, 5, 1),
    deployment="docker"
)

interval = Interval(query)
interval.run()

# Access data as a pandas Series
print(interval.data)
# 2018-04-24 06:25:01    0.000
# 2018-04-24 06:25:05    5.911
# 2018-04-24 11:18:19    5.660
# ...

# Access disconnect events separately
print(interval.disconnects)

# For multiple channels, use parallel queries
data, disconnects, metadata = Interval.run_parallel(
    pvlist=["channel2", "channel3"],
    begin=datetime(2019, 8, 12, 0, 0, 0),
    end=datetime(2019, 8, 12, 1, 20, 45),
    deployment="docker",
    prior_point=True
)
```

### MyStats - Statistical Aggregations

Compute statistics (min, max, mean, etc.) over time bins. Efficient for analyzing trends.

**Note:** Statistical computations are performed on the myquery server which saves on outbound traffic, but still requires all data be streamed to the myquery server.

**Note:** Example assumes you are running the provided docker container.

```python
from jlab_archiver_client import MyStats, MyStatsQuery
from datetime import datetime
import pandas as pd

# Query statistics with 1-hour bins
query = MyStatsQuery(
    start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
    end=datetime.strptime("2019-08-13 00:00:00", "%Y-%m-%d %H:%M:%S"),
    num_bins=24,  # 24 bins (one hour per bin)
    pvlist=["channel1", "channel100"],
    deployment="docker"
)

mystats = MyStats(query)
mystats.run()

# Access data as MultiIndex DataFrame (timestamp, stat)
print(mystats.data)
#                                   channel1    channel100
# timestamp           stat
# 2019-08-12 00:00:00 duration    3594.421033   3600.000000
#                     eventCount  1716.000000      2.000000
#                     max           96.952400      5.658000
#                     mean          94.964400      5.658000
# ...

# Query specific statistics at a time
print(mystats.data.loc['2019-08-12 00:00:00'])

# Query specific stat and time
print(mystats.data.loc[(pd.Timestamp('2019-08-12 00:00:00'), 'mean'), 'channel1'])
# 94.9644

# Query a range of times and stats using IndexSlice
idx = pd.IndexSlice
print(mystats.data.loc[idx['2019-08-12 00:00:00':'2019-08-12 12:00:00', ['mean', 'max']], :])
```

### Point - Single Event Query

Retrieve a single event at or near a specific timestamp.

**Note:** Example assumes you are running the provided docker container.

```python
from jlab_archiver_client import Point, PointQuery
from datetime import datetime

# Get the event at or before a specific time
query = PointQuery(
    channel="channel1",
    time=datetime.strptime("2019-08-12 12:00:00", "%Y-%m-%d %H:%M:%S"),
    deployment="docker"
)

point = Point(query)
point.run()

# Access event data
print(point.event)
# {'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya',
#  'data': {'d': '2019-08-12 11:55:22', 'v': 6.20794}}
```

### Channel - Search for Channels

Discover available channels and their metadata using SQL-style pattern matching.

**Note:** Example assumes you are running the provided docker container.

```python
from jlab_archiver_client import Channel, ChannelQuery

# Search for all channels starting with "channel10"
query = ChannelQuery(pattern="channel10%", deployment="docker")

channel = Channel(query)
channel.run()

# Access matching channels
print(channel.matches)
# [{'name': 'channel100', 'datatype': 'DBR_DOUBLE', 'datasize': 1, ...},
#  {'name': 'channel101', 'datatype': 'DBR_DOUBLE', 'datasize': 1, ...}]
```

### Command Line Tools
This package includes command-line tools for quick queries.  After installation, use the `--help` or `-h` flag for usage information.

| Command                          | Description                                              |
|----------------------------------|----------------------------------------------------------|
| `jac-interval`                   | Query all events for a single PV over a time range       |
| `jac-mysampler`                  | Regularly sample multiple PVs                            |
| `jac-mystats`                    | Compute statistical aggregations over time bins          |
| `jac-point`                      | Retrieve a single event at or near a specific time       |
| `jac-channel`                    | Search and discover available channel names and metadata |

`jac-mysampler` streams its results to parquet when the output file ends in `.parquet`.  See
[MySampler - Streaming to Parquet](#mysampler---streaming-to-parquet) for the file layout and how to read the files.

```bash
# Writes samples.parquet and samples-disconnects.parquet
jac-mysampler -c channel1 channel2 -b "2019-08-12 00:00:00" -i 1800000 -n 15 -o samples.parquet

# Set the number of samples per request and the disconnects file path
jac-mysampler -c channel1 channel2 -b "2019-08-12 00:00:00" -i 1000 -n 10000000 -o samples.parquet \
    --chunk-size 50000 --disconnects-output events.parquet
```
