/** Generated sales extension; run node scripts/generate-sales-api.mjs --write. */

export const salesInputSchemas: Record<string, unknown> = {
  "sales-prospect": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "objective": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Objective",
        "type": "string"
      },
      "bounds": {
        "additionalProperties": false,
        "properties": {
          "max_steps": {
            "maximum": 16,
            "minimum": 1,
            "title": "Max Steps",
            "type": "integer"
          },
          "max_model_calls": {
            "maximum": 8,
            "minimum": 0,
            "title": "Max Model Calls",
            "type": "integer"
          },
          "max_concurrent_steps": {
            "maximum": 2,
            "minimum": 1,
            "title": "Max Concurrent Steps",
            "type": "integer"
          },
          "automatic_model_repair": {
            "const": false,
            "title": "Automatic Model Repair",
            "type": "boolean"
          }
        },
        "title": "ExecutionBounds",
        "type": "object"
      }
    },
    "title": "ProspectArguments",
    "type": "object"
  },
  "sales-research": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Buyer Id"
      },
      "research_question": {
        "anyOf": [
          {
            "maxLength": 4000,
            "minLength": 1,
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Research Question"
      },
      "max_sources": {
        "maximum": 12,
        "minimum": 1,
        "title": "Max Sources",
        "type": "integer"
      }
    },
    "title": "ResearchArguments",
    "type": "object"
  },
  "sales-quick": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Buyer Id"
      },
      "research_question": {
        "anyOf": [
          {
            "maxLength": 4000,
            "minLength": 1,
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Research Question"
      },
      "max_sources": {
        "maximum": 3,
        "minimum": 1,
        "title": "Max Sources",
        "type": "integer"
      }
    },
    "title": "QuickArguments",
    "type": "object"
  },
  "sales-qualify": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "profile_id": {
        "format": "uuid",
        "title": "Profile Id",
        "type": "string"
      },
      "profile_version": {
        "minimum": 1,
        "title": "Profile Version",
        "type": "integer"
      },
      "rubric": {
        "const": "BANT_MEDDIC",
        "title": "Rubric",
        "type": "string"
      }
    },
    "title": "QualificationArguments",
    "type": "object"
  },
  "sales-contacts": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "purpose": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Purpose",
        "type": "string"
      },
      "roles": {
        "items": {
          "maxLength": 240,
          "minLength": 1,
          "type": "string"
        },
        "maxItems": 5,
        "minItems": 1,
        "title": "Roles",
        "type": "array"
      }
    },
    "title": "ContactsArguments",
    "type": "object"
  },
  "sales-outreach": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "profile_id": {
        "format": "uuid",
        "title": "Profile Id",
        "type": "string"
      },
      "recipient_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Recipient Id"
      },
      "objective": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Objective",
        "type": "string"
      },
      "framework": {
        "enum": [
          "PAS",
          "AIDA",
          "BAB",
          "direct"
        ],
        "title": "Framework",
        "type": "string"
      }
    },
    "title": "OutreachArguments",
    "type": "object"
  },
  "sales-followup": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "profile_id": {
        "format": "uuid",
        "title": "Profile Id",
        "type": "string"
      },
      "recipient_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Recipient Id"
      },
      "objective": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Objective",
        "type": "string"
      },
      "framework": {
        "enum": [
          "PAS",
          "AIDA",
          "BAB",
          "direct"
        ],
        "title": "Framework",
        "type": "string"
      },
      "interaction_ref": {
        "additionalProperties": false,
        "properties": {
          "id": {
            "format": "uuid",
            "title": "Id",
            "type": "string"
          },
          "version": {
            "minimum": 1,
            "title": "Version",
            "type": "integer"
          },
          "kind": {
            "enum": [
              "project_fact",
              "profile",
              "buyer",
              "document",
              "output",
              "run",
              "provider_evidence",
              "drive"
            ],
            "title": "Kind",
            "type": "string"
          },
          "locator": {
            "maxLength": 500,
            "minLength": 1,
            "pattern": "^[^\\r\\n]+$",
            "title": "Locator",
            "type": "string"
          },
          "retention_class": {
            "enum": [
              "durable",
              "metadata_only",
              "zero_content"
            ],
            "title": "Retention Class",
            "type": "string"
          }
        },
        "required": [
          "id",
          "version",
          "kind",
          "locator",
          "retention_class"
        ],
        "title": "SourceRef",
        "type": "object"
      },
      "scenario": {
        "enum": [
          "post_meeting",
          "post_demo",
          "post_proposal",
          "recovery",
          "nurture"
        ],
        "title": "Scenario",
        "type": "string"
      }
    },
    "title": "FollowupArguments",
    "type": "object"
  },
  "sales-prep": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "meeting_at": {
        "format": "date-time",
        "title": "Meeting At",
        "type": "string"
      },
      "objective": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Objective",
        "type": "string"
      },
      "attendee_ids": {
        "items": {
          "format": "uuid",
          "type": "string"
        },
        "maxItems": 20,
        "title": "Attendee Ids",
        "type": "array"
      },
      "duration_minutes": {
        "enum": [
          30,
          60
        ],
        "title": "Duration Minutes",
        "type": "integer"
      }
    },
    "title": "MeetingArguments",
    "type": "object"
  },
  "sales-proposal": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "profile_id": {
        "format": "uuid",
        "title": "Profile Id",
        "type": "string"
      },
      "pain_points": {
        "items": {
          "maxLength": 4000,
          "minLength": 1,
          "type": "string"
        },
        "maxItems": 10,
        "minItems": 1,
        "title": "Pain Points",
        "type": "array"
      },
      "terms": {
        "items": {
          "additionalProperties": false,
          "properties": {
            "price": {
              "additionalProperties": false,
              "properties": {
                "amount": {
                  "anyOf": [
                    {
                      "minimum": 0,
                      "type": "number"
                    },
                    {
                      "pattern": "^(?!^[-+.]*$)[+-]?0*(?:\\d{0,14}|(?=[\\d.]{1,19}0*$)\\d{0,14}\\.\\d{0,4}0*$)",
                      "type": "string"
                    }
                  ],
                  "title": "Amount"
                },
                "currency": {
                  "pattern": "^[A-Z]{3}$",
                  "title": "Currency",
                  "type": "string"
                }
              },
              "required": [
                "amount",
                "currency"
              ],
              "title": "Money",
              "type": "object"
            },
            "scope": {
              "maxLength": 4000,
              "minLength": 1,
              "title": "Scope",
              "type": "string"
            },
            "exclusions": {
              "maxLength": 4000,
              "minLength": 1,
              "title": "Exclusions",
              "type": "string"
            },
            "timeline": {
              "maxLength": 4000,
              "minLength": 1,
              "title": "Timeline",
              "type": "string"
            },
            "evidence": {
              "items": {
                "additionalProperties": false,
                "properties": {
                  "id": {
                    "format": "uuid",
                    "title": "Id",
                    "type": "string"
                  },
                  "version": {
                    "minimum": 1,
                    "title": "Version",
                    "type": "integer"
                  },
                  "kind": {
                    "enum": [
                      "project_fact",
                      "profile",
                      "buyer",
                      "document",
                      "output",
                      "run",
                      "provider_evidence",
                      "drive"
                    ],
                    "title": "Kind",
                    "type": "string"
                  },
                  "locator": {
                    "maxLength": 500,
                    "minLength": 1,
                    "pattern": "^[^\\r\\n]+$",
                    "title": "Locator",
                    "type": "string"
                  },
                  "retention_class": {
                    "enum": [
                      "durable",
                      "metadata_only",
                      "zero_content"
                    ],
                    "title": "Retention Class",
                    "type": "string"
                  }
                },
                "required": [
                  "id",
                  "version",
                  "kind",
                  "locator",
                  "retention_class"
                ],
                "title": "SourceRef",
                "type": "object"
              },
              "maxItems": 16,
              "minItems": 1,
              "title": "Evidence",
              "type": "array"
            }
          },
          "required": [
            "price",
            "scope",
            "exclusions",
            "timeline",
            "evidence"
          ],
          "title": "CommercialTerms",
          "type": "object"
        },
        "maxItems": 3,
        "minItems": 1,
        "title": "Terms",
        "type": "array"
      },
      "case_study_refs": {
        "items": {
          "additionalProperties": false,
          "properties": {
            "id": {
              "format": "uuid",
              "title": "Id",
              "type": "string"
            },
            "version": {
              "minimum": 1,
              "title": "Version",
              "type": "integer"
            },
            "kind": {
              "enum": [
                "project_fact",
                "profile",
                "buyer",
                "document",
                "output",
                "run",
                "provider_evidence",
                "drive"
              ],
              "title": "Kind",
              "type": "string"
            },
            "locator": {
              "maxLength": 500,
              "minLength": 1,
              "pattern": "^[^\\r\\n]+$",
              "title": "Locator",
              "type": "string"
            },
            "retention_class": {
              "enum": [
                "durable",
                "metadata_only",
                "zero_content"
              ],
              "title": "Retention Class",
              "type": "string"
            }
          },
          "required": [
            "id",
            "version",
            "kind",
            "locator",
            "retention_class"
          ],
          "title": "SourceRef",
          "type": "object"
        },
        "maxItems": 10,
        "title": "Case Study Refs",
        "type": "array"
      }
    },
    "title": "ProposalArguments",
    "type": "object"
  },
  "sales-objections": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "profile_id": {
        "format": "uuid",
        "title": "Profile Id",
        "type": "string"
      },
      "buyer_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Buyer Id"
      },
      "objections": {
        "items": {
          "maxLength": 4000,
          "minLength": 1,
          "type": "string"
        },
        "maxItems": 20,
        "minItems": 1,
        "title": "Objections",
        "type": "array"
      }
    },
    "title": "ObjectionsArguments",
    "type": "object"
  },
  "sales-icp": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "offer_description": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Offer Description",
        "type": "string"
      },
      "profile_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Profile Id"
      }
    },
    "title": "ICPArguments",
    "type": "object"
  },
  "sales-competitors": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_id": {
        "format": "uuid",
        "title": "Buyer Id",
        "type": "string"
      },
      "profile_id": {
        "format": "uuid",
        "title": "Profile Id",
        "type": "string"
      },
      "competitor_names": {
        "items": {
          "maxLength": 240,
          "minLength": 1,
          "type": "string"
        },
        "maxItems": 5,
        "title": "Competitor Names",
        "type": "array"
      }
    },
    "title": "CompetitorsArguments",
    "type": "object"
  },
  "sales-report": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "as_of": {
        "format": "date-time",
        "title": "As Of",
        "type": "string"
      },
      "buyer_ids": {
        "items": {
          "format": "uuid",
          "type": "string"
        },
        "maxItems": 100,
        "minItems": 1,
        "title": "Buyer Ids",
        "type": "array"
      },
      "list_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "List Id"
      }
    },
    "title": "ReportArguments",
    "type": "object"
  },
  "sales-report-pdf": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "output_id": {
        "format": "uuid",
        "title": "Output Id",
        "type": "string"
      },
      "output_revision": {
        "minimum": 1,
        "title": "Output Revision",
        "type": "integer"
      },
      "export_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Export Id"
      }
    },
    "title": "ExportArguments",
    "type": "object"
  },
  "first-project": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "offer_description": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Offer Description",
        "type": "string"
      },
      "buyer_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Buyer Id"
      },
      "recipient_id": {
        "anyOf": [
          {
            "format": "uuid",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Recipient Id"
      }
    },
    "title": "ProjectArguments",
    "type": "object"
  },
  "understand-documents": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "document_ids": {
        "items": {
          "format": "uuid",
          "type": "string"
        },
        "maxItems": 20,
        "minItems": 1,
        "title": "Document Ids",
        "type": "array"
      },
      "question": {
        "maxLength": 4000,
        "minLength": 1,
        "title": "Question",
        "type": "string"
      }
    },
    "title": "DocumentsArguments",
    "type": "object"
  },
  "review-buyers": {
    "additionalProperties": false,
    "properties": {
      "language": {
        "enum": [
          "en",
          "zh-HK"
        ],
        "title": "Language",
        "type": "string"
      },
      "buyer_ids": {
        "items": {
          "format": "uuid",
          "type": "string"
        },
        "maxItems": 100,
        "minItems": 1,
        "title": "Buyer Ids",
        "type": "array"
      },
      "profile_id": {
        "format": "uuid",
        "title": "Profile Id",
        "type": "string"
      },
      "profile_version": {
        "minimum": 1,
        "title": "Profile Version",
        "type": "integer"
      }
    },
    "title": "ReviewArguments",
    "type": "object"
  }
};
