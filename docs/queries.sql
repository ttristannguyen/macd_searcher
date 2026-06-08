-- macd_searcher — analytical query pack
-- =====================================================================
-- Usage:
--   Run the whole file:   sqlite3 state/macd_searcher.sqlite3 < docs/queries.sql
--   Or open the DB:       sqlite3 state/macd_searcher.sqlite3
--                         then paste individual queries.
--
-- Notes:
--   * Run SECTION A (the helper view) ONCE before the performance queries —
--     they depend on it. It only adds a view; it never modifies your data.
--   * "Directional return" is normalized so a POSITIVE number always means the
--     predicted move happened (bullish up / bearish down). Win = return > 0.
--   * Many queries need ~1-2 weeks of finalized outcomes before they say
--     anything — until px_7d / px_14d fill in, the performance sections return
--     few or zero rows. The health/volume sections work from day one.
--   * Sample sizes are tiny early on; treat win-rates with < ~20 rows as noise.
--   * The two .headers/.mode lines below are sqlite3-CLI conveniences; ignore
--     them if you're pasting into a GUI.

.headers on
.mode column


-- =====================================================================
-- SECTION A — helper view (run once)
-- Adds asset_class (joined from snapshots) and direction-normalized returns.
-- =====================================================================

CREATE VIEW IF NOT EXISTS signal_perf AS
SELECT
    s.*,
    a.asset_class,
    CASE WHEN s.direction = 'bullish' THEN s.px_1d  / s.fire_close - 1
         ELSE 1 - s.px_1d  / s.fire_close END AS ret_1d,
    CASE WHEN s.direction = 'bullish' THEN s.px_3d  / s.fire_close - 1
         ELSE 1 - s.px_3d  / s.fire_close END AS ret_3d,
    CASE WHEN s.direction = 'bullish' THEN s.px_7d  / s.fire_close - 1
         ELSE 1 - s.px_7d  / s.fire_close END AS ret_7d,
    CASE WHEN s.direction = 'bullish' THEN s.px_14d / s.fire_close - 1
         ELSE 1 - s.px_14d / s.fire_close END AS ret_14d
FROM signals s
LEFT JOIN asset_snapshots a
       ON a.run_id = s.run_id AND a.symbol = s.symbol;


-- =====================================================================
-- SECTION B — operational health (works immediately)
-- =====================================================================

-- B1. How much data exists.
SELECT 'runs'            AS table_name, COUNT(*) AS row_count FROM runs
UNION ALL SELECT 'asset_snapshots', COUNT(*) FROM asset_snapshots
UNION ALL SELECT 'signals',         COUNT(*) FROM signals;

-- B2. The last 10 runs — is the scan healthy?
SELECT started_at, universe_total, universe_kept, signals_count,
       notify_status, ROUND(duration_s, 1) AS secs
FROM runs
ORDER BY started_at DESC
LIMIT 10;

-- B3. Dispatch outcome breakdown (sent / quiet_hours / no_creds / failed / ...).
SELECT notify_status, COUNT(*) AS n
FROM runs
GROUP BY notify_status
ORDER BY n DESC;

-- B4. Runs per day — should be ~6 (every 4h). Gaps = the cron didn't fire.
SELECT substr(started_at, 1, 10) AS day, COUNT(*) AS runs
FROM runs
GROUP BY day
ORDER BY day DESC
LIMIT 14;

-- B5. Any failed runs, with the error.
SELECT started_at, error
FROM runs
WHERE notify_status = 'failed' OR error IS NOT NULL
ORDER BY started_at DESC;


-- =====================================================================
-- SECTION C — signal volume & composition (works immediately)
-- =====================================================================

-- C1. Signals by stage and direction.
SELECT stage, direction, COUNT(*) AS n
FROM signals
GROUP BY stage, direction
ORDER BY n DESC;

-- C2. Signals by asset class (crypto / equity / commodity / fx / index).
SELECT asset_class, COUNT(*) AS n
FROM signal_perf
GROUP BY asset_class
ORDER BY n DESC;

-- C3. Which symbols fire the most.
SELECT symbol, COUNT(*) AS fires
FROM signals
GROUP BY symbol
ORDER BY fires DESC
LIMIT 20;

-- C4. Signals per day.
SELECT substr(fired_at, 1, 10) AS day, COUNT(*) AS signals
FROM signals
GROUP BY day
ORDER BY day DESC
LIMIT 14;


-- =====================================================================
-- SECTION D — outcome readiness (is update_outcomes keeping up?)
-- =====================================================================

-- D1. How many signals have each horizon scored / are finalized.
SELECT COUNT(*)                                                AS total,
       SUM(outcome_updated_at IS NOT NULL)                     AS finalized,
       SUM(px_1d  IS NOT NULL)                                 AS have_1d,
       SUM(px_3d  IS NOT NULL)                                 AS have_3d,
       SUM(px_7d  IS NOT NULL)                                 AS have_7d,
       SUM(px_14d IS NOT NULL)                                 AS have_14d
FROM signals;

-- D2. Oldest still-pending signal. If this is more than ~15 days old, the
--     update_outcomes job probably isn't running.
SELECT MIN(fired_at) AS oldest_pending, COUNT(*) AS pending
FROM signals
WHERE outcome_updated_at IS NULL;


-- =====================================================================
-- SECTION E — performance / edge  (needs finalized outcomes)
-- =====================================================================

-- E1. ★ Headline: win-rate and average 7d return by stage and direction.
SELECT stage, direction,
       COUNT(*)                                       AS n,
       ROUND(AVG(ret_7d > 0) * 100, 1)                AS win_pct,
       ROUND(AVG(ret_7d) * 100, 2)                    AS avg_ret_pct,
       ROUND(MIN(ret_7d) * 100, 2)                    AS worst_pct,
       ROUND(MAX(ret_7d) * 100, 2)                    AS best_pct
FROM signal_perf
WHERE ret_7d IS NOT NULL
GROUP BY stage, direction
ORDER BY stage, direction;

-- E2. Win-rate by asset class × stage — which markets does the model work on?
SELECT asset_class, stage,
       COUNT(*)                          AS n,
       ROUND(AVG(ret_7d > 0) * 100, 1)   AS win_pct,
       ROUND(AVG(ret_7d) * 100, 2)       AS avg_ret_pct
FROM signal_perf
WHERE ret_7d IS NOT NULL
GROUP BY asset_class, stage
HAVING n >= 5
ORDER BY avg_ret_pct DESC;

-- E3. Average return across horizons by stage — does the edge grow or decay?
SELECT stage,
       ROUND(AVG(ret_1d)  * 100, 2) AS r1d,
       ROUND(AVG(ret_3d)  * 100, 2) AS r3d,
       ROUND(AVG(ret_7d)  * 100, 2) AS r7d,
       ROUND(AVG(ret_14d) * 100, 2) AS r14d,
       COUNT(ret_14d)               AS n_14d
FROM signal_perf
GROUP BY stage;


-- =====================================================================
-- SECTION F — lead time (does Stage 1 really warn earlier?)
-- =====================================================================

-- F1. Zero-cross timing by stage, over FINALIZED signals only (so a NULL
--     bars_to_zero_cross genuinely means "never crossed within the horizon").
--     crossed_n / finalized_n = how often the predicted cross actually happened.
SELECT stage,
       COUNT(*)                                    AS finalized_n,
       SUM(bars_to_zero_cross IS NOT NULL)         AS crossed_n,
       ROUND(AVG(bars_to_zero_cross), 2)           AS avg_bars_to_cross,
       MIN(bars_to_zero_cross)                     AS min_bars,
       MAX(bars_to_zero_cross)                     AS max_bars
FROM signals
WHERE outcome_updated_at IS NOT NULL
GROUP BY stage;


-- =====================================================================
-- SECTION G — threshold tuning
-- =====================================================================

-- G1. Stage 3: bucket by how close to zero MACD was at fire. If the tightest
--     buckets win more, LOWER signal.price_pct_threshold.
SELECT
    CASE WHEN fire_macd_pct_of_price < 0.001 THEN 'a <0.1%'
         WHEN fire_macd_pct_of_price < 0.002 THEN 'b 0.1-0.2%'
         WHEN fire_macd_pct_of_price < 0.003 THEN 'c 0.2-0.3%'
         WHEN fire_macd_pct_of_price < 0.005 THEN 'd 0.3-0.5%'
         ELSE 'e >=0.5%' END           AS proximity_bucket,
    COUNT(*)                           AS n,
    ROUND(AVG(ret_7d > 0) * 100, 1)    AS win_pct,
    ROUND(AVG(ret_7d) * 100, 2)        AS avg_ret_pct
FROM signal_perf
WHERE stage = 'zero_line_proximity'
  AND ret_7d IS NOT NULL
  AND fire_macd_pct_of_price IS NOT NULL
GROUP BY proximity_bucket
ORDER BY proximity_bucket;

-- G2. Stage 1: bucket by how far the histogram had shrunk from its peak. If
--     deeper reductions win more, RAISE signal.histogram_flattening.min_reduction_from_peak.
SELECT
    CASE WHEN fire_reduction_from_peak < 0.4 THEN 'a 0.3-0.4'
         WHEN fire_reduction_from_peak < 0.6 THEN 'b 0.4-0.6'
         WHEN fire_reduction_from_peak < 0.8 THEN 'c 0.6-0.8'
         ELSE 'd 0.8-1.0' END          AS reduction_bucket,
    COUNT(*)                           AS n,
    ROUND(AVG(ret_7d > 0) * 100, 1)    AS win_pct,
    ROUND(AVG(ret_7d) * 100, 2)        AS avg_ret_pct
FROM signal_perf
WHERE stage = 'histogram_flattening'
  AND ret_7d IS NOT NULL
  AND fire_reduction_from_peak IS NOT NULL
GROUP BY reduction_bucket
ORDER BY reduction_bucket;


-- =====================================================================
-- SECTION H — tradeability (MFE / MAE)
-- =====================================================================

-- H1. Average best (favorable) and worst (adverse) excursion within the
--     horizon. Big favorable + small adverse = clean; the reverse = you'd need
--     a wide stop to survive. Helps size targets/stops.
SELECT stage, direction,
       COUNT(*)                                       AS n,
       ROUND(AVG(max_favorable_move_pct) * 100, 2)    AS avg_mfe_pct,
       ROUND(AVG(max_adverse_move_pct) * 100, 2)      AS avg_mae_pct
FROM signals
WHERE max_favorable_move_pct IS NOT NULL
GROUP BY stage, direction;


-- =====================================================================
-- SECTION I — per-symbol reliability
-- =====================================================================

-- I1. Which tickers' signals you can trust (min 5 scored signals).
SELECT symbol,
       COUNT(*)                          AS n,
       ROUND(AVG(ret_7d > 0) * 100, 1)   AS win_pct,
       ROUND(AVG(ret_7d) * 100, 2)       AS avg_ret_pct
FROM signal_perf
WHERE ret_7d IS NOT NULL
GROUP BY symbol
HAVING n >= 5
ORDER BY avg_ret_pct DESC;


-- =====================================================================
-- SECTION J — counterfactual alert volume (uses asset_snapshots, no outcomes)
-- =====================================================================

-- J1. Average number of assets per run sitting within each MACD-to-zero band.
--     Sizes how many MORE Stage-3-style alerts you'd get if you loosened
--     price_pct_threshold. (Upper bound: ignores the strict-shrink condition,
--     so actual fires would be fewer.)
WITH per_run AS (
    SELECT run_id,
           SUM(macd_pct_of_price < 0.002) AS u02,
           SUM(macd_pct_of_price < 0.005) AS u05,
           SUM(macd_pct_of_price < 0.010) AS u10
    FROM asset_snapshots
    GROUP BY run_id
)
SELECT ROUND(AVG(u02), 1) AS avg_assets_under_0_2pct,
       ROUND(AVG(u05), 1) AS avg_assets_under_0_5pct,
       ROUND(AVG(u10), 1) AS avg_assets_under_1pct
FROM per_run;
