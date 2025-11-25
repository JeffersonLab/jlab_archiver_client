import unittest
from unittest.mock import MagicMock
import requests

from jlab_archiver_client.utils import check_response


class TestCheckResponse(unittest.TestCase):
    """Test cases for check_response function."""

    def test_check_response_http_ok_with_json(self):
        """Test check_response with HTTP 200 OK and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = requests.codes.OK
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"data": "test"}'

        # Should not raise any exception
        try:
            check_response(mock_response)
        except requests.RequestException:
            self.fail("check_response raised RequestException unexpectedly for HTTP 200 with JSON")

    def test_check_response_http_ok_with_html(self):
        """Test check_response with HTTP 200 OK and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = requests.codes.OK
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Success</body></html>'

        # Should not raise any exception
        try:
            check_response(mock_response)
        except requests.RequestException:
            self.fail("check_response raised RequestException unexpectedly for HTTP 200 with HTML")

    def test_check_response_http_redirect_with_html(self):
        """Test check_response with HTTP 302 redirect and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 302
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Success</body></html>'

        # Should not raise any exception
        try:
            check_response(mock_response)
        except requests.RequestException:
            self.fail("check_response raised RequestException unexpectedly for HTTP 302 with HTML")

    def test_check_response_http_400_with_json(self):
        """Test check_response with HTTP 400 Bad Request and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Invalid request parameters"}'
        mock_response.reason = 'Bad Request'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        # Should include the JSON text in the error message
        self.assertIn('status=400', str(context.exception))
        self.assertIn('{"error": "Invalid request parameters"}', str(context.exception))

    def test_check_response_http_400_with_html(self):
        """Test check_response with HTTP 400 Bad Request and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Bad Request</body></html>'
        mock_response.reason = 'Bad Request'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        # Should include the reason in the error message, not the HTML text
        self.assertIn('status=400', str(context.exception))
        self.assertIn('Bad Request', str(context.exception))
        self.assertNotIn('<html>', str(context.exception))

    def test_check_response_http_401_with_json(self):
        """Test check_response with HTTP 401 Unauthorized and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 401
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Authentication required"}'
        mock_response.reason = 'Unauthorized'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=401', str(context.exception))
        self.assertIn('{"error": "Authentication required"}', str(context.exception))

    def test_check_response_http_401_with_html(self):
        """Test check_response with HTTP 401 Unauthorized and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 401
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Unauthorized</body></html>'
        mock_response.reason = 'Unauthorized'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=401', str(context.exception))
        self.assertIn('Unauthorized', str(context.exception))
        self.assertNotIn('<html>', str(context.exception))

    def test_check_response_http_403_with_json(self):
        """Test check_response with HTTP 403 Forbidden and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 403
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Access denied"}'
        mock_response.reason = 'Forbidden'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=403', str(context.exception))
        self.assertIn('{"error": "Access denied"}', str(context.exception))

    def test_check_response_http_403_with_html(self):
        """Test check_response with HTTP 403 Forbidden and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 403
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Forbidden</body></html>'
        mock_response.reason = 'Forbidden'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=403', str(context.exception))
        self.assertIn('Forbidden', str(context.exception))
        self.assertNotIn('<html>', str(context.exception))

    def test_check_response_http_404_with_json(self):
        """Test check_response with HTTP 404 Not Found and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Resource not found"}'
        mock_response.reason = 'Not Found'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=404', str(context.exception))
        self.assertIn('{"error": "Resource not found"}', str(context.exception))

    def test_check_response_http_404_with_html(self):
        """Test check_response with HTTP 404 Not Found and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Not Found</body></html>'
        mock_response.reason = 'Not Found'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=404', str(context.exception))
        self.assertIn('Not Found', str(context.exception))
        self.assertNotIn('<html>', str(context.exception))

    def test_check_response_http_500_with_json(self):
        """Test check_response with HTTP 500 Internal Server Error and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Internal server error"}'
        mock_response.reason = 'Internal Server Error'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=500', str(context.exception))
        self.assertIn('{"error": "Internal server error"}', str(context.exception))

    def test_check_response_http_500_with_html(self):
        """Test check_response with HTTP 500 Internal Server Error and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Internal Server Error</body></html>'
        mock_response.reason = 'Internal Server Error'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=500', str(context.exception))
        self.assertIn('Internal Server Error', str(context.exception))
        self.assertNotIn('<html>', str(context.exception))

    def test_check_response_http_502_with_json(self):
        """Test check_response with HTTP 502 Bad Gateway and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 502
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Bad gateway"}'
        mock_response.reason = 'Bad Gateway'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=502', str(context.exception))
        self.assertIn('{"error": "Bad gateway"}', str(context.exception))

    def test_check_response_http_502_with_html(self):
        """Test check_response with HTTP 502 Bad Gateway and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 502
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Bad Gateway</body></html>'
        mock_response.reason = 'Bad Gateway'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=502', str(context.exception))
        self.assertIn('Bad Gateway', str(context.exception))
        self.assertNotIn('<html>', str(context.exception))

    def test_check_response_http_503_with_json(self):
        """Test check_response with HTTP 503 Service Unavailable and JSON content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 503
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"error": "Service temporarily unavailable"}'
        mock_response.reason = 'Service Unavailable'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=503', str(context.exception))
        self.assertIn('{"error": "Service temporarily unavailable"}', str(context.exception))

    def test_check_response_http_503_with_html(self):
        """Test check_response with HTTP 503 Service Unavailable and HTML content type."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 503
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.text = '<html><body>Service Unavailable</body></html>'
        mock_response.reason = 'Service Unavailable'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        self.assertIn('status=503', str(context.exception))
        self.assertIn('Service Unavailable', str(context.exception))
        self.assertNotIn('<html>', str(context.exception))

    def test_check_response_json_content_type_with_charset(self):
        """Test check_response correctly handles JSON content type with charset parameter."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.headers = {'Content-Type': 'application/json; charset=utf-8'}
        mock_response.text = '{"error": "Bad request with charset"}'
        mock_response.reason = 'Bad Request'

        with self.assertRaises(requests.RequestException) as context:
            check_response(mock_response)

        # Should still recognize as JSON and include the text
        self.assertIn('status=400', str(context.exception))
        self.assertIn('{"error": "Bad request with charset"}', str(context.exception))


if __name__ == '__main__':
    unittest.main()
