from jlab_archiver_client.channel import Channel
from jlab_archiver_client.query import ChannelQuery
import unittest


class TestChannel(unittest.TestCase):

    def test_get_channel_1(self):
        """Test getting one channel's info"""
        channel = Channel(ChannelQuery(pattern="channel1", deployment="docker"))
        channel.run()
        result = channel.matches

        exp = [{"name": "channel1", "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                "active": True}]

        self.assertEqual(exp, result)

    def test_get_channel_2(self):
        """Test a SQL wildcard pattern"""
        channel = Channel(ChannelQuery(pattern="channel1%", deployment="docker"))
        channel.run()
        result = channel.matches

        exp = [{"name": "channel1", "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                "active": True},
               {"name": "channel100", "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                "active": True},
               {"name": "channel101", "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                "active": True},
               {"name": "channel102", "datatype": "DBR_SHORT", "datasize": 11, "datahost": "mya", "ioc": None,
                "active": True},
               ]

        self.assertEqual(exp, result)

    def test_get_channel_3(self):
        """Test a SQL wildcard pattern with limit and offset"""
        channel = Channel(ChannelQuery(pattern="channel%", limit=3, offset=1, deployment="docker"))
        channel.run()
        result = channel.matches

        exp = [{"name": "channel100", "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                "active": True},
               {"name": "channel101", "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                "active": True},
               {"name": "channel102", "datatype": "DBR_SHORT", "datasize": 11, "datahost": "mya", "ioc": None,
                "active": True},
               ]

        self.assertEqual(exp, result)

    def test_get_channel_4(self):
        """Test a SQL wildcard pattern that returns no matches"""
        channel = Channel(ChannelQuery(pattern="asdf%", deployment="docker"))
        channel.run()
        result = channel.matches
        exp = []

        self.assertEqual(exp, result)

    def test_get_channel_102(self):
        """Test getting channel102's info"""
        channel = Channel(ChannelQuery(pattern="channel102", deployment="docker"))
        channel.run()
        result = channel.matches

        exp = [{"name": "channel102", "datatype": "DBR_SHORT", "datasize": 11, "datahost": "mya", "ioc": None,
                "active": True}]

        self.assertEqual(exp, result)
