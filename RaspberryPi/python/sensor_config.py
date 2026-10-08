"""Explicit startup configuration; no remote changes or sensor imports here."""
import json
import re

DEFAULTS = dict(imu_port='/dev/ttyUSB1', imu_baud=9600, imu_slave=80,
                gps_port='/dev/ttyUSB0', gps_baud=4800, bme_address='0x76',
                ct_board=0, ct_channel=1, ftm_board=0, ftm_humidity=1, ftm_temperature=2)

def load_config(path):
    if path is None:
        return None
    with open(path, encoding='utf-8-sig') as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
        raise ValueError('sensor config: version must be 1')
    if set(data) != set(DEFAULTS) | {'version'}:
        raise ValueError('sensor config: missing or unknown fields')
    for key, default in DEFAULTS.items():
        value = data[key]
        if type(value) is not type(default):
            raise ValueError(f'{key}: invalid type')
        if key.endswith('_port') and (not re.fullmatch(r'/dev/[A-Za-z0-9_./-]+', value) or '..' in value):
            raise ValueError(f'{key}: invalid device path')
    for key in ('imu_baud', 'gps_baud'):
        if data[key] not in (1200,2400,4800,9600,19200,38400,57600,115200):
            raise ValueError(f'{key}: unsupported baud rate')
    for key, low, high in [('imu_slave',1,247),('ct_board',0,7),('ftm_board',0,7),
                           ('ct_channel',1,4),('ftm_humidity',1,4),('ftm_temperature',1,4)]:
        if not low <= data[key] <= high:
            raise ValueError(f'{key}: expected {low}..{high}')
    if data['bme_address'] not in ('0x76','0x77'):
        raise ValueError('bme_address: expected 0x76 or 0x77')
    if data['imu_port'] == data['gps_port'] or data['ftm_humidity'] == data['ftm_temperature']:
        raise ValueError('sensor config: duplicate ports or FTM02 channels')
    return data

def apply_config(config, imu, gps, ct100, ftm02, bme280):
    if config is None:
        return
    imu.PORT, imu.BAUDRATE, imu.SLAVE_ID = config['imu_port'], config['imu_baud'], config['imu_slave']
    gps.GPS_PORT, gps.BAUD_RATE = config['gps_port'], config['gps_baud']
    ct100.BOARD_ID, ct100.CURRENT_CHANNEL = config['ct_board'], config['ct_channel']
    ftm02.BOARD_ID, ftm02.HUMI_CHANNEL, ftm02.TEMP_CHANNEL = config['ftm_board'], config['ftm_humidity'], config['ftm_temperature']
    bme280.I2C_ADDRESS = int(config['bme_address'], 16)
