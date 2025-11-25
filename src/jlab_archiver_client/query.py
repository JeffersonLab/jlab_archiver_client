r"""Query builder classes for Jefferson Lab Archiver myquery endpoints.

This module provides query builder classes for constructing requests to various
Jefferson Lab Archiver myquery service endpoints. Each query class encapsulates
the parameters needed for a specific endpoint and handles conversion to web
request parameters.

The query classes serve as parameter containers that are passed to their
corresponding client classes (MySampler, MyStats, Interval, Point, Channel)
which execute the queries and process the results.

Key Features:
    * Type-safe query parameter validation
    * Automatic conversion to myquery web API format
    * Support for all major myquery endpoints
    * Extensible via kwargs for future API changes
    * Consistent interface across different query types

Classes:
    Query: Abstract base class for all query types.
    IntervalQuery: Query for retrieving all events in a time range from the interval end point.
    MySamplerQuery: Query for regularly sampled data across multiple PVs from the mysampler endpoint.
    MyStatsQuery: Query for statistical aggregations over time bins from the mystats endpoint.
    ChannelQuery: Query for searching/discovering channel names from the channel endpoint.
    PointQuery: Query for retrieving a single event at a specific time from the point endpoint.

Note:
    All query classes support additional parameters via \*\*kwargs to allow for
    future API extensions. Using kwargs will generate a warning to prevent
    accidental misuse.

See Also:
    * jlab_archiver_client.mysampler: MySampler client for MySamplerQuery
    * jlab_archiver_client.mystats: MyStats client for MyStatsQuery
    * jlab_archiver_client.interval: Interval client for IntervalQuery
    * jlab_archiver_client.point: Point client for PointQuery
    * jlab_archiver_client.channel: Channel client for ChannelQuery
"""
import warnings
from datetime import datetime
from typing import Optional, List, Dict


__all__ = ["Query", "IntervalQuery", "MySamplerQuery", "ChannelQuery", "PointQuery", "MyStatsQuery"]


class Query:
    """An abstract base class to be used by various mya utility wrappers."""

    def __init__(self):
        raise NotImplementedError("Query class is abstract")

    def to_web_params(self):
        raise NotImplementedError("Query class is abstract")


class IntervalQuery(Query):
    """A class for holding the parameters of an interval myquery call"""
    # noinspection PyMissingConstructor
    def __init__(self, channel: str, begin: datetime, end: datetime,
                 bin_limit: Optional[int] = None,
                 sample_type: Optional[str] = None,
                 deployment: Optional[str] = "history",
                 frac_time_digits: int = 0,
                 sig_figs: int = 6,
                 data_updates_only: bool = False,
                 prior_point: bool = False,
                 enums_as_strings: bool = False,
                 unix_timestamps_ms: bool = False,
                 adjust_time_to_server_offset: bool = False,
                 integrate: bool = False,
                 **kwargs
                 ):
        """Construct a query to the myquery interval service.

        Args:
            channel: A list of PV Names to query
            begin: The start time of the query
            end: The end time of the query
            deployment: The mya deployment to query
            bin_limit: How many points returned from MYA before sampling kicks in
            sample_type: What sampling algorithm should be used.  [graphical, eventsimple, myget, mysampler]
            frac_time_digits: How many digits should be displayed for fractional seconds
            sig_figs: How many significant figures should be reported in the PV values
            data_updates_only: Should the response include updates that only include value changes (not disconnects?)
            prior_point: Should the query use the most recent update prior to the start to give a value at the start of
                         the query.
            enums_as_strings:  Should enum PV values be returned as their named strings instead of ints
            unix_timestamps_ms:  Should timestamps be returned as millis since unix epoch
            adjust_time_to_server_offset: Should the timestamp be localized to the myquery server
            integrate: Should the values be integrated (ony supported for float PVs)
            kwargs: Any extra parameters to be supplied to the interval web end point.  Will produce a warning if used
                    to avoid accidental use.
        """
        self.channel = channel
        self.begin = begin
        self.end = end
        self.bin_limit = bin_limit
        self.sample_type = sample_type
        self.deployment = deployment
        self.frac_time_digits = frac_time_digits
        self.sig_figs = sig_figs
        self.data_updates_only = data_updates_only
        self.prior_point = prior_point
        self.enums_as_strings = enums_as_strings
        self.unix_timestamps_ms = unix_timestamps_ms
        self.adjust_time_to_server_offset = adjust_time_to_server_offset
        self.integrate = integrate
        self.extra_opts = kwargs

    def to_web_params(self):
        """
        Convert the query to web parameters.

        Based on myquery v6.2, but use of kwargs makes this more flexible.

        Example URL that we're targeting
        https://epicsweb.jlab.org/myquery/interval?c=R1M1GMES&b=2023-05-09&e=2023-05-09+15%3A59%3A00&l=&t=graphical&m=history&f=0&v=6&d=on&p=on&s=on&u=on&a=on&i=on
        """
        ts_fmt = "%Y-%m-%dT%H:%M:%S"
        out = {'c': self.channel,
               'b': self.begin.strftime(ts_fmt),
               'e': self.end.strftime(ts_fmt),
               'm': self.deployment,
               'f': self.frac_time_digits,
               'v': self.sig_figs,
               }

        # It looks like the form keeps the 'l' param with "" passed if not specified
        if self.bin_limit is None:
            out['l'] = ""
        else:
            out['l'] = self.bin_limit

        # myquery app assumes its own default if 't' is missing.  Don't need to send anything.
        if self.sample_type is not None:
            out['t'] = self.sample_type

        # API takes presence of some params to mean == true, and the web form uses 'on' instead of a boolean.
        if self.data_updates_only:
            out['d'] = 'on'
        if self.prior_point:
            out['p'] = 'on'
        if self.enums_as_strings:
            out['s'] = 'on'
        if self.unix_timestamps_ms:
            out['u'] = 'on'
        if self.adjust_time_to_server_offset:
            out['a'] = 'on'
        # only valid for float events, but that's left to the user
        if self.integrate:
            out['i'] = 'on'

        # Allow the user to add extra options if they so choose.
        if self.extra_opts is not None and len(self.extra_opts) > 0:
            warnings.warn(f"Using extra_opts - {self.extra_opts}")
            out.update(self.extra_opts)

        return out


class MySamplerQuery(Query):
    """A class for containing the arguments needed by mySampler."""

    # noinspection PyMissingConstructor
    def __init__(self, start: datetime, interval: int, num_samples: int, pvlist: List[str],
                 deployment: Optional[str] = "history", sample_strategy: Optional[str] = None,
                 data_updates_only: bool=False, enums_as_strings: bool=False,
                 unix_timestamps_ms: bool=False, adjust_time_to_server_offset: bool=False, **kwargs):
        """Construct an instance of MySamplerQuery.

        Args:
            start: The start date of the query.
            interval: The number of milliseconds between each query.
            num_samples: The number of samples to take
            pvlist: The list of PVs to collect on
            deployment: The mya deployment to use.  (Default:"history", unlike the myquery endpoint).
            sample_strategy: The sampling strategy to use.  Options are None (default), 'n_queries', 'stream'.  If None,
                             then default sampling strategy is determined by the myquery server. 'n_queries' queries the
                             database once for each data point returned.  'stream' queries the database once per PV and
                             constructs the returned data from the stream.  'n_queries' is generally more efficient for
                             queries with a large number of update events per sample while 'stream' is generally more
                             efficient for queries with a small number of update events per sample.  Developer testing
                             indicates the threshold for switching strategies to maintain the best response time is
                             somewhere around 5,000 update events per sample.
            data_updates_only: Should the response ignore events such as "NETWORK_DISCONNECT" and assume the previous
                                value is still in effect  (Default: False)
            enums_as_strings: Should enum PV values be returned as their names instead of ints
            unix_timestamps_ms: Should timestamps be returned as millis since unix epoch
            adjust_time_to_server_offset: Should the timestamp be localized to the myquery server
            extra_opts: Extra options to pass to the mysampler endpoint.  Helps to future-proof, produces a warning to
                        avoid accidental use.
        """
        self.start = start.replace(microsecond=0).isoformat().replace("T", " ")
        self.interval = interval
        self.num_samples = num_samples
        self.pvlist = pvlist
        self.deployment = deployment
        self.sample_strategy = sample_strategy
        self.data_updates_only = data_updates_only
        self.enums_as_strings = enums_as_strings
        self.unix_timestamps_ms = unix_timestamps_ms
        self.adjust_time_to_server_offset = adjust_time_to_server_offset
        self.extra_opts = kwargs

        if self.sample_strategy is not None:
            self.sample_strategy = self.sample_strategy.lower()
            if self.sample_strategy not in ("n_queries", "stream"):
                raise ValueError("sample_strategy must be None, 'n_queries', or 'stream'")

    def to_web_params(self) -> Dict[str, str]:
        """Convert the objects command line parameters to their web counterparts"""
        out = {'c': ",".join(self.pvlist),
               'b': self.start.replace(" ", "T"),
               'n': self.num_samples,
               'm': self.deployment,
               's': self.interval,
               }

        if self.sample_strategy is not None:
            if self.sample_strategy == "n_queries":
                out['x'] = "n"
            elif self.sample_strategy == "stream":
                out['x'] = "s"

        # API takes presence of some params to mean == true, and the web form uses 'on' instead of a boolean.
        if self.data_updates_only:
            out['d'] = 'on'
        if self.enums_as_strings:
            out['e'] = 'on'
        if self.unix_timestamps_ms:
            out['u'] = 'on'
        if self.adjust_time_to_server_offset:
            out['a'] = 'on'

        if self.extra_opts is not None and len(self.extra_opts) > 0:
            warnings.warn(f"Using extra_opts - {self.extra_opts}")
            out.update(self.extra_opts)

        return out


class ChannelQuery(Query):
    """A class for containing the arguments needed by myquery's channel endpoint."""
    # noinspection PyMissingConstructor
    def __init__(self, pattern: str, limit: Optional[int] = None, offset: Optional[int] = None,
                 deployment: Optional[str] = "history", **kwargs):
        """Construct an instance of ChannelQuery.

        Args:
            pattern: The channel name pattern to match against (SQL patterns)
            limit: The maximum number of results to return
            offset: The offset to start from
            deployment: The mya deployment to use.
            kwargs: Additional arguments to pass to the myquery endpoint.
        """
        self.pattern = pattern
        self.limit = limit
        self.offset = offset
        self.deployment = deployment
        self.extra_opts = kwargs

    def to_web_params(self) -> Dict[str, str]:
        """Convert the objects command line parameters to their web counterparts"""
        out = {'q': self.pattern,
               'l': self.limit,
               'o': self.offset,
               'm': self.deployment,
               }

        if self.extra_opts is not None and len(self.extra_opts) > 0:
            warnings.warn(f"Using extra_opts - {self.extra_opts}")
            out.update(self.extra_opts)

        return out


class PointQuery(Query):
    """A class for holding the parameters of an interval myquery call"""
    # noinspection PyMissingConstructor
    def __init__(self, channel: str, time: datetime,
                 deployment: Optional[str] = "history",
                 frac_time_digits: int = 0,
                 sig_figs: int = 6,
                 data_updates_only: bool = False,
                 forward_time_search: bool = False,
                 exclude_given_time: bool = False,
                 enums_as_strings: bool = False,
                 unix_timestamps_ms: bool = False,
                 adjust_time_to_server_offset: bool = False,
                 **kwargs
                 ):
        """Construct a query to the myquery interval service.

        Args:
            channel: A list of PV Names to query
            time: The start time of the query
            deployment: The mya deployment to query
            frac_time_digits: How many digits should be displayed for fractional seconds
            sig_figs: How many significant figures should be reported in the PV values
            data_updates_only: Should the response include updates that only include value changes (not disconnects)
            forward_time_search: Look forward in time from the given time for the next event (if True)
            exclude_given_time:  Don't include the given time in the search space for the next event (if True)
            enums_as_strings:  Should enum PV values be returned as their named strings instead of ints
            unix_timestamps_ms:  Should timestamps be returned as millis since unix epoch
            adjust_time_to_server_offset: Should the timestamp be localized to the myquery server
            integrate: Should the values be integrated (ony supported for float PVs)
            kwargs: Any extra parameters to be supplied to the interval web end point.  Will produce a warning if used
                    to avoid accidental use.
        """
        self.channel = channel
        self.time = time
        self.deployment = deployment
        self.frac_time_digits = frac_time_digits
        self.sig_figs = sig_figs
        self.forward_time_search = forward_time_search
        self.exclude_given_time = exclude_given_time
        self.data_updates_only = data_updates_only
        self.enums_as_strings = enums_as_strings
        self.unix_timestamps_ms = unix_timestamps_ms
        self.adjust_time_to_server_offset = adjust_time_to_server_offset
        self.extra_opts = kwargs

    def to_web_params(self):
        """
        Convert the query to web parameters.

        Based on myquery v6.2, but use of kwargs makes this more flexible.

        Example URL that we're targeting
        https://epicsweb.jlab.org/myquery/point?c=channel100&t=2018-04-24+12%3A00%3A00&m=docker&f=&v=&w=on&x=on
        """
        ts_fmt = "%Y-%m-%dT%H:%M:%S"
        out = {'c': self.channel,
               't': self.time.strftime(ts_fmt),
               'm': self.deployment,
               'f': self.frac_time_digits,
               'v': self.sig_figs,
               }

        # API takes presence of some params to mean == true, and the web form uses 'on' instead of a boolean.
        if self.data_updates_only:
            out['d'] = 'on'
        if self.forward_time_search:
            out['w'] = "on"
        if self.exclude_given_time:
            out['x'] = "on"
        if self.enums_as_strings:
            out['s'] = 'on'
        if self.unix_timestamps_ms:
            out['u'] = 'on'
        if self.adjust_time_to_server_offset:
            out['a'] = 'on'

        # Allow the user to add extra options if they so choose.
        if self.extra_opts is not None and len(self.extra_opts) > 0:
            warnings.warn(f"Using extra_opts - {self.extra_opts}")
            out.update(self.extra_opts)

        return out


class MyStatsQuery(Query):
    """A class for containing the arguments needed by mystats endpoint."""

    # noinspection PyMissingConstructor
    def __init__(self,
                 pvlist: List[str],
                 start: datetime,
                 end: datetime,
                 num_bins: int = 1,
                 deployment: Optional[str] = "history",
                 frac_time_digits: int = 0,
                 sig_figs: int = 6,
                 data_updates_only: bool=False,
                 enums_as_strings: bool=False,
                 unix_timestamps_ms: bool=False,
                 adjust_time_to_server_offset: bool=False,
                 **kwargs):
        """Construct an instance of MyStatsQuery.

        Args:
            pvlist: The list of PVs to collect on
            start: The start date/time of the query.
            end: The end date/time of the query.
            num_bins: The number of bins to compute statistics over
            deployment: The mya deployment to use.  (Default:"history", unlike the myquery endpoint).
            data_updates_only: Should the response ignore events such as "NETWORK_DISCONNECT" and assume the previous
                                value is still in effect  (Default: False)
            enums_as_strings: Should enum PV values be returned as their names instead of ints
            unix_timestamps_ms: Should timestamps be returned as millis since unix epoch
            adjust_time_to_server_offset: Should the timestamp be localized to the myquery server
            kwargs: Extra options to pass to the mysampler endpoint.  Helps to future-proof, produces a warning to
                        avoid accidental use.
        """
        self.pvlist = pvlist
        self.start = start
        self.end = end
        self.num_bins = num_bins
        self.deployment = deployment
        self.frac_time_digits = frac_time_digits
        self.sig_figs = sig_figs
        self.data_updates_only = data_updates_only
        self.enums_as_strings = enums_as_strings
        self.unix_timestamps_ms = unix_timestamps_ms
        self.adjust_time_to_server_offset = adjust_time_to_server_offset
        self.extra_opts = kwargs

    def to_web_params(self) -> Dict[str, str]:
        """Convert the objects command line parameters to their web counterparts"""
        out = {'c': ",".join(self.pvlist),
               'b': self.start.isoformat(),
               'e': self.end.isoformat(),
               'n': self.num_bins,
               'm': self.deployment,
               'f': self.frac_time_digits,
               'v': self.sig_figs,
               }

        # API takes presence of some params to mean == true, and the web form uses 'on' instead of a boolean.
        if self.data_updates_only:
            out['d'] = 'on'
        if self.unix_timestamps_ms:
            out['u'] = 'on'
        if self.adjust_time_to_server_offset:
            out['a'] = 'on'

        if self.extra_opts is not None and len(self.extra_opts) > 0:
            warnings.warn(f"Using extra_opts - {self.extra_opts}")
            out.update(self.extra_opts)

        return out
