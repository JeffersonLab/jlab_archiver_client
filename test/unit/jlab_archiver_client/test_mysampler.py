import io
import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import requests
from requests import RequestException

from jlab_archiver_client import MySampler, MySamplerQuery
from jlab_archiver_client.mysampler import _parse_json_iteratively


BAD_ERROR = "Unable to find channel: 'bad_channel' in deployment: 'docker'"


def good_channel(name: str, values: list) -> dict:
    """Build a mysampler channel object with one sample per value, one millisecond apart."""
    return {
        "metadata": {"name": name, "datatype": "DBR_DOUBLE", "datasize": 1, "datahost": "mya", "ioc": None,
                     "active": True},
        "data": [{"d": f"2019-08-12 00:00:00.00{i}000000", "v": v} for i, v in enumerate(values)],
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
                                   sig_figs=6, unix_timestamps_ms=False)


class TestParseJsonIteratively(unittest.TestCase):
    """Test the mysampler streaming parser against responses that include unarchived PVs."""

    def test_good_channels(self):
        body = {"channels": {"ch1": good_channel("ch1", [1.0, 2.0, 3.0]),
                             "ch2": good_channel("ch2", [4.0, 5.0, 6.0])}}
        data, metadata, disconnects = parse(body)
        self.assertListEqual(["ch1", "ch2"], list(data.columns))
        self.assertListEqual([1.0, 2.0, 3.0], data.ch1.tolist())
        self.assertListEqual([4.0, 5.0, 6.0], data.ch2.tolist())
        self.assertEqual("2019-08-12 00:00:00.002000", str(data.index[2]))
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
        self.assertIn("bad1: bad1 missing", str(context.exception))
        self.assertIn("bad2: bad2 missing", str(context.exception))

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


if __name__ == '__main__':
    unittest.main()
