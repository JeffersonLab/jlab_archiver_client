"""This package provides a Python interface to the JLab Archiver's myquery service."""
import importlib.metadata

from .query import (IntervalQuery as IntervalQuery, MySamplerQuery as MySamplerQuery, ChannelQuery as ChannelQuery,
                   PointQuery as PointQuery, MyStatsQuery as MyStatsQuery)
from .mysampler import MySampler as MySampler
from .interval import Interval as Interval
from .point import Point as Point
from .channel import Channel as Channel
from .mystats import MyStats as MyStats

__version__ = importlib.metadata.version("jlab_archiver_client")
