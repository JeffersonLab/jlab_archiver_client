import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from jlab_archiver_client import MySampler, MySamplerQuery
from jlab_archiver_client.config import config
# noinspection PyProtectedMember
from jlab_archiver_client.mysampler import (
    _chunk_queries, _merge_metadata, default_disconnects_path, PARQUET_QUERY_KEY, PARQUET_METADATA_KEY,
    PARQUET_VERSION_KEY, DEFAULT_PARQUET_CHUNK_SIZE
)


def make_query(start=datetime(2019, 8, 12), interval=1_000, num_samples=10, **kwargs):
    return MySamplerQuery(start=start, interval=interval, num_samples=num_samples,
                          pvlist=kwargs.pop("pvlist", ["pv_float", "pv_enum"]), deployment="docker", **kwargs)


def fake_fetch(chunk_query: MySamplerQuery):
    """Build a synthetic mysampler result for a chunk.  Values are the sample's offset (seconds) from 2019-08-12.

    Every third sample of pv_float is a disconnect, and pv_enum is an Int16 column that is entirely disconnected in
    any chunk that starts at or after 2019-08-12 00:00:08.
    """
    start = datetime.fromisoformat(chunk_query.start)
    dates = pd.DatetimeIndex([start + timedelta(milliseconds=i * chunk_query.interval)
                              for i in range(chunk_query.num_samples)], name="Date")
    offsets = np.asarray((dates - pd.Timestamp("2019-08-12")).total_seconds())

    floats = offsets.astype(np.float32)
    float_disconnect = (offsets % 3) == 0
    floats[float_disconnect] = np.nan
    enum_values = pd.array(offsets.astype(np.int16), dtype="Int16")
    if start >= datetime(2019, 8, 12, 0, 0, 8):
        enum_values[:] = pd.NA

    df = pd.DataFrame({"pv_float": floats, "pv_enum": enum_values}, index=dates)
    raw_dates = [d.strftime("%Y-%m-%dT%H:%M:%S") for d in dates]
    disconnects = {
        "pv_float": pd.Series(["NETWORK_DISCONNECTION"] * int(float_disconnect.sum()),
                              index=[d for d, x in zip(raw_dates, float_disconnect) if x], name="pv_float"),
        "pv_enum": pd.Series([], index=[], name="pv_enum", dtype=object),
    }
    if start >= datetime(2019, 8, 12, 0, 0, 8):
        disconnects["pv_enum"] = pd.Series(["UNDEFINED"] * len(dates), index=raw_dates, name="pv_enum")

    metadata = {
        "pv_float": {"metadata": {"name": "pv_float", "datatype": "DBR_DOUBLE", "datasize": 1},
                     "returnCount": chunk_query.num_samples},
        "pv_enum": {"metadata": {"name": "pv_enum", "datatype": "DBR_ENUM", "datasize": 1},
                    "labels": [{"d": "2016-08-12T13:00:49", "value": ["A", "B"]}],
                    "returnCount": chunk_query.num_samples},
    }
    return df, metadata, disconnects


class TestChunkQueries(unittest.TestCase):
    """Test how mysampler queries are split into time chunks."""

    def assert_chunks(self, chunks, expected):
        self.assertListEqual(expected, [(c.start, c.num_samples) for c in chunks])

    def test_split_with_remainder(self):
        chunks = _chunk_queries(make_query(num_samples=10), chunk_size=4, server_timezone="America/New_York")
        self.assert_chunks(chunks, [("2019-08-12 00:00:00", 4), ("2019-08-12 00:00:04", 4),
                                    ("2019-08-12 00:00:08", 2)])

    def test_split_even(self):
        chunks = _chunk_queries(make_query(num_samples=8), chunk_size=4, server_timezone="America/New_York")
        self.assert_chunks(chunks, [("2019-08-12 00:00:00", 4), ("2019-08-12 00:00:04", 4)])

    def test_single_chunk(self):
        query = make_query(num_samples=10)
        chunks = _chunk_queries(query, chunk_size=DEFAULT_PARQUET_CHUNK_SIZE, server_timezone="America/New_York")
        self.assert_chunks(chunks, [("2019-08-12 00:00:00", 10)])
        # Chunks are copies.  The original query is left alone.
        self.assertIsNot(query, chunks[0])

    def test_chunks_keep_query_options(self):
        query = make_query(num_samples=10, enums_as_strings=True, unix_timestamps_ms=True,
                           sample_strategy="n_queries", sig_figs=3)
        for chunk in _chunk_queries(query, chunk_size=3, server_timezone="America/New_York"):
            self.assertTrue(chunk.enums_as_strings)
            self.assertTrue(chunk.unix_timestamps_ms)
            self.assertEqual("n_queries", chunk.sample_strategy)
            self.assertEqual(3, chunk.sig_figs)
            self.assertListEqual(["pv_float", "pv_enum"], chunk.pvlist)
        self.assertEqual("2019-08-12 00:00:00", query.start)
        self.assertEqual(10, query.num_samples)

    def test_fractional_second_starts(self):
        chunks = _chunk_queries(make_query(interval=250, num_samples=10), chunk_size=3,
                                server_timezone="America/New_York")
        self.assert_chunks(chunks, [("2019-08-12 00:00:00", 3), ("2019-08-12 00:00:00.750", 3),
                                    ("2019-08-12 00:00:01.500", 3), ("2019-08-12 00:00:02.250", 1)])
        self.assertEqual("2019-08-12T00:00:00.750", chunks[1].to_web_params()["b"])

    def test_spring_forward(self):
        """Clocks skip 02:00-03:00 on 2019-03-10.  Samples are 15 minutes apart in absolute time."""
        chunks = _chunk_queries(make_query(start=datetime(2019, 3, 10, 1, 0), interval=900_000, num_samples=12),
                                chunk_size=4, server_timezone="America/New_York")
        self.assert_chunks(chunks, [("2019-03-10 01:00:00", 4), ("2019-03-10 03:00:00", 4),
                                    ("2019-03-10 04:00:00", 4)])

    def test_fall_back_boundary_moved_past_repeated_hour(self):
        """Clocks repeat 01:00-02:00 on 2019-11-03.  myquery can't start a chunk during the repeated hour."""
        chunks = _chunk_queries(make_query(start=datetime(2019, 11, 3, 0, 0), interval=900_000, num_samples=20),
                                chunk_size=4, server_timezone="America/New_York")
        # 00:00 EDT, 01:00 EDT, then samples 8-11 (01:00-01:45 EST) are repeated wall times, so chunk 2 runs until the
        # sample at 02:00 EST.
        self.assert_chunks(chunks, [("2019-11-03 00:00:00", 4), ("2019-11-03 01:00:00", 8),
                                    ("2019-11-03 02:00:00", 4), ("2019-11-03 03:00:00", 4)])

    def test_fall_back_first_occurrence_allowed(self):
        """A chunk may start during the first occurrence of the repeated hour, which is what myquery assumes."""
        chunks = _chunk_queries(make_query(start=datetime(2019, 11, 3, 0, 0), interval=1_800_000, num_samples=6),
                                chunk_size=3, server_timezone="America/New_York")
        self.assert_chunks(chunks, [("2019-11-03 00:00:00", 3), ("2019-11-03 01:30:00", 3)])

    def test_fall_back_boundary_pushed_past_end(self):
        """If no sample after the boundary can be requested, the last chunk absorbs the rest of the query."""
        chunks = _chunk_queries(make_query(start=datetime(2019, 11, 3, 1, 0), interval=900_000, num_samples=6),
                                chunk_size=4, server_timezone="America/New_York")
        self.assert_chunks(chunks, [("2019-11-03 01:00:00", 6)])

    def test_utc_server(self):
        """No DST adjustments for a server that runs on UTC."""
        chunks = _chunk_queries(make_query(start=datetime(2019, 11, 3, 0, 0), interval=900_000, num_samples=12),
                                chunk_size=4, server_timezone="UTC")
        self.assert_chunks(chunks, [("2019-11-03 00:00:00", 4), ("2019-11-03 01:00:00", 4),
                                    ("2019-11-03 02:00:00", 4)])


class TestHelpers(unittest.TestCase):

    def test_default_disconnects_path(self):
        self.assertEqual("out-disconnects.parquet", default_disconnects_path("out.parquet"))
        self.assertEqual(os.path.join("a.b", "out-disconnects.parquet"),
                         default_disconnects_path(os.path.join("a.b", "out.parquet")))
        self.assertEqual("out-disconnects.parquet", default_disconnects_path("out.PARQUET"))
        self.assertEqual("out.pq-disconnects.parquet", default_disconnects_path("out.pq"))

    def test_merge_metadata(self):
        chunk1 = {"pv": {"metadata": {"name": "pv"}, "returnCount": 4,
                         "labels": [{"d": "2016-01-01T00:00:00", "value": ["A"]}]}}
        chunk2 = {"pv": {"metadata": {"name": "pv"}, "returnCount": 2,
                         "labels": [{"d": "2016-01-01T00:00:00", "value": ["A"]},
                                    {"d": "2020-01-01T00:00:00", "value": ["A", "B"]}]}}
        merged = _merge_metadata(None, chunk1)
        merged = _merge_metadata(merged, chunk2)
        self.assertEqual(6, merged["pv"]["returnCount"])
        self.assertListEqual([{"d": "2016-01-01T00:00:00", "value": ["A"]},
                              {"d": "2020-01-01T00:00:00", "value": ["A", "B"]}], merged["pv"]["labels"])
        # The first chunk's metadata is copied, not modified.
        self.assertEqual(4, chunk1["pv"]["returnCount"])
        self.assertEqual(1, len(chunk1["pv"]["labels"]))


class TestRunToParquet(unittest.TestCase):
    """Test MySampler.run_to_parquet with a fake server response."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "out.parquet")
        self.disconnects_path = os.path.join(self.tmp.name, "out-disconnects.parquet")

    def tearDown(self):
        self.tmp.cleanup()

    def run_fake(self, query, **kwargs):
        mysampler = MySampler(query, url="http://example.com/myquery/mysampler")
        with patch.object(MySampler, "_fetch", side_effect=fake_fetch) as mock_fetch:
            mysampler.run_to_parquet(self.path, **kwargs)
        return mysampler, mock_fetch

    def test_data_matches_single_request(self):
        query = make_query(num_samples=10)
        mysampler, mock_fetch = self.run_fake(query, chunk_size=4)

        self.assertListEqual([("2019-08-12 00:00:00", 4), ("2019-08-12 00:00:04", 4), ("2019-08-12 00:00:08", 2)],
                             [(c.args[0].start, c.args[0].num_samples) for c in mock_fetch.call_args_list])
        exp_data = pd.concat([fake_fetch(c.args[0])[0] for c in mock_fetch.call_args_list])
        self.assertEqual(10, len(exp_data))

        data = pd.read_parquet(self.path)
        self.assertTrue(exp_data.equals(data), f"\nExpected:\n{exp_data}\nResult:\n{data}\n")
        self.assertEqual(np.float32, data.pv_float.dtype)
        self.assertEqual(pd.Int16Dtype(), data.pv_enum.dtype)
        self.assertEqual(3, pq.ParquetFile(self.path).num_row_groups)

        # Data fields aren't populated by run_to_parquet.  Metadata is.
        self.assertIsNone(mysampler.data)
        self.assertIsNone(mysampler.disconnects)
        self.assertEqual(10, mysampler.metadata["pv_float"]["returnCount"])

    def test_disconnects_sidecar(self):
        self.run_fake(make_query(num_samples=10), chunk_size=4)

        disconnects = pd.read_parquet(self.disconnects_path)
        self.assertListEqual(["pv", "Date", "event"], list(disconnects.columns))
        self.assertEqual("datetime64[ns]", disconnects.Date.dtype)

        float_events = disconnects[disconnects.pv == "pv_float"]
        self.assertListEqual(list(pd.to_datetime(["2019-08-12 00:00:00", "2019-08-12 00:00:03",
                                                  "2019-08-12 00:00:06", "2019-08-12 00:00:09"])),
                             list(float_events.Date))
        self.assertTrue((float_events.event == "NETWORK_DISCONNECTION").all())

        enum_events = disconnects[disconnects.pv == "pv_enum"]
        self.assertListEqual(list(pd.to_datetime(["2019-08-12 00:00:08", "2019-08-12 00:00:09"])),
                             list(enum_events.Date))
        self.assertTrue((enum_events.event == "UNDEFINED").all())

    def test_file_metadata(self):
        query = make_query(num_samples=10, enums_as_strings=False)
        self.run_fake(query, chunk_size=4)

        exp_query = {
            "endpoint": "mysampler",
            "url": "http://example.com/myquery/mysampler",
            "query": query.to_dict(),
            "web_params": json.loads(json.dumps(query.to_web_params())),
            "chunk_size": 4,
            "server_timezone": config.server_timezone,
        }
        for path in (self.path, self.disconnects_path):
            kv = pq.read_metadata(path).metadata
            self.assertDictEqual(exp_query, json.loads(kv[PARQUET_QUERY_KEY.encode()]))
            self.assertIn(PARQUET_VERSION_KEY.encode(), kv)

        data_metadata = json.loads(pq.read_metadata(self.path).metadata[PARQUET_METADATA_KEY.encode()])
        self.assertEqual(10, data_metadata["pv_float"]["returnCount"])
        self.assertEqual(10, data_metadata["pv_enum"]["returnCount"])
        self.assertListEqual([{"d": "2016-08-12T13:00:49", "value": ["A", "B"]}], data_metadata["pv_enum"]["labels"])
        self.assertNotIn(PARQUET_METADATA_KEY.encode(), pq.read_metadata(self.disconnects_path).metadata)

        # The query is also available from the arrow schema.
        self.assertIn(PARQUET_QUERY_KEY.encode(), pq.read_schema(self.path).metadata)

    def test_custom_disconnects_path(self):
        other = os.path.join(self.tmp.name, "events.parquet")
        self.run_fake(make_query(num_samples=5), chunk_size=2, disconnects_path=other)
        self.assertTrue(os.path.exists(other))
        self.assertFalse(os.path.exists(self.disconnects_path))
        self.assertEqual(2, len(pd.read_parquet(other)))

    def test_no_disconnects(self):
        """Sidecar is written even if there are no disconnects."""
        def no_disconnects(chunk_query):
            df, metadata, disconnects = fake_fetch(chunk_query)
            return df, metadata, {pv: s.iloc[0:0] for pv, s in disconnects.items()}

        mysampler = MySampler(make_query(num_samples=5))
        with patch.object(MySampler, "_fetch", side_effect=no_disconnects):
            mysampler.run_to_parquet(self.path, chunk_size=2)

        disconnects = pd.read_parquet(self.disconnects_path)
        self.assertEqual(0, len(disconnects))
        self.assertListEqual(["pv", "Date", "event"], list(disconnects.columns))

    def test_unix_timestamps_ms(self):
        def epoch_fetch(chunk_query):
            df, metadata, disconnects = fake_fetch(chunk_query)
            df.index = pd.Index(df.index.as_unit("ms").asi8, name="Date")
            disconnects = {pv: pd.Series(s.values, index=pd.to_datetime(s.index).as_unit("ms").asi8, name=pv)
                           for pv, s in disconnects.items()}
            return df, metadata, disconnects

        mysampler = MySampler(make_query(num_samples=5, unix_timestamps_ms=True))
        with patch.object(MySampler, "_fetch", side_effect=epoch_fetch):
            mysampler.run_to_parquet(self.path, chunk_size=2)

        data = pd.read_parquet(self.path)
        self.assertEqual(np.int64, data.index.dtype)
        self.assertEqual(int(pd.Timestamp("2019-08-12").timestamp() * 1000), data.index[0])
        disconnects = pd.read_parquet(self.disconnects_path)
        self.assertEqual(np.int64, disconnects.Date.dtype)

    def test_failure_cleans_up(self):
        """A failed request removes partial output and leaves existing output untouched."""
        with open(self.path, "w") as f:
            f.write("existing")

        calls = []
        failing_call = 2

        def fail_second(chunk_query):
            calls.append(chunk_query)
            if len(calls) == failing_call:
                raise RuntimeError("server error")
            return fake_fetch(chunk_query)

        mysampler = MySampler(make_query(num_samples=10))
        with patch.object(MySampler, "_fetch", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                mysampler.run_to_parquet(self.path, chunk_size=4)

        self.assertListEqual(["out.parquet"], os.listdir(self.tmp.name))
        with open(self.path) as f:
            self.assertEqual("existing", f.read())
        self.assertIsNone(mysampler.metadata)

    def test_invalid_arguments(self):
        mysampler = MySampler(make_query(num_samples=10))
        with patch.object(MySampler, "_fetch", side_effect=fake_fetch) as mock_fetch:
            with self.assertRaises(ValueError):
                mysampler.run_to_parquet(self.path, chunk_size=0)
            with self.assertRaises(ValueError):
                mysampler.run_to_parquet(self.path, disconnects_path=self.path)
            with self.assertRaises(ValueError):
                MySampler(make_query(num_samples=0)).run_to_parquet(self.path)
        mock_fetch.assert_not_called()
        self.assertListEqual([], os.listdir(self.tmp.name))

    def test_missing_pyarrow(self):
        mysampler = MySampler(make_query())
        with patch.dict(sys.modules, {"pyarrow": None, "pyarrow.parquet": None}):
            with self.assertRaises(ImportError) as context:
                mysampler.run_to_parquet(self.path)
        self.assertIn("jlab_archiver_client[parquet]", str(context.exception))
