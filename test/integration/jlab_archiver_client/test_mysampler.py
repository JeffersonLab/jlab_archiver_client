import os
import unittest
import json
from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd

from jlab_archiver_client import MySampler
from jlab_archiver_client import MySamplerQuery
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
                x[i] = np.fromstring(val.strip("[]"), sep=" ", dtype=np.float32)
        elif isinstance(val, float):
            pass
        elif isinstance(val, object):
            # This seems to work, but IDE throws a warning.
            # noinspection PyUnresolvedReferences
            if val.str.startswith("[") and val.str.endswith("]"):
                # noinspection PyUnresolvedReferences
                x[i] = np.fromstring(val.str.strip("[]"), sep=" ", dtype=np.float32)

    return x


class TestMySampler(unittest.TestCase):
    """Test the MySampler class to ensure it gives responses that mimic the myquery endpoint.

    Testing strategy here is to compare 'live' query against saved results.  The saved results have been inspected
    and should include situations with and without non-update events (disconnects, etc.)
    """

    @staticmethod
    def load_mysampler_data(ident: str):
        """Load test case data for mysampler"""
        exp_data = pd.read_csv(f"{DIR}/data/myquery_{ident}-data.csv", index_col=0)
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
