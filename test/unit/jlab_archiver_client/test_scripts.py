import unittest
import json
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
from io import StringIO

import pandas as pd

# noinspection PyProtectedMember
from jlab_archiver_client.scripts import (
    _parse_datetime,
    _configure_server,
    interval_main,
    mysampler_main,
    mystats_main,
    point_main,
    channel_main
)
from jlab_archiver_client.config import config


class TestParseDatetime(unittest.TestCase):
    """Test cases for _parse_datetime helper function."""

    def test_parse_iso_format(self):
        """Test parsing ISO format datetime."""
        result = _parse_datetime("2023-05-09T12:30:45")
        expected = datetime(2023, 5, 9, 12, 30, 45)
        self.assertEqual(result, expected)

    def test_parse_iso_format_with_microseconds(self):
        """Test parsing ISO format with microseconds."""
        result = _parse_datetime("2023-05-09T12:30:45.123456")
        expected = datetime(2023, 5, 9, 12, 30, 45, 123456)
        self.assertEqual(result, expected)

    def test_parse_common_format(self):
        """Test parsing common datetime format."""
        result = _parse_datetime("2023-05-09 12:30:45")
        expected = datetime(2023, 5, 9, 12, 30, 45)
        self.assertEqual(result, expected)

    def test_parse_common_format_with_microseconds(self):
        """Test parsing common format with microseconds."""
        result = _parse_datetime("2023-05-09 12:30:45.123456")
        expected = datetime(2023, 5, 9, 12, 30, 45, 123456)
        self.assertEqual(result, expected)

    def test_parse_date_only(self):
        """Test parsing date without time."""
        result = _parse_datetime("2023-05-09")
        expected = datetime(2023, 5, 9, 0, 0, 0)
        self.assertEqual(result, expected)

    def test_parse_invalid_format(self):
        """Test parsing invalid datetime format raises ValueError."""
        with self.assertRaises(ValueError) as context:
            _parse_datetime("invalid-date")

        self.assertIn("Unable to parse datetime", str(context.exception))


class TestConfigureServer(unittest.TestCase):
    """Test cases for _configure_server helper function."""

    def setUp(self):
        """Save original config values."""
        self.original_server = config.myquery_server
        self.original_protocol = config.protocol

    def tearDown(self):
        """Restore original config values."""
        config.set(myquery_server=self.original_server)
        config.set(protocol=self.original_protocol)

    def test_configure_server_only(self):
        """Test configuring only the server."""
        _configure_server("testserver.example.com", None)
        self.assertEqual(config.myquery_server, "testserver.example.com")

    def test_configure_protocol_only(self):
        """Test configuring only the protocol."""
        _configure_server(None, "https")
        self.assertEqual(config.protocol, "https")

    def test_configure_both(self):
        """Test configuring both server and protocol."""
        _configure_server("testserver.example.com", "https")
        self.assertEqual(config.myquery_server, "testserver.example.com")
        self.assertEqual(config.protocol, "https")

    def test_configure_neither(self):
        """Test calling with None for both parameters."""
        original_server = config.myquery_server
        original_protocol = config.protocol

        _configure_server(None, None)

        # Should remain unchanged
        self.assertEqual(config.myquery_server, original_server)
        self.assertEqual(config.protocol, original_protocol)


class TestIntervalMain(unittest.TestCase):
    """Test cases for interval_main function."""

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    def test_interval_main_minimal_args_stdout(self, mock_argv, mock_interval_class):
        """Test interval_main with minimal arguments outputting to stdout."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 01:00:00'
        ][i]

        # Mock the Interval instance
        mock_interval = MagicMock()
        mock_interval.data = {'test': 'data'}
        mock_interval.disconnects = None
        mock_interval.metadata = {'meta': 'info'}
        mock_interval_class.return_value = mock_interval

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            interval_main()

        # Verify Interval was created and run
        mock_interval_class.assert_called_once()
        mock_interval.run.assert_called_once()

        # Verify JSON output to stdout
        output = mock_stdout.getvalue()
        self.assertIn('"test": "data"', output)
        self.assertIn('"meta": "info"', output)

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    @patch('builtins.open', new_callable=mock_open)
    def test_interval_main_json_output(self, mock_file, mock_argv, mock_interval_class):
        """Test interval_main with JSON file output."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 01:00:00',
            '-o', 'output.json'
        ][i]

        # Mock the Interval instance
        mock_interval = MagicMock()
        mock_interval.data.to_dict.return_value = {'test': 'data'}
        mock_interval.disconnects = None
        mock_interval.metadata = {'meta': 'info'}
        mock_interval_class.return_value = mock_interval

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            interval_main()

        # Verify file was opened for writing
        mock_file.assert_called_once_with('output.json', 'w')

        # Verify success message
        output = mock_stdout.getvalue()
        self.assertIn("Successfully saved results to output.json", output)

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    def test_interval_main_csv_output(self, mock_argv, mock_interval_class):
        """Test interval_main with CSV file output."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 01:00:00',
            '-o', 'output.csv'
        ][i]

        # Mock the Interval instance
        mock_interval = MagicMock()
        mock_interval_class.return_value = mock_interval

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            interval_main()

        # Verify CSV was saved
        mock_interval.data.to_csv.assert_called_once_with('output.csv')

        # Verify success message
        output = mock_stdout.getvalue()
        self.assertIn("Successfully saved results to output.csv", output)

    @patch('sys.argv')
    @patch('sys.exit')
    def test_interval_main_invalid_datetime(self, mock_exit, mock_argv):
        """Test interval_main with invalid datetime format."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', 'invalid-date',
            '-e', '2023-05-09 01:00:00'
        ][i]

        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                interval_main()

        # Verify error message and exit
        error_output = mock_stderr.getvalue()
        self.assertIn("Error:", error_output)
        mock_exit.assert_called_once_with(1)

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    @patch('sys.exit')
    def test_interval_main_invalid_output_extension(self, mock_exit, mock_argv, mock_interval_class):
        """Test interval_main with invalid output file extension."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 01:00:00',
            '-o', 'output.txt'
        ][i]

        # Mock the Interval instance
        mock_interval = MagicMock()
        mock_interval_class.return_value = mock_interval

        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                interval_main()

        # Verify error message
        error_output = mock_stderr.getvalue()
        self.assertIn("Output file must be .csv or .json", error_output)
        mock_exit.assert_called_once_with(1)

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    def test_interval_main_with_all_flags(self, mock_argv, mock_interval_class):
        """Test interval_main with all optional flags."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 01:00:00',
            '-m', 'ops',
            '-l', '5000',
            '-t', 'graphical',
            '-f', '3',
            '-v', '8',
            '-d', '-p', '-s', '-u', '-a', '-i',
            '--server', 'testserver.com',
            '--protocol', 'https'
        ][i]

        # Mock the Interval instance
        mock_interval = MagicMock()
        mock_interval.data.to_dict.return_value = {}
        mock_interval.disconnects = None
        mock_interval.metadata = {}
        mock_interval_class.return_value = mock_interval

        with patch('sys.stdout', new_callable=StringIO):
            interval_main()

        # Verify Interval was called with correct parameters
        call_args = mock_interval_class.call_args
        query = call_args[0][0]

        self.assertEqual(query.channel, 'channel100')
        self.assertEqual(query.deployment, 'ops')
        self.assertEqual(query.bin_limit, 5000)
        self.assertEqual(query.sample_type, 'graphical')
        self.assertEqual(query.frac_time_digits, 3)
        self.assertEqual(query.sig_figs, 8)
        self.assertTrue(query.data_updates_only)
        self.assertTrue(query.prior_point)
        self.assertTrue(query.enums_as_strings)
        self.assertTrue(query.unix_timestamps_ms)
        self.assertTrue(query.adjust_time_to_server_offset)
        self.assertTrue(query.integrate)


class TestMySamplerMain(unittest.TestCase):
    """Test cases for mysampler_main function."""

    @patch('jlab_archiver_client.scripts.MySampler')
    @patch('sys.argv')
    def test_mysampler_main_minimal_args_stdout(self, mock_argv, mock_mysampler_class):
        """Test mysampler_main with minimal arguments outputting to stdout."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mysampler',
            '-c', 'channel1', 'channel2',
            '-b', '2023-05-09 12:00:00',
            '-i', '1000',
            '-n', '100'
        ][i]

        # Mock the MySampler instance
        mock_mysampler = MagicMock()
        mock_mysampler.data = pd.DataFrame({'pv1': [1.0, 2.0], 'pv2': [10, 20]},
                                           index=pd.to_datetime(['2023-05-09 12:00:00', '2023-05-09 13:00:00']))
        mock_mysampler.disconnects = {}
        mock_mysampler.metadata = {'meta': 'info'}
        mock_mysampler_class.return_value = mock_mysampler

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            mysampler_main()

        # Verify MySampler was created and run
        mock_mysampler_class.assert_called_once()
        mock_mysampler.run.assert_called_once()

        # Verify JSON output to stdout
        output = mock_stdout.getvalue()
        self.assertIn('"data": {', output)

    @patch('jlab_archiver_client.scripts.MySampler')
    @patch('sys.argv')
    def test_mysampler_main_with_flags(self, mock_argv, mock_mysampler_class):
        """Test mysampler_main with optional flags."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mysampler',
            '-c', 'pv1 pv2',
            '-b', '2023-05-09 12:00:00',
            '-i', '3600000',
            '-n', '2',
            '-m', 'ops',
            '-d', '-s', '-u', '-a'
        ][i]

        # Mock the MySampler instance
        mock_mysampler = MagicMock()
        mock_mysampler.data.to_dict.return_value = {}
        mock_mysampler.disconnects = {}
        mock_mysampler.metadata = {}
        mock_mysampler_class.return_value = mock_mysampler

        with patch('sys.stdout', new_callable=StringIO):
            mysampler_main()

        # Verify query parameters
        call_args = mock_mysampler_class.call_args
        query = call_args[0][0]

        self.assertEqual(query.deployment, 'ops')
        self.assertTrue(query.data_updates_only)
        self.assertTrue(query.enums_as_strings)
        self.assertTrue(query.unix_timestamps_ms)
        self.assertTrue(query.adjust_time_to_server_offset)

    @patch('jlab_archiver_client.scripts.MySampler')
    @patch('sys.argv')
    def test_mysampler_main_with_n_queries_strategy(self, mock_argv, mock_mysampler_class):
        """Test mysampler_main with sample_strategy='n_queries'.  Check resulting query parameters"""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mysampler',
            '-c', 'channel1', 'channel2',
            '-b', '2023-05-09 12:00:00',
            '-i', '1000',
            '-n', '100',
            '--sample-strategy', 'n_queries'
        ][i]

        with patch('sys.stdout', new_callable=StringIO):
            mysampler_main()

        # Verify query parameters
        call_args = mock_mysampler_class.call_args
        query = call_args[0][0]

        self.assertEqual(query.sample_strategy, 'n_queries')

    @patch('jlab_archiver_client.scripts.MySampler')
    @patch('sys.argv')
    def test_mysampler_main_with_stream_strategy(self, mock_argv, mock_mysampler_class):
        """Test mysampler_main with sample_strategy='stream'.  Check resulting query parameters"""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mysampler',
            '-c', 'channel1', 'channel2',
            '-b', '2023-05-09 12:00:00',
            '-i', '1000',
            '-n', '100',
            '-x', 'stream'
        ][i]

        with patch('sys.stdout', new_callable=StringIO):
            mysampler_main()

        # Verify query parameters
        call_args = mock_mysampler_class.call_args
        query = call_args[0][0]

        self.assertEqual(query.sample_strategy, 'stream')

    @patch('jlab_archiver_client.scripts.MySampler')
    @patch('sys.argv')
    def test_mysampler_main_without_sample_strategy(self, mock_argv, mock_mysampler_class):
        """Test mysampler_main without sample_strategy (should default to 'stream' in query)."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mysampler',
            '-c', 'channel1', 'channel20',
            '-b', '2023-05-09 12:00:00',
            '-i', '1000',
            '-n', '100'
        ][i]

        with patch('sys.stdout', new_callable=StringIO):
            mysampler_main()

        # Verify query parameters
        call_args = mock_mysampler_class.call_args
        query = call_args[0][0]

        self.assertEquals("stream", query.sample_strategy)


class TestMyStatsMain(unittest.TestCase):
    """Test cases for mystats_main function."""

    @patch('jlab_archiver_client.scripts.MyStats')
    @patch('sys.argv')
    def test_mystats_main_minimal_args_stdout(self, mock_argv, mock_mystats_class):
        """Test mystats_main with minimal arguments outputting to stdout."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mystats',
            '-c', 'channel1', 'channel2',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 23:59:59'
        ][i]

        # Mock the MyStats instance
        mock_mystats = MagicMock()
        mock_mystats.data = pd.DataFrame({'pv1': [1.0, 2.0, 3.0, 4.0], 'pv2': [10, 20, 30, 40]},
                                         index=pd.MultiIndex.from_product(
                                             [pd.to_datetime(['2023-05-09 12:00:00', '2023-05-09 13:00:00']),
                                              ['stat1', 'stat2']]))
        mock_mystats.metadata = {'meta': 'info'}
        mock_mystats_class.return_value = mock_mystats

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            mystats_main()

        # Verify MyStats was created and run
        mock_mystats_class.assert_called_once()
        mock_mystats.run.assert_called_once()

        # Verify JSON output to stdout
        output = mock_stdout.getvalue()
        self.assertIn('"data": {', output)

    @patch('jlab_archiver_client.scripts.MyStats')
    @patch('sys.argv')
    def test_mystats_main_with_num_bins(self, mock_argv, mock_mystats_class):
        """Test mystats_main with num_bins parameter."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mystats',
            '-c', 'channel1',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 23:59:59',
            '--num-bins', '24'
        ][i]

        # Mock the MyStats instance
        mock_mystats = MagicMock()
        mock_mystats.data.to_dict.return_value = {}
        mock_mystats.metadata = {}
        mock_mystats_class.return_value = mock_mystats

        with patch('sys.stdout', new_callable=StringIO):
            mystats_main()

        # Verify query parameters
        call_args = mock_mystats_class.call_args
        query = call_args[0][0]

        self.assertEqual(query.num_bins, 24)


class TestPointMain(unittest.TestCase):
    """Test cases for point_main function."""

    @patch('jlab_archiver_client.scripts.Point')
    @patch('sys.argv')
    def test_point_main_minimal_args_stdout(self, mock_argv, mock_point_class):
        """Test point_main with minimal arguments outputting to stdout."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-point',
            '-c', 'channel100',
            '-t', '2023-05-09 12:00:00'
        ][i]

        # Mock the Point instance
        mock_point = MagicMock()
        mock_point.event = {'value': 123.45, 'timestamp': '2023-05-09T12:00:00'}
        mock_point_class.return_value = mock_point

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            point_main()

        # Verify Point was created and run
        mock_point_class.assert_called_once()
        mock_point.run.assert_called_once()

        # Verify JSON output to stdout
        output = mock_stdout.getvalue()
        self.assertIn('"value": 123.45', output)

    @patch('jlab_archiver_client.scripts.Point')
    @patch('sys.argv')
    @patch('builtins.open', new_callable=mock_open)
    def test_point_main_json_output(self, mock_file, mock_argv, mock_point_class):
        """Test point_main with JSON file output."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-point',
            '-c', 'channel100',
            '-t', '2023-05-09 12:00:00',
            '-o', 'output.json'
        ][i]

        # Mock the Point instance
        mock_point = MagicMock()
        mock_point.event = {'value': 123.45}
        mock_point_class.return_value = mock_point

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            point_main()

        # Verify file was opened for writing
        mock_file.assert_called_once_with('output.json', 'w')

        # Verify success message
        output = mock_stdout.getvalue()
        self.assertIn("Successfully saved results to output.json", output)

    @patch('jlab_archiver_client.scripts.Point')
    @patch('sys.argv')
    @patch('sys.exit')
    def test_point_main_invalid_output_extension(self, mock_exit, mock_argv, mock_point_class):
        """Test point_main with invalid output file extension."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-point',
            '-c', 'channel100',
            '-t', '2023-05-09 12:00:00',
            '-o', 'output.csv'
        ][i]

        # Mock the Point instance
        mock_point = MagicMock()
        mock_point.event = {}
        mock_point_class.return_value = mock_point

        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                point_main()

        # Verify error message
        error_output = mock_stderr.getvalue()
        self.assertIn("Output file must be .json for point queries", error_output)
        mock_exit.assert_called_once_with(1)

    @patch('jlab_archiver_client.scripts.Point')
    @patch('sys.argv')
    def test_point_main_with_all_flags(self, mock_argv, mock_point_class):
        """Test point_main with all optional flags."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-point',
            '-c', 'channel100',
            '-t', '2023-05-09 12:00:00',
            '-m', 'ops',
            '-f', '3',
            '-v', '8',
            '-d', '-w', '-x', '-s', '-u', '-a'
        ][i]

        # Mock the Point instance
        mock_point = MagicMock()
        mock_point.event = {}
        mock_point_class.return_value = mock_point

        with patch('sys.stdout', new_callable=StringIO):
            point_main()

        # Verify query parameters
        call_args = mock_point_class.call_args
        query = call_args[0][0]

        self.assertEqual(query.deployment, 'ops')
        self.assertEqual(query.frac_time_digits, 3)
        self.assertEqual(query.sig_figs, 8)
        self.assertTrue(query.data_updates_only)
        self.assertTrue(query.forward_time_search)
        self.assertTrue(query.exclude_given_time)
        self.assertTrue(query.enums_as_strings)
        self.assertTrue(query.unix_timestamps_ms)
        self.assertTrue(query.adjust_time_to_server_offset)


class TestChannelMain(unittest.TestCase):
    """Test cases for channel_main function."""

    @patch('jlab_archiver_client.scripts.Channel')
    @patch('sys.argv')
    def test_channel_main_minimal_args_stdout(self, mock_argv, mock_channel_class):
        """Test channel_main with minimal arguments outputting to stdout."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-channel',
            '-p', 'channel%'
        ][i]

        # Mock the Channel instance
        mock_channel = MagicMock()
        mock_channel.matches = ['channel1', 'channel2', 'channel3']
        mock_channel_class.return_value = mock_channel

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            channel_main()

        # Verify Channel was created and run
        mock_channel_class.assert_called_once()
        mock_channel.run.assert_called_once()

        # Verify JSON output to stdout
        output = mock_stdout.getvalue()
        self.assertIn('"channel1"', output)
        self.assertIn('"channel2"', output)

    @patch('jlab_archiver_client.scripts.Channel')
    @patch('sys.argv')
    @patch('builtins.open', new_callable=mock_open)
    def test_channel_main_json_output(self, mock_file, mock_argv, mock_channel_class):
        """Test channel_main with JSON file output."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-channel',
            '-p', 'channel%',
            '-o', 'output.json'
        ][i]

        # Mock the Channel instance
        mock_channel = MagicMock()
        mock_channel.matches = ['channel1', 'channel2']
        mock_channel_class.return_value = mock_channel

        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            channel_main()

        # Verify file was opened for writing
        mock_file.assert_called_once_with('output.json', 'w')

        # Verify success message
        output = mock_stdout.getvalue()
        self.assertIn("Successfully saved 2 results to output.json", output)

    @patch('jlab_archiver_client.scripts.Channel')
    @patch('sys.argv')
    @patch('sys.exit')
    def test_channel_main_invalid_output_extension(self, mock_exit, mock_argv, mock_channel_class):
        """Test channel_main with invalid output file extension."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-channel',
            '-p', 'channel%',
            '-o', 'output.csv'
        ][i]

        # Mock the Channel instance
        mock_channel = MagicMock()
        mock_channel.matches = []
        mock_channel_class.return_value = mock_channel

        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                channel_main()

        # Verify error message
        error_output = mock_stderr.getvalue()
        self.assertIn("Output file must be .json for channel queries", error_output)
        mock_exit.assert_called_once_with(1)

    @patch('jlab_archiver_client.scripts.Channel')
    @patch('sys.argv')
    def test_channel_main_with_limit_and_offset(self, mock_argv, mock_channel_class):
        """Test channel_main with limit and offset parameters."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-channel',
            '-p', 'channel%',
            '-l', '100',
            '--offset', '50'
        ][i]

        # Mock the Channel instance
        mock_channel = MagicMock()
        mock_channel.matches = []
        mock_channel_class.return_value = mock_channel

        with patch('sys.stdout', new_callable=StringIO):
            channel_main()

        # Verify query parameters
        call_args = mock_channel_class.call_args
        query = call_args[0][0]

        self.assertEqual(query.pattern, 'channel%')
        self.assertEqual(query.limit, 100)
        self.assertEqual(query.offset, 50)


class TestTimestampSerialization(unittest.TestCase):
    """Test cases for proper serialization of pandas Timestamp objects."""

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    def test_interval_main_stdout_with_timestamp_index(self, mock_argv, mock_interval_class):
        """Test interval_main properly serializes pandas Series with Timestamp index to JSON."""

        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2018-04-24',
            '-e', '2018-05-01'
        ][i]

        # Create a realistic pandas Series with Timestamp index (like real data)
        timestamps = pd.to_datetime([
            '2018-04-24 06:25:01',
            '2018-04-24 06:25:05',
            '2018-04-24 11:18:19'
        ])
        values = [0.000, 5.911, 5.660]
        mock_data = pd.Series(values, index=timestamps, name='channel100')

        # Create disconnect series with Timestamp index
        disconnect_timestamps = pd.to_datetime(['2018-04-24 12:19:44'])
        disconnect_values = ['NETWORK_DISCONNECTION']
        mock_disconnects = pd.Series(disconnect_values, index=disconnect_timestamps, name='channel100')

        # Mock the Interval instance
        mock_interval = MagicMock()
        mock_interval.data = mock_data
        mock_interval.disconnects = mock_disconnects
        mock_interval.metadata = {'datatype': 'DBR_DOUBLE', 'returnCount': 3}
        mock_interval_class.return_value = mock_interval

        # Capture stdout - this should not raise an error
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            interval_main()

        # Verify JSON output was created successfully
        output = mock_stdout.getvalue()

        # Should be valid JSON
        try:
            output_json = json.loads(output)
            # Verify structure
            self.assertIn('data', output_json)
            self.assertIn('disconnects', output_json)
            self.assertIn('metadata', output_json)
            # Verify metadata is correct
            self.assertEqual(output_json['metadata']['datatype'], 'DBR_DOUBLE')
        except json.JSONDecodeError as e:
            self.fail(f"Output is not valid JSON: {e}\nOutput: {output}")

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    @patch('builtins.open', new_callable=mock_open)
    def test_interval_main_json_file_with_timestamp_index(self, mock_file, mock_argv, mock_interval_class):
        """Test interval_main properly serializes to JSON file with Timestamp index."""

        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2018-04-24',
            '-e', '2018-05-01',
            '-o', 'output.json'
        ][i]

        # Create a realistic pandas Series with Timestamp index
        timestamps = pd.to_datetime(['2018-04-24 06:25:01', '2018-04-24 06:25:05'])
        values = [0.000, 5.911]
        mock_data = pd.Series(values, index=timestamps, name='channel100')

        # Mock the Interval instance
        mock_interval = MagicMock()
        mock_interval.data = mock_data
        mock_interval.disconnects = None
        mock_interval.metadata = {'datatype': 'DBR_DOUBLE'}
        mock_interval_class.return_value = mock_interval

        # This should not raise an error
        with patch('sys.stdout', new_callable=StringIO):
            interval_main()

        # Verify file was opened
        mock_file.assert_called_once_with('output.json', 'w')


class TestErrorHandling(unittest.TestCase):
    """Test cases for error handling in script functions."""

    @patch('jlab_archiver_client.scripts.Interval')
    @patch('sys.argv')
    @patch('sys.exit')
    def test_interval_main_query_exception(self, mock_exit, mock_argv, mock_interval_class):
        """Test interval_main handles exceptions during query execution."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-interval',
            '-c', 'channel100',
            '-b', '2023-05-09 00:00:00',
            '-e', '2023-05-09 01:00:00'
        ][i]

        # Mock the Interval instance to raise an exception
        mock_interval = MagicMock()
        mock_interval.run.side_effect = Exception("Query failed")
        mock_interval_class.return_value = mock_interval

        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                interval_main()

        # Verify error message and exit
        error_output = mock_stderr.getvalue()
        self.assertIn("Error executing query: Query failed", error_output)
        mock_exit.assert_called_once_with(1)

    @patch('jlab_archiver_client.scripts.MySampler')
    @patch('sys.argv')
    @patch('sys.exit')
    def test_mysampler_main_query_exception(self, mock_exit, mock_argv, mock_mysampler_class):
        """Test mysampler_main handles exceptions during query execution."""
        mock_argv.__getitem__ = lambda s, i: [
            'jac-mysampler',
            '-c', 'channel1',
            '-b', '2023-05-09 12:00:00',
            '-i', '1000',
            '-n', '100'
        ][i]

        # Mock the MySampler instance to raise an exception
        mock_mysampler = MagicMock()
        mock_mysampler.run.side_effect = Exception("Sampler failed")
        mock_mysampler_class.return_value = mock_mysampler

        # Make sys.exit raise SystemExit to stop execution
        mock_exit.side_effect = SystemExit(1)

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit):
                mysampler_main()

        # Verify error message and exit
        error_output = mock_stderr.getvalue()
        self.assertIn("Error executing query: Sampler failed", error_output)
        mock_exit.assert_called_once_with(1)


if __name__ == '__main__':
    unittest.main()
