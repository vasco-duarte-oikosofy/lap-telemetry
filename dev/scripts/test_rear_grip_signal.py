"""Slice 01 (rear-grip-signal): what the recorded slip channel physically is.

Two things are pinned here, both from measurements on committed recordings:

1. **The refusal is a measurement, not a hedge.** `_SLIP_REASON` must name the
   mechanism the spike proved, and the numbers behind it must be reproducible
   from `sessions/session_20261113T184458Z_circuit-de-barcelona_lmu_race.parquet`
   (the session that triggered the mission):
     - the channel is dominated by steering input (r = +0.52),
     - it idles at ±180° on a straight where a real sideslip angle is ~0°,
     - its rate of change is uncorrelated with an independently derived yaw rate,
   so it is a *direction of travel in the car frame*, not a tyre slip angle.

2. **The recorder now records what a slip angle actually needs.** `mGripFract`,
   the rear wheels' ground velocities and the car's yaw rate are added as
   nullable columns: a new recording carries them, every existing session and
   reference lap still loads unchanged, and a frame without them writes nulls
   (never a fabricated 0.0).

The numeric interpretation of those new columns is deliberately NOT asserted
here — the calibration gates in
`work/active/rear-grip-signal/01-true-slip-angle/plan.md` phase B step 6 must
pass on a real recording before any product surface reads them.
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import SessionWriter, _SCHEMA
from lap_telemetry.session_corner_extras import (
    SLIP_SANE_MAX_DEG,
    _SLIP_REASON,
    unmeasurable_channels,
)

BARCELONA = ROOT / 'sessions/session_20261113T184458Z_circuit-de-barcelona_lmu_race.parquet'
OLD_SESSION = ROOT / 'sessions/session_20260517T173100Z_autodromo-enzo-e-dino-ferrari_lmu.parquet'
NEW_COLUMNS = (
    'grip_fraction_rl', 'grip_fraction_rr',
    'wheel_ground_vel_lat_rl', 'wheel_ground_vel_lon_rl',
    'wheel_ground_vel_lat_rr', 'wheel_ground_vel_lon_rr',
    'yaw_rate_radps',
)
passed = failed = 0


def ok(value, label):
    global passed, failed
    passed += bool(value)
    failed += not bool(value)
    print(f'[{"PASS" if value else "FAIL"}] {label}')


def corr(a, b):
    n = len(a)
    if n < 3:
        return float('nan')
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return float('nan')
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def yaw_rate_from_positions(xs, zs, ts, step=5):
    """Heading from a central difference of position, then its rate in deg/s."""
    headings, times = [], []
    for i in range(step, len(xs) - step, step):
        dx, dz = xs[i + step] - xs[i - step], zs[i + step] - zs[i - step]
        dt = ts[i + step] - ts[i - step]
        if None in (dx, dz, dt) or dt <= 0:
            continue
        headings.append(math.degrees(math.atan2(dx, dz)))
        times.append(ts[i])
    unwrapped, prev = [], None
    for value in headings:
        if prev is not None:
            while value - prev > 180.0:
                value -= 360.0
            while value - prev < -180.0:
                value += 360.0
        unwrapped.append(value)
        prev = value
    return [(b - a) / (tb - ta) for a, b, ta, tb
            in zip(unwrapped, unwrapped[1:], times, times[1:]) if tb > ta]


def main():
    # --- 1. the refusal states the measured mechanism --------------------
    ok('atan2' in _SLIP_REASON, 'reason names the formula that produced the channel')
    ok('steering' in _SLIP_REASON, 'reason names the input the channel actually follows')
    ok('no wheel heading' in _SLIP_REASON or 'wheel heading' in _SLIP_REASON,
       'reason names what the schema is missing to fix it')
    ok('wrap' not in _SLIP_REASON.split(';')[0].lower() or 'idle' in _SLIP_REASON,
       'reason is not the old wrap-only hedge')

    ok(BARCELONA.exists(), 'the trigger session is committed')
    if not BARCELONA.exists():
        return
    table = pq.read_table(BARCELONA)
    steering = table.column('steering_norm').to_pylist()
    rl = table.column('slip_angle_rl_deg').to_pylist()
    pairs = [(s, v) for s, v in zip(steering, rl) if s is not None and v is not None]
    ok(corr([p[0] for p in pairs], [p[1] for p in pairs]) > 0.4,
       'recorded rear slip is dominated by steering input (r > 0.4, measured 0.52)')
    ok(sum(1 for v in rl if v is not None and abs(v) > 90) / len(rl) > 0.7,
       'most samples sit outside ±90°, i.e. it is not an angle a tyre can make')
    ok(len(unmeasurable_channels(table)) >= 2,
       'the session is reported with unmeasurable channels (not silently zero-filled)')

    # A real car sideslip angle on a straight is ~0°. This one reads near ±180°.
    dist = table.column('lap_distance_m').to_pylist()
    straight = [v for d, v in zip(dist, rl)
                if d is not None and v is not None and 1600 <= d <= 1800]
    ok(straight and abs(median(straight)) > 90,
       f"on a straight the channel reads {median(straight):+.0f}° where a real slip angle is ~0°")

    # Its rate of change carries no yaw information.
    yaw = yaw_rate_from_positions(
        table.column('pos_x_m').to_pylist(),
        table.column('pos_z_m').to_pylist(),
        table.column('session_time_s').to_pylist(),
    )
    slip_rate = [(b - a) / 0.1 for a, b in zip(rl, rl[1:]) if a is not None and b is not None]
    ok(len(yaw) > 100 and abs(corr(yaw, slip_rate[:len(yaw)])) < 0.1,
       'the channel\'s rate of change is uncorrelated with position-derived yaw rate (|r| < 0.1)')

    # Older recordings hit the same refusal: this is not a new-session artefact.
    ok(_SLIP_REASON in unmeasurable_channels(pq.read_table(OLD_SESSION)).values(),
       'an older recording gets the same measured refusal')
    ok(SLIP_SANE_MAX_DEG <= 60, 'the sanity bound that triggers the refusal is a real slip-angle scale')

    # --- 2. the recorder can now record the missing physics --------------
    names = set(_SCHEMA.names)
    for column in NEW_COLUMNS:
        ok(column in names, f'schema records {column}')
        field = _SCHEMA.field(column)
        ok(field.nullable, f'{column} is nullable, so existing sessions keep loading')

    with tempfile.TemporaryDirectory() as tmpdir:
        writer = SessionWriter(Path(tmpdir), sim='lmu', track='silverstone-national-circuit', rate_hz=50.0)
        for _ in range(3):
            writer.append(Frame(
                sim='lmu', session_time_s=0.0, lap_number=1, lap_distance_m=0.0,
                lap_time_s=0.0, speed_kph=0.0, throttle_norm=0.0, brake_norm=0.0,
                steering_norm=0.0, gear=1, engine_rpm=0.0, lap_valid=True,
                pos_x_m=0.0, pos_y_m=0.0, pos_z_m=0.0,
                last_sector_1_s=math.nan, last_sector_2_s=math.nan,
                slip_angle_fl_deg=0.0, slip_angle_fr_deg=0.0,
                slip_angle_rl_deg=0.0, slip_angle_rr_deg=0.0,
                abs_active=None, tc_active=None, in_realtime=True, paused=False,
                track_name='silverstone-national-circuit', vehicle_name='DKR4',
                player_scor_index=0,
            ))
        path, _ = writer.close()
        written = pq.read_table(path)
    for column in NEW_COLUMNS:
        values = written.column(column).to_pylist()
        ok(all(v is None for v in values),
           f'{column} writes nulls (not 0.0) when the sim did not supply it')

    # A populated frame survives the round trip, so the readers can fill them.
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = SessionWriter(Path(tmpdir), sim='lmu', track='silverstone-national-circuit', rate_hz=50.0)
        writer.append(Frame(
            sim='lmu', session_time_s=1.0, lap_number=1, lap_distance_m=10.0,
            lap_time_s=1.0, speed_kph=50.0, throttle_norm=1.0, brake_norm=0.0,
            steering_norm=0.2, gear=3, engine_rpm=5000.0, lap_valid=True,
            pos_x_m=0.0, pos_y_m=0.0, pos_z_m=0.0,
            last_sector_1_s=math.nan, last_sector_2_s=math.nan,
            slip_angle_fl_deg=0.0, slip_angle_fr_deg=0.0,
            slip_angle_rl_deg=0.0, slip_angle_rr_deg=0.0,
            abs_active=None, tc_active=None, in_realtime=True, paused=False,
            track_name='silverstone-national-circuit', vehicle_name='DKR4',
            player_scor_index=0,
            grip_fraction_rl=0.25, grip_fraction_rr=0.30,
            wheel_ground_vel_lat_rl=1.5, wheel_ground_vel_lon_rl=30.0,
            wheel_ground_vel_lat_rr=1.6, wheel_ground_vel_lon_rr=30.0,
            yaw_rate_radps=0.4,
        ))
        path, _ = writer.close()
        written = pq.read_table(path)
    for column in NEW_COLUMNS:
        ok(written.column(column).to_pylist()[0] is not None,
           f'{column} carries a supplied value through the writer')

    # --- 3. the readers degrade to None, never to a number ---------------
    from lap_telemetry.recorder.connect import _wheel_float, _yaw_rate_radps

    class _Wheel:
        def __init__(self, **fields):
            self.__dict__.update(fields)

    class _Rot:
        y = 0.35

    class _Telemetry:
        mLocalRot = _Rot()

    class _NoRot:
        pass

    ok(_wheel_float(_Wheel(mGripFract=0.42), 'mGripFract') == 0.42,
       'the LMU/rF2 reader extracts mGripFract')
    ok(_wheel_float(_Wheel(), 'mGripFract') is None,
       'a sim build without mGripFract yields None, not 0.0')
    ok(_wheel_float(_Wheel(mGripFract=float('nan')), 'mGripFract') is None,
       'a NaN reading yields None instead of poisoning the column')
    ok(_yaw_rate_radps(_Telemetry()) == 0.35, 'yaw rate is read from mLocalRot.y')
    ok(_yaw_rate_radps(_NoRot()) is None, 'a sim without mLocalRot yields None')

    # --- 4. the real ctypes mapping carries those field names ------------
    # The risk this covers: `_wheel_float` / `_yaw_rate_radps` are only correct
    # if the vendored shared-memory mapping exposes the names they read. A
    # vendored header bump that renames a field would otherwise surface as an
    # AttributeError in the middle of a recording session.
    from pyLMUSharedMemory import lmu_data

    tele = lmu_data.LMUVehicleTelemetry()
    tele.mWheels[2].mGripFract = 0.42
    tele.mWheels[2].mLateralGroundVel = 1.5
    tele.mWheels[2].mLongitudinalGroundVel = 30.0
    tele.mWheels[3].mGripFract = 0.30
    tele.mLocalRot.y = 0.35
    ok(_wheel_float(tele.mWheels[2], 'mGripFract') == 0.42,
       'vendored LMU mapping exposes mGripFract')
    ok(_wheel_float(tele.mWheels[2], 'mLateralGroundVel') == 1.5,
       'vendored LMU mapping exposes mLateralGroundVel')
    ok(_wheel_float(tele.mWheels[2], 'mLongitudinalGroundVel') == 30.0,
       'vendored LMU mapping exposes mLongitudinalGroundVel')
    ok(_yaw_rate_radps(tele) == 0.35, 'vendored LMU mapping exposes mLocalRot')

    from pyRfactor2SharedMemory import rF2data

    rf_tele = rF2data.rF2VehicleTelemetry()
    rf_tele.mWheels[3].mGripFract = 0.55
    rf_tele.mWheels[3].mLongitudinalGroundVel = 25.0
    rf_tele.mLocalRot.y = -0.2
    ok(_wheel_float(rf_tele.mWheels[3], 'mGripFract') == 0.55,
       'vendored rF2 mapping exposes mGripFract')
    ok(_wheel_float(rf_tele.mWheels[3], 'mLongitudinalGroundVel') == 25.0,
       'vendored rF2 mapping exposes mLongitudinalGroundVel')
    ok(_yaw_rate_radps(rf_tele) == -0.2, 'vendored rF2 mapping exposes mLocalRot')

    # --- 5. end to end: synthetic SHM image -> read_frame -> parquet ------
    # This is the "will it record?" check: the real LMU reader builds a Frame
    # from an LMUObjectOut, and the writer persists the new columns.
    import types as _types

    from lap_telemetry.recorder.connect import LMUConnection

    conn = LMUConnection.__new__(LMUConnection)
    LMUConnection.__mro__[1].__init__(conn)
    image = lmu_data.LMUObjectOut()
    image.generic.gameVersion = 3
    image.scoring.scoringInfo.mNumVehicles = 1
    image.scoring.scoringInfo.mCurrentET = 100.0
    image.scoring.vehScoringInfo[0].mIsPlayer = True
    image.scoring.vehScoringInfo[0].mID = 7
    image.scoring.vehScoringInfo[0].mLapDist = 1000.0
    image.scoring.vehScoringInfo[0].mPathLateral = 0.5
    image.scoring.vehScoringInfo[0].mTrackEdge = 6.0
    telemetry = image.telemetry.telemInfo[0]
    telemetry.mID = 7
    telemetry.mLapNumber = 14
    telemetry.mLapStartET = 45.0
    telemetry.mLocalVel.z = 55.0
    telemetry.mUnfilteredThrottle = 1.0
    telemetry.mGear = 4
    telemetry.mLocalRot.y = 0.42
    for index, grip in ((2, 0.37), (3, 0.41)):
        telemetry.mWheels[index].mGripFract = grip
        telemetry.mWheels[index].mLateralGroundVel = 2.4
        telemetry.mWheels[index].mLongitudinalGroundVel = 54.0
    conn._mmap = _types.SimpleNamespace(data=image, update=lambda: None, close=lambda: None)
    conn._tele_indexes = {7: 0}
    recorded = conn.read_frame()
    ok(recorded is not None, 'the LMU reader builds a frame from a live-shaped SHM image')
    if recorded is None:
        return
    ok(recorded.grip_fraction_rl == 0.37 and recorded.grip_fraction_rr == 0.41,
       'grip fraction is read per rear wheel')
    ok(recorded.wheel_ground_vel_lat_rl == 2.4 and recorded.wheel_ground_vel_lon_rl == 54.0,
       'rear-left ground velocity is read')
    ok(recorded.wheel_ground_vel_lat_rr == 2.4 and recorded.wheel_ground_vel_lon_rr == 54.0,
       'rear-right ground velocity is read')
    ok(recorded.yaw_rate_radps == 0.42, 'yaw rate is read')

    with tempfile.TemporaryDirectory() as tmpdir:
        writer = SessionWriter(Path(tmpdir), sim='lmu', track='silverstone-national-circuit', rate_hz=50.0)
        writer.append(recorded)
        path, _ = writer.close()
        persisted = pq.read_table(path)
    row = {c: persisted.column(c).to_pylist()[0] for c in NEW_COLUMNS}
    ok(abs(row['grip_fraction_rl'] - 0.37) < 1e-6 and abs(row['grip_fraction_rr'] - 0.41) < 1e-6,
       'grip fraction survives SHM -> frame -> parquet')
    ok(abs(row['wheel_ground_vel_lon_rl'] - 54.0) < 1e-6 and
       abs(row['wheel_ground_vel_lat_rl'] - 2.4) < 1e-6,
       'rear left ground velocity survives SHM -> frame -> parquet')
    ok(abs(row['yaw_rate_radps'] - 0.42) < 1e-6, 'yaw rate survives SHM -> frame -> parquet')


if __name__ == '__main__':
    main()
    print(f'{passed}/{passed + failed} assertions passed')
    sys.exit(bool(failed))
