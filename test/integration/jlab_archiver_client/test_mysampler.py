import os
import unittest
import json
from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd
import requests
from requests import RequestException

from jlab_archiver_client import MySampler
from jlab_archiver_client import MySamplerQuery
from jlab_archiver_client.config import config
# noinspection PyProtectedMember
from jlab_archiver_client.mysampler import _parse_json_iteratively
from jlab_archiver_client.utils import json_normalize


DIR = os.path.dirname(__file__)

def process_vector_series(x: pd.Series):
    """Process a Series where some columns are strings representing a vector.  Modify only if needed.

    Args:
        x: Series to process
    """

    for i in range(len(x)):
        idx = x.index[i]
        val = x[idx]
        if val is None:
            continue
        if isinstance(val, str):
            if val.startswith("[") and val.endswith("]"):
                x[idx] = np.fromstring(val.strip("[]"), sep=" ", dtype=np.float32)
        elif isinstance(val, float):
            pass
        elif isinstance(val, object):
            # This seems to work, but IDE throws a warning.
            # noinspection PyUnresolvedReferences
            if val.str.startswith("[") and val.str.endswith("]"):
                # noinspection PyUnresolvedReferences
                x[idx] = np.fromstring(val.str.strip("[]"), sep=" ", dtype=np.float32)

    return x


class TestMySampler(unittest.TestCase):
    """Test the MySampler class to ensure it gives responses that mimic the myquery endpoint.

    Testing strategy here is to compare 'live' query against saved results.  The saved results have been inspected
    and should include situations with and without non-update events (disconnects, etc.)
    """

    @staticmethod
    def load_mysampler_data(ident: str, unix_epoch_ms: bool = False):
        """Load test case data for mysampler"""
        exp_data = pd.read_csv(f"{DIR}/data/myquery_{ident}-data.csv", index_col=0)
        if not unix_epoch_ms:
            exp_data.index = pd.to_datetime(exp_data.index)

        for col in exp_data:
            if exp_data[col].dtype == "float64":
                exp_data[col] = exp_data[col].astype("float32")

        with open(f"{DIR}/data/myquery_{ident}-disconnects.json", "r") as f:
            exp_disconnects = json.load(f)

        with open(f"{DIR}/data/myquery_{ident}-metadata.json", "r") as f:
            exp_metadata = json.load(f)

        return exp_data, exp_disconnects, exp_metadata


    @staticmethod
    def save_mysampler_data(ident: str, data: pd.DataFrame, disconnects: Dict[str, pd.Series],
                            metadata: Dict[str, object]):
        """Convenient way to save test case data for mysampler."""
        data.to_csv(f"{DIR}/data/myquery_{ident}-data.csv", date_format="%Y-%m-%d %H:%M:%S.%f")

        with open(f"{DIR}/data/myquery_{ident}-disconnects.json", "w") as f:
            # noinspection PyTypeChecker
            json.dump(json_normalize(disconnects), f)
            # json.dump(disconnects, f, cls=myquery.MyQueryEncoder)

        with open(f"{DIR}/data/myquery_{ident}-metadata.json", "w") as f:
            # noinspection PyTypeChecker
            json.dump(json_normalize(metadata), f)

    def check_mysampler_result(self, exp_data, exp_disconnects, exp_metadata, res_data,
                               res_disconnects, res_metadata):
        """Utility function for checking tes results of mysampler"""
        self.assertTrue(exp_data.equals(res_data), f"\nExpected:\n{exp_data}\nResult:\n{res_data}\n")
        self.assertDictEqual(exp_disconnects, json_normalize(res_disconnects),
                                  f"\nExpected:\n{exp_disconnects}\nResult:\n{res_disconnects}\n")
        self.assertDictEqual(exp_metadata, json_normalize(res_metadata),
                                  f"\nExpected:\n{exp_metadata}\nResult:\n{res_metadata}\n")

    def test_get_mysampler_1(self):
        """Test basic query with lots of default values. (includes NaN)"""

        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=600_000,  # 10 minutes
                                       num_samples=10,
                                       pvlist=["channel100", "channel101"],
                                       deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_1", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_1")
        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                                    res_metadata)
        self.assertEqual(np.float32, res_data.channel100.dtype)
        self.assertEqual(np.float32, res_data.channel101.dtype)


    def test_get_mysampler_2(self):
        """Test basic query with lots of default values. (includes NaNs)"""

        query = MySamplerQuery(start=datetime.strptime("2018-04-24 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=3_600_000, # hourly
                                       num_samples=15,
                                       pvlist=["channel100", "channel101"],
                                       deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_2", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_2")
        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                               res_metadata)
        self.assertEqual(np.float32, res_data.channel100.dtype)
        self.assertEqual(np.float32, res_data.channel101.dtype)


    def test_get_mysampler_3(self):
        """Test basic query with an enum type."""

        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=1_800_000, # 30 minutes
                                       num_samples=15,
                                       pvlist=["channel1", "channel2"],
                                       deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_3", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_3")
        exp_data['channel2'] = exp_data['channel2'].astype("Int16")

        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                               res_metadata)
        self.assertEqual(np.float32, res_data.channel1.dtype)
        self.assertEqual(pd.Int16Dtype(), res_data.channel2.dtype)


    def test_get_mysampler_4(self):
        """Test basic query with an enum type with string response."""

        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=1_800_000, # 30 minutes
                                       num_samples=15,
                                       pvlist=["channel1", "channel2"],
                                       enums_as_strings=True,
                                       deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_4", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_4")
        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                               res_metadata)
        self.assertEqual(np.float32, res_data.channel1.dtype)
        self.assertEqual(object, res_data.channel2.dtype)



    def test_get_mysampler_5(self):
        """Test basic query with an enum type with string responses and a vector valued (DBR_DOUBLE) channel."""

        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=1_800_000, # 30 minutes
                                       num_samples=15,
                                       pvlist=["channel2", "channel3"],
                                       enums_as_strings=True,
                                       deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_5", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_5")
        exp_data = exp_data.apply(process_vector_series, axis=0)
        exp_data[exp_data.isnull()] = None

        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                               res_metadata)
        self.assertEqual(object, res_data.channel2.dtype)
        self.assertEqual(object, res_data.channel3.dtype)

    def test_get_mysampler_unarchived_pv(self):
        """Test query with a float type and a PV name that is not in the archiver raises error (< 1000 samples).

        We've seen situations where a small request behaves differently than a large request, breakpoint ~1000 samples
        """
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=1, # 1 millisecond
                                       num_samples=500,
                                       pvlist=["channel1", "bad_channel"],
                                       deployment="docker")

        mysampler = MySampler(query)
        with self.assertRaises(RequestException):
            mysampler.run()

    def test_get_mysampler_unarchived_pv2(self):
        """Test query with a float type and a PV name that is not in the archiver raises error (>= 1000 samples).

        We've seen situations where a small request behaves differently than a large request, breakpoint ~1000 samples
        """
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=1, # 1 millisecond
                                       num_samples=5000,
                                       pvlist=["channel1", "bad_channel"],
                                       deployment="docker")

        mysampler = MySampler(query)
        with self.assertRaises(RequestException):
            mysampler.run()

    def test_get_mysampler_unarchived_pv3(self):
        """Test query with a float type and a PV name that is not in the archiver raises error (< 1000 samples).

        We've seen situations where a small request behaves differently than a large request, breakpoint ~1000 samples.
        Trying different orders of the PV as we've seen that have an impact.
        """
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=1,  # 1 millisecond
                               num_samples=500,
                               pvlist=["bad_channel", "channel1"],
                               deployment="docker")

        mysampler = MySampler(query)
        with self.assertRaises(RequestException):
            mysampler.run()

    def test_get_mysampler_unarchived_pv4(self):
        """Test query with a float type and a PV name that is not in the archiver raises error (>= 1000 samples).

        We've seen situations where a small request behaves differently than a large request, breakpoint ~1000 samples
        Trying different orders of the PV as we've seen that have an impact.
        """
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=1,  # 1 millisecond
                               num_samples=5000,
                               pvlist=["bad_channel", "channel1"],
                               deployment="docker")

        mysampler = MySampler(query)
        with self.assertRaises(RequestException):
            mysampler.run()

    def test_get_mysampler_history_origin(self):
        """Test mysampler when the first sample is both a non-standard update event ("CHANNELS_PRIOR_DATA_DISCARDED")"""

        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:01", "%Y-%m-%d %H:%M:%S"),
                                       interval=1_800_000, # 30 minutes
                                       num_samples=15,
                                       pvlist=["channel1", "channel2"],
                                       deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_history_origin", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_history_origin")
        exp_data['channel2'] = exp_data['channel2'].astype("Int16")

        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                               res_metadata)
        self.assertEqual(np.float32, res_data.channel1.dtype)
        self.assertEqual(pd.Int16Dtype(), res_data.channel2.dtype)


    def test_get_mysampler_with_n_queries_strategy(self):
        """Test query with sample_strategy='n_queries'.  Should match test_mysampler_1."""

        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=600_000,  # 10 minutes
                                       num_samples=10,
                                       pvlist=["channel100", "channel101"],
                                       deployment="docker",
                                       sample_strategy="n_queries")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # Should get same results as test_get_mysampler_1 (which uses default strategy)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_1")
        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                                    res_metadata)
        self.assertEqual(np.float32, res_data.channel100.dtype)
        self.assertEqual(np.float32, res_data.channel101.dtype)

    def test_get_mysampler_with_stream_strategy(self):
        """Test query with sample_strategy='stream'.  Should match test_mysampler_1."""

        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=600_000,  # 10 minutes
                                       num_samples=10,
                                       pvlist=["channel100", "channel101"],
                                       deployment="docker",
                                       sample_strategy="stream")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # Should get same results as test_get_mysampler_1 (which uses default strategy)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_1")
        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                                    res_metadata)
        self.assertEqual(np.float32, res_data.channel100.dtype)
        self.assertEqual(np.float32, res_data.channel101.dtype)

    def test_get_mysampler_invalid_strategy(self):
        """Test that invalid sample_strategy raises ValueError."""

        with self.assertRaises(ValueError) as context:
            MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                   interval=600_000,
                                   num_samples=10,
                                   pvlist=["channel100", "channel101"],
                                   deployment="docker",
                                   sample_strategy="invalid_strategy")

        self.assertIn("sample_strategy must be None, 'n_queries', or 'stream'", str(context.exception))

    def test_get_mysampler_102(self):
        """Test mysampler query for channel102 over similar time range as channel101."""

        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=600_000,  # 10 minutes
                                       num_samples=10,
                                       pvlist=["channel102"],
                                       deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_102", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_102")
        exp_data = exp_data.apply(process_vector_series, axis=0)
        exp_data[exp_data.isnull()] = None
        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                                    res_metadata)

    def test_get_mysampler_102_epoch(self):
        """Test mysampler query for channel102 over similar time range as channel101."""

        unix_timestamps_ms = True
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000,  # 10 minutes
                               num_samples=10,
                               pvlist=["channel102"],
                               unix_timestamps_ms=unix_timestamps_ms,
                               deployment="docker")

        mysampler = MySampler(query)
        mysampler.run()
        res_data = mysampler.data
        res_disconnects = mysampler.disconnects
        res_metadata = mysampler.metadata

        # self.save_mysampler_data("mysampler_102_epoch", res_data, res_disconnects, res_metadata)
        exp_data, exp_disconnects, exp_metadata = self.load_mysampler_data("mysampler_102_epoch",
                                                                           unix_epoch_ms=unix_timestamps_ms)
        exp_data = exp_data.apply(process_vector_series, axis=0)
        exp_data[exp_data.isnull()] = None

        self.check_mysampler_result(exp_data, exp_disconnects, exp_metadata, res_data, res_disconnects,
                                    res_metadata)


class TestMySamplerTimestampTransfer(unittest.TestCase):
    """MySampler always transfers timestamps as millis since unix epoch.  When presented as datetimes, the results
    should match what myquery returns when asked for its local time strings directly.
    """

    @staticmethod
    def run_local_time_strings(query: MySamplerQuery):
        """Run the query without unix timestamps, parsing myquery's local time strings as MySampler used to."""
        opts = query.to_web_params()
        del opts["u"]
        url = f"{config.protocol}://{config.myquery_server}{config.mysampler_path}"
        with requests.get(url, params=opts, stream=True) as r:
            r.raise_for_status()
            return _parse_json_iteratively(r, num_samples=query.num_samples, enums_as_strings=query.enums_as_strings,
                                           sig_figs=int(opts.get("v", 6)), unix_timestamps_ms=False)

    def check_matches_local_time_strings(self, query: MySamplerQuery):
        exp_data, exp_metadata, exp_disconnects = self.run_local_time_strings(query)

        mysampler = MySampler(query)
        mysampler.run()

        self.assertEqual("datetime64[ns]", mysampler.data.index.dtype)
        self.assertTrue(exp_data.equals(mysampler.data), f"\nExpected:\n{exp_data}\nResult:\n{mysampler.data}\n")
        self.assertDictEqual(json_normalize(exp_disconnects), json_normalize(mysampler.disconnects))
        self.assertDictEqual(json_normalize(exp_metadata), json_normalize(mysampler.metadata))
        return mysampler

    def test_frac_time_digits(self):
        """Disconnect and label timestamps are formatted as myquery would for each frac_time_digits setting."""
        for frac_time_digits in (None, 0, 3, 9):
            with self.subTest(frac_time_digits=frac_time_digits):
                query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                                       interval=1_800_000, num_samples=15, pvlist=["channel1", "channel2"],
                                       frac_time_digits=frac_time_digits, deployment="docker")
                mysampler = self.check_matches_local_time_strings(query)
                self.assertIn("labels", mysampler.metadata["channel2"])
                self.assertGreater(len(mysampler.disconnects["channel2"]), 0)

    def test_disconnects(self):
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel100", "channel101", "channel102"],
                               deployment="docker")
        self.check_matches_local_time_strings(query)

    def test_dst_transitions(self):
        """Local times match myquery across both daylight saving time transitions."""
        for start in ("2019-03-10 00:00:00", "2019-11-03 00:00:00"):
            with self.subTest(start=start):
                query = MySamplerQuery(start=datetime.strptime(start, "%Y-%m-%d %H:%M:%S"),
                                       interval=900_000, num_samples=16, pvlist=["channel1", "channel100"],
                                       deployment="docker")
                self.check_matches_local_time_strings(query)

    def test_fall_back_unix_timestamps_are_unique(self):
        """Samples in the repeated hour share local times, but their unix timestamps are distinct."""
        kwargs = dict(start=datetime.strptime("2019-11-03 00:30:00", "%Y-%m-%d %H:%M:%S"), interval=900_000,
                      num_samples=12, pvlist=["channel1"], deployment="docker")

        local = MySampler(MySamplerQuery(**kwargs))
        local.run()
        unix = MySampler(MySamplerQuery(unix_timestamps_ms=True, **kwargs))
        unix.run()

        self.assertFalse(local.data.index.is_unique)
        self.assertTrue(unix.data.index.is_unique)
        self.assertTrue((np.diff(unix.data.index.to_numpy()) == kwargs["interval"]).all())
        self.assertTrue(local.data.reset_index(drop=True).equals(unix.data.reset_index(drop=True)))

    def test_adjust_time_to_server_offset(self):
        """myquery always returns unix timestamps when adjusting to the server offset.  These are presented as the
        same local times as an unadjusted query, and as shifted unix timestamps when requested.
        """
        kwargs = dict(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"), interval=600_000,
                      num_samples=10, pvlist=["channel100"], deployment="docker")

        unadjusted = MySampler(MySamplerQuery(**kwargs))
        unadjusted.run()
        adjusted = MySampler(MySamplerQuery(adjust_time_to_server_offset=True, **kwargs))
        adjusted.run()
        adjusted_ms = MySampler(MySamplerQuery(adjust_time_to_server_offset=True, unix_timestamps_ms=True, **kwargs))
        adjusted_ms.run()

        self.assertTrue(unadjusted.data.equals(adjusted.data))
        self.assertDictEqual(json_normalize(unadjusted.disconnects), json_normalize(adjusted.disconnects))
        # 2018-04-24 12:00:00 as if it were UTC
        self.assertEqual(1524571200000, adjusted_ms.data.index[0])
