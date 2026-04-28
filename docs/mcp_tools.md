# MCP Tool Server MVP

## Overview

This project includes an MCP-compatible Tool Server MVP designed for portfolio explanation and local workflow integration. The current implementation does not depend on a full MCP SDK runtime yet. Instead, it uses a lightweight registry pattern that mirrors MCP tool concepts closely enough to demonstrate:

- tool-level separation of responsibilities
- discoverable tool metadata
- structured input and output schemas
- explicit `run` execution contracts
- easy migration path to an official MCP SDK later

The implementation entry point is:

- `app/mcp_server/server.py`

The tool modules are separated by capability:

- `app/mcp_server/tools/policy_search_tool.py`
- `app/mcp_server/tools/product_recommend_tool.py`
- `app/mcp_server/tools/design_condition_tool.py`

## MCP-Compatible Interface

Each tool exposes the following fields and method:

- `name`
- `description`
- `input_schema`
- `output_schema`
- `run(payload)`

This shape is intentionally close to how MCP tools are typically described and invoked, while remaining simple enough for a portfolio MVP.

## Tool Registry

`MCPToolServer` acts as a local registry and execution layer.

Available server methods:

- `list_tools()`: returns metadata for discovery or UI rendering
- `call_tool(name, payload)`: executes a tool by name and returns structured output

This allows the project to show a clear separation between:

- agent orchestration
- business/domain tools
- transport/runtime concerns

## Tools

### 1. `policy_search_tool`

Purpose:

- search the synthetic sample policy
- return relevant clauses with citation metadata

Implementation:

- calls the existing keyword-based RAG retriever
- reuses the synthetic `sample_policy.md` document pipeline

Typical input:

```json
{
  "query": "입원일당 청구 서류는 무엇인가요?",
  "top_k": 3
}
```

### 2. `product_recommend_tool`

Purpose:

- recommend riders and plan settings from synthetic design history

Implementation:

- calls `recommendation_service`
- filters by `age_group`, `gender`, and `product_name`
- returns rider recommendations, payment settings, coverage amount, `confidence_score`, and `basis_count`

Typical input:

```json
{
  "age_group": "30s",
  "gender": "F",
  "product_name": "Sample Care Plan"
}
```

### 3. `design_condition_tool`

Purpose:

- update the current synthetic design condition by applying rider add/remove operations

Implementation:

- accepts a `current_design` object
- applies `add_riders` and `remove_riders`
- returns the updated design and applied change summary

Typical input:

```json
{
  "current_design": {
    "product_name": "Sample Care Plan",
    "payment_period": "20 years",
    "insurance_period": "80 years",
    "payment_cycle": "monthly",
    "coverage_amount": 50000000,
    "riders": ["Standard Hospital Rider"]
  },
  "add_riders": ["Critical Diagnosis Rider"],
  "remove_riders": ["Standard Hospital Rider"]
}
```

## Why This Structure Works for a Portfolio

This structure is useful in a portfolio because it makes the tool boundary explicit. Instead of hiding policy retrieval, recommendation, and design modification inside a single agent function, each capability is modeled as a tool with:

- a distinct domain purpose
- a clear interface contract
- reusable execution logic
- easy future replacement or extension

That makes it easier to explain how an enterprise GenAI system can move from monolithic prompt logic to modular tool-driven orchestration.

## Future MCP SDK Migration Plan

The current version is intentionally SDK-light. A future migration to an official MCP SDK can follow this path:

1. replace the local `MCPToolServer` registry with an MCP SDK server runtime
2. register each tool using the SDK's tool declaration format
3. map `input_schema` and `output_schema` into SDK-native schema definitions
4. keep the existing domain `run` logic as the execution body for each tool
5. expose the server over the preferred MCP transport layer

Because the domain logic is already separated by tool, the migration should be mostly transport- and registration-level work rather than a business-logic rewrite.

## Data Safety

All tools in this MVP operate only on synthetic sample data. No real insurer data, real customer information, or real production API contracts are included.
