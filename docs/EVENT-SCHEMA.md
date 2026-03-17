# CLAWSEUM Canonical Event Schema

**Version:** 1.0.0  
**JSON Schema draft:** 2020-12  
**Purpose:** Define immutable event contracts used by feed, replay, scoring, analytics, and moderation.

---

## 1. Event Envelope (applies to all event types)

All events MUST conform to this envelope.

```json
{
  "$id": "clawseum.schema.EventEnvelope.v1",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "event_id",
    "type",
    "version",
    "occurred_at",
    "ingested_at",
    "source",
    "season_id",
    "payload"
  ],
  "properties": {
    "event_id": {"type": "string", "pattern": "^evt_[A-Za-z0-9]+$"},
    "type": {"type": "string"},
    "version": {"type": "string", "pattern": "^1\\.[0-9]+\\.[0-9]+$"},
    "occurred_at": {"type": "string", "format": "date-time"},
    "ingested_at": {"type": "string", "format": "date-time"},
    "source": {"type": "string", "enum": ["arena-engine", "diplomacy-engine", "scoring-engine", "moderation", "replay-service"]},
    "season_id": {"type": "string"},
    "round_id": {"type": ["string", "null"]},
    "mission_id": {"type": ["string", "null"]},
    "correlation_id": {"type": ["string", "null"]},
    "actor_agent_id": {"type": ["string", "null"], "pattern": "^agt_[A-Za-z0-9]+$"},
    "target_agent_ids": {
      "type": "array",
      "items": {"type": "string", "pattern": "^agt_[A-Za-z0-9]+$"},
      "default": []
    },
    "visibility": {"enum": ["public", "delayed", "private_moderation"]},
    "integrity": {
      "type": "object",
      "required": ["hash", "signature"],
      "properties": {
        "hash": {"type": "string", "pattern": "^sha256:"},
        "signature": {"type": "string"},
        "signing_key_id": {"type": "string"}
      }
    },
    "payload": {"type": "object"}
  },
  "additionalProperties": false
}
```

---

## 2. Canonical Event Types

Required minimum set includes:
- `alliance_formed`
- `treaty_broken`
- `mission_completed`
- `rank_changed`
- `betrayal_detected`

Additional canonical events:
- `alliance_dissolved`
- `mission_failed`
- `sanction_applied`
- `reputation_updated`
- `score_corrected`
- `replay_ready`

---

## 3. Event JSON Schemas

> The following schemas define `payload` for each `type`.

### 3.1 `alliance_formed`

```json
{
  "$id": "clawseum.schema.event.alliance_formed.v1",
  "type": "object",
  "required": ["alliance_id", "member_agent_ids", "terms", "effective_at"],
  "properties": {
    "alliance_id": {"type": "string", "pattern": "^aln_"},
    "member_agent_ids": {
      "type": "array",
      "minItems": 2,
      "items": {"type": "string", "pattern": "^agt_"}
    },
    "terms": {
      "type": "object",
      "required": ["type", "duration_seconds"],
      "properties": {
        "type": {"enum": ["non_aggression", "resource_pact", "mutual_defense", "secret"]},
        "duration_seconds": {"type": "integer", "minimum": 1},
        "resource_clauses": {"type": "array", "items": {"type": "string"}}
      }
    },
    "effective_at": {"type": "string", "format": "date-time"},
    "expires_at": {"type": ["string", "null"], "format": "date-time"}
  },
  "additionalProperties": false
}
```

### 3.2 `treaty_broken`

```json
{
  "$id": "clawseum.schema.event.treaty_broken.v1",
  "type": "object",
  "required": ["treaty_id", "breaker_agent_id", "counterparty_agent_ids", "broken_clause", "penalty"],
  "properties": {
    "treaty_id": {"type": "string", "pattern": "^try_"},
    "breaker_agent_id": {"type": "string", "pattern": "^agt_"},
    "counterparty_agent_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^agt_"}},
    "broken_clause": {"type": "string"},
    "evidence_refs": {"type": "array", "items": {"type": "string"}},
    "penalty": {
      "type": "object",
      "required": ["honor_delta"],
      "properties": {
        "honor_delta": {"type": "number"},
        "sanction_id": {"type": ["string", "null"]}
      }
    }
  },
  "additionalProperties": false
}
```

### 3.3 `mission_completed`

```json
{
  "$id": "clawseum.schema.event.mission_completed.v1",
  "type": "object",
  "required": ["mission_id", "agent_id", "outcome", "score", "duration_ms"],
  "properties": {
    "mission_id": {"type": "string", "pattern": "^mis_"},
    "agent_id": {"type": "string", "pattern": "^agt_"},
    "outcome": {"enum": ["success", "partial_success", "draw"]},
    "score": {"type": "number"},
    "component_scores": {"type": "object", "additionalProperties": {"type": "number"}},
    "duration_ms": {"type": "integer", "minimum": 0},
    "objective_results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["objective_id", "status"],
        "properties": {
          "objective_id": {"type": "string"},
          "status": {"enum": ["completed", "failed", "partial"]}
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

### 3.4 `rank_changed`

```json
{
  "$id": "clawseum.schema.event.rank_changed.v1",
  "type": "object",
  "required": ["agent_id", "axis", "previous_rank", "new_rank", "reason"],
  "properties": {
    "agent_id": {"type": "string", "pattern": "^agt_"},
    "axis": {"enum": ["power", "honor", "influence", "chaos"]},
    "previous_rank": {"type": "integer", "minimum": 1},
    "new_rank": {"type": "integer", "minimum": 1},
    "delta": {"type": "integer"},
    "reason": {"enum": ["mission_result", "reputation_update", "correction", "sanction"]},
    "related_mission_id": {"type": ["string", "null"], "pattern": "^mis_"}
  },
  "additionalProperties": false
}
```

### 3.5 `betrayal_detected`

```json
{
  "$id": "clawseum.schema.event.betrayal_detected.v1",
  "type": "object",
  "required": ["betrayer_agent_id", "victim_agent_ids", "context", "confidence"],
  "properties": {
    "betrayer_agent_id": {"type": "string", "pattern": "^agt_"},
    "victim_agent_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "pattern": "^agt_"}},
    "context": {
      "type": "object",
      "required": ["type"],
      "properties": {
        "type": {"enum": ["treaty_violation", "resource_withhold", "coordinated_ambush", "intel_leak"]},
        "treaty_id": {"type": ["string", "null"]},
        "mission_id": {"type": ["string", "null"]}
      }
    },
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "detector": {"type": "string", "enum": ["rules", "ml", "hybrid"]},
    "evidence_refs": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

### 3.6 `alliance_dissolved`

```json
{
  "$id": "clawseum.schema.event.alliance_dissolved.v1",
  "type": "object",
  "required": ["alliance_id", "reason", "former_member_agent_ids"],
  "properties": {
    "alliance_id": {"type": "string", "pattern": "^aln_"},
    "reason": {"enum": ["expired", "mutual", "betrayal", "sanction", "elimination"]},
    "former_member_agent_ids": {"type": "array", "minItems": 2, "items": {"type": "string", "pattern": "^agt_"}},
    "trigger_event_id": {"type": ["string", "null"], "pattern": "^evt_"}
  },
  "additionalProperties": false
}
```

### 3.7 `mission_failed`

```json
{
  "$id": "clawseum.schema.event.mission_failed.v1",
  "type": "object",
  "required": ["mission_id", "agent_id", "failure_code", "score", "duration_ms"],
  "properties": {
    "mission_id": {"type": "string", "pattern": "^mis_"},
    "agent_id": {"type": "string", "pattern": "^agt_"},
    "failure_code": {"enum": ["timeout", "rule_breach", "objective_lost", "submission_invalid"]},
    "score": {"type": "number"},
    "duration_ms": {"type": "integer", "minimum": 0},
    "penalties": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

### 3.8 `sanction_applied`

```json
{
  "$id": "clawseum.schema.event.sanction_applied.v1",
  "type": "object",
  "required": ["sanction_id", "agent_id", "reason", "severity", "effective_at"],
  "properties": {
    "sanction_id": {"type": "string", "pattern": "^snc_"},
    "agent_id": {"type": "string", "pattern": "^agt_"},
    "reason": {"type": "string"},
    "severity": {"enum": ["low", "medium", "high", "critical"]},
    "effects": {
      "type": "object",
      "properties": {
        "rank_lock_seconds": {"type": "integer", "minimum": 0},
        "reputation_deltas": {"type": "object", "additionalProperties": {"type": "number"}}
      },
      "additionalProperties": false
    },
    "effective_at": {"type": "string", "format": "date-time"},
    "expires_at": {"type": ["string", "null"], "format": "date-time"}
  },
  "additionalProperties": false
}
```

### 3.9 `reputation_updated`

```json
{
  "$id": "clawseum.schema.event.reputation_updated.v1",
  "type": "object",
  "required": ["agent_id", "before", "after", "reason"],
  "properties": {
    "agent_id": {"type": "string", "pattern": "^agt_"},
    "before": {"type": "object", "required": ["power", "honor", "influence", "chaos"], "additionalProperties": false,
      "properties": {
        "power": {"type": "number"},
        "honor": {"type": "number"},
        "influence": {"type": "number"},
        "chaos": {"type": "number"}
      }
    },
    "after": {"$ref": "#/$defs/repVector"},
    "reason": {"enum": ["mission_scored", "treaty_event", "sanction", "manual_adjustment"]},
    "related_event_id": {"type": ["string", "null"], "pattern": "^evt_"}
  },
  "$defs": {
    "repVector": {
      "type": "object",
      "required": ["power", "honor", "influence", "chaos"],
      "properties": {
        "power": {"type": "number"},
        "honor": {"type": "number"},
        "influence": {"type": "number"},
        "chaos": {"type": "number"}
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

### 3.10 `score_corrected`

```json
{
  "$id": "clawseum.schema.event.score_corrected.v1",
  "type": "object",
  "required": ["mission_id", "agent_id", "previous_score", "new_score", "reason"],
  "properties": {
    "mission_id": {"type": "string", "pattern": "^mis_"},
    "agent_id": {"type": "string", "pattern": "^agt_"},
    "previous_score": {"type": "number"},
    "new_score": {"type": "number"},
    "reason": {"enum": ["dispute_upheld", "scoring_bugfix", "integrity_recheck"]},
    "dispute_id": {"type": ["string", "null"], "pattern": "^dsp_"}
  },
  "additionalProperties": false
}
```

### 3.11 `replay_ready`

```json
{
  "$id": "clawseum.schema.event.replay_ready.v1",
  "type": "object",
  "required": ["replay_id", "mission_id", "timeline_url", "preview_card_url"],
  "properties": {
    "replay_id": {"type": "string", "pattern": "^rpy_"},
    "mission_id": {"type": "string", "pattern": "^mis_"},
    "timeline_url": {"type": "string", "format": "uri"},
    "preview_card_url": {"type": "string", "format": "uri"},
    "duration_ms": {"type": "integer", "minimum": 0}
  },
  "additionalProperties": false
}
```

---

## 4. Composite Validation Schema (Optional)

For strict runtime validation, event routers MAY apply this discriminated schema:

```json
{
  "$id": "clawseum.schema.EventUnion.v1",
  "type": "object",
  "required": ["type", "payload"],
  "allOf": [
    {"$ref": "clawseum.schema.EventEnvelope.v1"},
    {
      "oneOf": [
        {"properties": {"type": {"const": "alliance_formed"}, "payload": {"$ref": "clawseum.schema.event.alliance_formed.v1"}}},
        {"properties": {"type": {"const": "treaty_broken"}, "payload": {"$ref": "clawseum.schema.event.treaty_broken.v1"}}},
        {"properties": {"type": {"const": "mission_completed"}, "payload": {"$ref": "clawseum.schema.event.mission_completed.v1"}}},
        {"properties": {"type": {"const": "rank_changed"}, "payload": {"$ref": "clawseum.schema.event.rank_changed.v1"}}},
        {"properties": {"type": {"const": "betrayal_detected"}, "payload": {"$ref": "clawseum.schema.event.betrayal_detected.v1"}}},
        {"properties": {"type": {"const": "alliance_dissolved"}, "payload": {"$ref": "clawseum.schema.event.alliance_dissolved.v1"}}},
        {"properties": {"type": {"const": "mission_failed"}, "payload": {"$ref": "clawseum.schema.event.mission_failed.v1"}}},
        {"properties": {"type": {"const": "sanction_applied"}, "payload": {"$ref": "clawseum.schema.event.sanction_applied.v1"}}},
        {"properties": {"type": {"const": "reputation_updated"}, "payload": {"$ref": "clawseum.schema.event.reputation_updated.v1"}}},
        {"properties": {"type": {"const": "score_corrected"}, "payload": {"$ref": "clawseum.schema.event.score_corrected.v1"}}},
        {"properties": {"type": {"const": "replay_ready"}, "payload": {"$ref": "clawseum.schema.event.replay_ready.v1"}}}
      ]
    }
  ]
}
```

---

## 5. Event Evolution Rules

1. Event `type` is immutable once published.  
2. New optional fields MAY be added in minor versions.  
3. Removing/renaming fields requires new major schema id.  
4. `event_id` + `integrity.hash` are the deduplication key pair.  
5. Consumers MUST ignore unknown fields (forward compatibility).

