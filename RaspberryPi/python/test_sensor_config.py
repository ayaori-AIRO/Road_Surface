import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from RaspberryPi.python.sensor_config import DEFAULTS, load_config, apply_config

class SensorConfigTests(unittest.TestCase):
    def load(self, overrides):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps(dict(version=1, **DEFAULTS) | overrides), encoding='utf-8')
            return load_config(path)

    def test_explicit_config_updates_driver_settings(self):
        config = self.load(dict(imu_port='/dev/serial/by-id/imu', imu_baud=19200, bme_address='0x77'))
        imu, gps, ct, ftm, bme = [SimpleNamespace() for _ in range(5)]
        apply_config(config, imu, gps, ct, ftm, bme)
        self.assertEqual(imu.PORT, '/dev/serial/by-id/imu')
        self.assertEqual(imu.BAUDRATE, 19200)
        self.assertEqual(gps.GPS_PORT, '/dev/ttyUSB0')
        self.assertEqual(bme.I2C_ADDRESS, 0x77)
        self.assertEqual(ftm.TEMP_CHANNEL, 2)

    def test_reject_invalid_and_conflicting_settings(self):
        for overrides in [dict(imu_port='/tmp/file'), dict(imu_baud=True), dict(imu_slave=0),
                          dict(gps_port=DEFAULTS['imu_port']), dict(ct_channel=0),
                          dict(bme_address='0x00'), dict(ftm_temperature=1), dict(version=2),
                          dict(unexpected=10)]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.load(overrides)

    def test_omitted_config_preserves_existing_settings(self):
        self.assertIsNone(load_config(None))
        imu = SimpleNamespace(PORT='original')
        apply_config(None, imu, None, None, None, None)
        self.assertEqual(imu.PORT, 'original')

if __name__ == '__main__':
    unittest.main()
