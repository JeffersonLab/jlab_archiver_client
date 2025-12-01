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
Release are generated automatically when the VERSION file recieves a commit on the main branch.  Artifcats (packages) are deployed to PyPI automatically as this is intended for a broader audience.  Build artifacts are automatically attached to the releases when generated along with the python dependency information for the build (requirements.txt).











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
