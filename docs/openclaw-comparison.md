# Hermit and OpenClaw Positioning Comparison

This document is only a high-level positioning comparison. It is not intended to be a file-by-file or version-by-version implementation analysis of OpenClaw.

Constraints:

- conclusions about Hermit are based on the current repository source
- conclusions about OpenClaw are limited to stable public positioning, without freezing volatile external implementation details into the document

## One-Sentence Conclusion

Both are local-first agent systems, but their design priorities are different:

- Hermit is more runtime-first, centered on personal workflows and readable source
- OpenClaw is more platform-first, with a broader channel surface and heavier operational overhead

## Hermit’s Current Real Positioning

Based on the current repository, Hermit is centered on:

- `AgentRunner`
- `AgentRuntime`
- `PluginManager`
- the `~/.hermit` file-based state directory

The surfaces currently implemented are:

- CLI
- Feishu adapter
- scheduler
- webhook
- MCP
- macOS companion

## Hermit’s Strengths

Hermit is a better fit if you care more about:

- being able to understand the runtime in a relatively short time
- keeping state on the local filesystem
- extending private capabilities through plugins
- building around a personal workflow instead of a full platform

## Hermit’s Tradeoffs

This design also comes with clear tradeoffs:

- a lighter control plane
- fewer built-in channels by default
- less productized packaging than heavier platforms
- some capabilities require writing your own plugins

## How It Differs from Heavier Platforms

Platform-oriented systems usually emphasize:

- more channels
- a fuller control console
- a heavier gateway and operations layer
- more standardized multi-tenant or team capabilities

Hermit is not currently trying to compete head-on on those dimensions.

## When to Choose Hermit

Hermit is a better choice when:

- you want a personal agent runtime, not a product platform
- you want to modify the provider, plugins, and state model yourself
- you care more about local inspectability, recoverability, and auditability
- you are willing to accept fewer default channels and a lighter control plane

## Principles Behind This Documentation Update

The previous version contained some descriptions that were more likely to drift as external products changed.

After this update, the document keeps only:

- conclusions that are stably true for the current Hermit codebase
- the positioning comparison at the level of “light runtime vs heavy platform”
