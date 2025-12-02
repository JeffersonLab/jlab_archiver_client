import os
import unittest
import json
from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd

from jlab_archiver_client.interval import Interval
from jlab_archiver_client.query import IntervalQuery
from jlab_archiver_client.utils import json_normalize


DIR = os.path.dirname(__file__)


def process_vector_series(x: pd.Series):
    """Process a Series where some columns are strings representing a vector.  Modify only if needed.

    Args:
        x: Series to process
    """

    for i in range(len(x)):
        val = x[i]
        if val is None:
            continue
        if isinstance(val, str):
            if val.startswith("[") and val.endswith("]"):
                x[i] = np.fromstring(val.strip("[]"), sep=" ", dtype=float)
        elif isinstance(val, float):
            pass
        elif isinstance(val, object):
            if val.str.startswith("[") and val.str.endswith("]"):
                x[i] = np.fromstring(val.str.strip("[]"), sep=" ", dtype=float)

    return x

class TestInterval(unittest.TestCase):
    s1 = pd.Series(
        [7.930, 0.000, 6.996, 7.930, 7.755, np.nan, 7.755, np.nan],
        index=pd.to_datetime([
            "2018-04-24 00:00:00",
            "2018-04-24 11:12:51",
            "2018-04-24 11:12:55",
            "2018-04-24 11:12:56",
            "2018-04-24 11:18:18",
            "2018-04-24 12:19:44",
            "2018-04-24 12:32:45",
            "2018-04-25 01:20:45",
        ]),
        name="channel101",
        dtype="float64",
    )

    s2 = pd.Series(
        [5.911, 0.0, np.nan, 5.66, np.nan, 5.657, 5.657],
        index=pd.to_datetime([
            "2018-04-24 00:00:00",
            "2018-04-24 06:25:01",
            "2018-04-24 06:25:05",
            "2018-04-24 11:18:19",
            "2018-04-24 12:19:44",
            "2018-04-24 12:31:11",
            "2018-04-25 01:20:45"]),
        name="channel100",
        dtype="float64",
    )

    df_s1_s2 = pd.DataFrame(
        {
            # Was modified version of R123GMES
            "channel101": [7.930, 7.930, 7.930, 0.000, 6.996, 7.930, 7.755, 7.755, np.nan, np.nan, 7.755, np.nan],
            # Was modified version of R121GMES
            "channel100": [5.911, 0.000, np.nan, np.nan, np.nan, np.nan, np.nan, 5.660, np.nan, 5.657, 5.657, 5.657],
        },
        index=pd.to_datetime([
            "2018-04-24 00:00:00",
            "2018-04-24 06:25:01",
            "2018-04-24 06:25:05",
            "2018-04-24 11:12:51",
            "2018-04-24 11:12:55",
            "2018-04-24 11:12:56",
            "2018-04-24 11:18:18",
            "2018-04-24 11:18:19",
            "2018-04-24 12:19:44",
            "2018-04-24 12:31:11",
            "2018-04-24 12:32:45",
            "2018-04-25 01:20:45",
        ]),
    )

    @staticmethod
    def save_interval_data_parallel(ident: str, data: pd.DataFrame, disconnects: Dict[str, pd.Series],
                            metadata: Dict[str, object]):
        """Convenient way to save test case data for interval parallel calls."""
        data.to_csv(f"{DIR}/data/myquery_{ident}-data.csv")

        with open(f"{DIR}/data/myquery_{ident}-disconnects.json", "w") as f:
            # noinspection PyTypeChecker
            json.dump(json_normalize(disconnects), f)
            # json.dump(disconnects, f, cls=myquery.MyQueryEncoder)

        with open(f"{DIR}/data/myquery_{ident}-metadata.json", "w") as f:
            # noinspection PyTypeChecker
            json.dump(json_normalize(metadata), f)

    @staticmethod
    def load_interval_data_parallel(ident: str):
        """Load test case data for interval parallel calls"""
        exp_data = pd.read_csv(f"{DIR}/data/myquery_{ident}-data.csv", index_col=0)
        exp_data.index = pd.to_datetime(exp_data.index)

        with open(f"{DIR}/data/myquery_{ident}-disconnects.json", "r") as f:
            exp_disconnects = json.load(f)

        with open(f"{DIR}/data/myquery_{ident}-metadata.json", "r") as f:
            exp_metadata = json.load(f)

        return exp_data, exp_disconnects, exp_metadata


    @staticmethod
    def load_interval_data(ident: str, pv: str):
        """Load test case data for interval"""
        exp_data = pd.read_csv(f"{DIR}/data/myquery_{ident}-data.csv", index_col=0)[pv]
        exp_data.index = pd.to_datetime(exp_data.index)

        exp_disconnects = pd.read_csv(f"{DIR}/data/myquery_{ident}-disconnects.csv", index_col=0)[pv]
        with open(f"{DIR}/data/myquery_{ident}-metadata.json", "r") as f:
            exp_metadata = json.load(f)

        return exp_data, exp_disconnects, exp_metadata

    @staticmethod
    def save_interval_data(ident: str, data: pd.Series, disconnects: pd.Series, metadata: Dict[str, object]):
        """Convenient way to save test case data for interval."""
        data.to_csv(f"{DIR}/data/myquery_{ident}-data.csv")
        disconnects.to_csv(f"{DIR}/data/myquery_{ident}-disconnects.csv")

        with open(f"{DIR}/data/myquery_{ident}-metadata.json", "w") as f:
            # noinspection PyTypeChecker
            json.dump(json_normalize(metadata), f)

    def check_interval_result(self, exp_data, exp_disconnects, exp_metadata, res_data,
                              res_disconnects, res_metadata):
        """Utility function for checking tes results of interval"""
        self.assertTrue(exp_data.equals(res_data), f"\nExp:\n{exp_data}\nResult:\n{res_data}\n")
        self.assertTrue(exp_disconnects.equals(res_disconnects),
                             f"\nExp:\n{exp_disconnects}\nResult:\n{res_disconnects}\n")
        self.assertDictEqual(exp_metadata, res_metadata, f"\nExp:\n{exp_metadata}\nResult:\n{res_metadata}\n")

    def check_interval_result_parallel(self, exp_data, exp_disconnects, exp_metadata, res_data,
                               res_disconnects, res_metadata):
        """Utility function for checking tes results of interval parallel calls."""
        pd.testing.assert_frame_equal(exp_data, res_data)
        self.assertDictEqual(exp_disconnects, json_normalize(res_disconnects),
                                  f"\nExpected:\n{exp_disconnects}\nResult:\n{res_disconnects}\n")
        self.assertDictEqual(exp_metadata, json_normalize(res_metadata),
                                  f"\nExpected:\n{exp_metadata}\nResult:\n{res_metadata}\n")


    def test_get_interval_1(self):
        """Test basic query with lots of default values. (Has NaN)"""
        pv = "channel100"
        query = IntervalQuery(channel=pv,
                                      begin=datetime.strptime("2018-04-24", "%Y-%m-%d"),
                                      end=datetime.strptime("2018-05-01", "%Y-%m-%d"),
                                      deployment="docker"
                                      )
        interval = Interval(query)
        interval.run()
        res_data = interval.data
        res_disconnects = interval.disconnects
        res_metadata = interval.metadata

        exp_data, exp_disconnects, exp_metadata = self.load_interval_data("interval_1", pv=pv)
        self.check_interval_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects, res_metadata)

    def test_get_interval_2(self):
        """Test query that uses sampling and some extra options (no NaNs)"""
        # Was R123GMES
        pv = "channel101"
        query = IntervalQuery(channel=pv,
                                      begin=datetime.strptime("2018-04-24", "%Y-%m-%d"),
                                      end=datetime.strptime("2018-05-01", "%Y-%m-%d"),
                                      deployment="docker",
                                      bin_limit=5,
                                      sample_type="myget",
                                      frac_time_digits=2,
                                      sig_figs=3,
                                      data_updates_only=False,
                                      prior_point=False,
                                      enums_as_strings=False,
                                      unix_timestamps_ms=False,
                                      adjust_time_to_server_offset=False,
                                      integrate=False,
                                      )
        interval = Interval(query)
        interval.run()
        res_data = interval.data
        res_disconnects = interval.disconnects
        res_metadata = interval.metadata

        exp_data, exp_disconnects, exp_metadata = self.load_interval_data("interval_2", pv=pv)
        self.check_interval_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects, res_metadata)

    def test_get_interval_3(self):
        """Test query that gets a non-scaler (waveform) record."""
        # Was R123GMES
        pv = "channel3"
        query = IntervalQuery(channel=pv,
                                      begin=datetime.strptime("2019-08-12", "%Y-%m-%d"),
                                      end=datetime.strptime("2019-08-13", "%Y-%m-%d"),
                                      deployment="docker",
                                      )
        interval = Interval(query)
        interval.run()
        res_data = interval.data
        res_disconnects = interval.disconnects
        res_metadata = interval.metadata

        # We can directly save the data as usual, but pandas saves each row as a string.  Need a little help getting it
        # back.
        exp_data, exp_disconnects, exp_metadata = self.load_interval_data("interval_3", pv=pv)
        exp_data = exp_data.apply(lambda x: np.fromstring(x.strip("[]"), sep=" "))
        self.check_interval_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects, res_metadata)

    def test_run_parallel_combined(self):

        out = Interval.run_parallel(pvlist=["channel101", "channel100"],
                                            begin=datetime.strptime("2018-04-24", "%Y-%m-%d"),
                                            end=datetime.strptime("2018-04-25 01:20:45.002",
                                                                "%Y-%m-%d %H:%M:%S.%f"),
                                            deployment="docker",
                                            prior_point=True,)
        res_data, res_disconnects, res_metadata = out

        exp_data, exp_disconnects, exp_metadata = self.load_interval_data_parallel("interval_parallel_1")
        self.check_interval_result_parallel(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                                            res_metadata)
        self.assertEqual(res_data.channel101.dtype, float)
        self.assertEqual(res_data.channel100.dtype, float)

    def test_run_parallel_combined2(self):
        out = Interval.run_parallel(pvlist=["channel2", "channel3"],
                                            begin=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                            end=datetime.strptime("2019-08-12 01:20:45.002",
                                                                "%Y-%m-%d %H:%M:%S.%f"),
                                            deployment="docker",
                                            prior_point=True,)
        res_data, res_disconnects, res_metadata = out

        exp_data, exp_disconnects, exp_metadata = self.load_interval_data_parallel("interval_parallel_2")
        exp_data = exp_data.apply(process_vector_series, axis=0)
        self.check_interval_result_parallel(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                                            res_metadata)
        self.assertEqual(float, res_data.channel2.dtype)
        self.assertEqual(object, res_data.channel3.dtype)

    def test__combine_series(self):
        """Test if internal logic for combining series works."""
        exp = self.df_s1_s2
        result = Interval._combine_series([self.s1, self.s2])
        self.assertTrue(exp.equals(result), f"\nExp:\n{exp}\nResult:\n{result}\n")
