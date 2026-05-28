import unittest
import warnings
from datetime import datetime

from jlab_archiver_client.query import (
    IntervalQuery,
    MySamplerQuery,
    ChannelQuery,
    PointQuery,
    MyStatsQuery, MAX_FRACTIONAL_SECOND_DIGITS, DEFAULT_SIG_FIGS
)


class TestIntervalQuery(unittest.TestCase):
    """Test cases for IntervalQuery class."""

    def test_init_minimal(self):
        """Test IntervalQuery initialization with minimal required parameters."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(channel=channel, begin=begin, end=end)

        self.assertEqual(query.channel, channel)
        self.assertEqual(query.begin, begin)
        self.assertEqual(query.end, end)
        self.assertIsNone(query.bin_limit)
        self.assertIsNone(query.sample_type)
        self.assertEqual(query.deployment, "history")
        self.assertEqual(query.frac_time_digits, MAX_FRACTIONAL_SECOND_DIGITS)
        self.assertEqual(query.sig_figs, DEFAULT_SIG_FIGS)
        self.assertFalse(query.data_updates_only)
        self.assertFalse(query.prior_point)
        self.assertFalse(query.enums_as_strings)
        self.assertFalse(query.unix_timestamps_ms)
        self.assertFalse(query.adjust_time_to_server_offset)
        self.assertFalse(query.integrate)
        self.assertEqual(query.extra_opts, {})

    def test_init_all_parameters(self):
        """Test IntervalQuery initialization with all parameters."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(
            channel=channel,
            begin=begin,
            end=end,
            bin_limit=1000,
            sample_type="graphical",
            deployment="ops",
            frac_time_digits=3,
            sig_figs=8,
            data_updates_only=True,
            prior_point=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True,
            integrate=True
        )

        self.assertEqual(query.channel, channel)
        self.assertEqual(query.begin, begin)
        self.assertEqual(query.end, end)
        self.assertEqual(query.bin_limit, 1000)
        self.assertEqual(query.sample_type, "graphical")
        self.assertEqual(query.deployment, "ops")
        self.assertEqual(query.frac_time_digits, 3)
        self.assertEqual(query.sig_figs, 8)
        self.assertTrue(query.data_updates_only)
        self.assertTrue(query.prior_point)
        self.assertTrue(query.enums_as_strings)
        self.assertTrue(query.unix_timestamps_ms)
        self.assertTrue(query.adjust_time_to_server_offset)
        self.assertTrue(query.integrate)

    def test_init_with_kwargs(self):
        """Test IntervalQuery initialization with extra kwargs produces warning."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(
            channel=channel,
            begin=begin,
            end=end,
            custom_param="value"
        )

        self.assertEqual(query.extra_opts, {"custom_param": "value"})

        # Verify that using kwargs produces a warning when to_web_params is called
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")

    def test_to_web_params_minimal(self):
        """Test to_web_params with minimal parameters."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(channel=channel, begin=begin, end=end)
        params = query.to_web_params()

        self.assertEqual(params['c'], channel)
        self.assertEqual(params['b'], "2023-05-09T00:00:00")
        self.assertEqual(params['e'], "2023-05-09T15:59:00")
        self.assertEqual(params['m'], "history")
        self.assertEqual(params['f'], MAX_FRACTIONAL_SECOND_DIGITS)
        self.assertEqual(params['v'], DEFAULT_SIG_FIGS)
        self.assertEqual(params['l'], "")
        self.assertNotIn('t', params)
        self.assertNotIn('d', params)
        self.assertNotIn('p', params)
        self.assertNotIn('s', params)
        self.assertNotIn('u', params)
        self.assertNotIn('a', params)
        self.assertNotIn('i', params)

    def test_to_web_params_with_bin_limit(self):
        """Test to_web_params with bin_limit specified."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(channel=channel, begin=begin, end=end, bin_limit=5000)
        params = query.to_web_params()

        self.assertEqual(params['l'], 5000)

    def test_to_web_params_with_sample_type(self):
        """Test to_web_params with sample_type specified."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(channel=channel, begin=begin, end=end, sample_type="mysampler")
        params = query.to_web_params()

        self.assertEqual(params['t'], "mysampler")

    def test_to_web_params_all_boolean_flags(self):
        """Test to_web_params with all boolean flags enabled."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(
            channel=channel,
            begin=begin,
            end=end,
            data_updates_only=True,
            prior_point=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True,
            integrate=True
        )
        params = query.to_web_params()

        self.assertEqual(params['d'], 'on')
        self.assertEqual(params['p'], 'on')
        self.assertEqual(params['s'], 'on')
        self.assertEqual(params['u'], 'on')
        self.assertEqual(params['a'], 'on')
        self.assertEqual(params['i'], 'on')

    def test_to_web_params_with_extra_opts(self):
        """Test to_web_params with extra options produces warning."""
        channel = "R123GMES"
        begin = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 15, 59, 0)

        query = IntervalQuery(
            channel=channel,
            begin=begin,
            end=end,
            custom_param="value"
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")


class TestMySamplerQuery(unittest.TestCase):
    """Test cases for MySamplerQuery class."""

    def test_init_minimal(self):
        """Test MySamplerQuery initialization with minimal required parameters."""
        start = datetime(2023, 5, 9, 12, 0, 0)
        interval = 1000
        num_samples = 100
        pvlist = ["R123GMES", "R121GMES"]

        query = MySamplerQuery(
            start=start,
            interval=interval,
            num_samples=num_samples,
            pvlist=pvlist
        )

        self.assertEqual(query.start, "2023-05-09 12:00:00")
        self.assertEqual(query.interval, interval)
        self.assertEqual(query.num_samples, num_samples)
        self.assertEqual(query.pvlist, pvlist)
        self.assertEqual(query.deployment, "history")
        self.assertFalse(query.data_updates_only)
        self.assertFalse(query.enums_as_strings)
        self.assertFalse(query.unix_timestamps_ms)
        self.assertFalse(query.adjust_time_to_server_offset)
        self.assertEqual(query.extra_opts, {})

    def test_init_all_parameters(self):
        """Test MySamplerQuery initialization with all parameters."""
        start = datetime(2023, 5, 9, 12, 0, 0)
        interval = 1000
        num_samples = 100
        pvlist = ["R123GMES", "R121GMES"]

        query = MySamplerQuery(
            start=start,
            interval=interval,
            num_samples=num_samples,
            pvlist=pvlist,
            deployment="ops",
            data_updates_only=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True
        )

        self.assertEqual(query.deployment, "ops")
        self.assertTrue(query.data_updates_only)
        self.assertTrue(query.enums_as_strings)
        self.assertTrue(query.unix_timestamps_ms)
        self.assertTrue(query.adjust_time_to_server_offset)

    def test_init_removes_microseconds(self):
        """Test that MySamplerQuery removes microseconds from start time."""
        start = datetime(2023, 5, 9, 12, 0, 0, 123456)
        interval = 1000
        num_samples = 100
        pvlist = ["R123GMES"]

        query = MySamplerQuery(
            start=start,
            interval=interval,
            num_samples=num_samples,
            pvlist=pvlist
        )

        # Should strip microseconds
        self.assertEqual(query.start, "2023-05-09 12:00:00")

    def test_init_with_kwargs(self):
        """Test MySamplerQuery initialization with extra kwargs produces warning."""
        start = datetime(2023, 5, 9, 12, 0, 0)
        interval = 1000
        num_samples = 100
        pvlist = ["R123GMES"]

        query = MySamplerQuery(
            start=start,
            interval=interval,
            num_samples=num_samples,
            pvlist=pvlist,
            custom_param="value"
        )

        self.assertEqual(query.extra_opts, {"custom_param": "value"})

        # Verify that using kwargs produces a warning when to_web_params is called
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")

    def test_to_web_params_minimal(self):
        """Test to_web_params with minimal parameters."""
        start = datetime(2023, 5, 9, 12, 0, 0)
        interval = 1000
        num_samples = 100
        pvlist = ["R123GMES", "R121GMES"]

        query = MySamplerQuery(
            start=start,
            interval=interval,
            num_samples=num_samples,
            pvlist=pvlist
        )
        params = query.to_web_params()

        self.assertEqual(params['c'], "R123GMES,R121GMES")
        self.assertEqual(params['b'], "2023-05-09T12:00:00")
        self.assertEqual(params['n'], 100)
        self.assertEqual(params['m'], "history")
        self.assertEqual(params['s'], 1000)
        self.assertNotIn('d', params)
        self.assertNotIn('e', params)
        self.assertNotIn('u', params)
        self.assertNotIn('a', params)

    def test_to_web_params_all_boolean_flags(self):
        """Test to_web_params with all boolean flags enabled."""
        start = datetime(2023, 5, 9, 12, 0, 0)
        interval = 1000
        num_samples = 100
        pvlist = ["R123GMES"]

        query = MySamplerQuery(
            start=start,
            interval=interval,
            num_samples=num_samples,
            pvlist=pvlist,
            data_updates_only=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True
        )
        params = query.to_web_params()

        self.assertEqual(params['d'], 'on')
        self.assertEqual(params['e'], 'on')
        self.assertEqual(params['u'], 'on')
        self.assertEqual(params['a'], 'on')

    def test_to_web_params_with_extra_opts(self):
        """Test to_web_params with extra options produces warning."""
        start = datetime(2023, 5, 9, 12, 0, 0)
        interval = 1000
        num_samples = 100
        pvlist = ["R123GMES"]

        query = MySamplerQuery(
            start=start,
            interval=interval,
            num_samples=num_samples,
            pvlist=pvlist,
            custom_param="value"
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")


class TestChannelQuery(unittest.TestCase):
    """Test cases for ChannelQuery class."""

    def test_init_minimal(self):
        """Test ChannelQuery initialization with minimal required parameters."""
        pattern = "R%GMES"

        query = ChannelQuery(pattern=pattern)

        self.assertEqual(query.pattern, pattern)
        self.assertIsNone(query.limit)
        self.assertIsNone(query.offset)
        self.assertEqual(query.deployment, "history")
        self.assertEqual(query.extra_opts, {})

    def test_init_all_parameters(self):
        """Test ChannelQuery initialization with all parameters."""
        pattern = "R%GMES"
        limit = 100
        offset = 50
        deployment = "ops"

        query = ChannelQuery(
            pattern=pattern,
            limit=limit,
            offset=offset,
            deployment=deployment
        )

        self.assertEqual(query.pattern, pattern)
        self.assertEqual(query.limit, limit)
        self.assertEqual(query.offset, offset)
        self.assertEqual(query.deployment, deployment)

    def test_init_with_kwargs(self):
        """Test ChannelQuery initialization with extra kwargs produces warning."""
        pattern = "R%GMES"

        query = ChannelQuery(pattern=pattern, custom_param="value")

        self.assertEqual(query.extra_opts, {"custom_param": "value"})

        # Verify that using kwargs produces a warning when to_web_params is called
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")

    def test_to_web_params_minimal(self):
        """Test to_web_params with minimal parameters."""
        pattern = "R%GMES"

        query = ChannelQuery(pattern=pattern)
        params = query.to_web_params()

        self.assertEqual(params['q'], pattern)
        self.assertIsNone(params['l'])
        self.assertIsNone(params['o'])
        self.assertEqual(params['m'], "history")

    def test_to_web_params_all_parameters(self):
        """Test to_web_params with all parameters."""
        pattern = "R%GMES"
        limit = 100
        offset = 50
        deployment = "ops"

        query = ChannelQuery(
            pattern=pattern,
            limit=limit,
            offset=offset,
            deployment=deployment
        )
        params = query.to_web_params()

        self.assertEqual(params['q'], pattern)
        self.assertEqual(params['l'], limit)
        self.assertEqual(params['o'], offset)
        self.assertEqual(params['m'], deployment)

    def test_to_web_params_with_extra_opts(self):
        """Test to_web_params with extra options produces warning."""
        pattern = "R%GMES"

        query = ChannelQuery(pattern=pattern, custom_param="value")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")


class TestPointQuery(unittest.TestCase):
    """Test cases for PointQuery class."""

    def test_init_minimal(self):
        """Test PointQuery initialization with minimal required parameters."""
        channel = "R123GMES"
        time = datetime(2018, 4, 24, 12, 0, 0)

        query = PointQuery(channel=channel, time=time)

        self.assertEqual(query.channel, channel)
        self.assertEqual(query.time, time)
        self.assertEqual(query.deployment, "history")
        self.assertEqual(query.frac_time_digits, MAX_FRACTIONAL_SECOND_DIGITS)
        self.assertEqual(query.sig_figs, 6)
        self.assertFalse(query.data_updates_only)
        self.assertFalse(query.forward_time_search)
        self.assertFalse(query.exclude_given_time)
        self.assertFalse(query.enums_as_strings)
        self.assertFalse(query.unix_timestamps_ms)
        self.assertFalse(query.adjust_time_to_server_offset)
        self.assertEqual(query.extra_opts, {})

    def test_init_all_parameters(self):
        """Test PointQuery initialization with all parameters."""
        channel = "R123GMES"
        time = datetime(2018, 4, 24, 12, 0, 0)

        query = PointQuery(
            channel=channel,
            time=time,
            deployment="ops",
            frac_time_digits=3,
            sig_figs=8,
            data_updates_only=True,
            forward_time_search=True,
            exclude_given_time=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True
        )

        self.assertEqual(query.deployment, "ops")
        self.assertEqual(query.frac_time_digits, 3)
        self.assertEqual(query.sig_figs, 8)
        self.assertTrue(query.data_updates_only)
        self.assertTrue(query.forward_time_search)
        self.assertTrue(query.exclude_given_time)
        self.assertTrue(query.enums_as_strings)
        self.assertTrue(query.unix_timestamps_ms)
        self.assertTrue(query.adjust_time_to_server_offset)

    def test_init_with_kwargs(self):
        """Test PointQuery initialization with extra kwargs produces warning."""
        channel = "R123GMES"
        time = datetime(2018, 4, 24, 12, 0, 0)

        query = PointQuery(channel=channel, time=time, custom_param="value")

        self.assertEqual(query.extra_opts, {"custom_param": "value"})

        # Verify that using kwargs produces a warning when to_web_params is called
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")

    def test_to_web_params_minimal(self):
        """Test to_web_params with minimal parameters."""
        channel = "R123GMES"
        time = datetime(2018, 4, 24, 12, 0, 0)

        query = PointQuery(channel=channel, time=time)
        params = query.to_web_params()

        self.assertEqual(params['c'], channel)
        self.assertEqual(params['t'], "2018-04-24T12:00:00")
        self.assertEqual(params['m'], "history")
        self.assertEqual(params['f'], MAX_FRACTIONAL_SECOND_DIGITS)
        self.assertEqual(params['v'], DEFAULT_SIG_FIGS)
        self.assertNotIn('d', params)
        self.assertNotIn('w', params)
        self.assertNotIn('x', params)
        self.assertNotIn('s', params)
        self.assertNotIn('u', params)
        self.assertNotIn('a', params)

    def test_to_web_params_all_boolean_flags(self):
        """Test to_web_params with all boolean flags enabled."""
        channel = "R123GMES"
        time = datetime(2018, 4, 24, 12, 0, 0)

        query = PointQuery(
            channel=channel,
            time=time,
            data_updates_only=True,
            forward_time_search=True,
            exclude_given_time=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True
        )
        params = query.to_web_params()

        self.assertEqual(params['d'], 'on')
        self.assertEqual(params['w'], 'on')
        self.assertEqual(params['x'], 'on')
        self.assertEqual(params['s'], 'on')
        self.assertEqual(params['u'], 'on')
        self.assertEqual(params['a'], 'on')

    def test_to_web_params_with_extra_opts(self):
        """Test to_web_params with extra options produces warning."""
        channel = "R123GMES"
        time = datetime(2018, 4, 24, 12, 0, 0)

        query = PointQuery(channel=channel, time=time, custom_param="value")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")


class TestMyStatsQuery(unittest.TestCase):
    """Test cases for MyStatsQuery class."""

    def test_init_minimal(self):
        """Test MyStatsQuery initialization with minimal required parameters."""
        pvlist = ["R123GMES", "R121GMES"]
        start = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 23, 59, 59)

        query = MyStatsQuery(pvlist=pvlist, start=start, end=end)

        self.assertEqual(query.pvlist, pvlist)
        self.assertEqual(query.start, start)
        self.assertEqual(query.end, end)
        self.assertEqual(query.num_bins, 1)
        self.assertEqual(query.deployment, "history")
        self.assertEqual(query.frac_time_digits, MAX_FRACTIONAL_SECOND_DIGITS)
        self.assertEqual(query.sig_figs, DEFAULT_SIG_FIGS)
        self.assertFalse(query.data_updates_only)
        self.assertFalse(query.enums_as_strings)
        self.assertFalse(query.unix_timestamps_ms)
        self.assertFalse(query.adjust_time_to_server_offset)
        self.assertEqual(query.extra_opts, {})

    def test_init_all_parameters(self):
        """Test MyStatsQuery initialization with all parameters."""
        pvlist = ["R123GMES", "R121GMES"]
        start = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 23, 59, 59)

        query = MyStatsQuery(
            pvlist=pvlist,
            start=start,
            end=end,
            num_bins=10,
            deployment="ops",
            frac_time_digits=3,
            sig_figs=8,
            data_updates_only=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True
        )

        self.assertEqual(query.num_bins, 10)
        self.assertEqual(query.deployment, "ops")
        self.assertEqual(query.frac_time_digits, 3)
        self.assertEqual(query.sig_figs, 8)
        self.assertTrue(query.data_updates_only)
        self.assertTrue(query.enums_as_strings)
        self.assertTrue(query.unix_timestamps_ms)
        self.assertTrue(query.adjust_time_to_server_offset)

    def test_init_with_kwargs(self):
        """Test MyStatsQuery initialization with extra kwargs produces warning."""
        pvlist = ["R123GMES"]
        start = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 23, 59, 59)

        query = MyStatsQuery(
            pvlist=pvlist,
            start=start,
            end=end,
            custom_param="value"
        )

        self.assertEqual(query.extra_opts, {"custom_param": "value"})

        # Verify that using kwargs produces a warning when to_web_params is called
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")

    def test_to_web_params_minimal(self):
        """Test to_web_params with minimal parameters."""
        pvlist = ["R123GMES", "R121GMES"]
        start = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 23, 59, 59)

        query = MyStatsQuery(pvlist=pvlist, start=start, end=end)
        params = query.to_web_params()

        self.assertEqual(params['c'], "R123GMES,R121GMES")
        self.assertEqual(params['b'], "2023-05-09T00:00:00")
        self.assertEqual(params['e'], "2023-05-09T23:59:59")
        self.assertEqual(params['n'], 1)
        self.assertEqual(params['m'], "history")
        self.assertEqual(params['f'], MAX_FRACTIONAL_SECOND_DIGITS)
        self.assertEqual(params['v'], DEFAULT_SIG_FIGS)
        self.assertNotIn('d', params)
        self.assertNotIn('u', params)
        self.assertNotIn('a', params)

    def test_to_web_params_all_parameters(self):
        """Test to_web_params with all parameters."""
        pvlist = ["R123GMES", "R121GMES"]
        start = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 23, 59, 59)

        query = MyStatsQuery(
            pvlist=pvlist,
            start=start,
            end=end,
            num_bins=10,
            deployment="ops",
            frac_time_digits=3,
            sig_figs=8,
            data_updates_only=True,
            enums_as_strings=True,
            unix_timestamps_ms=True,
            adjust_time_to_server_offset=True
        )
        params = query.to_web_params()

        self.assertEqual(params['n'], 10)
        self.assertEqual(params['m'], "ops")
        self.assertEqual(params['f'], 3)
        self.assertEqual(params['v'], 8)
        self.assertEqual(params['d'], 'on')
        self.assertEqual(params['u'], 'on')
        self.assertEqual(params['a'], 'on')

    def test_to_web_params_with_extra_opts(self):
        """Test to_web_params with extra options produces warning."""
        pvlist = ["R123GMES"]
        start = datetime(2023, 5, 9, 0, 0, 0)
        end = datetime(2023, 5, 9, 23, 59, 59)

        query = MyStatsQuery(
            pvlist=pvlist,
            start=start,
            end=end,
            custom_param="value"
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            params = query.to_web_params()

            self.assertEqual(len(w), 1)
            self.assertIn("extra_opts", str(w[0].message))
            self.assertEqual(params['custom_param'], "value")


if __name__ == '__main__':
    unittest.main()
