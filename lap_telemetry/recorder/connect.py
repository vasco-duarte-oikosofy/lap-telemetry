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
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


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
    in_realtime: bool
    paused: bool
    track_name: str
    vehicle_name: str
    player_scor_index: int


class _BaseConnection:
    sim: SimName = ""

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


# ---------- LMU ---------------------------------------------------------------

class LMUConnection(_BaseConnection):
    sim = "lmu"

    def __init__(self) -> None:
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

        return Frame(
            sim=self.sim,
            session_time_s=float(scor_info.mCurrentET),
            lap_number=int(tele_v.mLapNumber),
            lap_distance_m=float(scor_v.mLapDist),
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
            in_realtime=bool(scor_info.mInRealtime),
            paused=False,
            track_name=_decode(bytes(scor_info.mTrackName)),
            vehicle_name=_decode(bytes(tele_v.mVehicleName)),
            player_scor_index=idx,
        )


# ---------- rF2 ---------------------------------------------------------------

class RF2Connection(_BaseConnection):
    sim = "rf2"

    def __init__(self) -> None:
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

        return Frame(
            sim=self.sim,
            session_time_s=float(scor_info.mCurrentET),
            lap_number=int(tele_v.mLapNumber),
            lap_distance_m=float(scor_v.mLapDist),
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
            in_realtime=bool(scor_info.mInRealtime),
            paused=False,
            track_name=_decode(bytes(scor_info.mTrackName)),
            vehicle_name=_decode(bytes(tele_v.mVehicleName)),
            player_scor_index=idx,
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
