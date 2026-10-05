import os
import tempfile
import unittest
import json
from datetime import datetime
from typing import Dict
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests
from requests import RequestException

from jlab_archiver_client import MySampler
from jlab_archiver_client import MySamplerQuery
from jlab_archiver_client.mysampler import PARQUET_METADATA_KEY, PARQUET_QUERY_KEY
from jlab_archiver_client.utils import json_normalize, format_index_ns


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


class TestMySamplerParquet(unittest.TestCase):
    """Test MySampler.run_to_parquet against the same saved results as MySampler.run().

    Small chunk sizes are used so that each query is split into several requests, including a partial final chunk.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "out.parquet")
        self.disconnects_path = os.path.join(self.tmp.name, "out-disconnects.parquet")

    def tearDown(self):
        self.tmp.cleanup()

    def run_parquet(self, query: MySamplerQuery, chunk_size: int = 4):
        """Run the query to parquet and read the results back in the same form MySampler.run() provides."""
        mysampler = MySampler(query)
        mysampler.run_to_parquet(self.path, chunk_size=chunk_size)

        data = pd.read_parquet(self.path)
        metadata = json.loads(pq.read_metadata(self.path).metadata[PARQUET_METADATA_KEY.encode()])

        # Disconnect timestamps in the saved results are the strings returned by myquery.
        events = pd.read_parquet(self.disconnects_path)
        disconnects = {}
        for pv in query.pvlist:
            pv_events = events[events.pv == pv]
            index = pv_events.Date.to_numpy()
            if not query.unix_timestamps_ms:
                index = format_index_ns(pd.DatetimeIndex(index), query.frac_time_digits)
            disconnects[pv] = pd.Series(pv_events.event.to_numpy(), index=index, name=pv)

        return data, disconnects, metadata, mysampler

    def check_parquet_result(self, ident: str, query: MySamplerQuery, chunk_size: int = 4, unix_epoch_ms=False,
                             vector=False, int_columns=()):
        res_data, res_disconnects, res_metadata, mysampler = self.run_parquet(query, chunk_size)

        exp_data, exp_disconnects, exp_metadata = TestMySampler.load_mysampler_data(ident, unix_epoch_ms=unix_epoch_ms)
        if vector:
            exp_data = exp_data.apply(process_vector_series, axis=0)
            exp_data[exp_data.isnull()] = None
        for col in int_columns:
            exp_data[col] = exp_data[col].astype("Int16")

        self.assertTrue(exp_data.equals(res_data), f"\nExpected:\n{exp_data}\nResult:\n{res_data}\n")
        self.assertDictEqual(exp_disconnects, json_normalize(res_disconnects))
        self.assertDictEqual(exp_metadata, res_metadata)
        self.assertDictEqual(exp_metadata, json_normalize(mysampler.metadata))
        return res_data

    def test_parquet_1(self):
        """Test basic query with lots of default values. (includes NaN)"""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel100", "channel101"],
                               deployment="docker")
        res_data = self.check_parquet_result("mysampler_1", query)
        self.assertEqual(np.float32, res_data.channel100.dtype)
        self.assertEqual(np.float32, res_data.channel101.dtype)
        self.assertEqual(3, pq.ParquetFile(self.path).num_row_groups)

    def test_parquet_2(self):
        """Test basic query with lots of default values. (includes NaNs)"""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 00:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=3_600_000, num_samples=15, pvlist=["channel100", "channel101"],
                               deployment="docker")
        self.check_parquet_result("mysampler_2", query)

    def test_parquet_3(self):
        """Test basic query with an enum type."""
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=1_800_000, num_samples=15, pvlist=["channel1", "channel2"],
                               deployment="docker")
        res_data = self.check_parquet_result("mysampler_3", query, int_columns=["channel2"])
        self.assertEqual(np.float32, res_data.channel1.dtype)
        self.assertEqual(pd.Int16Dtype(), res_data.channel2.dtype)

    def test_parquet_4(self):
        """Test basic query with an enum type with string response."""
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=1_800_000, num_samples=15, pvlist=["channel1", "channel2"],
                               enums_as_strings=True, deployment="docker")
        res_data = self.check_parquet_result("mysampler_4", query)
        self.assertEqual(object, res_data.channel2.dtype)

    def test_parquet_5(self):
        """Test basic query with an enum type with string responses and a vector valued (DBR_DOUBLE) channel."""
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=1_800_000, num_samples=15, pvlist=["channel2", "channel3"],
                               enums_as_strings=True, deployment="docker")
        self.check_parquet_result("mysampler_5", query, vector=True)

    def test_parquet_history_origin(self):
        """Test when the first sample is a non-standard update event ("CHANNELS_PRIOR_DATA_DISCARDED")"""
        query = MySamplerQuery(start=datetime.strptime("2019-08-12 00:00:01", "%Y-%m-%d %H:%M:%S"),
                               interval=1_800_000, num_samples=15, pvlist=["channel1", "channel2"],
                               deployment="docker")
        self.check_parquet_result("mysampler_history_origin", query, int_columns=["channel2"])

    def test_parquet_with_n_queries_strategy(self):
        """Test query with sample_strategy='n_queries'.  Should match test_mysampler_1."""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel100", "channel101"],
                               deployment="docker", sample_strategy="n_queries")
        self.check_parquet_result("mysampler_1", query)

    def test_parquet_102(self):
        """Test vector valued channel102."""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel102"], deployment="docker")
        self.check_parquet_result("mysampler_102", query, vector=True)

    def test_parquet_102_epoch(self):
        """Test vector valued channel102 with unix timestamps."""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel102"], unix_timestamps_ms=True,
                               deployment="docker")
        res_data = self.check_parquet_result("mysampler_102_epoch", query, unix_epoch_ms=True, vector=True)
        self.assertEqual(np.int64, res_data.index.dtype)

    def test_parquet_chunk_sizes(self):
        """Chunk sizes of one sample, and more samples than the query, give the same results."""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel100", "channel101"],
                               deployment="docker")
        for chunk_size, row_groups in ((1, 10), (1_000, 1)):
            with self.subTest(chunk_size=chunk_size):
                self.check_parquet_result("mysampler_1", query, chunk_size=chunk_size)
                self.assertEqual(row_groups, pq.ParquetFile(self.path).num_row_groups)

    def test_parquet_query_metadata(self):
        """Both files record the query that generated them."""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel100", "channel101"],
                               deployment="docker")
        self.run_parquet(query)
        for path in (self.path, self.disconnects_path):
            description = json.loads(pq.read_metadata(path).metadata[PARQUET_QUERY_KEY.encode()])
            self.assertEqual("mysampler", description["endpoint"])
            self.assertEqual(4, description["chunk_size"])
            self.assertDictEqual(query.to_dict(), description["query"])
            self.assertEqual("2018-04-24T12:00:00", description["web_params"]["b"])

    def test_parquet_dst(self):
        """Chunked queries reproduce the sample times of a single query across daylight saving time transitions."""
        for start in ("2019-03-10 00:00:00", "2019-11-03 00:00:00"):
            for unix_timestamps_ms in (False, True):
                with self.subTest(start=start, unix_timestamps_ms=unix_timestamps_ms):
                    query = MySamplerQuery(start=datetime.strptime(start, "%Y-%m-%d %H:%M:%S"),
                                           interval=900_000, num_samples=24, pvlist=["channel1", "channel100"],
                                           unix_timestamps_ms=unix_timestamps_ms, deployment="docker")
                    expected = MySampler(query)
                    expected.run()

                    res_data, res_disconnects, res_metadata, _ = self.run_parquet(query, chunk_size=4)
                    self.assertTrue(expected.data.equals(res_data),
                                    f"\nExpected:\n{expected.data}\nResult:\n{res_data}\n")
                    self.assertDictEqual(json_normalize(expected.metadata), res_metadata)
                    if unix_timestamps_ms:
                        self.assertDictEqual(json_normalize(expected.disconnects), json_normalize(res_disconnects))

    def test_parquet_bad_pv(self):
        """An unknown PV fails on the first request and leaves no output behind."""
        query = MySamplerQuery(start=datetime.strptime("2018-04-24 12:00:00", "%Y-%m-%d %H:%M:%S"),
                               interval=600_000, num_samples=10, pvlist=["channel100", "not_a_channel"],
                               deployment="docker")
        with patch("jlab_archiver_client.mysampler.requests.get", wraps=requests.get) as mock_get:
            with self.assertRaises(RequestException):
                MySampler(query).run_to_parquet(self.path, chunk_size=2)
        self.assertEqual(1, mock_get.call_count)
        self.assertListEqual([], os.listdir(self.tmp.name))
