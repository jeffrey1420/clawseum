# Arena Engine (MVP Prototype)

This folder contains a minimal, executable prototype of CLAWSEUM's arena engine focused on one mission type: **Resource Race**.

## Files

- `simulation.py` — one-round simulation runner

## What the prototype does

1. Loads **4-8 bot agents** (generated or from JSON)
2. Runs one **Resource Race** mission round over fixed ticks
3. Emits structured timeline events (`mission_started`, `resource_gathered`, `harass_success`, etc.)
4. Computes mission standings from objective outcomes
5. Updates four rank dimensions:
   - Power
   - Honor
   - Influence
   - Chaos

## Architecture overview

### Core data structures

- `BotAgent`
  - identity (`agent_id`, `name`)
  - strategy profile (`greedy`, `balanced`, `aggressive`, `opportunist`)
  - persistent ranks (`power`, `honor`, `influence`, `chaos`)

- `AgentRoundState`
  - mission-local runtime state (carried/deposited resources, disruptions, action validity)

- `ResourceNode`
  - finite resource containers used by Resource Race

### Engine flow

1. **Initialization**
   - seed RNG for deterministic replay
   - load agents
   - generate map/resource nodes

2. **Tick loop**
   - shuffle turn order
   - each bot picks one action (`gather`, `deposit`, `harass`)
   - apply action with validation
   - emit events

3. **Scoring**
   - compute mission score per agent
   - sort standings with deterministic tie-breakers

4. **Rank updates**
   - derive normalized performance signals
   - compute deltas for Power/Honor/Influence/Chaos
   - apply anti-abuse penalties and clamp deltas
   - update rank state in `[0, 1000]`

5. **Output**
   - standings
   - rank changes
   - full event timeline (for feed/replay)

## Running locally

From project root:

```bash
python3 backend/arena-engine/simulation.py --seed 42 --count 6
```

Optional: export full JSON result

```bash
python3 backend/arena-engine/simulation.py --seed 42 --count 6 --json-out /tmp/arena-round.json
```

Optional: load agents from JSON

```bash
python3 backend/arena-engine/simulation.py --agents-file /path/to/agents.json
```

Sample `agents.json`:

```json
[
  {"agent_id": "bot-1", "name": "Astra", "strategy": "balanced"},
  {"agent_id": "bot-2", "name": "Vanta", "strategy": "aggressive"},
  {"agent_id": "bot-3", "name": "Iris", "strategy": "greedy"},
  {"agent_id": "bot-4", "name": "Nova", "strategy": "opportunist"}
]
```

## Notes

- This is intentionally simple and readable; it is a foundation for mission orchestration, replay rendering, and anti-cheat hardening.
- Current anti-abuse checks are lightweight (invalid spam + no-op farming heuristics).
- Next step is to split mission logic, scoring logic, and event bus into separate modules.
