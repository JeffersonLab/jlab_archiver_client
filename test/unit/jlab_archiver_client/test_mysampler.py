import io
import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import requests
from requests import RequestException

from jlab_archiver_client import MySampler, MySamplerQuery
from jlab_archiver_client.config import config
# noinspection PyProtectedMember
from jlab_archiver_client.mysampler import (_parse_json_iteratively, _ms_to_local_time, _format_local_time,
                                            _present_as_local_time)


BAD_ERROR = "Unable to find channel: 'bad_channel' in deployment: 'docker'"


# 2019-08-12 00:00:00 America/New_York as millis since unix epoch
START_MS = 1565582400000


def good_channel(name: str, values: list) -> dict:
    """Build a mysampler channel object with one sample per value, one millisecond apart.

    Timestamps are millis since unix epoch, since MySampler always requests them from myquery.
    """
    return {
        "metadata": {"name": name, "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                     "active": True},
        "data": [{"d": START_MS + i, "v": v} for i, v in enumerate(values)],
        "returnCount": len(values),
    }


def bad_channel() -> dict:
    """Build the channel object myquery returns for a PV that is not archived."""
    return {"error": BAD_ERROR}


def make_response(body: dict, status_code: int = 200) -> MagicMock:
    """Build a mock streaming response with the given JSON body."""
    content = json.dumps(body).encode("utf-8")
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.reason = "Bad Request" if status_code == requests.codes.bad_request else "OK"
    response.headers = {"Content-Type": "application/json;charset=UTF-8"}
    response.raw = io.BytesIO(content)
    response.text = content.decode("utf-8")
    response.json.return_value = body
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def parse(body: dict, num_samples: int = 3):
    return _parse_json_iteratively(make_response(body), num_samples=num_samples, enums_as_strings=False,
                                   sig_figs=6, unix_timestamps_ms=True)


class TestParseJsonIteratively(unittest.TestCase):
    """Test the mysampler streaming parser against responses that include unarchived PVs."""

    def test_good_channels(self):
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0, 3.0]),
                             "ch2": good_channel("ch2", [4.0, 5.0, 6.0])}}
        data, metadata, disconnects = parse(body)
        self.assertListEqual(["ch1", "ch2"], list(data.columns))
        self.assertListEqual([1.0, 2.0, 3.0], data.ch1.tolist())
        self.assertListEqual([4.0, 5.0, 6.0], data.ch2.tolist())
        self.assertEqual(START_MS + 2, data.index[2])
        self.assertNotIn("error", metadata["ch1"])
        self.assertEqual(3, metadata["ch2"]["returnCount"])

    def test_bad_channel_last(self):
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0, 3.0]), "bad_channel": bad_channel()}}
        with self.assertRaises(RequestException) as context:
            parse(body)
        self.assertIn("bad_channel", str(context.exception))
        self.assertIn(BAD_ERROR, str(context.exception))
        self.assertNotIn("ch1:", str(context.exception))

    def test_bad_channel_first(self):
        body = {"channels": {"bad_channel": bad_channel(), "ch1": good_channel("ch1", [1.0, 2.0, 3.0])}}
        with self.assertRaises(RequestException) as context:
            parse(body)
        self.assertIn(BAD_ERROR, str(context.exception))

    def test_bad_channel_middle(self):
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0, 3.0]),
                             "bad_channel": bad_channel(),
                             "ch2": good_channel("ch2", [4.0, 5.0, 6.0])}}
        with self.assertRaises(RequestException) as context:
            parse(body)
        self.assertIn(BAD_ERROR, str(context.exception))

    def test_multiple_bad_channels(self):
        body = {"channels": {"bad1": {"error": "bad1 missing"},
                             "ch1": good_channel("ch1", [1.0, 2.0, 3.0]),
                             "bad2": {"error": "bad2 missing"}}}
        with self.assertRaises(RequestException) as context:
            parse(body)
        # Fail fast on the first error rather than parsing the rest of the stream
        self.assertIn("bad1: bad1 missing", str(context.exception))
        self.assertNotIn("bad2", str(context.exception))

    def test_bad_channel_stops_parsing(self):
        """The parser should raise on the first channel error without reading the rest of the stream."""
        content = (b'{"channels":{"bad_channel":{"error":"' + BAD_ERROR.encode("utf-8") + b'"},'
                   b'"ch1":{ this is not valid JSON and would fail if parsed')
        response = make_response({})
        response.raw = io.BytesIO(content)
        with self.assertRaises(RequestException) as context:
            _parse_json_iteratively(response, num_samples=3, enums_as_strings=False, sig_figs=6,
                                    unix_timestamps_ms=True)
        self.assertIn(BAD_ERROR, str(context.exception))

    def test_truncated_channel(self):
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0])}}
        with self.assertRaises(RequestException) as context:
            parse(body, num_samples=3)
        self.assertIn("Expected 3 samples, received 2", str(context.exception))


class TestMySamplerRun(unittest.TestCase):
    """Test MySampler.run() handling of responses that include unarchived PVs."""

    def setUp(self):
        self.query = MySamplerQuery(start=datetime(2019, 8, 12), interval=1, num_samples=3,
                                    pvlist=["ch1", "bad_channel"], deployment="docker")

    @patch("jlab_archiver_client.mysampler.requests.get")
    def test_bad_channel_200(self, mock_get):
        """Large responses are returned with a 200 and the channel error in the body."""
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0, 3.0]), "bad_channel": bad_channel()}}
        mock_get.return_value = make_response(body, status_code=200)
        mysampler = MySampler(self.query, url="http://localhost/mysampler")
        with self.assertRaises(RequestException) as context:
            mysampler.run()
        self.assertIn(BAD_ERROR, str(context.exception))
        self.assertIsNone(mysampler.data)

    @patch("jlab_archiver_client.mysampler.requests.get")
    def test_bad_channel_400(self, mock_get):
        """Small responses are returned with a 400.  Report the channel error, not the whole body."""
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0, 3.0]), "bad_channel": bad_channel()}}
        mock_get.return_value = make_response(body, status_code=400)
        mysampler = MySampler(self.query, url="http://localhost/mysampler")
        with self.assertRaises(RequestException) as context:
            mysampler.run()
        self.assertIn("status=400", str(context.exception))
        self.assertIn(BAD_ERROR, str(context.exception))
        self.assertNotIn("metadata", str(context.exception))

    @patch("jlab_archiver_client.mysampler.requests.get")
    def test_400_without_channel_errors(self, mock_get):
        """Other 400s fall back to reporting the response body."""
        body = {"error": "Invalid request parameters"}
        mock_get.return_value = make_response(body, status_code=400)
        mysampler = MySampler(self.query, url="http://localhost/mysampler")
        with self.assertRaises(RequestException) as context:
            mysampler.run()
        self.assertIn("status=400", str(context.exception))
        self.assertIn("Invalid request parameters", str(context.exception))


class TestPresentAsLocalTime(unittest.TestCase):
    """Test conversion of millis since unix epoch from myquery to the server's local time."""

    def test_ms_to_local_time_dst(self):
        # 2019-08-12 04:00:00Z is 00:00 EDT
        idx = _ms_to_local_time([START_MS, START_MS + 1], adjusted=False, server_timezone="America/New_York")
        self.assertEqual("datetime64[ns]", idx.dtype)
        self.assertListEqual([pd.Timestamp("2019-08-12 00:00:00"), pd.Timestamp("2019-08-12 00:00:00.001")],
                             list(idx))

    def test_ms_to_local_time_standard_time(self):
        # 2019-12-01 05:00:00Z is 00:00 EST
        idx = _ms_to_local_time([1575176400000], adjusted=False, server_timezone="America/New_York")
        self.assertEqual(pd.Timestamp("2019-12-01 00:00:00"), idx[0])

    def test_ms_to_local_time_fall_back(self):
        """Distinct instants an hour apart share a local time when clocks fall back."""
        # 2019-11-03 05:30Z (01:30 EDT) and 06:30Z (01:30 EST)
        idx = _ms_to_local_time([1572759000000, 1572762600000], adjusted=False, server_timezone="America/New_York")
        self.assertListEqual([pd.Timestamp("2019-11-03 01:30:00")] * 2, list(idx))

    def test_ms_to_local_time_adjusted(self):
        """myquery has already shifted adjusted timestamps to local time, so no conversion is applied."""
        # 2019-08-12 00:00:00 as if it were UTC
        idx = _ms_to_local_time([1565568000000], adjusted=True, server_timezone="America/New_York")
        self.assertEqual(pd.Timestamp("2019-08-12 00:00:00"), idx[0])

    def test_ms_to_local_time_utc_server(self):
        idx = _ms_to_local_time([START_MS], adjusted=False, server_timezone="UTC")
        self.assertEqual(pd.Timestamp("2019-08-12 04:00:00"), idx[0])

    def test_format_local_time(self):
        idx = pd.DatetimeIndex(["2019-08-12 00:00:00.25"]).as_unit("ns")
        # Formats match what myquery returns for each frac_time_digits setting when not using unix timestamps
        self.assertEqual("2019-08-12T00:00:00", _format_local_time(idx, None)[0])
        self.assertEqual("2019-08-12 00:00:00", _format_local_time(idx, 0)[0])
        self.assertEqual("2019-08-12 00:00:00.250", _format_local_time(idx, 3)[0])
        self.assertEqual("2019-08-12 00:00:00.250000000", _format_local_time(idx, 9)[0])

    def test_present_as_local_time(self):
        data = pd.DataFrame({"ch1": [1.0, np.nan]}, index=pd.Index([START_MS, START_MS + 1000], name="Date"))
        metadata = {"ch1": {"metadata": {"name": "ch1"}, "returnCount": 2},
                    "ch2": {"metadata": {"name": "ch2"}, "returnCount": 2,
                            "labels": [{"d": 1471021249000, "value": ["A", "B"]}]}}
        disconnects = {"ch1": pd.Series(["NETWORK_DISCONNECTION"], index=[START_MS + 1000], name="ch1"),
                       "ch2": pd.Series([], index=[], name="ch2", dtype=object)}

        _present_as_local_time(data, metadata, disconnects, adjusted=False, frac_time_digits=9,
                               server_timezone="America/New_York")

        self.assertEqual("datetime64[ns]", data.index.dtype)
        self.assertEqual("Date", data.index.name)
        self.assertListEqual([pd.Timestamp("2019-08-12 00:00:00"), pd.Timestamp("2019-08-12 00:00:01")],
                             list(data.index))
        self.assertListEqual(["2019-08-12 00:00:01.000000000"], list(disconnects["ch1"].index))
        self.assertEqual(0, len(disconnects["ch2"]))
        self.assertEqual("2016-08-12 13:00:49.000000000", metadata["ch2"]["labels"][0]["d"])
        self.assertNotIn("labels", metadata["ch1"])

    def test_present_as_local_time_no_channels(self):
        data = pd.DataFrame()
        _present_as_local_time(data, {}, {}, adjusted=False, frac_time_digits=9, server_timezone="America/New_York")
        self.assertEqual(0, len(data))


class TestMySamplerTimestamps(unittest.TestCase):
    """Test that MySampler always requests unix timestamps and presents them as the query asks."""

    def run_mysampler(self, mock_get, **kwargs):
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0, 3.0])}}
        mock_get.return_value = make_response(body)
        query = MySamplerQuery(start=datetime(2019, 8, 12), interval=1, num_samples=3, pvlist=["ch1"],
                               deployment="docker", **kwargs)
        mysampler = MySampler(query, url="http://localhost/mysampler")
        mysampler.run()
        self.assertEqual("on", mock_get.call_args.kwargs["params"]["u"])
        return mysampler

    @patch("jlab_archiver_client.mysampler.requests.get")
    def test_datetime_presentation(self, mock_get):
        mysampler = self.run_mysampler(mock_get)
        self.assertEqual("datetime64[ns]", mysampler.data.index.dtype)
        self.assertEqual(pd.Timestamp("2019-08-12 00:00:00.002"), mysampler.data.index[2])

    @patch("jlab_archiver_client.mysampler.requests.get")
    def test_unix_timestamps_ms_presentation(self, mock_get):
        mysampler = self.run_mysampler(mock_get, unix_timestamps_ms=True)
        self.assertEqual(np.int64, mysampler.data.index.dtype)
        self.assertEqual(START_MS + 2, mysampler.data.index[2])

    @patch("jlab_archiver_client.mysampler.requests.get")
    def test_server_timezone_config(self, mock_get):
        with patch.object(config, "server_timezone", "UTC"):
            mysampler = self.run_mysampler(mock_get)
        self.assertEqual(pd.Timestamp("2019-08-12 04:00:00.002"), mysampler.data.index[2])

if __name__ == '__main__':
    unittest.main()
