// Recursive STA/LTA trigger, the classic seismology onset detector (as in MyShake/GeoShake).
// STA follows the last ~0.5 s of shaking energy, LTA the last ~10 s of background.
// A table shake makes STA jump while LTA stays at the quiet level, so the ratio spikes.
export class ShakeDetector {
  constructor({sta = .5, lta = 10, on = 4, off = 1.5, minLevel = .6, warmup = 3, holdoff = 3} = {}) {
    Object.assign(this, {staWindow: sta, ltaWindow: lta, on, off, minLevel, warmup, holdoff});
    this.sta = 0; this.lta = 0; this.elapsed = 0; this.gravity = null;
    this.active = false; this.since = -Infinity; this.peak = 0;
  }
  // a: linear acceleration {x,y,z} in m/s^2 (gravity removed when `withGravity` is false), dt in seconds.
  push(a, dt, withGravity = false) {
    let {x, y, z} = a;
    if (withGravity) {
      // Low-pass estimate of gravity, subtracted to keep only the shaking.
      if (!this.gravity) this.gravity = {x, y, z};
      const k = Math.min(1, dt / .8);
      for (const axis of ['x', 'y', 'z']) this.gravity[axis] += (a[axis] - this.gravity[axis]) * k;
      x -= this.gravity.x; y -= this.gravity.y; z -= this.gravity.z;
    }
    const value = Math.hypot(x, y, z), energy = value * value;
    this.elapsed += dt;
    const kSta = 1 - Math.exp(-dt / this.staWindow), kLta = 1 - Math.exp(-dt / this.ltaWindow);
    this.sta += (energy - this.sta) * kSta;
    // Freeze the background while shaking, otherwise a long shake raises its own baseline.
    if (!this.active) this.lta += (energy - this.lta) * (this.elapsed < this.warmup ? kSta : kLta);
    const ratio = this.sta / Math.max(this.lta, 1e-4), level = Math.sqrt(this.sta);
    let onset = false;
    if (this.active) {
      this.peak = Math.max(this.peak, value);
      if (ratio < this.off && this.elapsed - this.since > this.holdoff) this.active = false;
    } else if (this.elapsed >= this.warmup && ratio > this.on && level > this.minLevel) {
      this.active = true; this.since = this.elapsed; this.peak = value; onset = true;
    }
    return {value, level, ratio, onset, active: this.active, peak: this.peak};
  }
}

// Training-map node ids map onto the synthetic grid (see backend/seed.py).
export function nodePosition(id) {
  const [, row, col] = /^n(\d)_(\d)$/.exec(id) || [null, 3, 4];
  return {lat: 40.365 + row * .0025, lng: 49.828 + col * .0035};
}
