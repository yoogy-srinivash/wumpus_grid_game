import pygame
import sys
import random
import math
import time
import json
import os
from collections import deque

pygame.init()
try:
    pygame.mixer.init(frequency=44100, size=8, channels=1, buffer=1024)
except Exception:
    pass

# ─── Constants ───────────────────────────────────────────────────────────────
GRID_SIZE   = 6
CELL_SIZE   = 90
PANEL_W     = 280
WIDTH       = GRID_SIZE * CELL_SIZE + PANEL_W
HEIGHT      = GRID_SIZE * CELL_SIZE
FPS         = 60

# High score persistence
SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wumpus_highscore.json")

def load_high_score():
    try:
        with open(SCORE_FILE, "r") as f:
            data = json.load(f)
            return int(data.get("high_score", 0))
    except Exception:
        return 0

def save_high_score(score):
    try:
        with open(SCORE_FILE, "w") as f:
            json.dump({"high_score": score}, f)
    except Exception:
        pass

# Palette
WHITE       = (255, 255, 255)
C_BG        = (10, 12, 20)
C_CELL_DARK = (22, 28, 45)
C_CELL_MID  = (30, 38, 60)
C_VISITED   = (25, 42, 70)
C_SAFE      = (20, 80, 55)
C_DANGER    = (90, 40, 20)
C_WUMPUS    = (120, 20, 30)
C_PIT       = (15, 15, 35)
C_GOLD      = (200, 170, 30)
C_PANEL     = (14, 18, 32)
C_BORDER    = (40, 55, 100)
C_PLAYER    = (80, 180, 255)
C_TEXT      = (235, 242, 255)   # bright near-white for primary text
C_DIM       = (140, 158, 205)   # clearly readable secondary text
C_GREEN     = (60, 200, 120)
C_RED       = (220, 60, 60)
C_ORANGE    = (230, 150, 40)
C_PURPLE    = (160, 80, 220)
C_CYAN      = (40, 210, 210)

# Game states
STATE_PLAY   = "play"
STATE_WIN    = "win"
STATE_DEAD   = "dead"
STATE_MENU   = "menu"

# ─── Sound synthesis ─────────────────────────────────────────────────────────
def _make_sound(freq, duration_ms, waveform="sine", volume=0.3):
    sample_rate = 44100
    n = int(sample_rate * duration_ms / 1000)
    buf = bytearray(n)
    for i in range(n):
        t = i / sample_rate
        if waveform == "sine":
            v = math.sin(2 * math.pi * freq * t)
        elif waveform == "square":
            v = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
        else:
            v = random.uniform(-1, 1)
        fade = min(1.0, min(i, n - i) / max(1, int(sample_rate * 0.01)))
        val = int(127 + 127 * v * volume * fade)
        buf[i] = max(0, min(255, val))
    return pygame.mixer.Sound(buffer=bytes(buf))

def _make_chord(freqs, duration_ms, volume=0.25):
    sample_rate = 44100
    n = int(sample_rate * duration_ms / 1000)
    raw = [0.0] * n
    for freq in freqs:
        for i in range(n):
            t = i / sample_rate
            fade = min(1.0, min(i, n - i) / max(1, int(sample_rate * 0.05)))
            raw[i] += math.sin(2 * math.pi * freq * t) * fade
    peak = max(abs(v) for v in raw) or 1.0
    buf = bytearray(n)
    for i, v in enumerate(raw):
        buf[i] = max(0, min(255, int(127 + 127 * v / peak * volume)))
    return pygame.mixer.Sound(buffer=bytes(buf))

class _SilentSound:
    def play(self): pass

def _safe_make(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return _SilentSound()

SND_MOVE   = _safe_make(_make_sound, 440, 80,  "sine",   0.2)
SND_SAFE   = _safe_make(_make_chord, [523, 659, 784], 300, 0.25)
SND_DANGER = _safe_make(_make_sound, 180, 400, "square", 0.2)
SND_GOLD   = _safe_make(_make_chord, [523, 659, 784, 1047], 600, 0.3)
SND_DEATH  = _safe_make(_make_sound, 80,  800, "square", 0.3)
SND_WIN    = _safe_make(_make_chord, [523, 659, 784, 1047, 1319], 1000, 0.3)
SND_CLICK  = _safe_make(_make_sound, 880,  60, "sine",   0.15)
SND_ARROW  = _safe_make(_make_sound, 660, 150, "square", 0.2)

def play_snd(snd):
    try:
        snd.play()
    except Exception:
        pass

# ─── Fonts — load DejaVu Sans Mono TTF directly for pixel-perfect clarity ────
# Priority: exact TTF path → SysFont name fallback → pygame built-in default
_DVMONO      = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
_DVMONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

# Additional cross-platform TTF search paths (Windows / macOS / other Linux)
_MONO_TTF_PATHS = [
    # Linux alternatives
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    # macOS
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Courier New.ttf",
    # Windows
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
]

def _load_font(size, bold=False):
    """Load the sharpest available monospace TTF at `size` px."""
    primary = _DVMONO_BOLD if bold else _DVMONO
    # 1. Try exact DejaVu path
    if os.path.exists(primary):
        try:
            return pygame.font.Font(primary, size)
        except Exception:
            pass
    # 2. Try other known TTF paths
    for path in _MONO_TTF_PATHS:
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                pass
    # 3. SysFont name fallback
    for name in ["dejavusansmono", "liberationmono", "ubuntumono",
                 "consolas", "couriernew", "courier"]:
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f.size("A")[0] > 0:
                return f
        except Exception:
            pass
    # 4. pygame built-in (always works)
    return pygame.font.SysFont(None, size, bold=bold)

FONT_TITLE  = _load_font(34, bold=True)
FONT_BIG    = _load_font(24, bold=True)
FONT_MED    = _load_font(17, bold=True)
FONT_SMALL  = _load_font(15)            # 15px — comfortably readable
FONT_CELL   = _load_font(13, bold=True)
FONT_ICON   = _load_font(20, bold=True)

# ─── Particle system ─────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color, vx=0, vy=0, life=60, size=4):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.color = color
        self.life = self.max_life = life
        self.size = size

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.15
        self.life -= 1

    def draw(self, surf):
        alpha = self.life / self.max_life
        r, g, b = self.color
        c = (int(r*alpha), int(g*alpha), int(b*alpha))
        sz = max(1, int(self.size * alpha))
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), sz)

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def burst(self, x, y, color, n=20, speed=3):
        for _ in range(n):
            a  = random.uniform(0, 2*math.pi)
            sp = random.uniform(0.5, speed)
            self.particles.append(Particle(x, y, color,
                math.cos(a)*sp, math.sin(a)*sp,
                random.randint(30, 80), random.randint(2, 6)))

    def update_draw(self, surf):
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update()
            p.draw(surf)

# ─── AI Knowledge Base — full propositional logic inference ──────────────────
class KnowledgeBase:
    """
    Maintains all logical knowledge about the Wumpus grid.

    Inference rules (applied to fixpoint):
      R1: visited(r,c) ∧ ¬breeze(r,c)  → ¬pit(n)    for all n ∈ adj(r,c)
      R2: visited(r,c) ∧ ¬stench(r,c)  → ¬wumpus(n) for all n ∈ adj(r,c)
      R3: ¬pit(r,c)    → safe_from_pit(r,c)
      R4: ¬wumpus(r,c) → safe_from_wumpus(r,c)
      R5: safe_from_pit(r,c) ∧ safe_from_wumpus(r,c) → safe(r,c)
      R6: breeze(r,c) ∧ all-but-one adj are safe_from_pit
              → the remaining adj has a pit  → pit_confirmed(r,c)
      R7: stench(r,c) ∧ wumpus_alive ∧ all-but-one adj are safe_from_wumpus
              → the remaining adj has wumpus → wumpus_loc confirmed
      R8: pit_confirmed at some cell → its adj are breezy (back-propagate safety)
      R9: intersection of all stench-adj candidate sets of size 1 → wumpus_loc
    """
    def __init__(self, size):
        self.size = size
        self.reset()

    def reset(self):
        self.breeze   = {}        # (r,c) -> bool  (only visited cells)
        self.stench   = {}        # (r,c) -> bool
        self.visited  = set()
        self.safe     = set()     # proven safe (no pit, no live wumpus)
        self.no_pit   = set()     # logically proven pit-free
        self.no_wump  = set()     # logically proven wumpus-free
        self.pit_confirmed  = set()   # logically proven to contain a pit
        self.wumpus_alive   = True
        self.wumpus_loc     = None    # confirmed wumpus location
        self.frontier       = set()
        # heuristic danger scores for unproven cells (0..1 each axis)
        self.pit_prob   = {}
        self.wumpus_prob = {}

    def all_cells(self):
        for r in range(self.size):
            for c in range(self.size):
                yield r, c

    def adj(self, r, c):
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                yield nr, nc

    def _mark_safe(self, r, c):
        self.no_pit.add((r,c))
        self.no_wump.add((r,c))
        self.safe.add((r,c))

    def observe(self, r, c, has_breeze, has_stench):
        """Called whenever the agent steps into (r,c)."""
        self.breeze[(r,c)] = has_breeze
        self.stench[(r,c)] = has_stench
        self.visited.add((r,c))
        self._mark_safe(r, c)   # visited cells are always safe
        self._infer()

    def wumpus_killed(self):
        self.wumpus_alive = False
        if self.wumpus_loc:
            self.no_wump.add(self.wumpus_loc)
            # re-derive safe: if that cell also has no pit it is now safe
            if self.wumpus_loc in self.no_pit:
                self.safe.add(self.wumpus_loc)
        self._infer()

    # ── core inference engine ─────────────────────────────────────────────────
    def _infer(self):
        changed = True
        while changed:
            changed = False

            for (r, c) in list(self.visited):

                # R1: no breeze → all neighbours pit-free
                if not self.breeze.get((r,c), True):
                    for nr, nc in self.adj(r, c):
                        if (nr,nc) not in self.no_pit:
                            self.no_pit.add((nr,nc))
                            changed = True

                # R2: no stench → all neighbours wumpus-free
                if not self.stench.get((r,c), True):
                    for nr, nc in self.adj(r, c):
                        if (nr,nc) not in self.no_wump:
                            self.no_wump.add((nr,nc))
                            changed = True

                # R6: breeze + exactly one unproven pit-candidate adj
                #     → that candidate MUST contain the pit
                if self.breeze.get((r,c)) == True:
                    pit_cands = [n for n in self.adj(r,c)
                                 if n not in self.no_pit and n not in self.visited]
                    if len(pit_cands) == 1:
                        pc = pit_cands[0]
                        if pc not in self.pit_confirmed:
                            self.pit_confirmed.add(pc)
                            changed = True

                # R7: stench + exactly one unproven wumpus-candidate adj
                #     → wumpus confirmed there
                if self.stench.get((r,c)) == True and self.wumpus_alive:
                    w_cands = [n for n in self.adj(r,c)
                               if n not in self.no_wump and n not in self.visited]
                    if len(w_cands) == 1:
                        wc_cell = w_cands[0]
                        if self.wumpus_loc != wc_cell:
                            self.wumpus_loc = wc_cell
                            changed = True

            # R9: intersect all stench-adj candidate sets → if size 1, confirmed
            if self.wumpus_alive and self.wumpus_loc is None:
                candidates = None
                for (r, c) in self.visited:
                    if self.stench.get((r,c)) == True:
                        cands = frozenset(n for n in self.adj(r,c)
                                          if n not in self.no_wump
                                          and n not in self.visited)
                        if candidates is None:
                            candidates = set(cands)
                        else:
                            candidates &= cands
                if candidates and len(candidates) == 1:
                    wloc = next(iter(candidates))
                    if self.wumpus_loc != wloc:
                        self.wumpus_loc = wloc
                        changed = True

            # Confirmed pit cells → their neighbours are pit-free from OTHER direction?
            # (not derivable further, but mark pit_confirmed cells as no_wump if wumpus_loc differs)
            for pc in self.pit_confirmed:
                if pc != self.wumpus_loc and pc not in self.no_wump:
                    # A confirmed pit cell is not the wumpus cell (wumpus is unique)
                    # We can't mark it no_wump in general, but can note it's a pit.
                    pass

            # R5: no_pit ∧ (no_wump ∨ wumpus dead) → safe
            for r, c in self.all_cells():
                if (r,c) not in self.safe:
                    pit_ok  = (r,c) in self.no_pit
                    wump_ok = (r,c) in self.no_wump or not self.wumpus_alive
                    if pit_ok and wump_ok:
                        self.safe.add((r,c))
                        changed = True

            # Propagate: if wumpus_loc is confirmed, all OTHER unvisited cells are wumpus-free
            if self.wumpus_loc and self.wumpus_alive:
                for r, c in self.all_cells():
                    if (r,c) != self.wumpus_loc and (r,c) not in self.no_wump:
                        self.no_wump.add((r,c))
                        changed = True

        # Update frontier
        self.frontier = set()
        for (r,c) in self.visited:
            for nr,nc in self.adj(r,c):
                if (nr,nc) not in self.visited:
                    self.frontier.add((nr,nc))

        # Update heuristic danger for unproven cells (used only when no safe move exists)
        self._update_danger()

    def _update_danger(self):
        self.pit_prob   = {}
        self.wumpus_prob = {}
        for r, c in self.all_cells():
            if (r,c) in self.safe or (r,c) in self.visited:
                self.pit_prob[(r,c)]    = 0.0
                self.wumpus_prob[(r,c)] = 0.0
                continue
            if (r,c) in self.pit_confirmed:
                self.pit_prob[(r,c)] = 1.0
            elif (r,c) in self.no_pit:
                self.pit_prob[(r,c)] = 0.0
            else:
                breezy = sum(1 for n in self.adj(r,c) if self.breeze.get(n) == True)
                clean  = sum(1 for n in self.adj(r,c) if self.breeze.get(n) == False)
                self.pit_prob[(r,c)] = 0.0 if clean > 0 else min(0.9, breezy * 0.3)

            if not self.wumpus_alive or (r,c) in self.no_wump:
                self.wumpus_prob[(r,c)] = 0.0
            elif self.wumpus_loc == (r,c):
                self.wumpus_prob[(r,c)] = 1.0
            else:
                stenchy = sum(1 for n in self.adj(r,c) if self.stench.get(n) == True)
                clean_s = sum(1 for n in self.adj(r,c) if self.stench.get(n) == False)
                self.wumpus_prob[(r,c)] = 0.0 if clean_s > 0 else min(0.9, stenchy * 0.35)

    # ── pathfinding ───────────────────────────────────────────────────────────
    def _path_to(self, src, dst, allow_unsafe=False):
        """BFS from src to dst, traversing only safe+visited cells.
           If allow_unsafe=True, will also consider unvisited frontier cells
           ordered by danger (used as last resort)."""
        if src == dst:
            return []
        q = deque([(src, [])])
        seen = {src}
        while q:
            (r,c), path = q.popleft()
            for nr, nc in self.adj(r, c):
                if (nr,nc) in seen:
                    continue
                seen.add((nr,nc))
                new_path = path + [(nr,nc)]
                if (nr,nc) == dst:
                    return new_path
                # Only traverse cells we know are safe to walk through
                if (nr,nc) in self.safe or (nr,nc) in self.visited:
                    q.append(((nr,nc), new_path))
        if allow_unsafe:
            # Try again allowing frontier cells as waypoints
            q = deque([(src, [])])
            seen = {src}
            while q:
                (r,c), path = q.popleft()
                for nr, nc in self.adj(r, c):
                    if (nr,nc) in seen:
                        continue
                    seen.add((nr,nc))
                    new_path = path + [(nr,nc)]
                    if (nr,nc) == dst:
                        return new_path
                    if (nr,nc) not in self.pit_confirmed:
                        if (nr,nc) not in self.no_pit:
                            pass  # risky but allow
                        q.append(((nr,nc), new_path))
        return None

    def danger(self, r, c):
        if (r,c) in self.safe:
            return 0.0
        if (r,c) in self.pit_confirmed:
            return 2.0
        return self.pit_prob.get((r,c), 0.1) + self.wumpus_prob.get((r,c), 0.1)

    # ── decision helpers used by ai_step ─────────────────────────────────────
    def unvisited_safe_cells(self):
        return [p for p in self.safe if p not in self.visited]

    def shoot_target(self, current):
        """Return (dr,dc) direction to shoot if wumpus location is confirmed
           and is reachable by arrow from current position."""
        if not self.wumpus_alive or self.wumpus_loc is None:
            return None
        cr, cc = current
        wr, wc = self.wumpus_loc
        if wr == cr and wc != cc:
            return (0, 1 if wc > cc else -1)
        if wc == cc and wr != cr:
            return (1 if wr > cr else -1, 0)
        return None

    def safest_frontier(self, current):
        """Among frontier cells, return the one with lowest danger score,
           preferring cells that are at least pit-free or wumpus-free."""
        candidates = []
        for (r,c) in self.frontier:
            if (r,c) not in self.visited:
                d = self.danger(r,c)
                # Never step onto a confirmed pit
                if (r,c) in self.pit_confirmed:
                    continue
                # Never step onto confirmed wumpus location (unless it's dead)
                if self.wumpus_loc == (r,c) and self.wumpus_alive:
                    continue
                candidates.append((d, r, c))
        candidates.sort()
        return (candidates[0][1], candidates[0][2]) if candidates else None

# ─── World generation ────────────────────────────────────────────────────────
def generate_world(size, pit_prob=0.15):
    start = (size-1, 0)

    # 1. Place wumpus (not at start or its immediate neighbours)
    while True:
        wr, wc = random.randint(0, size-1), random.randint(0, size-1)
        if (wr, wc) != start and (wr, wc) != (size-1, 1) and (wr, wc) != (size-2, 0):
            break

    # 2. Generate pits first so gold placement can avoid them
    pit_cells = set()
    for r in range(size):
        for c in range(size):
            if (r, c) != start and (r, c) != (wr, wc) and random.random() < pit_prob:
                pit_cells.add((r, c))

    # Both (5,1) and (4,0) are adjacent to start — never allow both simultaneously
    # as it would make the start cell completely surrounded by danger
    if (size-1, 1) in pit_cells and (size-2, 0) in pit_cells:
        pit_cells.discard(random.choice([(size-1, 1), (size-2, 0)]))

    # 3. Place gold — not at start, not on wumpus, not inside a pit
    while True:
        gr, gc = random.randint(0, size-1), random.randint(0, size-1)
        if (gr, gc) != start and (gr, gc) != (wr, wc) and (gr, gc) not in pit_cells:
            break

    # 4. Build cell dict
    world = {}
    for r in range(size):
        for c in range(size):
            world[(r, c)] = {
                "pit":    (r, c) in pit_cells,
                "wumpus": (r == wr and c == wc),
                "gold":   (r == gr and c == gc),
                "breeze": False,
                "stench": False,
            }

    # 5. Propagate breeze / stench
    for r in range(size):
        for c in range(size):
            if world[(r, c)]["pit"]:
                for nr, nc in _adj(r, c, size):
                    world[(nr, nc)]["breeze"] = True
            if world[(r, c)]["wumpus"]:
                for nr, nc in _adj(r, c, size):
                    world[(nr, nc)]["stench"] = True

    return world, (wr, wc), (gr, gc)

def _adj(r, c, size):
    for dr,dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr,nc = r+dr, c+dc
        if 0 <= nr < size and 0 <= nc < size:
            yield nr, nc

# ─── Main Game ───────────────────────────────────────────────────────────────
class WumpusGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("⚔  WUMPUS WORLD  ⚔")
        self.clock  = pygame.time.Clock()
        self.ps     = ParticleSystem()
        self.state  = STATE_MENU
        self.high_score = load_high_score()   # ← load from disk on startup
        self.world = {}
        self.player = (GRID_SIZE-1, 0)
        self.kb = KnowledgeBase(GRID_SIZE)
        self.arrows = 1
        self.score = 0
        self.has_gold = False
        self.wumpus_dead = False
        self.wumpus_pos = (0, 0)
        self.gold_pos = (0, 0)
        self.log = []
        self.ai_path = []
        self.ai_mode = False
        self.ai_timer = 0
        self.anim_player = [float(self.player[1]*CELL_SIZE + CELL_SIZE//2),
                            float(self.player[0]*CELL_SIZE + CELL_SIZE//2)]
        self.anim_target = self.anim_player[:]
        self.shake_timer = 0
        self.flash_color = None
        self.flash_timer = 0

    def _new_game(self):
        self.world, self.wumpus_pos, self.gold_pos = generate_world(GRID_SIZE)
        self.player = (GRID_SIZE-1, 0)
        self.kb     = KnowledgeBase(GRID_SIZE)
        self.arrows = 1
        self.score  = 0
        self.has_gold    = False
        self.wumpus_dead = False
        self.log    = ["► New game started", "► You enter the cave..."]
        self.ai_path     = []
        self.ai_mode     = False
        self.ai_timer    = 0
        self.anim_player = [float(self.player[1]*CELL_SIZE + CELL_SIZE//2),
                            float(self.player[0]*CELL_SIZE + CELL_SIZE//2)]
        self.anim_target = self.anim_player[:]
        self.shake_timer = 0
        self.flash_color = None
        self.flash_timer = 0
        self.state  = STATE_PLAY
        self._enter_cell()

    def _enter_cell(self):
        r, c = self.player
        cell = self.world[(r,c)]
        b = cell["breeze"]
        s = cell["stench"]
        self.kb.observe(r, c, b, s)
        self.score -= 1

        msgs = []
        if b:  msgs.append("💨 You feel a breeze!")
        if s:  msgs.append("🦨 You smell a stench!")
        if cell["gold"] and not self.has_gold:
            msgs.append("✨ GOLD found! Press G to grab!")
        if not b and not s:
            msgs.append("✓ This room seems safe.")

        for m in msgs:
            self._log(m)

        if cell["pit"]:
            self._log("💀 You fell into a PIT!")
            self.score -= 1000
            self.state = STATE_DEAD
            self.shake_timer = 30
            self.flash_color = C_RED
            self.flash_timer = 45
            play_snd(SND_DEATH)
            self.ps.burst(*self.anim_player, C_RED, 40, 5)

        elif cell["wumpus"] and not self.wumpus_dead:
            self._log("💀 The WUMPUS devoured you!")
            self.score -= 1000
            self.state = STATE_DEAD
            self.shake_timer = 30
            self.flash_color = C_WUMPUS
            self.flash_timer = 45
            play_snd(SND_DEATH)
            self.ps.burst(*self.anim_player, C_WUMPUS, 40, 5)

        elif b or s:
            play_snd(SND_DANGER)
        else:
            play_snd(SND_SAFE)
            self.ps.burst(*self.anim_player, C_GREEN, 8, 2)

    def _log(self, msg):
        self.log.append(msg)
        if len(self.log) > 12:
            self.log.pop(0)

    def cell_center(self, r, c):
        return (c * CELL_SIZE + CELL_SIZE//2, r * CELL_SIZE + CELL_SIZE//2)

    def move(self, dr, dc):
        if self.state != STATE_PLAY: return
        nr, nc = self.player[0]+dr, self.player[1]+dc
        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
            self.player = (nr, nc)
            cx, cy = self.cell_center(nr, nc)
            self.anim_target = [float(cx), float(cy)]
            play_snd(SND_MOVE)
            self._enter_cell()

    def shoot(self, dr, dc):
        if self.state != STATE_PLAY or self.arrows <= 0: return
        self.arrows -= 1
        self.score  -= 10
        play_snd(SND_ARROW)
        self._log("🏹 Arrow fired!")
        pr, pc = self.player
        r, c = pr+dr, pc+dc
        while 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
            if self.world[(r,c)]["wumpus"] and not self.wumpus_dead:
                self.wumpus_dead = True
                self.world[(r,c)]["wumpus"] = False
                self.score += 500
                self._log("🎯 WUMPUS slain! +500")
                play_snd(SND_GOLD)
                self.ps.burst(*self.cell_center(r,c), C_RED, 40, 5)
                self.kb.wumpus_killed()   # full KB re-inference after kill
                return
            r, c = r+dr, c+dc
        self._log("🏹 Arrow missed...")
        # Mark the entire line of fire as wumpus-free then re-infer
        r, c = pr+dr, pc+dc
        while 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
            self.kb.no_wump.add((r,c))
            r, c = r+dr, c+dc
        self.kb._infer()

    def grab_gold(self):
        if self.state != STATE_PLAY: return
        r, c = self.player
        if self.world[(r,c)]["gold"] and not self.has_gold:
            self.has_gold = True
            self.world[(r,c)]["gold"] = False
            self.score += 1000
            self._log("💰 GOLD collected! +1000")
            play_snd(SND_GOLD)
            self.ps.burst(*self.anim_player, C_GOLD, 50, 6)
            self.flash_color = C_GOLD
            self.flash_timer = 30

    def climb_out(self):
        if self.state != STATE_PLAY: return
        if self.player == (GRID_SIZE-1, 0):
            if self.has_gold:
                self.score += 500
                self._log("🏆 Escaped with gold! +500")
            else:
                self._log("🚪 Escaped without gold.")
            if self.score > self.high_score:
                self.high_score = self.score
                save_high_score(self.high_score)
            play_snd(SND_WIN)
            self.state = STATE_WIN
            self.ps.burst(*self.anim_player, C_GOLD, 80, 7)

    def _check_death_high_score(self):
        if self.score > self.high_score:
            self.high_score = self.score
            save_high_score(self.high_score)

    # ── Goal-directed AI planner ──────────────────────────────────────────────
    def ai_step(self):
        """
        Strict priority planner — never steps onto a confirmed dangerous cell:
          1. Grab gold if standing on it
          2. Climb out if carrying gold and at start
          3. Shoot wumpus if confirmed location is in line of fire from here
          4. If carrying gold, navigate back to start via safe cells
          5. Move to nearest safe unvisited cell (explore safely)
          6. Navigate to a shoot position if wumpus loc is confirmed
          7. Take the safest frontier step (cautious exploration)
          8. Last resort: unsafe path to start with gold
        """
        if self.state != STATE_PLAY:
            return

        # Flush next step of queued path
        if self.ai_path:
            next_pos = self.ai_path.pop(0)
            dr = next_pos[0] - self.player[0]
            dc = next_pos[1] - self.player[1]
            self.move(dr, dc)
            return

        kb  = self.kb
        r, c = self.player

        # 1. Grab gold immediately when standing on it
        if self.world[(r,c)]["gold"] and not self.has_gold:
            self.grab_gold()
            return

        # 2. Escape if carrying gold and standing at start
        if self.has_gold and self.player == (GRID_SIZE-1, 0):
            self.climb_out()
            return

        # 3. Shoot if wumpus confirmed in straight line from current position
        shoot_dir = kb.shoot_target(self.player)
        if shoot_dir and self.arrows > 0:
            self._log("🤖 AI: Shooting confirmed Wumpus!")
            self.ai_path = []
            self.shoot(*shoot_dir)
            return

        # 4. Returning home with gold — find safe path to start
        if self.has_gold:
            start = (GRID_SIZE-1, 0)
            path = kb._path_to(self.player, start)
            if path:
                self._log("🤖 AI: Heading to exit with gold")
                self.ai_path = path
                return

        # 5. Safe exploration — BFS to closest safe unvisited cell
        unvisited = kb.unvisited_safe_cells()
        if unvisited:
            best_path = None
            for target in unvisited:
                p = kb._path_to(self.player, target)
                if p and (best_path is None or len(p) < len(best_path)):
                    best_path = p
            if best_path:
                self.ai_path = best_path
                return

        # 6. Try to reach a shoot position for confirmed wumpus
        if kb.wumpus_loc and kb.wumpus_alive and self.arrows > 0:
            wr, wc = kb.wumpus_loc
            shoot_spots = []
            for sc in range(GRID_SIZE):   # same row as wumpus
                cell = (wr, sc)
                if cell != kb.wumpus_loc and cell in kb.safe:
                    shoot_spots.append(cell)
            for sr in range(GRID_SIZE):   # same col as wumpus
                cell = (sr, wc)
                if cell != kb.wumpus_loc and cell in kb.safe:
                    shoot_spots.append(cell)
            best_path = None
            for sp in shoot_spots:
                p = kb._path_to(self.player, sp)
                if p and (best_path is None or len(p) < len(best_path)):
                    best_path = p
            if best_path:
                self._log("🤖 AI: Moving to shoot position")
                self.ai_path = best_path
                return

        # 7. Cautious frontier step — lowest danger, never confirmed pit/wumpus
        sf = kb.safest_frontier(self.player)
        if sf:
            path = kb._path_to(self.player, sf, allow_unsafe=True)
            if path:
                self._log(f"🤖 AI: Cautious step (d={kb.danger(*sf):.2f})")
                self.ai_path = path
                return

        # 8. Absolute last resort: unsafe path home if carrying gold
        if self.has_gold:
            start = (GRID_SIZE-1, 0)
            path = kb._path_to(self.player, start, allow_unsafe=True)
            if path:
                self.ai_path = path
                return

        self._log("🤖 AI: No moves — exiting without gold")
        # If truly stuck, try to at least escape
        start = (GRID_SIZE-1, 0)
        path = kb._path_to(self.player, start, allow_unsafe=True)
        if path:
            self.ai_path = path



    def update(self, dt):
        tx, ty = self.anim_target
        self.anim_player[0] += (tx - self.anim_player[0]) * 0.25
        self.anim_player[1] += (ty - self.anim_player[1]) * 0.25

        if self.shake_timer > 0: self.shake_timer -= 1
        if self.flash_timer > 0: self.flash_timer -= 1

        if self.ai_mode and self.state == STATE_PLAY:
            self.ai_timer += 1
            if self.ai_timer >= 18:
                self.ai_timer = 0
                self.ai_step()

    # ── Drawing helpers ───────────────────────────────────────────────────────
    def _draw_pit(self, surf, cx, cy, size=34):
        t = time.time()
        for r2, col in [
            (size,      (35,  20,  70)),
            (size-6,    (20,  10,  50)),
            (size-12,   (10,   5,  30)),
            (size-18,   (4,    2,  15)),
            (size-24,   (0,    0,   5)),
            (max(2, size-30), (0, 0, 0)),
        ]:
            if r2 > 0:
                pygame.draw.circle(surf, col, (cx, cy), r2)
        arm_surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        off_x, off_y = cx - CELL_SIZE//2, cy - CELL_SIZE//2
        for arm in range(3):
            base_angle = t * 2.0 + arm * (2 * math.pi / 3)
            pts = []
            for step in range(18):
                frac  = step / 17
                angle = base_angle + frac * math.pi * 1.4
                r2    = int((size - 3) * (1 - frac * 0.75))
                pts.append((cx + int(math.cos(angle) * r2) - off_x,
                            cy + int(math.sin(angle) * r2) - off_y))
            for i in range(len(pts) - 1):
                fade = int(130 * (1 - i / len(pts)))
                pygame.draw.line(arm_surf, (120, 70, 230, fade), pts[i], pts[i+1], 2)
        surf.blit(arm_surf, (off_x, off_y))
        pygame.draw.circle(surf, (100, 50, 200), (cx, cy), size, 3)
        pygame.draw.circle(surf, (140, 80, 255), (cx, cy), size + 2, 1)
        pygame.draw.circle(surf, (0, 0, 0), (cx, cy), 4)

    def _draw_wumpus(self, surf, cx, cy, size=24):
        pygame.draw.circle(surf, (180, 20, 20), (cx, cy), size)
        pygame.draw.circle(surf, (220, 60, 60), (cx, cy), size, 3)
        eo = size // 3
        pygame.draw.circle(surf, (255, 220, 0), (cx - eo, cy - eo//2), 5)
        pygame.draw.circle(surf, (255, 220, 0), (cx + eo, cy - eo//2), 5)
        pygame.draw.circle(surf, (0, 0, 0),     (cx - eo, cy - eo//2), 2)
        pygame.draw.circle(surf, (0, 0, 0),     (cx + eo, cy - eo//2), 2)
        fang_w = size // 4
        pygame.draw.polygon(surf, (255, 255, 255), [
            (cx - fang_w,     cy + size//3),
            (cx - fang_w//2,  cy + size//3 + 7),
            (cx,              cy + size//3),
        ])
        pygame.draw.polygon(surf, (255, 255, 255), [
            (cx + fang_w//2,  cy + size//3),
            (cx + fang_w,     cy + size//3 + 7),
            (cx + fang_w*2,   cy + size//3),
        ])

    def _draw_gold(self, surf, cx, cy, size=20):
        t = time.time()
        pulse = 0.85 + 0.15 * math.sin(t * 4)
        outer = int(size * pulse)
        inner = int(size * 0.45 * pulse)
        pts = []
        for i in range(10):
            angle = math.pi / 5 * i - math.pi / 2
            r2 = outer if i % 2 == 0 else inner
            pts.append((cx + int(math.cos(angle) * r2),
                        cy + int(math.sin(angle) * r2)))
        pygame.draw.polygon(surf, (255, 210, 0), pts)
        pygame.draw.polygon(surf, (255, 255, 140), pts, 2)
        pygame.draw.circle(surf, (255, 255, 200), (cx - outer//4, cy - outer//4), max(2, outer//6))

    def _draw_breeze(self, surf, x, y, cell_size):
        t = time.time()
        bsurf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
        for i in range(6):
            wy     = 12 + i * 13
            speed  = 1.5 + i * 0.3
            phase  = t * speed + i * 0.9
            pts    = []
            for px2 in range(0, cell_size + 1, 3):
                wave = int(math.sin(phase + px2 * 0.18) * 4)
                pts.append((px2, wy + wave))
            if len(pts) >= 2:
                alpha = 90 + i * 18
                col   = (40 + i*10, 200 + i*5, 230, alpha)
                pygame.draw.lines(bsurf, col, False, pts, 2)
        for i in range(8):
            phase = (t * 0.8 + i * 0.37) % 1.0
            px2   = int(phase * (cell_size + 10)) - 5
            py2   = 8 + (i * 11) % (cell_size - 16)
            r2    = 2 + (i % 2)
            alpha = int(160 * (1 - abs(phase - 0.5) * 2))
            pygame.draw.circle(bsurf, (100, 220, 255, alpha), (px2, py2), r2)
        surf.blit(bsurf, (x, y))
        lbl = FONT_SMALL.render("BREEZE", True, (80, 220, 255))
        surf.blit(lbl, (x + cell_size//2 - lbl.get_width()//2, y + cell_size - 18))

    def _draw_stench(self, surf, x, y, cell_size):
        t = time.time()
        ssurf = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
        for i in range(5):
            speed  = 0.6 + i * 0.15
            phase  = (t * speed + i * 0.55) % 1.0
            start_x = int(phase * (cell_size + 30)) - 15
            pts = []
            for step in range(0, cell_size + 8, 5):
                jitter = int(math.sin(t * 2 + step * 0.25 + i * 1.1) * 5)
                pts.append((start_x + step, cell_size - step + jitter))
            pts = [(px2, py2) for px2, py2 in pts
                   if -5 <= px2 <= cell_size + 5 and -5 <= py2 <= cell_size + 5]
            if len(pts) >= 2:
                alpha = 160 + i * 15
                green = min(255, 170 + i * 12)
                pygame.draw.lines(ssurf, (60, green, 30, alpha), False, pts, 3)
        blob_seeds = [(7, 0.0), (22, 0.33), (37, 0.66),
                      (52, 0.15), (67, 0.5),  (80, 0.82)]
        for bx, offset in blob_seeds:
            if bx >= cell_size: continue
            phase = (t * 0.55 + offset) % 1.0
            by    = int(cell_size - phase * (cell_size + 20)) + 10
            if by < -10 or by > cell_size + 10: continue
            sz    = 9 + int(math.sin(t * 1.8 + offset * 6) * 3)
            alpha = min(255, int(220 * math.sin(phase * math.pi) + 20))
            pygame.draw.circle(ssurf, (50,  min(255, 190 + int(offset*30)), 20, alpha),
                               (bx, by), sz)
            pygame.draw.circle(ssurf, (120, 255, 80, alpha // 2),
                               (bx - sz//4, by - sz//4), max(2, sz // 3))
            pygame.draw.circle(ssurf, (80, 255, 60, min(255, alpha + 40)),
                               (bx, by), sz, 2)
        for px2 in range(0, cell_size, 1):
            wave   = int(math.sin(t * 1.2 + px2 * 0.12) * 6)
            mist_y = cell_size - 28 + wave
            for dy in range(22):
                a = max(0, int(90 * (1 - dy / 22)))
                py3 = mist_y + dy
                if 0 <= py3 < cell_size:
                    ssurf.set_at((px2, py3), (70, min(255, 180 + dy*2), 40, a))
        surf.blit(ssurf, (x, y))
        lbl = FONT_SMALL.render("STENCH", True, (120, 255, 90))
        surf.blit(lbl, (x + cell_size//2 - lbl.get_width()//2, y + cell_size - 18))

    def _draw_safe_mark(self, surf, cx, cy):
        pts = [
            (cx - 10, cy),
            (cx - 4,  cy + 7),
            (cx + 10, cy - 8),
        ]
        pygame.draw.lines(surf, (60, 220, 100), False, pts, 3)

    def _draw_player_icon(self, surf, px, py, has_gold):
        for radius in range(22, 6, -5):
            alpha = max(0, 35 - radius)
            glow = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*C_PLAYER, alpha), (radius, radius), radius)
            surf.blit(glow, (px - radius, py - radius))
        shadow_surf = pygame.Surface((28, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 70), (0, 0, 28, 10))
        surf.blit(shadow_surf, (px - 14, py + 12))
        pygame.draw.circle(surf, (50, 140, 230), (px, py), 14)
        pygame.draw.circle(surf, (140, 210, 255), (px, py), 14, 2)
        pygame.draw.arc(surf, (200, 240, 255),
                        pygame.Rect(px-8, py-8, 16, 10), 0, math.pi, 2)
        if has_gold:
            pygame.draw.circle(surf, (255, 210, 0), (px + 10, py - 10), 6)
            pygame.draw.circle(surf, (255, 255, 140), (px + 10, py - 10), 6, 1)

    # ── main cell draw ─────────────────────────────────────────────────────────
    def draw_cell(self, surf, r, c, ox, oy):
        cell      = self.world[(r,c)]
        kb        = self.kb
        visited   = (r,c) in kb.visited
        safe      = (r,c) in kb.safe
        pit_p     = kb.pit_prob.get((r,c), 0.0)
        wump_p    = kb.wumpus_prob.get((r,c), 0.0)
        danger    = pit_p + wump_p
        game_over = self.state in (STATE_WIN, STATE_DEAD)

        x  = ox + c * CELL_SIZE
        y  = oy + r * CELL_SIZE
        cx = x + CELL_SIZE // 2
        cy = y + CELL_SIZE // 2
        rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

        if visited:
            base = C_SAFE if safe else (C_DANGER if danger > 0.4 else C_VISITED)
        else:
            base = (18, 50, 38) if safe else C_CELL_DARK
        pygame.draw.rect(surf, base, rect)

        if not visited and danger > 0:
            ov = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            ov.fill((200, 40, 40, int(danger * 130)))
            surf.blit(ov, (x, y))

        if wump_p > 0:
            bh = int((CELL_SIZE - 8) * wump_p)
            pygame.draw.rect(surf, (180, 30, 30),  (x + 2, y + CELL_SIZE - 4 - bh, 5, bh))
        if pit_p > 0:
            bh = int((CELL_SIZE - 8) * pit_p)
            pygame.draw.rect(surf, (60, 60, 180),  (x + CELL_SIZE - 7, y + CELL_SIZE - 4 - bh, 5, bh))

        if visited:
            has_b = cell["breeze"]
            has_s = cell["stench"]
            if has_b:
                self._draw_breeze(surf, x, y, CELL_SIZE)
            if has_s:
                self._draw_stench(surf, x, y, CELL_SIZE)
            if not has_b and not has_s:
                self._draw_safe_mark(surf, cx, cy)

        reveal = visited or game_over
        if reveal:
            if cell["pit"]:
                self._draw_pit(surf, cx, cy - 4)
                lbl = FONT_SMALL.render("PIT", True, (200, 170, 255))
                surf.blit(lbl, (cx - lbl.get_width()//2, y + 4))

            if cell["wumpus"] and not self.wumpus_dead:
                self._draw_wumpus(surf, cx, cy - 4)
                lbl = FONT_SMALL.render("WUMPUS", True, (255, 140, 140))
                surf.blit(lbl, (cx - lbl.get_width()//2, y + 4))

            elif cell["wumpus"] and self.wumpus_dead:
                pygame.draw.line(surf, (140, 30, 30), (cx-14, cy-14), (cx+14, cy+14), 4)
                pygame.draw.line(surf, (140, 30, 30), (cx+14, cy-14), (cx-14, cy+14), 4)
                lbl = FONT_SMALL.render("DEAD", True, (180, 80, 80))
                surf.blit(lbl, (cx - lbl.get_width()//2, y + 4))

            if cell["gold"]:
                self._draw_gold(surf, cx, cy - 4)
                lbl = FONT_SMALL.render("GOLD", True, (255, 240, 90))
                surf.blit(lbl, (cx - lbl.get_width()//2, y + 4))

        if not visited and not game_over:
            fog = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            fog.fill((0, 0, 0, 150 if not safe else 70))
            surf.blit(fog, (x, y))

        if self.ai_mode and (r,c) in self.ai_path:
            hl = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            hl.fill((80, 180, 255, 45))
            surf.blit(hl, (x, y))

        if self.kb.wumpus_loc == (r,c) and self.kb.wumpus_alive and not visited:
            hl = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            hl.fill((220, 40, 40, 55))
            surf.blit(hl, (x, y))
            pulse_w = 2 + int(abs(math.sin(time.time()*3)) * 2)
            pygame.draw.rect(surf, (220, 60, 60), rect, pulse_w)

        border_col = C_PLAYER if (r,c) == self.player else (C_DIM if (r,c) in kb.frontier else C_BORDER)
        pygame.draw.rect(surf, border_col, rect, 1)

        if (r,c) == (GRID_SIZE-1, 0):
            lbl = FONT_SMALL.render("START", True, C_CYAN)
            surf.blit(lbl, (x + 2, y + 2))

        coord = FONT_SMALL.render(f"{r},{c}", True, (90, 105, 155))
        surf.blit(coord, (x + CELL_SIZE - 26, y + CELL_SIZE - 16))

    def draw_player(self, surf, ox, oy):
        px = int(self.anim_player[0]) + ox
        py = int(self.anim_player[1]) + oy
        self._draw_player_icon(surf, px, py, self.has_gold)

    def draw_panel(self, surf):
        ox = GRID_SIZE * CELL_SIZE
        panel_h = HEIGHT
        panel = pygame.Rect(ox, 0, PANEL_W, panel_h)
        pygame.draw.rect(surf, C_PANEL, panel)
        pygame.draw.line(surf, C_BORDER, (ox, 0), (ox, panel_h), 2)

        surf.set_clip(pygame.Rect(ox, 0, PANEL_W, panel_h - 2))

        y = 10
        def header(text, col=C_TEXT):
            nonlocal y
            # subtle background bar for headers
            pygame.draw.rect(surf, (25, 32, 55), (ox + 4, y - 2, PANEL_W - 8, 22))
            t = FONT_MED.render(text, True, col)
            surf.blit(t, (ox + 10, y))
            y += 26

        def row(label, val, col=C_TEXT):
            nonlocal y
            t1 = FONT_SMALL.render(label, True, C_DIM)
            t2 = FONT_SMALL.render(str(val), True, col)
            surf.blit(t1, (ox + 10, y))
            surf.blit(t2, (ox + 112, y))
            y += 17

        def divider():
            nonlocal y
            pygame.draw.line(surf, C_BORDER, (ox+6, y+3), (ox+PANEL_W-6, y+3), 1)
            y += 10

        # ── Stats ─────────────────────────────────────────────────────────────
        header("WUMPUS WORLD", C_GOLD)
        divider()
        row("Score:",   self.score,  C_GREEN if self.score >= 0 else C_RED)
        row("Best:",    self.high_score, C_GOLD)
        row("Arrows:",  str(self.arrows) + " left", C_ORANGE)
        row("Gold:",    "CARRYING!" if self.has_gold else "not found",
                        C_GOLD if self.has_gold else C_DIM)
        row("Wumpus:",  "DEAD" if self.wumpus_dead else "ALIVE",
                        C_GREEN if self.wumpus_dead else C_RED)
        row("Pos:",     f"({self.player[0]},{self.player[1]})", C_CYAN)
        row("Visited:", f"{len(self.kb.visited)}/{GRID_SIZE**2}", C_TEXT)

        # ── AI ────────────────────────────────────────────────────────────────
        divider()
        ai_col = C_GREEN if self.ai_mode else C_DIM
        header("AI SOLVER  " + ("ON " if self.ai_mode else "OFF  [TAB]"), ai_col)
        if self.kb.wumpus_loc:
            row("W-loc:", str(self.kb.wumpus_loc), C_RED)

        # ── Log ───────────────────────────────────────────────────────────────
        divider()
        header("LOG", C_DIM)
        for msg in self.log[-5:]:
            t = FONT_SMALL.render(msg[:34], True, C_TEXT)
            surf.blit(t, (ox + 8, y))
            y += 15

        # ── Legend ────────────────────────────────────────────────────────────
        divider()
        header("LEGEND", C_DIM)
        legend = [
            ((200, 50,  50),  "Wumpus  (red circle)"),
            ((100, 60, 210),  "Pit     (dark vortex)"),
            ((230, 200, 20),  "Gold    (yellow star)"),
            ((50,  210, 240), "Breeze  (cyan waves)"),
            ((70,  230, 70),  "Stench  (green blobs)"),
            ((60,  220, 100), "Safe    (green check)"),
        ]
        for dot_col, txt in legend:
            pygame.draw.circle(surf, dot_col, (ox + 16, y + 7), 6)
            t3 = FONT_SMALL.render(txt, True, C_TEXT)
            surf.blit(t3, (ox + 28, y))
            y += 15

        # ── Controls ──────────────────────────────────────────────────────────
        divider()
        header("CONTROLS", C_TEXT)
        controls = [
            ("WASD/Arrows", "Move"),
            ("G",           "Grab gold"),
            ("E",           "Escape cave"),
            ("F + Arrow",   "Shoot arrow"),
            ("TAB",         "Toggle AI"),
            ("R",           "New game"),
            ("ESC",         "Menu"),
        ]
        for key, act in controls:
            t1 = FONT_SMALL.render(f"[{key}]", True, C_ORANGE)
            t2 = FONT_SMALL.render(act,        True, C_TEXT)
            surf.blit(t1, (ox + 8,  y))
            surf.blit(t2, (ox + 118, y))
            y += 15

        surf.set_clip(None)

    def draw_overlay(self, surf):
        if self.state == STATE_WIN:
            self._draw_endscreen(surf, "  VICTORY  ", C_GOLD,
                                 f"Score: {self.score}  |  Best: {self.high_score}",
                                 "Press R to play again")
        elif self.state == STATE_DEAD:
            self._draw_endscreen(surf, "  YOU DIED  ", C_RED,
                                 f"Score: {self.score}  |  Best: {self.high_score}",
                                 "Press R to try again")

    def _draw_endscreen(self, surf, title, col, sub, hint):
        # Draw the result banner inside the right panel — grid stays fully visible
        px = GRID_SIZE * CELL_SIZE   # left edge of panel
        pw = PANEL_W
        ph = HEIGHT

        # Redraw panel background so it sits on top of normal panel content
        pygame.draw.rect(surf, C_PANEL, (px, 0, pw, ph))
        pygame.draw.line(surf, C_BORDER, (px, 0), (px, ph), 2)

        cx = px + pw // 2
        y  = 30

        # Pulsing title bar
        pulse = 0.7 + 0.3 * abs(math.sin(time.time() * 3))
        r0, g0, b0 = col
        glow_col = (int(r0*pulse), int(g0*pulse), int(b0*pulse))
        bar_rect = pygame.Rect(px + 8, y, pw - 16, 52)
        pygame.draw.rect(surf, (20, 24, 44), bar_rect, border_radius=8)
        pygame.draw.rect(surf, glow_col, bar_rect, 3, border_radius=8)

        t1 = FONT_TITLE.render(title.strip(), True, col)
        surf.blit(t1, (cx - t1.get_width()//2, y + 10))
        y += 70

        # Divider
        pygame.draw.line(surf, col, (px + 16, y), (px + pw - 16, y), 1)
        y += 14

        # Score lines
        for line, line_col in [(sub, C_TEXT), (hint, C_DIM)]:
            t = FONT_MED.render(line, True, line_col)
            # word-wrap if too wide
            if t.get_width() > pw - 20:
                # split on |
                parts = [p.strip() for p in line.split("|")]
                for p in parts:
                    tp = FONT_MED.render(p, True, line_col)
                    surf.blit(tp, (cx - tp.get_width()//2, y))
                    y += 24
            else:
                surf.blit(t, (cx - t.get_width()//2, y))
                y += 28
        y += 10

        # Divider
        pygame.draw.line(surf, C_BORDER, (px + 16, y), (px + pw - 16, y), 1)
        y += 16

        # Keyboard hints
        keys = [("[R]", "New game"), ("[ESC]", "Menu")]
        for key, act in keys:
            tk = FONT_SMALL.render(key, True, C_ORANGE)
            ta = FONT_SMALL.render(act, True, C_TEXT)
            surf.blit(tk, (px + 16, y))
            surf.blit(ta, (px + 16 + tk.get_width() + 10, y))
            y += 20

        y += 10
        pygame.draw.line(surf, C_BORDER, (px + 16, y), (px + pw - 16, y), 1)
        y += 14

        # Show revealed grid legend note
        note = FONT_SMALL.render("Full grid revealed!", True, C_CYAN)
        surf.blit(note, (cx - note.get_width()//2, y))
        y += 20
        note2 = FONT_SMALL.render("Review the board above.", True, C_DIM)
        surf.blit(note2, (cx - note2.get_width()//2, y))

    def draw_menu(self, surf):
        surf.fill(C_BG)
        cx = WIDTH // 2
        t = time.time()

        title_str = "WUMPUS WORLD"
        total_w   = len(title_str) * 30
        start_x   = cx - total_w // 2
        for i, ch in enumerate(title_str):
            y_off = int(math.sin(t * 2 + i * 0.5) * 6)
            col = [C_GOLD, C_RED, C_ORANGE][i % 3]
            letter = FONT_TITLE.render(ch, True, col)
            surf.blit(letter, (start_x + i * 30, 100 + y_off))

        lines = [
            ("Hunt the Wumpus. Grab the gold. Escape alive.", C_TEXT,  FONT_MED,   185),
            ("",                                               C_DIM,   FONT_MED,   205),
            ("You are an adventurer in a dark cave.",          C_DIM,   FONT_SMALL, 225),
            ("Sense breezes (pits nearby) and stenches",       C_DIM,   FONT_SMALL, 243),
            ("(Wumpus nearby). Use logic to survive.",         C_DIM,   FONT_SMALL, 261),
            ("",                                               C_DIM,   FONT_MED,   280),
            ("Press  ENTER  to start",                         C_GREEN, FONT_BIG,   320),
        ]
        for text, col, font, y in lines:
            t2 = font.render(text, True, col)
            surf.blit(t2, (cx - t2.get_width()//2, y))

        # best score on menu
        if self.high_score > 0:
            hs = FONT_MED.render(f"Best score: {self.high_score}", True, C_GOLD)
            surf.blit(hs, (cx - hs.get_width()//2, 370))

        for i in range(4):
            for j in range(4):
                col2 = C_CELL_DARK if (i+j)%2==0 else C_CELL_MID
                pygame.draw.rect(surf, col2, (cx + 180 + j*20, 200 + i*20, 19, 19))
        pygame.draw.circle(surf, C_PLAYER, (cx + 190, 278), 7)

    def draw(self):
        if self.state == STATE_MENU:
            self.draw_menu(self.screen)
            self.ps.update_draw(self.screen)
            pygame.display.flip()
            return

        ox, oy = 0, 0
        if self.shake_timer > 0:
            ox = random.randint(-4, 4)
            oy = random.randint(-4, 4)

        self.screen.fill(C_BG)

        if self.flash_timer > 0 and self.flash_color:
            alpha = int(self.flash_timer / 45 * 100)
            fl = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fl.fill((*self.flash_color, alpha))
            self.screen.blit(fl, (0, 0))

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                self.draw_cell(self.screen, r, c, ox, oy)

        self.draw_player(self.screen, ox, oy)

        gw = GRID_SIZE * CELL_SIZE
        pygame.draw.rect(self.screen, C_BORDER, (ox, oy, gw, gw), 2)

        self.draw_panel(self.screen)
        self.ps.update_draw(self.screen)
        self.draw_overlay(self.screen)
        pygame.display.flip()

    def handle_shoot_key(self, key):
        dirs = {
            pygame.K_UP:    (-1, 0),
            pygame.K_DOWN:  ( 1, 0),
            pygame.K_LEFT:  ( 0,-1),
            pygame.K_RIGHT: ( 0, 1),
        }
        if key in dirs:
            self.shoot(*dirs[key])

    def run(self):
        self.shooting_mode = False

        while True:
            dt = self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()

                elif event.type == pygame.KEYDOWN:
                    key = event.key

                    if self.state == STATE_MENU:
                        if key == pygame.K_RETURN:
                            play_snd(SND_CLICK)
                            self._new_game()

                    elif self.state in (STATE_WIN, STATE_DEAD):
                        if key == pygame.K_r:
                            play_snd(SND_CLICK)
                            self._new_game()
                        elif key == pygame.K_ESCAPE:
                            self.state = STATE_MENU

                    elif self.state == STATE_PLAY:
                        if key == pygame.K_r:
                            play_snd(SND_CLICK)
                            self._new_game()
                        elif key == pygame.K_ESCAPE:
                            self.state = STATE_MENU
                            self.shooting_mode = False
                        elif key == pygame.K_TAB:
                            self.ai_mode = not self.ai_mode
                            play_snd(SND_CLICK)
                            self._log(f"🤖 AI {'enabled' if self.ai_mode else 'disabled'}")
                        elif key == pygame.K_g:
                            self.grab_gold()
                        elif key == pygame.K_e:
                            self.climb_out()
                        elif key == pygame.K_f:
                            self.shooting_mode = True
                            self._log("🏹 Aim! Press arrow key to shoot.")
                        elif self.shooting_mode:
                            self.handle_shoot_key(key)
                            self.shooting_mode = False
                        else:
                            move_map = {
                                pygame.K_w: (-1, 0), pygame.K_UP:    (-1, 0),
                                pygame.K_s: ( 1, 0), pygame.K_DOWN:  ( 1, 0),
                                pygame.K_a: ( 0,-1), pygame.K_LEFT:  ( 0,-1),
                                pygame.K_d: ( 0, 1), pygame.K_RIGHT: ( 0, 1),
                            }
                            if key in move_map:
                                self.move(*move_map[key])

            self.update(dt)
            self.draw()


if __name__ == "__main__":
    WumpusGame().run()