# Wumpus World

A Python desktop game and AI demonstration built with Pygame, implementing propositional logic, Horn clause inference, and an intelligent agent that reasons under uncertainty — based on the classic Wumpus World problem from Russell & Norvig's Artificial Intelligence: A Modern Approach.

---

## Overview

Wumpus World is a grid-based cave exploration game where a player (or AI agent) must navigate a 6×6 grid filled with hidden dangers. The agent perceives its environment through sensory cues only — it cannot see into unexplored cells. Using those percepts, the Knowledge Base builds a logical model of the world and decides the safest actions to take.

This project implements:
- A fully playable game with manual controls
- A propositional logic Knowledge Base with fixpoint inference
- A goal-directed AI solver that reasons about danger and navigates safely

---

## The Wumpus World Problem

The Wumpus World is a standard benchmark problem in AI for demonstrating logical reasoning under uncertainty. The environment is defined as follows:

| Element | Description |
|---------|-------------|
| **Grid** | 6×6 cave cells, each potentially containing a hazard |
| **Wumpus** | A deadly monster hiding in one cell. Adjacent cells emit a **stench** |
| **Pits** | Bottomless pits scattered across the grid. Adjacent cells emit a **breeze** |
| **Gold** | A treasure in one cell (never inside a pit). The goal is to collect it and escape |
| **Agent** | Starts at bottom-left `(5,0)`. Has one arrow to shoot the Wumpus |

The agent must use logical inference from breeze and stench percepts to deduce which cells are safe — it cannot directly observe pits, the Wumpus, or gold until it steps into a cell.

---

## Knowledge Base & Inference Engine

The core of the AI is the `KnowledgeBase` class, which stores all logical facts and applies propositional inference rules to a fixpoint (i.e. rules are re-applied repeatedly until no new facts can be derived).

### Inference Rules

| Rule | Description |
|------|-------------|
| **R1** | `visited(r,c) ∧ ¬breeze(r,c)` → all neighbours are pit-free |
| **R2** | `visited(r,c) ∧ ¬stench(r,c)` → all neighbours are Wumpus-free |
| **R3** | `no_pit(r,c) ∧ no_wumpus(r,c)` → cell is **safe** |
| **R4** | `breeze(r,c)` with exactly one unproven neighbour → that neighbour **contains a pit** (confirmed) |
| **R5** | `stench(r,c)` with exactly one unproven neighbour → that neighbour **contains the Wumpus** |
| **R6** | Intersection of all stench-adjacent candidate sets of size 1 → Wumpus location confirmed |
| **R7** | Once Wumpus location is confirmed → all other cells are marked Wumpus-free |
| **R8** | Arrow miss → entire line of fire marked Wumpus-free, then re-infer |
| **R9** | Wumpus killed → re-infer safety of all previously stench-blocked cells |

### Data Structures

```
visited      — set of cells the agent has stepped into
safe         — set of cells proven safe (no pit, no live Wumpus)
no_pit       — set of cells proven pit-free
no_wump      — set of cells proven Wumpus-free
pit_confirmed — set of cells proven to contain a pit
wumpus_loc   — confirmed Wumpus coordinates (or None)
frontier     — unvisited cells adjacent to visited cells
pit_prob     — heuristic danger score for unproven cells (0.0–1.0)
wumpus_prob  — heuristic Wumpus likelihood for unproven cells (0.0–1.0)
```

---

## AI Solver

The AI solver (`ai_step`) follows a strict 8-level priority plan each turn:

1. **Grab gold** — if standing on it
2. **Climb out** — if carrying gold and at the start cell
3. **Shoot** — if Wumpus location is confirmed and in the current line of fire
4. **Return home** — navigate back to start via safe cells if carrying gold
5. **Safe exploration** — BFS to the nearest safe unvisited cell
6. **Shoot positioning** — navigate to a cell that shares a row or column with the confirmed Wumpus
7. **Cautious frontier step** — move to the lowest-danger unproven cell (never a confirmed pit or Wumpus)
8. **Last resort** — unsafe path to start if carrying gold and all safe routes are exhausted

The AI never steps onto a confirmed pit or a confirmed live Wumpus cell.

---

## Scoring

| Event | Score |
|-------|-------|
| Each step taken | −1 |
| Firing an arrow | −10 |
| Killing the Wumpus | +500 |
| Collecting the gold | +1,000 |
| Escaping with gold | +500 |
| Falling into a pit | −1,000 |
| Being eaten by the Wumpus | −1,000 |

The best score is saved to `wumpus_highscore.json` and persists across sessions.

---

## Controls

| Key | Action |
|-----|--------|
| `W A S D` or Arrow Keys | Move |
| `G` | Grab gold (when standing on it) |
| `E` | Climb out (when at start cell) |
| `F` then Arrow Key | Fire arrow in a direction |
| `TAB` | Toggle AI solver on/off |
| `R` | Start a new game |
| `ESC` | Return to main menu |

---

## Visual Guide

| Colour / Symbol | Meaning |
|-----------------|---------|
| 🔵 Blue circle | Player |
| 🔴 Red circle with fangs | Wumpus |
| 🌀 Dark purple vortex | Pit |
| ⭐ Yellow star | Gold |
| 〰️ Cyan waves | Breeze (pit nearby) |
| 🟢 Green blobs | Stench (Wumpus nearby) |
| ✓ Green check | Safe cell (no percepts) |
| Red heat overlay | Danger probability heatmap |
| Left bar (red) | Wumpus probability indicator |
| Right bar (blue) | Pit probability indicator |

---

## Requirements

- Python 3.7+
- Pygame

```bash
pip install pygame
```

---

## Running the Game

```bash
python wumpus_world.py
```

The game window is 820×600 pixels. Font rendering uses DejaVu Sans Mono (bundled with most Linux systems) with fallbacks for Windows and macOS.

---

## File Structure

```
wumpus_world.py          # Main application (single file)
wumpus_highscore.json    # Auto-created on first win, stores best score
README.md                # This file
```

---

## Academic Context

This project was developed as a practical demonstration of:

- **Knowledge Representation** — propositional logic facts stored in a KB
- **Logical Inference** — Horn clause forward chaining to fixpoint
- **Reasoning Under Uncertainty** — heuristic danger scoring for unproven cells
- **Intelligent Agent Design** — goal-directed planning with prioritised actions
- **The Wumpus World Problem** — as defined in Chapter 7 of *Artificial Intelligence: A Modern Approach* (Russell & Norvig)
