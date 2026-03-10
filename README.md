# Alvin

Alvin is a modular trading system focused on deterministic decision flow, auditability, and staged operational build-out.

## Current stage

The repository is beyond foundation stage and now includes:

- config loading and validation
- bootstrap / doctor / show-config commands
- sqlite schema and database persistence base
- broker connectivity scaffold and order submit layer
- decision contracts and audit primitives
- strategy building blocks:
  - level detection
  - break / retest validation
  - M15 confirmation
  - signal candidate building
  - setup building
  - setup evaluation
- execution building blocks:
  - order intent builder
  - execution payload builder
  - sized execution payload builder
  - order executor
  - execution result handler
  - intent state manager
  - execution audit builder
  - retry policy
- risk building blocks:
  - risk gate
  - position sizer

## Important note

Alvin is not yet a fully integrated live trading system.
The repository currently contains strong modular building blocks, but end-to-end orchestration, broader testing, and full runtime integration are still in progress.

## Project structure

- `broker/` broker client and order execution
- `config/` runtime configuration
- `contracts/` shared contracts and lifecycle models
- `core/` events and core primitives
- `execution/` intent, payload, execution result, retry and audit flow
- `intelligence/` acceptance and intelligence modules
- `monitoring/` journal logging
- `risk/` risk gate and sizing
- `storage/` sqlite schema and persistence layer
- `strategy/` strategy modules and setup creation
- `utils/` config loading and validation

## Quick start

1. Copy `.env.example` to `.env`
2. Fill in OANDA practice or live credentials
3. Install dependencies
4. Run bootstrap
5. Run doctor
6. Inspect config if needed

## Commands

- `python main.py bootstrap`
- `python main.py doctor`
- `python main.py show-config`

## Current workflow direction

The main intended decision chain is:

`level -> break/retest -> M15 confirmation -> setup builder -> setup evaluator -> order intent -> sizing -> execution payload -> broker submit -> result handling -> state transition -> audit / retry`

## Environment

Expected `.env` values include:

- `OANDA_API_URL`
- `OANDA_ACCOUNT_ID`
- `OANDA_API_TOKEN`

## Status

Alvin currently has a strong architectural base and working module contracts, but it should still be treated as an in-progress system under controlled build-out rather than a production-ready autonomous trading engine.
