import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

from Jetson.tcp_server import Store, Web


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.ui = root / 'dist'
        self.ui.mkdir()
        (self.ui / 'index.html').write_text('<div id="root"></div>')
        (self.ui / 'app.js').write_text('console.log("React bundle")')
        (root / 'secret.txt').write_text('not public')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Web)
        self.server.store = Store()
        self.server.ui_dir = self.ui
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.temp.cleanup()

    def test_bundle_and_api(self):
        with urlopen(self.base + '/') as response:
            self.assertIn(b'root', response.read())
        with urlopen(self.base + '/app.js') as response:
            self.assertEqual(response.headers.get_content_type(), 'text/javascript')
        self.server.store.add(dict(snow_height_mm=None, road_temperature_c=0,
                                   air_temperature_c=20, humidity_pct=40, pressure_hpa=1011,
                                   prediction_status='warming_up'))
        with urlopen(self.base + '/api/data?after=0') as response:
            data = json.load(response)
        self.assertEqual(data['latest']['pressure_hpa'], 1011)
        self.assertEqual(data['latest']['prediction_status'], 'warming_up')
        self.assertNotEqual(data['instance_id'], Store().instance_id)

    def test_missing_build_bad_cursor_and_traversal(self):
        for path, code in [('/%2e%2e/secret.txt', 403), ('/missing.js', 404),
                           ('/api/data?after=no', 400)]:
            with self.assertRaises(HTTPError) as error:
                urlopen(self.base + path)
            self.assertEqual(error.exception.code, code)
        (self.ui / 'index.html').unlink()
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + '/')
        self.assertEqual(error.exception.code, 503)


if __name__ == '__main__':
    unittest.main()
