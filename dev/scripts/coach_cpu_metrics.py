"""Exact completed-child CPU accounting for the standalone coach benchmark.

Windows retains process times on Popen's open process handle after exit. Unix
already exposes cumulative reaped-child CPU through getrusage. Neither relies
on polling short-lived Node children (which would undercount their CPU).
"""
import os
import subprocess

_CHILD_CPU_S = 0.0


def track_child_cpu():
    """Install Windows-only accounting in this benchmark process, never the coach."""
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes
    get_times = ctypes.windll.kernel32.GetProcessTimes
    get_times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    get_times.restype = wintypes.BOOL
    original = subprocess.Popen

    class TrackedPopen(original):
        def wait(self, *args, **kwargs):
            global _CHILD_CPU_S
            result = super().wait(*args, **kwargs)
            if not getattr(self, '_cpu_accounted', False):
                created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
                if not get_times(int(self._handle), created, exited, kernel, user):
                    raise ctypes.WinError()
                ticks = lambda value: (value.dwHighDateTime << 32) | value.dwLowDateTime
                _CHILD_CPU_S += (ticks(kernel) + ticks(user)) / 10_000_000
                self._cpu_accounted = True
            return result

    subprocess.Popen = TrackedPopen


def child_cpu_seconds():
    if os.name == 'nt':
        return _CHILD_CPU_S
    import resource
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime
