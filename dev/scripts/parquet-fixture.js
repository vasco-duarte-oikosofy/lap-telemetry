#!/usr/bin/env node
'use strict';

/**
 * Parquet fixture builder — batches all synthetic Parquet creation into a
 * single `python3` process call, eliminating per-file spawn overhead.
 *
 * Usage:
 *   const b = new ParquetFixtureBuilder();
 *   const file1 = b.add('wp-single', WIDTH_PROFILE_COLS, rows1);
 *   const file2 = b.add('wp-single2', WIDTH_PROFILE_COLS, rows2);
 *   b.flush();  // creates file1 and file2 in one Python call
 *   // now use file1, file2 in assertions
 */

const { spawnSync } = require('child_process');
const os = require('os');
const path = require('path');

// ── Column schema presets ─────────────────────────────────────────────────────

const WIDTH_PROFILE_COLS = [
  { name: 'lap_number',          type: 'int32',   from: () => 1 },
  { name: 'lap_time_s',         type: 'float32', from: (_, i) => i * 0.1 },
  { name: 'lap_distance_m',     type: 'float32', from: r => r.raw_lap_distance_m ?? 0 },
  { name: 'raw_lap_distance_m', type: 'float32', from: r => r.raw_lap_distance_m },
  { name: 'path_lateral_m',     type: 'float32', from: r => r.path_lateral_m },
  { name: 'track_edge_m',       type: 'float32', from: r => r.track_edge_m },
];

const CENTER_PATH_COLS = [
  { name: 'lap_number',          type: 'int32',   from: () => 1 },
  { name: 'lap_time_s',         type: 'float32', from: (_, i) => i * 0.1 },
  { name: 'raw_lap_distance_m', type: 'float32', from: r => r.raw_lap_distance_m },
  { name: 'pos_x_m',           type: 'float32', from: r => r.pos_x_m },
  { name: 'pos_y_m',           type: 'float32', from: () => 0 },
  { name: 'pos_z_m',           type: 'float32', from: r => r.pos_z_m },
];

// ── Builder ──────────────────────────────────────────────────────────────────

class ParquetFixtureBuilder {
  constructor() { this._queue = []; }

  /**
   * Queue a Parquet file to be created. Returns the output path (usable after flush).
   * @param {string} name - temp file base name
   * @param {Array<object>} cols - column definitions (use WIDTH_PROFILE_COLS or CENTER_PATH_COLS)
   * @param {Array<object>} rows - row data as plain objects
   * @returns {string} output file path
   */
  add(name, cols, rows) {
    const out = path.join(os.tmpdir(), `${name}-${Date.now()}-${Math.random().toString(16).slice(2)}.parquet`);
    this._queue.push({ out, cols, rows });
    return out;
  }

  /**
   * Create all queued Parquet files in a single python3 process call.
   * @returns {string[]} array of output paths (same order as add() calls)
   */
  flush() {
    if (this._queue.length === 0) return [];

    const snippets = [];
    for (const { out, cols, rows } of this._queue) {
      const arrays = cols.map(col => {
        const values = rows.map(r => {
          const v = col.from(r, rows.indexOf(r));
          return v === null || v === undefined ? 'None' : JSON.stringify(v);
        });
        return `pa.array([${values.join(', ')}], type=pa.${col.type}())`;
      });
      const names = cols.map(c => c.name);
      snippets.push(
        `pq.write_table(pa.Table.from_arrays([${arrays.join(', ')}], names=${JSON.stringify(names)}), r'''${out}''', compression='snappy')`
      );
    }

    const code = 'import pyarrow as pa, pyarrow.parquet as pq\n' + snippets.join('\n');
    const res = spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
    if (res.error || res.status !== 0) {
      throw new Error(`Parquet fixture creation failed: ${res.error?.message || res.stderr}`);
    }

    const paths = this._queue.map(q => q.out);
    this._queue = [];
    return paths;
  }
}

module.exports = { ParquetFixtureBuilder, WIDTH_PROFILE_COLS, CENTER_PATH_COLS };