"""
Sim probe + thin shared-memory connector.

M1 scope: connect to whichever sim is active (LMU first, fall back to rF2),
expose the player's scoring + telemetry structs, and let the caller poll.

We use direct-access mmap mode (no copying, no version-check thread). This is
fine for frame-printing; M2 will move to version-checked copy access for
crash-safe recording.
"""
from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Make the vendored submodules importable when running from a source checkout
# without a pip install.
_VENDOR_DIR = Path(__file__).resolve().parents[4] / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))


SimName = str  # "lmu" | "rf2"


@dataclass
class Frame:
    """One sample, sim-agnostic."""
    sim: SimName
    session_time_s: float
    lap_number: int
    lap_distance_m: float
    lap_time_s: float
    speed_kph: float
    throttle_norm: float
    brake_norm: float
    steering_norm: float
    gear: int
    engine_rpm: float
    lap_valid: bool
    pos_x_m: float
    pos_y_m: float
    pos_z_m: float
    last_sector_1_s: float
    last_sector_2_s: float
    slip_angle_fl_deg: float
    slip_angle_fr_deg: float
    slip_angle_rl_deg: float
    slip_angle_rr_deg: float
    abs_active: Optional[bool]
    tc_active: Optional[bool]
    in_realtime: bool
    paused: bool
    track_name: str
    vehicle_name: str
    player_scor_index: int
    raw_lap_distance_m: Optional[float] = None
    path_lateral_m: Optional[float] = None
    track_edge_m: Optional[float] = None
    distance_to_track_edge_m: Optional[float] = None
    surface_type_fl: Optional[int] = None
    surface_type_fr: Optional[int] = None
    surface_type_rl: Optional[int] = None
    surface_type_rr: Optional[int] = None
    terrain_name_fl: Optional[str] = None
    terrain_name_fr: Optional[str] = None
    terrain_name_rl: Optional[str] = None
    terrain_name_rr: Optional[str] = None
    # Fuel and race-state fields (slice 08)
    fuel_l: Optional[float] = None
    fuel_capacity_l: Optional[float] = None
    session_type: Optional[int] = None
    session_time_remaining_s: Optional[float] = None
    race_laps_total: Optional[int] = None


class _BaseConnection:
    sim: SimName = ""

    def __init__(self) -> None:
        # State for speed-integrated distance (F4). mLapDist and mCurrentET both
        # update at scoring rate (~5 Hz), so we drive dt off wall clock — the
        # recorder polls at 50 Hz and we integrate speed between anchor ticks.
        # We also track the last wall-clock moment mCurrentET advanced; when it
        # stalls (>0.3 s), the sim is paused and we must NOT integrate the
        # stale velocity reported by the SHM.
        self._prev_lap_dist: float = math.nan
        self._prev_est_dist: float = 0.0
        self._prev_wall_time: float = math.nan
        self._prev_sim_time: float = math.nan
        self._last_sim_tick_wall: float = math.nan

    def _estimate_dist(self, raw_dist: float, speed_mps: float, sim_time: float) -> float:
        now = time.monotonic()
        dt = 0.0 if math.isnan(self._prev_wall_time) else now - self._prev_wall_time

        # Track when mCurrentET last advanced. During a pause it freezes, so
        # "no tick in >0.3 s" is our pause signal (scoring updates ~5 Hz, so
        # the gap between ticks during normal driving is ~0.2 s).
        if not math.isnan(self._prev_sim_time) and sim_time != self._prev_sim_time:
            self._last_sim_tick_wall = now
        sim_running = (
            not math.isnan(self._last_sim_tick_wall)
            and (now - self._last_sim_tick_wall) < 0.3
        )

        use_anchor = (
            math.isnan(self._prev_wall_time)     # first frame
            or dt <= 0.0 or dt > 0.5             # large gap / time went backwards
            or not sim_running                   # paused: SHM speed is stale, don't integrate
            or raw_dist != self._prev_lap_dist   # mLapDist ticked — use as ground truth
        )
        est = raw_dist if use_anchor else (self._prev_est_dist + speed_mps * dt)
        self._prev_lap_dist = raw_dist
        self._prev_est_dist = est
        self._prev_wall_time = now
        self._prev_sim_time = sim_time
        return est

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def update(self) -> None: ...
    def is_live(self) -> bool: ...
    def read_frame(self) -> Optional[Frame]: ...


def _decode(b: bytes) -> str:
    if not b:
        return ""
    try:
        return b.split(b"\x00", 1)[0].decode("utf-8")
    except UnicodeDecodeError:
        return b.split(b"\x00", 1)[0].decode("latin-1", errors="replace")


def _player_scor_index(scor_vehicles, count: int) -> int:
    for i in range(count):
        if scor_vehicles[i].mIsPlayer:
            return i
    # mIsPlayer is not set in LMU qualifying/race sessions; mControl==0 is local player
    for i in range(count):
        if int(scor_vehicles[i].mControl) == 0:
            return i
    return -1


def _sector_or_nan(value: float) -> float:
    """Sims report -1.0 for 'not yet set'. Map to NaN at the recorder boundary."""
    v = float(value)
    return math.nan if v < 0.0 else v


def _slip_deg(wheel) -> float:
    """Slip angle in degrees from patch velocities.

    Formula: atan2(lateral, longitudinal) converted to degrees.
    Both sims use the same mLateralPatchVel / mLongitudinalPatchVel fields.
    Wheel order: [0]=FL, [1]=FR, [2]=RL, [3]=RR.
    """
    lat = float(wheel.mLateralPatchVel)
    lon = float(wheel.mLongitudinalPatchVel)
    return math.degrees(math.atan2(lat, lon))


def _optional_float(obj, attr: str) -> Optional[float]:
    try:
        return float(getattr(obj, attr))
    except AttributeError:
        return None


def _optional_int(obj, attr: str) -> Optional[int]:
    try:
        v = int(getattr(obj, attr))
        return v if v > 0 else None
    except (AttributeError, ValueError):
        return None


def _positive_float(obj, attr: str) -> Optional[float]:
    """Read attr from obj, return float only if > 0, else None."""
    try:
        v = float(getattr(obj, attr))
        return v if v > 0.0 else None
    except AttributeError:
        return None


def _valid_session_type(obj, attr: str) -> Optional[int]:
    """Read session type, return int if valid (0-10), else None."""
    try:
        v = int(getattr(obj, attr))
        return v if 0 <= v <= 10 else None
    except (AttributeError, ValueError):
        return None


def _distance_to_track_edge(track_edge: Optional[float], path_lateral: Optional[float]) -> Optional[float]:
    if track_edge is None or path_lateral is None:
        return None
    return track_edge - abs(path_lateral)


def _wheel_surface(wheel) -> Optional[int]:
    try:
        return int(wheel.mSurfaceType)
    except AttributeError:
        return None


def _wheel_terrain(wheel) -> Optional[str]:
    try:
        return _decode(bytes(wheel.mTerrainName))
    except AttributeError:
        return None


# ---------- LMU ---------------------------------------------------------------

class LMUConnection(_BaseConnection):
    sim = "lmu"

    def __init__(self) -> None:
        super().__init__()
        # Imported lazily so import errors are reported only when probed.
        from pyLMUSharedMemory import lmu_data
        from pyLMUSharedMemory.lmu_mmap import LMUConstants, MMapControl

        self._lmu_data = lmu_data
        self._mmap = MMapControl(LMUConstants.LMU_SHARED_MEMORY_FILE, lmu_data.LMUObjectOut)
        self._tele_indexes: dict[int, int] = {}

    def start(self) -> None:
        self._mmap.create(0)  # copy mode — buffer refreshed only on sim update events
        self.update()

    def stop(self) -> None:
        try:
            self._mmap.close()
        except Exception:  # noqa: BLE001 — close is best-effort
            pass

    def update(self) -> None:
        self._mmap.update()
        tele = self._mmap.data.telemetry
        scor_info = self._mmap.data.scoring.scoringInfo
        n = max(scor_info.mNumVehicles, 0)
        for i in range(min(n, 128)):
            self._tele_indexes[tele.telemInfo[i].mID] = i

    def is_live(self) -> bool:
        return int(self._mmap.data.generic.gameVersion) != 0

    def read_frame(self) -> Optional[Frame]:
        scor = self._mmap.data.scoring
        tele_arr = self._mmap.data.telemetry.telemInfo
        scor_info = scor.scoringInfo

        idx = _player_scor_index(scor.vehScoringInfo, scor_info.mNumVehicles)
        if idx < 0:
            return None
        scor_v = scor.vehScoringInfo[idx]
        tele_idx = self._tele_indexes.get(scor_v.mID, -1)
        if tele_idx < 0:
            return None
        tele_v = tele_arr[tele_idx]

        vx, vy, vz = tele_v.mLocalVel.x, tele_v.mLocalVel.y, tele_v.mLocalVel.z
        speed_mps = (vx * vx + vy * vy + vz * vz) ** 0.5
        sim_time = float(scor_info.mCurrentET)
        raw_lap_dist = float(scor_v.mLapDist)
        path_lateral = _optional_float(scor_v, "mPathLateral")
        track_edge = _optional_float(scor_v, "mTrackEdge")

        return Frame(
            sim=self.sim,
            session_time_s=sim_time,
            lap_number=int(tele_v.mLapNumber),
            lap_distance_m=self._estimate_dist(raw_lap_dist, speed_mps, sim_time),
            lap_time_s=float(scor_info.mCurrentET - tele_v.mLapStartET),
            speed_kph=speed_mps * 3.6,
            throttle_norm=float(tele_v.mUnfilteredThrottle),
            brake_norm=float(tele_v.mUnfilteredBrake),
            steering_norm=float(tele_v.mUnfilteredSteering),
            gear=int(tele_v.mGear),
            engine_rpm=float(tele_v.mEngineRPM),
            lap_valid=int(scor_v.mCountLapFlag) > 0,
            pos_x_m=float(tele_v.mPos.x),
            pos_y_m=float(tele_v.mPos.y),
            pos_z_m=float(tele_v.mPos.z),
            last_sector_1_s=_sector_or_nan(scor_v.mLastSector1),
            last_sector_2_s=_sector_or_nan(scor_v.mLastSector2),
            slip_angle_fl_deg=_slip_deg(tele_v.mWheels[0]),
            slip_angle_fr_deg=_slip_deg(tele_v.mWheels[1]),
            slip_angle_rl_deg=_slip_deg(tele_v.mWheels[2]),
            slip_angle_rr_deg=_slip_deg(tele_v.mWheels[3]),
            abs_active=True if tele_v.mABSActive else None,
            tc_active=True if tele_v.mTCActive else None,
            in_realtime=bool(scor_info.mInRealtime),
            paused=False,
            track_name=_decode(bytes(scor_info.mTrackName)),
            vehicle_name=_decode(bytes(tele_v.mVehicleName)),
            player_scor_index=idx,
            raw_lap_distance_m=raw_lap_dist,
            path_lateral_m=path_lateral,
            track_edge_m=track_edge,
            distance_to_track_edge_m=_distance_to_track_edge(track_edge, path_lateral),
            surface_type_fl=_wheel_surface(tele_v.mWheels[0]),
            surface_type_fr=_wheel_surface(tele_v.mWheels[1]),
            surface_type_rl=_wheel_surface(tele_v.mWheels[2]),
            surface_type_rr=_wheel_surface(tele_v.mWheels[3]),
            terrain_name_fl=_wheel_terrain(tele_v.mWheels[0]),
            terrain_name_fr=_wheel_terrain(tele_v.mWheels[1]),
            terrain_name_rl=_wheel_terrain(tele_v.mWheels[2]),
            terrain_name_rr=_wheel_terrain(tele_v.mWheels[3]),
            fuel_l=_positive_float(tele_v, "mFuel"),
            fuel_capacity_l=_positive_float(tele_v, "mFuelCapacity"),
            session_type=_valid_session_type(scor_info, "mSession"),
            session_time_remaining_s=_optional_float(scor_info, "mSessionTimeRemaining"),
            race_laps_total=_optional_int(scor_info, "mMaxLaps"),
        )


# ---------- rF2 ---------------------------------------------------------------

class RF2Connection(_BaseConnection):
    sim = "rf2"

    def __init__(self) -> None:
        super().__init__()
        from pyRfactor2SharedMemory import rF2data
        from pyRfactor2SharedMemory.rF2MMap import MMapControl, rFactor2Constants

        self._rF2data = rF2data
        self._scor = MMapControl(rFactor2Constants.MM_SCORING_FILE_NAME, rF2data.rF2Scoring)
        self._tele = MMapControl(rFactor2Constants.MM_TELEMETRY_FILE_NAME, rF2data.rF2Telemetry)
        self._ext = MMapControl(rFactor2Constants.MM_EXTENDED_FILE_NAME, rF2data.rF2Extended)
        self._tele_indexes: dict[int, int] = {}

    def start(self) -> None:
        self._scor.create(0)
        self._tele.create(0)
        self._ext.create(0)
        self.update()

    def stop(self) -> None:
        for m in (self._scor, self._tele, self._ext):
            try:
                m.close()
            except Exception:  # noqa: BLE001
                pass

    def update(self) -> None:
        self._scor.update()
        self._tele.update()
        n = max(self._tele.data.mNumVehicles, 0)
        for i in range(min(n, 128)):
            self._tele_indexes[self._tele.data.mVehicles[i].mID] = i

    def is_live(self) -> bool:
        return bool(_decode(bytes(self._ext.data.mVersion)))

    def read_frame(self) -> Optional[Frame]:
        scor_info = self._scor.data.mScoringInfo
        idx = _player_scor_index(self._scor.data.mVehicles, scor_info.mNumVehicles)
        if idx < 0:
            return None
        scor_v = self._scor.data.mVehicles[idx]
        tele_idx = self._tele_indexes.get(scor_v.mID, -1)
        if tele_idx < 0:
            return None
        tele_v = self._tele.data.mVehicles[tele_idx]

        vx, vy, vz = tele_v.mLocalVel.x, tele_v.mLocalVel.y, tele_v.mLocalVel.z
        speed_mps = (vx * vx + vy * vy + vz * vz) ** 0.5
        sim_time = float(scor_info.mCurrentET)
        raw_lap_dist = float(scor_v.mLapDist)
        path_lateral = _optional_float(scor_v, "mPathLateral")
        track_edge = _optional_float(scor_v, "mTrackEdge")

        return Frame(
            sim=self.sim,
            session_time_s=sim_time,
            lap_number=int(tele_v.mLapNumber),
            lap_distance_m=self._estimate_dist(raw_lap_dist, speed_mps, sim_time),
            lap_time_s=float(scor_info.mCurrentET - tele_v.mLapStartET),
            speed_kph=speed_mps * 3.6,
            throttle_norm=float(tele_v.mUnfilteredThrottle),
            brake_norm=float(tele_v.mUnfilteredBrake),
            steering_norm=float(tele_v.mUnfilteredSteering),
            gear=int(tele_v.mGear),
            engine_rpm=float(tele_v.mEngineRPM),
            lap_valid=int(scor_v.mCountLapFlag) > 0,
            pos_x_m=float(tele_v.mPos.x),
            pos_y_m=float(tele_v.mPos.y),
            pos_z_m=float(tele_v.mPos.z),
            last_sector_1_s=_sector_or_nan(scor_v.mLastSector1),
            last_sector_2_s=_sector_or_nan(scor_v.mLastSector2),
            slip_angle_fl_deg=_slip_deg(tele_v.mWheels[0]),
            slip_angle_fr_deg=_slip_deg(tele_v.mWheels[1]),
            slip_angle_rl_deg=_slip_deg(tele_v.mWheels[2]),
            slip_angle_rr_deg=_slip_deg(tele_v.mWheels[3]),
            abs_active=None,
            tc_active=None,
            in_realtime=bool(scor_info.mInRealtime),
            paused=False,
            track_name=_decode(bytes(scor_info.mTrackName)),
            vehicle_name=_decode(bytes(tele_v.mVehicleName)),
            player_scor_index=idx,
            raw_lap_distance_m=raw_lap_dist,
            path_lateral_m=path_lateral,
            track_edge_m=track_edge,
            distance_to_track_edge_m=_distance_to_track_edge(track_edge, path_lateral),
            surface_type_fl=_wheel_surface(tele_v.mWheels[0]),
            surface_type_fr=_wheel_surface(tele_v.mWheels[1]),
            surface_type_rl=_wheel_surface(tele_v.mWheels[2]),
            surface_type_rr=_wheel_surface(tele_v.mWheels[3]),
            terrain_name_fl=_wheel_terrain(tele_v.mWheels[0]),
            terrain_name_fr=_wheel_terrain(tele_v.mWheels[1]),
            terrain_name_rl=_wheel_terrain(tele_v.mWheels[2]),
            terrain_name_rr=_wheel_terrain(tele_v.mWheels[3]),
            fuel_l=None,
            fuel_capacity_l=None,
            session_type=_valid_session_type(scor_info, "mSession"),
            session_time_remaining_s=_optional_float(scor_info, "mSessionTimeRemaining"),
            race_laps_total=_optional_int(scor_info, "mMaxLaps"),
        )


# ---------- probe -------------------------------------------------------------

PROBE_ORDER: tuple[type[_BaseConnection], ...] = (LMUConnection, RF2Connection)


class ConnectError(RuntimeError):
    pass


def probe_and_connect(
    timeout_s: float = 3.0,
    poll_interval_s: float = 0.1,
) -> _BaseConnection:
    """Try each sim in order, return the first one that reports live data.

    "Live" = the sim's plugin has written a non-zero version field. If neither
    is live within `timeout_s`, raise ConnectError.
    """
    deadline = time.monotonic() + timeout_s
    errors: list[str] = []
    for ConnCls in PROBE_ORDER:
        try:
            conn = ConnCls()
        except Exception as exc:  # noqa: BLE001 — surface in summary
            errors.append(f"{ConnCls.__name__}: import/init failed: {exc!r}")
            continue
        try:
            conn.start()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ConnCls.__name__}: start failed: {exc!r}")
            continue
        # Give the sim a moment to update the buffer if we just opened it.
        live = False
        while time.monotonic() < deadline:
            conn.update()
            if conn.is_live():
                live = True
                break
            time.sleep(poll_interval_s)
        if live:
            return conn
        conn.stop()
        errors.append(f"{ConnCls.__name__}: not live (no plugin data) within {timeout_s:.1f}s")
    raise ConnectError("No active sim detected.\n  " + "\n  ".join(errors))
