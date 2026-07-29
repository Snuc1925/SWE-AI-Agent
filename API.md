# SWE AI Agent API Reference

Management base URL: `http://localhost:8001`  
Evaluation base URL: `http://localhost:8002`  
Frontend proxy URLs: `/api/management` and `/api/evaluation`  
Interactive docs: `http://localhost:8001/docs` and `http://localhost:8002/docs`  
All request/response bodies are JSON unless noted otherwise.

---

## Skill Management API

The Skill Management service owns the skill library. It scans `SKILLS_DIR`, stores records in `database/skills.json`, and exposes CRUD, import/export, registry search, and tool-definition endpoints.

### `GET /skills`

List skills.

**Query params**

| Param | Type | Description |
|-------|------|-------------|
| `category` | `string` (optional) | Filter by category prefix |
| `level` | `string` (optional) | Filter by skill level, usually `atomic` or `composite` |
| `tag` | `string` (optional) | Filter by tag |

**Response `200`**

```jsonc
{
  "items": [
    {
      "id": "3343367d-479a-4c97-9bae-1cfa24d75561",
      "name": "domain-modeling",
      "version": "1.0.0",
      "level": "atomic",
      "category": "architecture-design/domain-modeling",
      "tags": [],
      "metadata": {
        "description": "Build and sharpen a project's domain model..."
      },
      "updated_at": "2026-07-26T14:53:35.150730+00:00"
    }
  ],
  "total": 100
}
```

---

### `GET /skills/search`

Search the in-memory skill registry.

**Query params**

| Param | Type | Description |
|-------|------|-------------|
| `q` | `string` | Search text |
| `top_k` | `integer` | Number of results, default `5`, maximum `20` |

**Response `200`**

```jsonc
{
  "query": "debug production error",
  "results": [
    {
      "skill": {
        "id": "...",
        "name": "diagnosing-bugs",
        "version": "1.0.0",
        "level": "atomic",
        "category": "debugging-observability/diagnosing-bugs",
        "tags": [],
        "metadata": {},
        "updated_at": "2026-07-26T14:53:35.150730+00:00"
      },
      "score": 0.8123
    }
  ]
}
```

---

### `GET /skills/{skill_id}`

Get full skill detail including raw markdown.

**Response `200`**

```jsonc
{
  "id": "3343367d-479a-4c97-9bae-1cfa24d75561",
  "name": "domain-modeling",
  "version": "1.0.0",
  "level": "atomic",
  "category": "architecture-design/domain-modeling",
  "tags": [],
  "metadata": {
    "description": "Build and sharpen a project's domain model..."
  },
  "raw_content": "---\nname: domain-modeling\n...",
  "full_markdown": "---\nname: domain-modeling\n...",
  "updated_at": "2026-07-26T14:53:35.150730+00:00"
}
```

**Errors**

| Code | Condition |
|------|-----------|
| `404` | Skill ID does not exist |

---

### `POST /skills`

Create a skill from metadata and instruction text.

**Request body**

```jsonc
{
  "metadata": {
    "name": "new-skill",
    "version": "1.0.0",
    "level": "atomic",
    "category": "workflow-planning/new-skill",
    "tags": ["planning"],
    "description": "Short description of when to use this skill."
  },
  "instruction": "# New Skill\n\nSkill instructions go here."
}
```

**Response `201`** - full `SkillRead` object.

**Errors**

| Code | Condition |
|------|-----------|
| `400` | Required metadata is missing or invalid |
| `409` | A skill with the same name already exists |

---

### `PUT /skills/{skill_id}`

Update metadata, instruction text, or full markdown.

**Request body**

```jsonc
{
  "metadata": {
    "description": "Updated description",
    "tags": ["review", "quality"]
  },
  "instruction": "# Updated instructions"
}
```

Alternative full markdown update:

```jsonc
{
  "full_markdown": "---\nname: new-skill\nversion: 1.0.0\nlevel: atomic\ncategory: workflow-planning/new-skill\n---\n\n# Instructions"
}
```

**Response `200`** - full `SkillRead` object.

---

### `DELETE /skills/{skill_id}`

Delete a skill record.

**Query params**

| Param | Type | Description |
|-------|------|-------------|
| `remove_file` | `boolean` | When `true`, also removes the backing markdown file if supported |

**Response `200`**

```json
{ "status": "deleted" }
```

---

### `POST /skills/import`

Import a markdown file.

**Request**

`multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | A `.md` file containing skill frontmatter and instructions |

**Response `201`** - full `SkillRead` object.

---

### `GET /skills/{skill_id}/export`

Export a skill as markdown.

**Response `200`**

Content type: `text/plain`

```markdown
---
name: domain-modeling
version: 1.0.0
---

# Skill instructions
```

---

### `GET /skills/tools`

Return all skills as tool definitions that can be used by an agent runtime.

**Response `200`**

```jsonc
[
  {
    "name": "domain-modeling",
    "description": "Build and sharpen a project's domain model...",
    "input_schema": {},
    "output_schema": {},
    "skill_id": "3343367d-479a-4c97-9bae-1cfa24d75561"
  }
]
```

---

### `GET /skills/{skill_id}/tool`

Return one skill as a tool definition.

**Response `200`** - one tool-definition object.

---

### `POST /skills/{skill_id}/execute`

Execute a skill with arbitrary input data. This endpoint is intended for experimentation and runtime integration.

**Request body**

```jsonc
{
  "input": {
    "task": "Review this API design",
    "context": "..."
  },
  "mock_mode": true,
  "api_key": null
}
```

**Response `200`**

```jsonc
{
  "skill_id": "...",
  "skill_name": "api-designer",
  "output": {},
  "telemetry": {
    "latency_ms": 1200.5,
    "token_usage": {},
    "retry_count": 0
  }
}
```

---

### `GET /registry/status`

Inspect the in-memory registry.

**Response `200`**

```jsonc
{
  "loaded_skills": 100,
  "skills_dir": "/data/skills",
  "skill_names": ["domain-modeling", "api-designer"]
}
```

---

### `POST /registry/reload`

Reload the registry from the current skill records.

**Response `200`**

```jsonc
{
  "status": "reloaded",
  "loaded_skills": 100
}
```

---

## Skill Evaluation API

The Skill Evaluation service evaluates `SKILL.md` markdown. The LLM is used only for configured feature extraction. Format checks and content scoring are deterministic rule-engine operations.

### `GET /health`

Health check.

**Response `200`**

```json
{ "status": "healthy", "service": "skill-evaluation" }
```

---

### `POST /evaluate/markdown`

Run the full evaluation pipeline:

1. Load evaluation profile
2. Extract corpus features for calibration
3. Extract target markdown features
4. Score format criteria
5. Score content criteria

**Request body**

```jsonc
{
  "markdown": "---\nname: sample-skill\nversion: 1.0.0\nlevel: atomic\n---\n\n# Instructions",
  "profile_id": "default"
}
```

**Response `200`**

```jsonc
{
  "format_review": {
    "score": 100,
    "max_score": 100,
    "passed": true,
    "frontmatter_valid": true,
    "errors": [],
    "criteria": [
      {
        "criterion": "format_name",
        "label": "Name",
        "score": 25,
        "max_score": 25,
        "explanation": "Front matter has a non-empty name field",
        "applied_steps": []
      }
    ],
    "features": {
      "format_has_name": true
    },
    "feature_evidence": {
      "format_has_name": {
        "evidence": "Computed by front matter parser.",
        "confidence": 1.0,
        "source": "format_parser"
      }
    }
  },
  "content_review": {
    "model": "deepseek-chat",
    "profile_id": "default",
    "profile_hash": "f40ca74892c6",
    "total_score": 42,
    "max_score": 50,
    "criteria": [
      {
        "criterion": "name_description_clarity",
        "label": "Name & Description",
        "score": 8,
        "max_score": 10,
        "explanation": "Score description length against corpus percentiles",
        "applied_steps": [
          {
            "id": "description_bucket",
            "before": 0,
            "after": 8
          }
        ]
      }
    ],
    "features": {
      "has_name": true,
      "description_word_count": 18
    },
    "feature_evidence": {
      "has_name": {
        "evidence": "name: sample-skill",
        "confidence": 1.0,
        "source": "llm"
      }
    },
    "calibration": {
      "description_word_count": {
        "p25": 12,
        "p50": 20,
        "p75": 34,
        "p90": 51
      }
    }
  }
}
```

**Errors**

| Code | Condition |
|------|-----------|
| `400` | LLM API key is missing |
| `502` | LLM provider is unreachable or returns an error |
| `500` | Unexpected evaluation failure |

---

### `POST /evaluate/features`

Extract features without final scoring. This is used by the feature correction UI.

**Request body**

```jsonc
{
  "markdown": "---\nname: sample-skill\n---\n\n# Instructions",
  "profile_id": "default"
}
```

**Response `200`**

```jsonc
{
  "model": "deepseek-chat",
  "profile_id": "default",
  "profile_hash": "f40ca74892c6",
  "content_features": {
    "has_name": true,
    "scenario_count": 2
  },
  "content_feature_evidence": {
    "scenario_count": {
      "evidence": "Two usage scenarios were found.",
      "confidence": 0.86,
      "source": "llm"
    }
  },
  "format_features": {
    "format_frontmatter_valid": true
  },
  "format_feature_evidence": {},
  "calibration": {
    "scenario_count": {
      "p25": 1,
      "p50": 2,
      "p75": 3,
      "p90": 5
    }
  },
  "metadata_fields": ["name"],
  "frontmatter_parse_error": null,
  "sync_log": [],
  "cache_complete": true
}
```

---

### `POST /evaluate/features/cache`

Check whether cached feature extraction exists for the supplied markdown/profile.

**Response behavior**

- If cache is complete, `content_features` is returned and `cache_complete` is `true`.
- If cache is missing or incomplete, `content_features` is empty and `cache_complete` is `false`.

---

### `POST /evaluate/features/sync`

Synchronize features for one markdown input. The endpoint returns sync logs so the frontend can show cache hit, LLM call, success, or failure status.

**Response fields of interest**

```jsonc
{
  "sync_log": [
    {
      "feature_id": "has_description",
      "status": "cache_hit"
    },
    {
      "feature_id": "scenario_count",
      "status": "llm_calling"
    },
    {
      "feature_id": "scenario_count",
      "status": "success"
    }
  ]
}
```

---

### `POST /evaluate/score-features`

Score corrected feature values without calling the LLM again.

**Request body**

```jsonc
{
  "markdown": "---\nname: sample-skill\n---\n\n# Instructions",
  "profile_id": "default",
  "content_features": {
    "has_name": true,
    "description_word_count": 18
  },
  "content_feature_evidence": {
    "has_name": {
      "evidence": "Corrected by user",
      "confidence": 1.0,
      "source": "user"
    }
  },
  "format_features": {
    "format_frontmatter_valid": true
  },
  "format_feature_evidence": {},
  "calibration": {
    "description_word_count": {
      "p25": 12,
      "p50": 20,
      "p75": 34,
      "p90": 51
    }
  }
}
```

**Response `200`** - same shape as `POST /evaluate/markdown`.

---

### `POST /evaluate/export-html`

Export an evaluation result as an HTML document.

**Request body**

```jsonc
{
  "evaluation": {
    "format_review": {},
    "content_review": {}
  }
}
```

**Response `200`**

Content type: `text/html`  
Header: `Content-Disposition: attachment; filename=skill-evaluation-report.html`

---

### `GET /evaluation/profiles/default`

Load the default evaluation profile.

**Response `200`**

```jsonc
{
  "schema_version": 1,
  "id": "default",
  "name": "Default Distribution Evaluation",
  "description": "Configurable skill format and content evaluation profile",
  "llm": {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": ""
  },
  "bucket_scheme": {
    "p25": 2,
    "p50": 4,
    "p75": 6,
    "p90": 8,
    "above": 10
  },
  "features": [
    {
      "id": "has_description",
      "type": "boolean",
      "extraction_guidance": "Return true when the skill has a meaningful description."
    }
  ],
  "criteria": [
    {
      "id": "name_description_clarity",
      "label": "Name & Description",
      "max_score": 10,
      "steps": []
    }
  ],
  "format_features": [],
  "format_criteria": []
}
```

---

### `PUT /evaluation/profiles/default`

Validate and save the default evaluation profile.

**Request body**

Same shape as `GET /evaluation/profiles/default`.

**Response `200`**

The saved profile JSON.

**Errors**

| Code | Condition |
|------|-----------|
| `400` | Profile schema is invalid |
| `500` | Profile could not be saved |

---

## Evaluation Rule Model

### Feature definition

```jsonc
{
  "id": "scenario_count",
  "type": "integer",
  "extraction_guidance": "Count concrete usage scenarios in the skill instructions."
}
```

Supported feature types:

| Type | Meaning |
|------|---------|
| `boolean` | `true` or `false` |
| `integer` | Whole number |

### Condition

```jsonc
{
  "any": [
    { "feature": "has_name", "operator": "eq", "value": false },
    { "feature": "has_description", "operator": "eq", "value": false }
  ]
}
```

Supported condition operators:

```text
exists, missing, eq, neq, lt, lte, gt, gte
```

Supported logical groups:

```text
all, any, not
```

### Rule step

```jsonc
{
  "id": "missing_name_or_description",
  "description": "Missing name or description forces score to 0",
  "condition": {
    "any": [
      { "feature": "has_name", "operator": "eq", "value": false },
      { "feature": "has_description", "operator": "eq", "value": false }
    ]
  },
  "action": "force_score",
  "value": 0
}
```

Supported actions:

| Action | Description |
|--------|-------------|
| `force_score` | Set final score immediately |
| `set_score_from_bucket` | Convert an integer feature to a percentile-based score |
| `set_baseline` | Set a minimum starting score |
| `add` | Add points |
| `subtract` | Subtract points |
| `cap_max` | Limit score to a maximum value |

---

## Common Error Format

FastAPI errors use the standard `detail` field.

```json
{
  "detail": "Evaluation failed: Missing LLM API key"
}
```
