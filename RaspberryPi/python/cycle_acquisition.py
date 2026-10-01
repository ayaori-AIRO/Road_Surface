"""Acquire a fresh sensor batch for every prediction; never reuse a batch."""
from concurrent.futures import ThreadPoolExecutor
import math
import time


def acquire_cycles(readers, stop, duration=0, period=.1):
    # CT100 and FTM02 access the same megaind board: serialize their I/O.
    groups = [[n for n in ("ftm02", "ct100") if n in readers]]
    groups += [[n] for n in readers if n not in ("ftm02", "ct100")]

    def read_group(names, cycle_id):
        items = {}
        for name in names:
            start = time.monotonic()
            try:
                value = readers[name][0]()
            except Exception as error:
                print(f"[{name.upper()} ERROR] {error}")
                value = None
            end = time.monotonic()
            items[name] = dict(value=value, started_monotonic=start,
                               received_monotonic=end, read_ms=(end-start)*1000,
                               cycle_id=cycle_id)
        return items

    origin = deadline = time.monotonic()
    previous = None
    cycle_id = 0
    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        while not stop.is_set():
            if stop.wait(max(0., deadline-time.monotonic())):
                return
            start = time.monotonic()
            if duration and start-origin >= duration:
                return
            cycle_id += 1
            futures = [pool.submit(read_group, group, cycle_id) for group in groups if group]
            context = {}
            for future in futures:
                context.update(future.result())
            if stop.is_set():
                return
            ready = time.monotonic()
            imu = context["imu"]
            yield dict(value=imu["value"], sample_time=imu["started_monotonic"],
                       cycle_id=cycle_id, cycle_start=start, ready_time=ready,
                       acquisition_ms=(ready-start)*1000,
                       read_ms=imu["read_ms"], context=context,
                       interval_ms=None if previous is None else
                       (imu["started_monotonic"]-previous)*1000)
            previous = imu["started_monotonic"]
            # Includes prediction time; late cycles are skipped, never burst.
            deadline += period
            now = time.monotonic()
            if deadline < now:
                deadline += (math.floor((now-deadline)/period)+1)*period
