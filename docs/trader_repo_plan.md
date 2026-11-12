# Plan: move the trading bot to its own repository

Status: Phases A, B, C and D are complete (2026-11-12).
Tick each item when it is complete. From phase D, `docs/trading_bot.md` is in
`b3_trader`.

**Phases E, G and H, and item F3, moved to `b3_trader` on 2026-11-12**
([docs/plan.md](https://github.com/ttristannguyen/b3_trader/blob/main/docs/plan.md)).
They are bot work, and a session in `b3_trader` must tick them. Items F1, F2 and F4
stay here, because they are research work in this repository.

## The design

`macd_searcher` tells what the book is. A new repository, `b3_trader`, tells how to
trade it. `b3_trader` installs `macd_searcher` as a dependency, pinned to a git tag.
There is no HTTP endpoint between them.

- A research commit or a scanner deploy cannot change the live bot. A rule change
  reaches the bot only when we change the pin.
- The agent key and the SDK stay out of the research code.
- The bot has no runtime dependency on the scanner. It reads the exchange directly.

| stays in `macd_searcher` | moves to `b3_trader` |
|---|---|
| detector, `book.py`, `research/backtest.py` | orders and the minimum-order rule (`plan.py`) |
| the new `target.py`: the book for a day | risk controls (`risk.py`) |
| Hyperliquid info client, Telegram sender | ledger, paper broker, live broker, daily run |
| detector settings in `config.yaml` | bot settings, `.env` keys, SDK dependency |
| research, watchlist, fidelity replay | `docs/trading_bot.md`, `tests/test_trader.py` |

The bot reads the book through one function:

```python
target.target_from_candles(day, candles, cfg, stopped, start)
```

The function returns the positions and the weights of today, and the positions of
yesterday. `stopped` and `start` are inputs, because only the bot knows them, and
they change the weights of the other names.

**No testnet (decided 2026-11-08).** We cannot get testnet funds. The sequence is paper
trade, then a small real-money check of the live broker, then the live book.

## Rules for each step

- Each item is one small commit. Revert it to undo it.
- `uv run pytest -q` passes after each item.
- Items in phase C do not change what the bot trades.
- Claude does not read `.env`, and does not send orders. "You" marks those steps.
- Commit, merge, tag and push only when you tell Claude to do it.

## Phase A: land the current work

- [x] **A1. Commit the bot** on a branch, then merge it to `main`.
  *Done when:* `git status` is clean and the tests pass.
- [x] **A2. Merge the research branch**
  `refs/heads/claude/research-live-checks-exits-15f25c`. It changes no file that the
  bot work changes (checked 2026-11-08).
  *Done when:* the bot tests and the new backtester tests pass together.
- [x] **A3. Remove the junction, then archive the research session.** The worktree has
  a junction, `state`, to the main `state/` folder. Run `cmd /c rmdir state` in the
  worktree before anything removes that worktree. A recursive delete could go through
  the junction and delete the live data.
  *Done when:* `state/` is intact and the worktree has no junction.

## Phase B: correct the bot with the research of 2026-11-07

- [x] **B1. Remove the drift band.** The band sends only closes on about a third of
  days, at each account size. At the maker fee, it saves 0.3% a year. Keep a small
  rounding tolerance on the gross alert, because the alert uses the band now.
  *Done when:* a test shows that a drifted weight trades back to its target.
- [x] **B2. Correct `docs/trading_bot.md`.** In §7, without the band, $5,000 is the
  smallest tested account that trades the tested book. In §6, remove the testnet step.
  *Done when:* the doc has the table of the research log and no testnet step.

## Phase C: make the boundary inside this repository

- [x] **C1. Add `target.py`.** Move `book_fires`, `target_on`, `listed_on`, `FIRE_DAYS`
  and `TRADED_LEGS` from `trader/plan.py`. Add `target_from_candles`. Re-export
  `Position` and the backtest cost constants. The replay test moves with them.
  *Done when:* the replay test passes from its new place.
- [x] **C2. Ship the detector settings in the package.** `config.yaml` is not in the
  wheel, and the code defaults are not its values (`shrink_lookback` 3 against 2, and
  a volume floor of $1M against $300k). Add it with `force-include`, and add
  `config.load_packaged()`.
  *Done when:* a built wheel has the file, and `load_packaged()` gives the
  `config.yaml` values.
- [x] **C3. Give the bot its own settings.** Move `TraderConfig` out of `AppConfig`, to
  `trader/settings.py`, with its own YAML file. Load `.env` from the bot's own root:
  `config._project_root()` is wrong for an installed package.
  *Done when:* `AppConfig` has no `trader` section, and the `_config_snapshot`
  exclusion is gone.
- [x] **C4. Narrow the imports.** The bot uses absolute imports of `target`, `config`,
  `hyperliquid` and `notify` only. Add a test that fails on any other import. Move the
  two Hyperliquid parser tests to `tests/test_hyperliquid.py`.
  *Done when:* the import test passes.

## Phase D: move to the new repository

- [x] **D1. Tag `strategy-v1`** on `main`, and push it. *2026-11-12:* the tag is on
  `e85e527`. The bot commits were on the public `main` before the tag (2026-11-11), so
  the bot code is in the public history of this repository. It has no secrets.
- [x] **D2. You:** create the GitHub repository `b3_trader`. Make it private.
- [x] **D3. Set up the project.** Pin
  `macd-searcher @ git+https://github.com/ttristannguyen/macd_searcher.git@strategy-v1`.
  Make the SDK a normal dependency. Add a short `CLAUDE.md` with the same style rules.
  *Done when:* `uv sync` installs the tag, and `load_packaged()` works.
  *2026-11-12:* `uv.lock` pins `e85e527`. The 34 tests pass, and the full book of
  2026-10-10 is the same. `b3_trader` is on GitHub at `c3b871b`.
- [x] **D4. Copy the bot, its tests, its doc and its `.env.example` keys.** A plain copy
  is enough, because the bot has few commits.
  *Done when:* `uv run pytest -q` passes in `b3_trader`. *2026-11-11:* 34 tests pass.
- [x] **D5. Compare the two repositories.** Run a paper dry-run from each on the same day.
  *Done when:* the target weights are equal. *2026-11-11:* the 6 targets of the day
  are equal. The full book of 2026-10-10 is also equal: 91 longs and 24 shorts.
- [x] **D6. Delete the bot from `macd_searcher`:** `trader/`, `tests/test_trader.py`, the
  `live` extra, the `trader` config and the `.env.example` keys. Link to the new
  repository from `docs/trading_strategy.md`.
  *Done when:* the tests pass and `uv.lock` has no SDK.

## Phase E: paper trade on the VPS

Moved to `b3_trader`, `docs/plan.md`.

## Phase F: close the research loop (during paper)

- [ ] **F1. Sync the ledger** to `macd_searcher`, in the same way as
  `scripts/sync_prod_db.ps1`.
- [ ] **F2. Build the fidelity replay** in `macd_searcher`. Run `backtest.account` over
  the recorded targets, and compare it with the paper equity.
  *Done when:* each gap has a name: a bug, a cost, an unfilled order, or timing.
- **F3.** Moved to `b3_trader`, `docs/plan.md`.
- [ ] **F4. Use one source for the Telegram book.** `book.py` has its own copy of the
  rules. It can call `target.py`. The Telegram universe has the OI filter and the bot
  universe does not, so decide which one the message shows.

## Phases G and H: the live broker and the live book

Moved to `b3_trader`, `docs/plan.md`, with the open questions on the capital and the
paper time. The repository name is `b3_trader` (decided 2026-11-11).
