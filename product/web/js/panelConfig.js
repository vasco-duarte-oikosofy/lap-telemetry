// ── Main trace panel configuration ───────────────────────────────────────────

export const COLUMNS = [
  'lap_number', 'lap_time_s', 'lap_distance_m', 'speed_kph',
  'throttle_norm', 'brake_norm', 'engine_rpm', 'gear',
  'steering_norm', 'slip_angle_fl_deg', 'slip_angle_fr_deg',
  'last_sector_1_s', 'last_sector_2_s',
  'pos_x_m', 'pos_z_m',
  'abs_active', 'tc_active',
];

export const PANEL_DEFS = [
  { id: 'speed', label: 'Speed (km/h)', height: 140,
    channels: [
      { col: 'speed_kph', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'speed_kph', trace: 'ref', color: 'var(--ref)', dash: true },
    ],
    yFixed: null, yStep: 50, zeroline: false },

  { id: 'throttle', label: 'Throttle', height: 60,
    channels: [
      { col: 'throttle_norm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'throttle_norm', trace: 'ref', color: 'var(--ref)', dash: true },
    ],
    yFixed: [0, 1], yStep: 0.5, zeroline: false,
    activityStrip: { col: 'tc_active', color: 'var(--throttle)' } },

  { id: 'tc', label: 'TC active', height: 50,
    channels: [
      { col: 'tc_active', trace: 'session', color: 'var(--session)', dash: false, step: true },
      { col: 'tc_active', trace: 'ref', color: 'var(--ref)', dash: true, step: true },
    ],
    yFixed: [0, 1], yStep: 1, midline: 0.5, zeroline: false },

  { id: 'brake', label: 'Brake', height: 60,
    channels: [
      { col: 'brake_norm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'brake_norm', trace: 'ref', color: 'var(--ref)', dash: true },
    ],
    yFixed: [0, 1], yStep: 0.5, zeroline: false,
    activityStrip: { col: 'abs_active', color: 'var(--brake)' } },

  { id: 'abs', label: 'ABS active', height: 50,
    channels: [
      { col: 'abs_active', trace: 'session', color: 'var(--brake)', dash: false, step: true },
    ],
    yFixed: [0, 1], yStep: 1, midline: 0.5, zeroline: false },

  { id: 'rpm', label: 'RPM', height: 80,
    channels: [
      { col: 'engine_rpm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'engine_rpm', trace: 'ref', color: 'var(--ref)', dash: true },
    ],
    yFixed: null, yStep: 2000, zeroline: false },

  { id: 'gear', label: 'Gear', height: 60, heightMultiplier: 1.3,
    channels: [
      { col: 'gear', trace: 'session', color: 'var(--session)', dash: false, step: true },
      { col: 'gear', trace: 'ref', color: 'var(--ref)', dash: true, step: true },
    ],
    yFixed: null, yStep: 1, zeroline: false },

  { id: 'steering', label: 'Steering', height: 80,
    channels: [
      { col: 'steering_norm', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'steering_norm', trace: 'ref', color: 'var(--ref)', dash: true },
    ],
    yFixed: [-1, 1], yStep: 0.5, zeroline: true },

  { id: 'slip', label: 'Slip angle FL / FR (deg)', height: 80,
    channels: [
      { col: 'slip_angle_fl_deg', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'slip_angle_fl_deg', trace: 'ref', color: 'var(--ref)', dash: true },
      { col: 'slip_angle_fr_deg', trace: 'session', color: 'var(--session)', dash: false },
      { col: 'slip_angle_fr_deg', trace: 'ref', color: 'var(--ref)', dash: true },
    ],
    yFixed: null, yStep: 2, zeroline: false, niceSteps: [0.5, 1, 2, 5] },

  { id: 'dt', label: 'Δt (ms, +session slower)', height: 100,
    channels: null,
    yFixed: null, yStep: 100, zeroline: true,
    niceSteps: [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000] },
];
