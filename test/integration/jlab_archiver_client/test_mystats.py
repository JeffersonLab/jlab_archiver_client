import unittest
import warnings
from datetime import datetime
from typing import Tuple, Any, Dict

import numpy as np
import pandas as pd
from jlab_archiver_client import MyStatsQuery, MyStats


class TestMyStats(unittest.TestCase):

    @staticmethod
    def construct_expected() -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Construct expected data and metadata for MyStats query integration tests.

        This helper method creates a reference DataFrame and metadata dictionary that represent
        the expected output from a MyStats query for two channels (channel100 and channel101)
        over a 6-day period from 2024-04-24 to 2024-04-29.

        The method constructs a pandas DataFrame with a MultiIndex structure where:
            - Level 0 (timestamp): Daily timestamps from 2024-04-24 to 2024-04-29 (6 days)
            - Level 1 (stat): Nine statistical measures for each timestamp

        Statistical measures included (in order):
            - duration: Time span of the bin in seconds (86400 = 24 hours)
            - eventCount: Number of events recorded in the bin
            - integration: Integrated value over the time period
            - max: Maximum value observed
            - mean: Average value
            - min: Minimum value observed
            - rms: Root mean square value
            - stdev: Standard deviation
            - updateCount: Number of updates in the bin

        Returns:
            tuple[pd.DataFrame, dict]: A tuple containing:
                - data (pd.DataFrame): A DataFrame with MultiIndex (timestamp, stat) and columns
                  for each channel. Each channel contains the same statistical pattern repeated
                  for each day in the date range.
                - metadata (dict): A dictionary mapping channel names to their metadata, including
                  name, datatype (DBR_DOUBLE), datasize, datahost (mya), ioc, and active status.

        Note:
            The statistical values are constant across all days for each channel, simulating
            a stable signal with known characteristics. This is useful for validating that
            the MyStats query correctly retrieves and formats data.

        Examples:
            >>> data, metadata = TestMyStats.construct_expected()
            >>> data.loc[("2024-04-24", "mean"), "channel100"]
            5.658
            >>> metadata["channel100"]["datatype"]
            'DBR_DOUBLE'
        """
        # Define the index levels
        dates = pd.date_range("2024-04-24", "2024-04-29", freq="D")
        stats = [
            "duration", "eventCount", "integration", "max", "mean",
            "min", "rms", "stdev", "updateCount"
        ]

        # Create a MultiIndex from their Cartesian product
        index = pd.MultiIndex.from_product([dates, stats], names=["timestamp", "stat"])

        # Fill in the repeated numeric pattern
        data = {
            "channel100": np.tile([
                86400.000000, 2.000000, 488851.199341, 5.658000, 5.658000,
                5.658000, 5.658000, 0.000000, 1.000000
            ], len(dates)),
            "channel101": np.tile([
                86400.000000, 2.000000, 669859.181213, 7.753000, 7.753000,
                7.753000, 7.753000, 0.000000, 1.000000
            ], len(dates)),
        }

        data = pd.DataFrame(data, index=index)

        metadata = {'channel100': {'name': 'channel100', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya',
                                   'ioc': None, 'active': True},
                    'channel101': {'name': 'channel101', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya',
                                   'ioc': None, 'active': True}}

        return data, metadata

    def test_construct_expected2(self):
        data = {
            'channel1': [
                # 2019-08-12 00:00:00
                42922.7005689144134521484375,  # duration
                18094,  # eventCount
                3482493.015712834894657135009765625,  # integration
                98.9699,  # max
                81.1341,  # mean
                0,  # min
                86.0953,  # rms
                28.8038,  # stdev
                18093,  # updateCount
                # 2019-08-12 12:00:00
                43200,  # duration
                14898,  # eventCount
                2831334.8737724614329636096954345703125,  # integration
                103.997,  # max
                65.5402,  # mean
                0,  # min
                73.6489,  # rms
                33.5954,  # stdev
                14897,  # updateCount
            ]
        }

        # Create the MultiIndex
        timestamps = [
            pd.Timestamp('2019-08-12 00:00:00'),
            pd.Timestamp('2019-08-12 12:00:00')
        ]

        stats = ['duration', 'eventCount', 'integration', 'max', 'mean', 'min', 'rms', 'stdev', 'updateCount']

        # Create tuples for MultiIndex
        index_tuples = [(ts, stat) for ts in timestamps for stat in stats]
        index = pd.MultiIndex.from_tuples(index_tuples, names=['timestamp', 'stat'])

        # Create the DataFrame
        return pd.DataFrame(data, index=index)

    def test_get_mystats(self):
        """Test basic usage"""
        #  http://localhost:8080/myquery/mystats?c=channel100,channel101&b=2024-04-24&e=2024-04-30&n=6&m=docker&f=&v=
        exp_data, exp_metadata = self.construct_expected()

        mystats = MyStats(MyStatsQuery(pvlist=["channel100", "channel101"],
                                       start=datetime.strptime("2024-04-24", "%Y-%m-%d"),
                                       end=datetime.strptime("2024-04-30", "%Y-%m-%d"),
                                       num_bins=6,
                                       deployment="docker")
                          )
        mystats.run()

        res_data = mystats.data
        res_metadata = mystats.metadata

        pd.testing.assert_frame_equal(exp_data, res_data)
        self.assertDictEqual(exp_metadata, res_metadata)

    def test_get_mystats_2(self):
        """Test basic usage with an unsupported Enum PV"""
        query = MyStatsQuery(
            start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
            end=datetime.strptime("2019-08-13 00:00:00", "%Y-%m-%d %H:%M:%S"),
            num_bins=2,  # 24 hours of data
            pvlist=["channel1", "channel2"],
            deployment="docker"
        )
        mystats = MyStats(query)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            mystats.run()
            self.assertEqual(len(w), 1)
            self.assertEqual(str(w[0].message),
                             "Error querying channel2: This myStats only supports FloatEvents - not"
                             " 'org.jlab.mya.event.IntEvent'.")

        res_data, res_metadata = mystats.data, mystats.metadata

        exp_data = self.test_construct_expected2()
        exp_metadata = {
            'channel1': {'name': 'channel1', 'datatype': 'DBR_DOUBLE', 'datasize': 1, 'datahost': 'mya', 'ioc': None,
                         'active': True}}

        pd.testing.assert_frame_equal(exp_data, res_data)
        self.assertDictEqual(exp_metadata, res_metadata)
