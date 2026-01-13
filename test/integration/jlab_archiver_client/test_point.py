import unittest

from datetime import datetime

from jlab_archiver_client import Point, PointQuery


class TestPointQuery(unittest.TestCase):

    def test_get_point_1(self):
        """Test basic usage"""

        point = Point(PointQuery(channel="channel100",
                                 time=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                 deployment="docker",
                                 ))
        point.run()
        result = point.event
        exp = {'name': 'channel100', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya',
               'data': {'d': '2018-04-24 11:18:19', 'v': 5.66}}
        self.assertDictEqual(exp, result)

    def test_get_point_2(self):
        """Test basic usage with options"""

        point = Point(PointQuery(channel="channel100",
                                 time=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                 deployment="docker",
                                 frac_time_digits=3,
                                 sig_figs=2,
                                 data_updates_only=True,
                                 forward_time_search=True,
                                 exclude_given_time=True,
                                 ))
        point.run()
        result = point.event
        exp = {'name': 'channel100', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya',
               'data': {'d': '2018-04-24 12:31:11.397', 'v': 5.7}}
        self.assertDictEqual(exp, result)

    def test_get_point_3(self):
        """Test basic usage with options"""

        point = Point(PointQuery(channel="channel100",
                                 time=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                 deployment="docker",
                                 frac_time_digits=3,
                                 sig_figs=2,
                                 data_updates_only=True,
                                 forward_time_search=True,
                                 exclude_given_time=True,
                                 unix_timestamps_ms=True,
                                 ))
        point.run()
        result = point.event
        exp = {'name': 'channel100', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya',
               'data': {'d': 1524587471397, 'v': 5.7}}
        self.assertDictEqual(exp, result)

    def test_get_point_102(self):
        """Test point query for channel102 over similar time range as channel101."""

        point = Point(PointQuery(channel="channel102",
                                 time=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                 deployment="docker",
                                 ))
        point.run()
        result = point.event

        exp = {"datatype": "DBR_SHORT", "datasize": 11, "datahost": "mya",
               "data": {"d": "2018-04-24 11:18:19", "x": True, "t": "UNKNOWN_UNAVAILABILTY"},
               "name": "channel102"}
        self.assertDictEqual(exp, result)
