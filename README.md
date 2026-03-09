# Alvin

Alvin is a clean, modular trading system focused on deterministic control, auditability, and staged build-out.

## Current stage
Foundation layer only:
- config loading
- bootstrap and doctor commands
- sqlite schema and storage layer
- core event primitives
- journal logging
- broker connectivity scaffold

## Usage
1. Copy `.env.example` to `.env`
2. Fill in OANDA credentials
3. Install dependencies
4. Run bootstrap
5. Run doctor

## Commands
- `python main.py bootstrap`
- `python main.py doctor`
- `python main.py show-config`
