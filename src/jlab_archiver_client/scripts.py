"""Command-line interface scripts for Jefferson Lab Archiver myquery endpoints.

This module provides command-line entry points for each myquery endpoint, allowing
users to query archived EPICS PV data directly from the command line. Each function
corresponds to a specific myquery endpoint and exposes all relevant options.

Available Commands:
    * jac-interval: Query all events in a time range for a single channel
    * jac-mysampler: Query regularly sampled data across multiple PVs
    * jac-mystats: Query statistical aggregations over time bins
    * jac-point: Query a single event at a specific time
    * jac-channel: Search for channel names using SQL patterns

Each command supports JSON or CSV output and can be configured to use different
myquery server deployments.

Example::

    # Query interval data for a single channel
    $ jac-interval -c channel100 -b "2019-08-12 00:00:00" -e "2019-08-12 01:00:00" -o output.csv

    # Query sampled data for multiple channels
    $ jac-mysampler -c channel1 channel2 -b "2019-08-12 00:00:00" -i 60000 -n 100 -o output.csv

    # Get statistics for channels
    $ jac-mystats -c channel1 channel2 -b "2019-08-12 00:00:00" -e "2019-08-13 00:00:00" --num-bins 24 -o output.csv

    # Find a point value at a specific time
    $ jac-point -c channel100 -t "2019-08-12 12:00:00" -o output.json

    # Search for channels
    $ jac-channel -p "channel10%" -o output.json

See Also:
    jlab_archiver_client.query: Query builder classes
    jlab_archiver_client.config: Configuration settings
"""
import argparse
import sys
import json
from datetime import datetime
from typing import Optional

from jlab_archiver_client.config import config
from jlab_archiver_client.query import (
    IntervalQuery, MySamplerQuery, MyStatsQuery, PointQuery, ChannelQuery
)
from jlab_archiver_client.interval import Interval
from jlab_archiver_client.mysampler import MySampler
from jlab_archiver_client.mystats import MyStats
from jlab_archiver_client.point import Point
from jlab_archiver_client.channel import Channel
from jlab_archiver_client.utils import json_normalize


def _parse_datetime(dt_str: str) -> datetime:
    """Parse a datetime string in ISO format or common formats.

    Args:
        dt_str: Datetime string to parse

    Returns:
        Parsed datetime object
    """
    # Try ISO format first
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        pass

    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Unable to parse datetime: {dt_str}")


def _configure_server(server: Optional[str], protocol: Optional[str]):
    """Configure the myquery server settings.

    Args:
        server: Server hostname (with optional port)
        protocol: Protocol (http or https)
    """
    if server:
        config.set(myquery_server=server)
    if protocol:
        config.set(protocol=protocol)


def interval_main():
    """Command-line interface for the interval endpoint.

    Retrieves all archived events for a single channel within a time range.
    """
    parser = argparse.ArgumentParser(
        description="Query all events in a time range for a single channel from the myquery interval endpoint"
    )

    # Required arguments
    parser.add_argument('-c', '--channel', required=True, type=str,
                        help='PV channel name to query')
    parser.add_argument('-b', '--begin', required=True, type=str,
                        help='Start time (ISO format or "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('-e', '--end', required=True, type=str,
                        help='End time (ISO format or "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('-o', '--output', required=False, type=str, default=None,
                        help='Output file path (.csv or .json). If not specified, outputs to stdout')

    # Optional query parameters
    parser.add_argument('-m', '--deployment', type=str, default='history',
                        help='MYA deployment (default: history)')
    parser.add_argument('-l', '--bin-limit', type=int, default=None,
                        help='Maximum points before sampling kicks in')
    parser.add_argument('-t', '--sample-type', type=str, default=None,
                        choices=['graphical', 'eventsimple', 'myget', 'mysampler'],
                        help='Sampling algorithm to use')
    parser.add_argument('-f', '--frac-time-digits', type=int, default=0,
                        help='Fractional seconds digits (default: 0)')
    parser.add_argument('-v', '--sig-figs', type=int, default=6,
                        help='Significant figures for values (default: 6)')

    # Boolean flags
    parser.add_argument('-d', '--data-updates-only', action='store_true',
                        help='Include only value changes (not disconnects)')
    parser.add_argument('-p', '--prior-point', action='store_true',
                        help='Include most recent update prior to start time')
    parser.add_argument('-s', '--enums-as-strings', action='store_true',
                        help='Return enum values as strings instead of ints')
    parser.add_argument('-u', '--unix-timestamps-ms', action='store_true',
                        help='Return timestamps as milliseconds since Unix epoch')
    parser.add_argument('-a', '--adjust-time-to-server-offset', action='store_true',
                        help='Localize timestamps to myquery server timezone')
    parser.add_argument('-i', '--integrate', action='store_true',
                        help='Integrate values (float PVs only)')

    # Server configuration
    parser.add_argument('--server', type=str, default=None,
                        help='Myquery server hostname (default: epicsweb.jlab.org)')
    parser.add_argument('--protocol', type=str, default=None, choices=['http', 'https'],
                        help='Protocol to use (default: http)')

    args = parser.parse_args()

    # Configure server
    _configure_server(args.server, args.protocol)

    # Parse datetimes
    try:
        begin = _parse_datetime(args.begin)
        end = _parse_datetime(args.end)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create query
    query = IntervalQuery(
        channel=args.channel,
        begin=begin,
        end=end,
        deployment=args.deployment,
        bin_limit=args.bin_limit,
        sample_type=args.sample_type,
        frac_time_digits=args.frac_time_digits,
        sig_figs=args.sig_figs,
        data_updates_only=args.data_updates_only,
        prior_point=args.prior_point,
        enums_as_strings=args.enums_as_strings,
        unix_timestamps_ms=args.unix_timestamps_ms,
        adjust_time_to_server_offset=args.adjust_time_to_server_offset,
        integrate=args.integrate
    )

    # Execute query
    try:
        interval = Interval(query)
        interval.run()

        # Save output
        if args.output is None:
            # Output to stdout as JSON
            output_data = json_normalize({
                'data': interval.data,
                'disconnects': interval.disconnects,
                'metadata': interval.metadata
            })
            print(json.dumps(output_data, indent=2, default=str))
        elif args.output.endswith('.json'):
            output_data = json_normalize({
                'data': interval.data,
                'disconnects': interval.disconnects,
                'metadata': interval.metadata
            })
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            print(f"Successfully saved results to {args.output}")
        elif args.output.endswith('.csv'):
            interval.data.to_csv(args.output)
            print(f"Successfully saved results to {args.output}")
        else:
            print("Error: Output file must be .csv or .json", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        sys.exit(1)


def mysampler_main():
    """Command-line interface for the mysampler endpoint.

    Retrieves regularly sampled data for multiple channels.
    """
    parser = argparse.ArgumentParser(
        description="Query regularly sampled data across multiple PVs from the myquery mysampler endpoint"
    )

    # Required arguments
    parser.add_argument('-c', '--channels', required=True, nargs='+', type=str,
                        help='PV channel names to query (space-separated)')
    parser.add_argument('-b', '--begin', required=True, type=str,
                        help='Start time (ISO format or "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('-i', '--interval', required=True, type=int,
                        help='Interval between samples in milliseconds')
    parser.add_argument('-n', '--num-samples', required=True, type=int,
                        help='Number of samples to retrieve')
    parser.add_argument('-o', '--output', required=False, type=str, default=None,
                        help='Output file path (.csv or .json). If not specified, outputs to stdout')

    # Optional query parameters
    parser.add_argument('-m', '--deployment', type=str, default='history',
                        help='MYA deployment (default: history)')
    parser.add_argument('-x', '--sample-strategy', type=str, default=None,
                        choices=['n_queries', 'stream'],
                        help='Sampling strategy: n_queries (efficient for many updates per sample) or '
                             'stream (efficient for few updates per sample). None uses myquery default.')

    # Boolean flags
    parser.add_argument('-d', '--data-updates-only', action='store_true',
                        help='Ignore disconnect events and assume previous value')
    parser.add_argument('-s', '--enums-as-strings', action='store_true',
                        help='Return enum values as strings instead of ints')
    parser.add_argument('-u', '--unix-timestamps-ms', action='store_true',
                        help='Return timestamps as milliseconds since Unix epoch')
    parser.add_argument('-a', '--adjust-time-to-server-offset', action='store_true',
                        help='Localize timestamps to myquery server timezone')

    # Server configuration
    parser.add_argument('--server', type=str, default=None,
                        help='Myquery server hostname (default: epicsweb.jlab.org)')
    parser.add_argument('--protocol', type=str, default=None, choices=['http', 'https'],
                        help='Protocol to use (default: http)')

    args = parser.parse_args()

    # Configure server
    _configure_server(args.server, args.protocol)

    # Parse datetime
    try:
        start = _parse_datetime(args.begin)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create query
    query = MySamplerQuery(
        start=start,
        interval=args.interval,
        num_samples=args.num_samples,
        pvlist=args.channels,
        deployment=args.deployment,
        sample_strategy=args.sample_strategy,
        data_updates_only=args.data_updates_only,
        enums_as_strings=args.enums_as_strings,
        unix_timestamps_ms=args.unix_timestamps_ms,
        adjust_time_to_server_offset=args.adjust_time_to_server_offset
    )

    # Execute query
    try:
        mysampler = MySampler(query)
        mysampler.run()

        # Save output
        if args.output is None:
            # Output to stdout as JSON
            output_data = json_normalize({
                'data': mysampler.data,
                'disconnects': mysampler.disconnects,
                'metadata': mysampler.metadata
            })
            print(json.dumps(output_data, indent=2, default=str))
        elif args.output.endswith('.json'):
            output_data = json_normalize({
                'data': mysampler.data,
                'disconnects': mysampler.disconnects,
                'metadata': mysampler.metadata
            })
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            print(f"Successfully saved results to {args.output}")
        elif args.output.endswith('.csv'):
            mysampler.data.to_csv(args.output)
            print(f"Successfully saved results to {args.output}")
        else:
            print("Error: Output file must be .csv or .json", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        sys.exit(1)


def mystats_main():
    """Command-line interface for the mystats endpoint.

    Retrieves statistical aggregations over time bins for multiple channels.
    """
    parser = argparse.ArgumentParser(
        description="Query statistical aggregations over time bins from the myquery mystats endpoint"
    )

    # Required arguments
    parser.add_argument('-c', '--channels', required=True, nargs='+', type=str,
                        help='PV channel names to query (space-separated)')
    parser.add_argument('-b', '--begin', required=True, type=str,
                        help='Start time (ISO format or "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('-e', '--end', required=True, type=str,
                        help='End time (ISO format or "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('-o', '--output', required=False, type=str, default=None,
                        help='Output file path (.csv or .json). If not specified, outputs to stdout')

    # Optional query parameters
    parser.add_argument('--num-bins', type=int, default=1,
                        help='Number of time bins for statistics (default: 1)')
    parser.add_argument('-m', '--deployment', type=str, default='history',
                        help='MYA deployment (default: history)')
    parser.add_argument('-f', '--frac-time-digits', type=int, default=0,
                        help='Fractional seconds digits (default: 0)')
    parser.add_argument('-v', '--sig-figs', type=int, default=6,
                        help='Significant figures for values (default: 6)')

    # Boolean flags
    parser.add_argument('-d', '--data-updates-only', action='store_true',
                        help='Ignore disconnect events and assume previous value')
    parser.add_argument('-s', '--enums-as-strings', action='store_true',
                        help='Return enum values as strings instead of ints')
    parser.add_argument('-u', '--unix-timestamps-ms', action='store_true',
                        help='Return timestamps as milliseconds since Unix epoch')
    parser.add_argument('-a', '--adjust-time-to-server-offset', action='store_true',
                        help='Localize timestamps to myquery server timezone')

    # Server configuration
    parser.add_argument('--server', type=str, default=None,
                        help='Myquery server hostname (default: epicsweb.jlab.org)')
    parser.add_argument('--protocol', type=str, default=None, choices=['http', 'https'],
                        help='Protocol to use (default: http)')

    args = parser.parse_args()

    # Configure server
    _configure_server(args.server, args.protocol)

    # Parse datetimes
    try:
        start = _parse_datetime(args.begin)
        end = _parse_datetime(args.end)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create query
    query = MyStatsQuery(
        pvlist=args.channels,
        start=start,
        end=end,
        num_bins=args.num_bins,
        deployment=args.deployment,
        frac_time_digits=args.frac_time_digits,
        sig_figs=args.sig_figs,
        data_updates_only=args.data_updates_only,
        enums_as_strings=args.enums_as_strings,
        unix_timestamps_ms=args.unix_timestamps_ms,
        adjust_time_to_server_offset=args.adjust_time_to_server_offset
    )

    # Execute query
    try:
        mystats = MyStats(query)
        mystats.run()

        # Save output
        if args.output is None:
            # Output to stdout as JSON
            output_data = json_normalize({
                'data': mystats.data,
                'metadata': mystats.metadata
            })
            print(json.dumps(output_data, indent=2, default=str))
        elif args.output.endswith('.json'):
            output_data = json_normalize({
                'data': mystats.data,
                'metadata': mystats.metadata
            })
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            print(f"Successfully saved results to {args.output}")
        elif args.output.endswith('.csv'):
            mystats.data.to_csv(args.output)
            print(f"Successfully saved results to {args.output}")
        else:
            print("Error: Output file must be .csv or .json", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        sys.exit(1)


def point_main():
    """Command-line interface for the point endpoint.

    Retrieves a single event at or near a specific time for a channel.
    """
    parser = argparse.ArgumentParser(
        description="Query a single event at a specific time from the myquery point endpoint"
    )

    # Required arguments
    parser.add_argument('-c', '--channel', required=True, type=str,
                        help='PV channel name to query')
    parser.add_argument('-t', '--time', required=True, type=str,
                        help='Time to query (ISO format or "YYYY-MM-DD HH:MM:SS")')
    parser.add_argument('-o', '--output', required=False, type=str, default=None,
                        help='Output file path (.json). If not specified, outputs to stdout')

    # Optional query parameters
    parser.add_argument('-m', '--deployment', type=str, default='history',
                        help='MYA deployment (default: history)')
    parser.add_argument('-f', '--frac-time-digits', type=int, default=0,
                        help='Fractional seconds digits (default: 0)')
    parser.add_argument('-v', '--sig-figs', type=int, default=6,
                        help='Significant figures for values (default: 6)')

    # Boolean flags
    parser.add_argument('-d', '--data-updates-only', action='store_true',
                        help='Include only value changes (not disconnects)')
    parser.add_argument('-w', '--forward-time-search', action='store_true',
                        help='Search forward in time instead of backward')
    parser.add_argument('-x', '--exclude-given-time', action='store_true',
                        help='Exclude the exact timestamp from search')
    parser.add_argument('-s', '--enums-as-strings', action='store_true',
                        help='Return enum values as strings instead of ints')
    parser.add_argument('-u', '--unix-timestamps-ms', action='store_true',
                        help='Return timestamps as milliseconds since Unix epoch')
    parser.add_argument('-a', '--adjust-time-to-server-offset', action='store_true',
                        help='Localize timestamps to myquery server timezone')

    # Server configuration
    parser.add_argument('--server', type=str, default=None,
                        help='Myquery server hostname (default: epicsweb.jlab.org)')
    parser.add_argument('--protocol', type=str, default=None, choices=['http', 'https'],
                        help='Protocol to use (default: http)')

    args = parser.parse_args()

    # Configure server
    _configure_server(args.server, args.protocol)

    # Parse datetime
    try:
        time = _parse_datetime(args.time)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create query
    query = PointQuery(
        channel=args.channel,
        time=time,
        deployment=args.deployment,
        frac_time_digits=args.frac_time_digits,
        sig_figs=args.sig_figs,
        data_updates_only=args.data_updates_only,
        forward_time_search=args.forward_time_search,
        exclude_given_time=args.exclude_given_time,
        enums_as_strings=args.enums_as_strings,
        unix_timestamps_ms=args.unix_timestamps_ms,
        adjust_time_to_server_offset=args.adjust_time_to_server_offset
    )

    # Execute query
    try:
        point = Point(query)
        point.run()

        # Save output (JSON only for point queries)
        if args.output is None:
            # Output to stdout as JSON
            print(json.dumps(json_normalize(point.event), indent=2, default=str))
        elif args.output.endswith('.json'):
            with open(args.output, 'w') as f:
                json.dump(json_normalize(point.event), f, indent=2, default=str)
            print(f"Successfully saved results to {args.output}")
        else:
            print("Error: Output file must be .json for point queries", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        sys.exit(1)


def channel_main():
    """Command-line interface for the channel endpoint.

    Searches for channel names using SQL-style pattern matching.
    """
    parser = argparse.ArgumentParser(
        description="Search for channel names using SQL patterns from the myquery channel endpoint"
    )

    # Required arguments
    parser.add_argument('-p', '--pattern', required=True, type=str,
                        help='SQL pattern to match (use %% for wildcard, _ for single char)')
    parser.add_argument('-o', '--output', required=False, type=str, default=None,
                        help='Output file path (.json). If not specified, outputs to stdout')

    # Optional query parameters
    parser.add_argument('-m', '--deployment', type=str, default='history',
                        help='MYA deployment (default: history)')
    parser.add_argument('-l', '--limit', type=int, default=None,
                        help='Maximum number of results to return')
    parser.add_argument('--offset', type=int, default=None,
                        help='Offset to start from (for pagination)')

    # Server configuration
    parser.add_argument('--server', type=str, default=None,
                        help='Myquery server hostname (default: epicsweb.jlab.org)')
    parser.add_argument('--protocol', type=str, default=None, choices=['http', 'https'],
                        help='Protocol to use (default: http)')

    args = parser.parse_args()

    # Configure server
    _configure_server(args.server, args.protocol)

    # Create query
    query = ChannelQuery(
        pattern=args.pattern,
        limit=args.limit,
        offset=args.offset,
        deployment=args.deployment
    )

    # Execute query
    try:
        channel = Channel(query)
        channel.run()

        # Save output (JSON only for channel queries)
        if args.output is None:
            # Output to stdout as JSON
            print(json.dumps(json_normalize(channel.matches), indent=2, default=str))
        elif args.output.endswith('.json'):
            with open(args.output, 'w') as f:
                json.dump(json_normalize(channel.matches), f, indent=2, default=str)
            print(f"Successfully saved {len(channel.matches)} results to {args.output}")
        else:
            print("Error: Output file must be .json for channel queries", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    print("This module provides command-line scripts. Use the installed commands:")
    print("  - jac-interval")
    print("  - jac-mysampler")
    print("  - jac-mystats")
    print("  - jac-point")
    print("  - jac-channel")
