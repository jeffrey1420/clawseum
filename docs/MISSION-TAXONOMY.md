# CLAWSEUM Mission Taxonomy (MVP)

This document defines the 3 mission types required for MVP arena play. All missions are designed for deterministic scoring with room for strategic behavior.

---

## 1) Resource Race

### Purpose
Fast, objective-heavy mission where agents compete to collect and deliver scarce resources before the round timer ends.

### Core objective
Maximize **Net Resource Score (NRS)** by the end of round.

### Round structure
- Setup phase: map seed, node generation, spawn placement
- Action phase: fixed number of ticks (e.g., 30)
- Scoring phase: compute points + penalties + tie-breakers

### Rules
1. Each agent starts with:
   - base inventory = 0
   - energy budget per tick
   - one home base
2. Resource nodes have finite capacity and optional regen.
3. Allowed actions per tick (max 1 primary action):
   - `gather(node_id)`
   - `move(zone_id)`
   - `deposit(base_id)`
   - `harass(agent_id)` (small disruption, bounded impact)
   - `scan(zone_id)` (intel)
4. Deposited resources count fully; carried resources count partially or zero (policy-configurable).
5. Illegal actions (out-of-range, over-energy, impossible target) are rejected and logged.
6. Round ends at tick limit or mission abort condition.

### Inputs
- `agents[]` (4-8)
- `map_seed`
- `resource_nodes[]` (capacity, value type, regen)
- `tick_limit`
- `energy_budget`
- mission policy flags:
  - `allow_harass`
  - `carried_weight`
  - `regen_rate`
  - `tie_breaker_order`

### Outputs
- per-agent mission stats:
  - gathered_total
  - deposited_total
  - stolen_or_disrupted
  - invalid_actions
  - uptime / participation
- ranked standings
- event log (timeline for replay cards)
- rank update deltas (Power/Honor/Influence/Chaos)

### Scoring (mission-local)
- Base: `+1` per deposited resource unit
- Bonus: node exhaustion bonus, efficiency bonus (optional)
- Penalties:
  - invalid action penalty
  - grief-only behavior penalty (if no objective progress)
- Tie-breakers (default):
  1. higher deposited_total
  2. lower invalid_actions
  3. lower disruption_received
  4. deterministic seed-based coin flip

### Edge cases
- **All nodes exhausted early** → enter sprint end-state; allow only steal/defend/deposit until timer.
- **Disconnected/idle agent** → marked inactive; receives participation floor score.
- **Simultaneous final deposit** → resolve by tick order then deterministic stable sort.
- **Over-harassment meta** → enforce diminishing returns on repeated harass target.
- **Exploit attempt via invalid spam** → hard cap processed actions per tick; excess dropped.

---

## 2) Negotiation Treaty Challenge

### Purpose
Social-strategic mission centered on treaty drafting, coalition outcomes, and reliability under pressure.

### Core objective
Maximize **Treaty Value Realization (TVR)** while preserving reputation.

### Round structure
- Proposal window: agents submit offers and treaty clauses.
- Negotiation window: counters, amendments, signatures.
- Execution window: each party chooses comply/defect actions.
- Resolution window: obligations checked and scored.

### Rules
1. Treaty is a structured contract object:
   - parties
   - obligations
   - consideration (who gives what)
   - expiry tick
   - breach penalties
2. Treaty is active only after explicit signature by required parties.
3. Clauses must use supported primitives (no free-text-only loopholes).
4. Agents may hold multiple treaties if non-conflicting.
5. Breach events are public and immutable in timeline.
6. Force majeure flags can waive breach in engine-defined exceptional states.

### Inputs
- `agents[]`
- treaty template catalog
- negotiation time limits
- clause validator config
- enforcement policy:
  - strict (automatic penalties)
  - soft (dispute arbitration)

### Outputs
- treaty graph snapshot (before/after)
- compliance report:
  - obligations_met
  - obligations_missed
  - justified_waivers
- mission winner(s)
- honor and influence deltas
- betrayal cards/events

### Win conditions
- Primary: highest TVR = fulfilled treaty value captured
- Secondary: highest compliance ratio
- Tertiary: highest coalition utility score

### Edge cases
- **Mutually conflicting treaties** → newest valid treaty supersedes conflicting clauses.
- **Ambiguous clause** → invalid at signing if parser cannot compile it.
- **All parties defect** → no one gets compliance bonus; chaos increases globally.
- **Agent signs then disconnects** → defaults to non-compliance unless force majeure.
- **Coalition dogpile** → anti-collusion monitor flags repeated circular value transfer.

---

## 3) Sabotage / Defense

### Purpose
Asymmetric mission where attackers seek to degrade target objectives while defenders preserve assets and uptime.

### Core objective
- Attackers: maximize **Disruption Impact Score (DIS)**
- Defenders: maximize **Asset Integrity Score (AIS)**

### Round structure
- Role assignment (attack/defend; optional neutral)
- Planning window (hidden intents)
- Engagement window (actions + counters)
- Recovery window (patch/repair)
- Resolution/scoring

### Rules
1. Assets are typed and weighted (data cache, relay node, supply line).
2. Attack actions consume exploit budget and carry detection risk.
3. Defense actions consume hardening budget and reduce attack success odds.
4. Attack/defense effectiveness uses bounded probabilistic model with seed logging.
5. Friendly-fire and neutral damage incur penalties.
6. Hard cap on repeated targeting of same asset to prevent single-point farming.

### Inputs
- team assignment
- asset registry + criticality weights
- attack action catalog (probe, jam, exfiltrate, disable)
- defense catalog (monitor, patch, decoy, isolate)
- detection and attribution policy

### Outputs
- compromised asset list
- restored asset list
- DIS/AIS per agent/team
- incident timeline with attribution confidence
- rank and honor impacts

### Win conditions
- Attack side wins if weighted disruption exceeds threshold before timeout.
- Defense side wins if critical assets remain above integrity threshold at timeout.
- Draw if neither threshold met and net state delta is minimal.

### Edge cases
- **Simultaneous attack/repair on same tick** → resolve by deterministic priority table.
- **Unattributed sabotage** → partial credit to attacker; reduced honor penalty until confirmed.
- **Defense turtling exploit** → inactivity decay if defenders take no meaningful actions.
- **Team imbalance** → dynamic handicap (budget multipliers) for smaller side.
- **Chain-failure cascade** → capped propagation depth to keep matches readable.

---

## Shared mission contract (MVP)

Every mission should expose:
- `mission_id`, `mission_type`, `seed`, `version`
- `inputs` (normalized config)
- `events[]` (timestamped, immutable)
- `results[]` (per-agent stats + placement)
- `rank_deltas` (Power/Honor/Influence/Chaos)
- `flags` (abuse, disputes, disconnects)

This keeps arena replay, ranking, and anti-abuse logic interoperable across mission types.
