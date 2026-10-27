"""Frozen v1 normalized record schemas; format is not Host authority."""

RECORD_SCHEMAS = {
    "position": {
        "type": "object",
        "properties": {
            "kind": {"const": "position"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "weight": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "weight_unit": {"enum": ["fraction", "percent"]},
            "snapshot_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "weight",
            "weight_unit",
            "snapshot_at",
        ],
        "additionalProperties": False,
    },
    "risk-event": {
        "type": "object",
        "properties": {
            "kind": {"const": "risk-event"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "event_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "category": {"enum": ["risk", "unlock", "insider"]},
            "announced_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
            "effective_date": {"type": "string", "format": "date"},
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "event_id",
            "category",
            "announced_at",
            "effective_date",
        ],
        "additionalProperties": False,
    },
    "source-version": {
        "type": "object",
        "properties": {
            "kind": {"const": "source-version"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "document_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "version_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "url_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
            "language": {"type": "string", "minLength": 1, "maxLength": 4096},
            "region": {"type": "string", "minLength": 1, "maxLength": 4096},
            "event_at": {
                "anyOf": [
                    {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    {"type": "null"},
                ]
            },
            "source_role": {"enum": ["original", "reprint", "translation"]},
            "parent_version_id": {
                "anyOf": [{"type": "string", "minLength": 1, "maxLength": 4096}, {"type": "null"}]
            },
            "full_text_available": {"type": "boolean"},
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "document_id",
            "version_id",
            "content_sha256",
            "url_ref",
            "language",
            "region",
            "event_at",
            "source_role",
            "parent_version_id",
            "full_text_available",
        ],
        "additionalProperties": False,
    },
    "actual": {
        "type": "object",
        "properties": {
            "kind": {"const": "actual"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "report_period": {"type": "string", "minLength": 1, "maxLength": 4096},
            "basis": {"enum": ["single-quarter", "cumulative"]},
            "metric": {"type": "string", "minLength": 1, "maxLength": 4096},
            "attribution": {"type": "string", "minLength": 1, "maxLength": 4096},
            "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
            "unit": {"type": "string", "minLength": 1, "maxLength": 4096},
            "value": {"type": "number"},
            "disclosed_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "report_period",
            "basis",
            "metric",
            "attribution",
            "currency",
            "unit",
            "value",
            "disclosed_at",
        ],
        "additionalProperties": False,
    },
    "forecast": {
        "type": "object",
        "properties": {
            "kind": {"const": "forecast"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "report_period": {"type": "string", "minLength": 1, "maxLength": 4096},
            "basis": {"enum": ["single-quarter", "cumulative"]},
            "metric": {"type": "string", "minLength": 1, "maxLength": 4096},
            "attribution": {"type": "string", "minLength": 1, "maxLength": 4096},
            "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
            "unit": {"type": "string", "minLength": 1, "maxLength": 4096},
            "value": {"type": "number"},
            "vintage_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
            "consensus_id": {"type": "string", "minLength": 1, "maxLength": 4096},
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "report_period",
            "basis",
            "metric",
            "attribution",
            "currency",
            "unit",
            "value",
            "vintage_at",
            "consensus_id",
        ],
        "additionalProperties": False,
    },
    "guidance": {
        "type": "object",
        "properties": {
            "kind": {"const": "guidance"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "report_period": {"type": "string", "minLength": 1, "maxLength": 4096},
            "basis": {"enum": ["single-quarter", "cumulative"]},
            "metric": {"type": "string", "minLength": 1, "maxLength": 4096},
            "attribution": {"type": "string", "minLength": 1, "maxLength": 4096},
            "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
            "unit": {"type": "string", "minLength": 1, "maxLength": 4096},
            "lower": {"type": "number"},
            "upper": {"type": "number"},
            "disclosed_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "report_period",
            "basis",
            "metric",
            "attribution",
            "currency",
            "unit",
            "lower",
            "upper",
            "disclosed_at",
        ],
        "additionalProperties": False,
    },
    "valuation": {
        "type": "object",
        "properties": {
            "kind": {"const": "valuation"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "metric": {"enum": ["PE"]},
            "basis": {"enum": ["TTM", "static", "forward"]},
            "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
            "unit": {"const": "multiple"},
            "observation_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
            "value": {"type": "number"},
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "metric",
            "basis",
            "currency",
            "unit",
            "observation_at",
            "value",
        ],
        "additionalProperties": False,
    },
    "exchange-session": {
        "type": "object",
        "properties": {
            "kind": {"const": "exchange-session"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "market": {"type": "string", "minLength": 1, "maxLength": 4096},
            "session_date": {"type": "string", "format": "date"},
            "open_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
            "close_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
        },
        "required": ["kind", "row_id", "origin", "market", "session_date", "open_at", "close_at"],
        "additionalProperties": False,
    },
    "daily-price": {
        "type": "object",
        "properties": {
            "kind": {"const": "daily-price"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "session_date": {"type": "string", "format": "date"},
            "close": {"type": "number"},
            "unit": {"type": "string", "minLength": 1, "maxLength": 4096},
            "adjustment": {"enum": ["forward", "backward", "none"]},
            "tradable": {"type": "boolean"},
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "session_date",
            "close",
            "unit",
            "adjustment",
            "tradable",
        ],
        "additionalProperties": False,
    },
    "sentiment-counts": {
        "type": "object",
        "properties": {
            "kind": {"const": "sentiment-counts"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "market": {"type": "string", "minLength": 1, "maxLength": 4096},
            "session_date": {"type": "string", "format": "date"},
            "universe_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "expected_count": {"type": "integer", "minimum": 0},
            "observed_count": {"type": "integer", "minimum": 0},
            "up": {"type": "integer", "minimum": 0},
            "down": {"type": "integer", "minimum": 0},
            "flat": {"type": "integer", "minimum": 0},
            "unknown": {"type": "integer", "minimum": 0},
            "limit_up": {"type": "integer", "minimum": 0},
            "opened_limit": {"type": "integer", "minimum": 0},
            "limit_touched": {"type": "integer", "minimum": 0},
            "regime_id": {"type": "string", "minLength": 1, "maxLength": 4096},
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "market",
            "session_date",
            "universe_hash",
            "expected_count",
            "observed_count",
            "up",
            "down",
            "flat",
            "unknown",
            "limit_up",
            "opened_limit",
            "limit_touched",
            "regime_id",
        ],
        "additionalProperties": False,
    },
    "holder-disclosure": {
        "type": "object",
        "properties": {
            "kind": {"const": "holder-disclosure"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "report_period": {"type": "string", "minLength": 1, "maxLength": 4096},
            "holder_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "holder_kind": {"enum": ["fund", "insider", "institution", "other"]},
            "shares": {"type": "number"},
            "unit": {"enum": ["share", "10k-share"]},
            "float_shares": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "float_unit": {"enum": ["share", "10k-share"]},
            "disclosed_at": {
                "type": "string",
                "format": "date-time",
                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
            },
            "disclosure_id": {"type": "string", "minLength": 1, "maxLength": 4096},
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "report_period",
            "holder_id",
            "holder_kind",
            "shares",
            "unit",
            "float_shares",
            "float_unit",
            "disclosed_at",
            "disclosure_id",
        ],
        "additionalProperties": False,
    },
    "report-calendar": {
        "type": "object",
        "properties": {
            "kind": {"const": "report-calendar"},
            "row_id": {"type": "string", "minLength": 1, "maxLength": 4096},
            "origin": {
                "type": "object",
                "properties": {
                    "locator": {
                        "type": "object",
                        "properties": {
                            "source_ref": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "resource_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "record_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                            "location": {"type": "string", "minLength": 1, "maxLength": 4096},
                        },
                        "required": ["source_ref", "resource_id", "record_id", "location"],
                        "additionalProperties": False,
                    },
                    "observed_at": {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    "published_at": {
                        "anyOf": [
                            {
                                "type": "string",
                                "format": "date-time",
                                "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                            },
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["locator", "observed_at", "published_at"],
                "additionalProperties": False,
            },
            "security": {
                "type": "object",
                "properties": {
                    "security_id": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "market": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "asset_class": {"enum": ["equity", "index", "fund"]},
                    "currency": {"type": "string", "minLength": 1, "maxLength": 4096},
                },
                "required": ["security_id", "market", "asset_class", "currency"],
                "additionalProperties": False,
            },
            "report_period": {"type": "string", "minLength": 1, "maxLength": 4096},
            "plan_version": {"type": "integer", "minimum": 0},
            "planned_date": {"type": "string", "format": "date"},
            "actual_disclosed_at": {
                "anyOf": [
                    {
                        "type": "string",
                        "format": "date-time",
                        "pattern": "(Z|[+-][0-9]{2}:[0-9]{2})$",
                    },
                    {"type": "null"},
                ]
            },
            "supersedes_row_id": {
                "anyOf": [{"type": "string", "minLength": 1, "maxLength": 4096}, {"type": "null"}]
            },
        },
        "required": [
            "kind",
            "row_id",
            "origin",
            "security",
            "report_period",
            "plan_version",
            "planned_date",
            "actual_disclosed_at",
            "supersedes_row_id",
        ],
        "additionalProperties": False,
    },
}
