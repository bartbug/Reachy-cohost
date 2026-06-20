"""Gesture palette and listening animator for Reachy Mini co-host."""

import math
import random
import threading
import time
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

# Antenna angle constants (radians). Positive = up.
ANTENNA_NEUTRAL = [0.0, 0.0]
ANTENNA_PERKED   = [0.4, 0.4]
ANTENNA_DROOP    = [-0.3, -0.3]
ANTENNA_FLARE    = [0.7, 0.7]
ANTENNA_ASYM_R   = [0.4, -0.1]   # right up, left relaxed
ANTENNA_ASYM_L   = [-0.1, 0.4]


def _go(mini, head=None, antennas=None, body_yaw=None, duration=0.5, method="minjerk"):
    """goto_target wrapper with sane defaults."""
    mini.goto_target(
        head=head,
        antennas=antennas,
        body_yaw=body_yaw,
        duration=duration,
        method=method,
    )


def _seq(mini, steps):
    """Run [(head, antennas, body_yaw, duration, method), ...] sequentially."""
    for step in steps:
        head, antennas, body_yaw, duration = step[:4]
        method = step[4] if len(step) > 4 else "minjerk"
        _go(mini, head=head, antennas=antennas, body_yaw=body_yaw,
            duration=duration, method=method)


# ---------------------------------------------------------------------------
# Named gesture library
# ---------------------------------------------------------------------------

def _gesture_nod(mini):
    _seq(mini, [
        (create_head_pose(pitch=0), ANTENNA_NEUTRAL, 0.0, 0.3, "minjerk"),   # center first
        (create_head_pose(pitch=12), ANTENNA_PERKED, 0.0, 0.35, "ease_in_out"),
        (create_head_pose(pitch=-3), ANTENNA_NEUTRAL, 0.0, 0.3, "ease_in_out"),
        (create_head_pose(pitch=6), None, 0.0, 0.2, "minjerk"),
        (create_head_pose(pitch=0), ANTENNA_NEUTRAL, 0.0, 0.3, "minjerk"),
    ])

def _gesture_double_nod(mini):
    _seq(mini, [
        (create_head_pose(pitch=0), ANTENNA_NEUTRAL, 0.0, 0.3, "minjerk"),   # center first
        (create_head_pose(pitch=12), ANTENNA_PERKED, 0.0, 0.3, "ease_in_out"),
        (create_head_pose(pitch=-2), None, 0.0, 0.25, "ease_in_out"),
        (create_head_pose(pitch=12), None, 0.0, 0.25, "ease_in_out"),
        (create_head_pose(pitch=0), ANTENNA_NEUTRAL, 0.0, 0.35, "minjerk"),
    ])

def _gesture_shake(mini):
    _seq(mini, [
        (create_head_pose(yaw=22), ANTENNA_ASYM_L, 0.0, 0.3, "ease_in_out"),
        (create_head_pose(yaw=-22), ANTENNA_ASYM_R, 0.0, 0.3, "ease_in_out"),
        (create_head_pose(yaw=10), None, 0.0, 0.2, "ease_in_out"),
        (create_head_pose(yaw=0), ANTENNA_NEUTRAL, 0.0, 0.3, "minjerk"),
    ])

def _gesture_tilt_right(mini):
    _seq(mini, [
        (create_head_pose(roll=-18, yaw=5), ANTENNA_ASYM_R, 0.0, 0.55, "ease_in_out"),
        (create_head_pose(roll=-10, yaw=5), None, 0.0, 0.3, "minjerk"),
        (create_head_pose(roll=0, yaw=0), ANTENNA_NEUTRAL, 0.0, 0.4, "minjerk"),
    ])

def _gesture_tilt_left(mini):
    _seq(mini, [
        (create_head_pose(roll=18, yaw=-5), ANTENNA_ASYM_L, 0.0, 0.55, "ease_in_out"),
        (create_head_pose(roll=10, yaw=-5), None, 0.0, 0.3, "minjerk"),
        (create_head_pose(roll=0, yaw=0), ANTENNA_NEUTRAL, 0.0, 0.4, "minjerk"),
    ])

def _gesture_look_up(mini):
    _seq(mini, [
        (create_head_pose(pitch=-28, roll=5), ANTENNA_PERKED, 0.0, 0.6, "ease_in_out"),
        (create_head_pose(pitch=-20, roll=5), None, 0.0, 0.5, "minjerk"),
        (create_head_pose(pitch=0, roll=0), ANTENNA_NEUTRAL, 0.0, 0.5, "minjerk"),
    ])

def _gesture_surprised(mini):
    _seq(mini, [
        (create_head_pose(pitch=-15), ANTENNA_FLARE, 0.0, 0.18, "ease_in_out"),
        (create_head_pose(pitch=-8), None, 0.0, 0.3, "minjerk"),
        (create_head_pose(pitch=0), ANTENNA_NEUTRAL, 0.0, 0.4, "minjerk"),
    ])

def _gesture_bow(mini):
    _seq(mini, [
        (create_head_pose(pitch=35), ANTENNA_DROOP, 0.0, 0.6, "ease_in_out"),
        (create_head_pose(pitch=35), None, 0.0, 0.3, "minjerk"),
        (create_head_pose(pitch=0), ANTENNA_NEUTRAL, 0.0, 0.55, "minjerk"),
    ])

def _gesture_excited(mini):
    _seq(mini, [
        (create_head_pose(pitch=-10), ANTENNA_FLARE, 0.0, 0.2, "ease_in_out"),
        (create_head_pose(pitch=5, roll=8), ANTENNA_PERKED, 0.08, 0.2, "ease_in_out"),
        (create_head_pose(pitch=-5, roll=-8), ANTENNA_FLARE, -0.08, 0.2, "ease_in_out"),
        (create_head_pose(pitch=0, roll=0), ANTENNA_NEUTRAL, 0.0, 0.35, "minjerk"),
    ])

def _gesture_think(mini):
    _seq(mini, [
        (create_head_pose(pitch=-18, roll=12, yaw=-8), ANTENNA_ASYM_R, 0.0, 0.7, "ease_in_out"),
        (create_head_pose(pitch=-18, roll=12, yaw=-8), None, 0.0, 0.6, "minjerk"),
        (create_head_pose(pitch=0, roll=0, yaw=0), ANTENNA_NEUTRAL, 0.0, 0.55, "minjerk"),
    ])

def _gesture_idle(mini):
    _go(mini, head=create_head_pose(), antennas=ANTENNA_NEUTRAL, body_yaw=None, duration=0.4)


_GESTURES = {
    "nod":        _gesture_nod,
    "double_nod": _gesture_double_nod,
    "shake":      _gesture_shake,
    "tilt_right": _gesture_tilt_right,
    "tilt_left":  _gesture_tilt_left,
    "look_up":    _gesture_look_up,
    "surprised":  _gesture_surprised,
    "bow":        _gesture_bow,
    "excited":    _gesture_excited,
    "think":      _gesture_think,
    "idle":       _gesture_idle,
}


def play_gesture(mini: ReachyMini, name: str):
    """Play a named gesture non-blocking in a background thread."""
    fn = _GESTURES.get(name, _gesture_idle)
    t = threading.Thread(target=fn, args=(mini,), daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Listening animator
# ---------------------------------------------------------------------------

# Small reactions triggered randomly while the human speaks
_MICRO_REACTIONS = [
    # (weight, fn)
    (4, lambda m: _go(m, head=create_head_pose(pitch=8), duration=0.5, method="ease_in_out")),   # micro-nod
    (3, lambda m: _go(m, head=create_head_pose(roll=10), duration=0.6, method="ease_in_out")),   # tilt
    (3, lambda m: _go(m, head=create_head_pose(roll=-10), duration=0.6, method="ease_in_out")),  # tilt other
    (2, lambda m: _go(m, antennas=ANTENNA_PERKED, duration=0.3)),                                # antenna perk
    (2, lambda m: (_go(m, antennas=ANTENNA_PERKED, duration=0.3), time.sleep(0.4),
                   _go(m, antennas=ANTENNA_NEUTRAL, duration=0.3))),                             # antenna bob
    (1, lambda m: _go(m, head=create_head_pose(pitch=-5, yaw=8), duration=0.6)),                 # glance
]
_MICRO_WEIGHTS = [w for w, _ in _MICRO_REACTIONS]
_MICRO_FNS     = [fn for _, fn in _MICRO_REACTIONS]


class ListeningAnimator:
    """Continuous motion in two modes:

    - listening: larger drift + random micro-reactions (human's turn)
    - speaking:  subtler drift that kicks in after the named gesture finishes,
                 giving Reachy life for the rest of the TTS duration
    """

    _MODE_OFF       = 0
    _MODE_LISTENING = 1
    _MODE_SPEAKING  = 2

    def __init__(self, mini: ReachyMini):
        self._mini = mini
        self._mode = self._MODE_OFF
        self._mode_lock = threading.Lock()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _center(self):
        """Return to neutral pose — call before starting any animation mode."""
        try:
            self._mini.goto_target(
                head=create_head_pose(),
                antennas=[0.0, 0.0],
                body_yaw=0.0,
                duration=0.6,
                method="minjerk",
            )
            time.sleep(0.65)
        except Exception:
            pass

    def start_listening(self):
        self._center()
        with self._mode_lock:
            self._mode = self._MODE_LISTENING
        self._wake.set()

    def start_speaking(self, gesture_duration: float = 1.5):
        """Start speaking idle after gesture_duration seconds (let gesture finish first)."""
        def _delayed():
            time.sleep(gesture_duration)
            with self._mode_lock:
                if self._mode == self._MODE_SPEAKING:
                    self._wake.set()
        with self._mode_lock:
            self._mode = self._MODE_SPEAKING
        threading.Thread(target=_delayed, daemon=True).start()

    def stop(self):
        with self._mode_lock:
            self._mode = self._MODE_OFF
        self._wake.clear()

    def _run(self):
        t = 0.0
        next_reaction = random.uniform(3.0, 7.0)
        last_tick = time.time()

        while True:
            self._wake.wait()

            with self._mode_lock:
                mode = self._mode

            if mode == self._MODE_OFF:
                self._wake.clear()
                t = 0.0
                last_tick = time.time()
                continue

            now = time.time()
            dt = min(now - last_tick, 0.5)  # clamp after wakeup gaps
            last_tick = now
            t += dt
            next_reaction -= dt

            TICK = 0.5   # 5 waypoints per 2.5s cycle → smooth sine
            FREQ = 2.513 # 2π / 2.5 — one full left-right swivel every 2.5s

            if mode == self._MODE_LISTENING:
                roll     = math.sin(t * FREQ) * 16.0
                body_rad = -math.sin(t * FREQ) * 0.28        # counter-swivel in radians
                yaw      = math.sin(t * FREQ * 0.6 + 1.2) * 6.0
                pitch    = 0.0
                ant_r    = (math.sin(t * FREQ * 0.4) * 0.5 + 0.5) * 0.35
                ant_l    = (math.sin(t * FREQ * 0.4 + 2.0) * 0.5 + 0.5) * 0.35

                try:
                    self._mini.goto_target(
                        head=create_head_pose(pitch=pitch, roll=roll, yaw=yaw),
                        antennas=[ant_r, ant_l],
                        body_yaw=body_rad,
                        duration=TICK, method="minjerk",
                    )
                except Exception:
                    pass

                if next_reaction <= 0:
                    fn = random.choices(_MICRO_FNS, weights=_MICRO_WEIGHTS, k=1)[0]
                    try:
                        fn(self._mini)
                        self._mini.goto_target(
                            head=create_head_pose(pitch=pitch, roll=roll, yaw=yaw),
                            body_yaw=None,
                            duration=0.5, method="minjerk",
                        )
                    except Exception:
                        pass
                    next_reaction = random.uniform(3.0, 7.0)

            elif mode == self._MODE_SPEAKING:
                roll     = math.sin(t * FREQ) * 10.0
                body_rad = -math.sin(t * FREQ) * 0.2
                yaw      = math.sin(t * FREQ * 0.6 + 0.8) * 5.0
                pitch    = 0.0
                ant      = (math.sin(t * FREQ * 0.4) * 0.5 + 0.5) * 0.28

                try:
                    self._mini.goto_target(
                        head=create_head_pose(pitch=pitch, roll=roll, yaw=yaw),
                        antennas=[ant, ant],
                        body_yaw=body_rad,
                        duration=TICK, method="minjerk",
                    )
                except Exception:
                    pass

            time.sleep(TICK)
