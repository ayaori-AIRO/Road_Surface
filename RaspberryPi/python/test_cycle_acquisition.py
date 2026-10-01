import threading
import time
import unittest

from .cycle_acquisition import acquire_cycles
from .live_prediction import input_values


class CycleTests(unittest.TestCase):
    def test_fresh_batches_and_failure_without_fallback(self):
        calls = dict(imu=0, ftm02=0, ct100=0)
        def reader(name):
            def read():
                calls[name] += 1
                if name == 'ftm02' and calls[name] == 2:
                    return None
                if name == 'imu':
                    return {'acc': dict(x=0., y=0., z=9.8)}
                return dict(temperature=float(calls[name]), humidity=30.)
            return read
        gen = acquire_cycles({n: (reader(n), .1) for n in calls}, threading.Event())
        try:
            first = next(gen)
            second = next(gen)
            for event in (first, second):
                for item in event['context'].values():
                    self.assertEqual(item['cycle_id'], event['cycle_id'])
                    self.assertGreaterEqual(item['started_monotonic'], event['cycle_start'])
                    self.assertLessEqual(item['received_monotonic'], event['ready_time'])
            self.assertEqual(calls, dict(imu=2, ftm02=2, ct100=2))
            self.assertIsNone(second['context']['ftm02']['value'])
            self.assertEqual(input_values(second, 'synthetic', 0)[2], 'ftm02_missing')
        finally:
            gen.close()

    def test_slow_reads_wait_and_do_not_overlap(self):
        def slow():
            time.sleep(.12)
            return dict(temperature=1., humidity=30.)
        readers = {'imu': (lambda: {'acc': dict(x=0., y=0., z=9.8)}, .1),
                   'ftm02': (slow, .1), 'ct100': (lambda: dict(temperature=2.), .1)}
        gen = acquire_cycles(readers, threading.Event())
        try:
            first, second = next(gen), next(gen)
            self.assertGreaterEqual(first['acquisition_ms'], 100)
            self.assertGreaterEqual(second['cycle_start'], first['ready_time'])
        finally:
            gen.close()

    def test_all_three_sensors_read_concurrently(self):
        barrier = threading.Barrier(3, timeout=2.)
        def read():
            barrier.wait()
            return dict(temperature=1., humidity=30.)
        readers = {name: (read, .1) for name in ('imu', 'ftm02', 'ct100')}
        gen = acquire_cycles(readers, threading.Event())
        try:
            event = next(gen)
            items = list(event['context'].values())
            self.assertTrue(all(item['value'] is not None for item in items))
            # All three calls must start before any call can finish.
            self.assertLessEqual(max(i['started_monotonic'] for i in items),
                                 min(i['received_monotonic'] for i in items))
        finally:
            gen.close()


if __name__ == '__main__':
    unittest.main()
