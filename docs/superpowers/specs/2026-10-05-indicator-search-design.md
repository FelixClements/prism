# Indicator search

**Date:** 2026-10-05
**Status:** Draft for review
**Scope:** Let the CrashGate search test an outside idea that uses a known technical indicator, including settings that are not on the breeding ladder. Add the indicator calculations that idea needs. The locked CrashGateV1 file stays unchanged.

This spec records the design agreed in chat. It extends `docs/superpowers/specs/2026-10-02-crashgate-search-design.md`. Where this spec is silent, that spec still applies.

## Goal

The search today refuses an idea unless both the indicator and the number are already on a short ladder. An 8-week average is tested. A 7-week average is not, even though the average function can compute it. A pivot that says RSI is not tested at all.

Split those two jobs. The ladder remains the list of steps the search uses when it copies one of the original three rule shapes. An outside idea is tested when the indicator is one this spec names and the numbers sit in the ranges below. If that idea later becomes one of the best rules, a later copy changes one of its numbers by one step.

## Non-goals

- Editing `price_forecast/strategies/crashgate_v1.py`, its fill, its fee, or its locked behavior
- Changing the ladder for the original three rule shapes. A locked 8-week average still moves to 6 or 10 weeks, not to 7
- Changing the pivot script. Phrases it already emits are parsed here
- Scoring an idea that is not one of the indicators below. Funding, a macro regime, earnings, and pairs stay untested
- Treating the number in a phrase as a count of days. The search decides once a week, so the number counts weeks
- Putting two comparisons in one phrase

## Two jobs

**Breeding** stays in `price_forecast/search/mutate.py`. For a parent whose mode is `threshold`, `dual_average`, or `prior_high`, the legal edits stay exactly as they are today. One edit still changes one mode, one ladder number, or one on/off filter.

**Outside ideas** are read in `price_forecast/search/translate.py`. A phrase is tested when it parses as a comparison of a known series and every number is inside its range. The position is in on a week when every comparison is true and every selected filter passes. Otherwise it is out. The fill stays the next weekly close. The fee stays 0.15% per fill. The start stays cash.

A draft that is already a valid original spec keeps that spec and today's in-until-exit behavior. The check is the same one `spec_from_mapping` already applies, including the ladder numbers. A lone `weekly_close > sma_8` is not a valid original spec, because that shape still needs an exit, so it becomes an indicator spec: in while the close is above the 8-week average. A draft that fails the original check is then parsed as an indicator spec. If any phrase still does not parse, the draft is not tested. It is appended to the side pile, as today, and it gets no score.

`down_week` is an exit event of the original threshold rule. It is not a comparison. A draft that contains `down_week` and is not a valid original threshold spec is not tested. That includes a draft that mixes `down_week` with RSI.

`base_or_breakout` and `above_long_averages` stay filters. On an indicator spec they are stored as the same two booleans. They are not comparisons. Breeding an indicator spec does not flip them. Only a number changes.

## Weekly bars

Indicator math reads one bar per Sunday-ending week, using the same week buckets as `weekly_sessions`. The open is the first day's open. The high is the highest daily high. The low is the lowest daily low. The close is the last day's close, the same close the original rules already use. The volume is the sum of the daily volumes when every day in the week has a volume. If any day has a blank volume, the week's volume is blank.

The original three modes keep reading weekly closes only. Their results do not change.

## Indicator spec

An indicator spec is data. It cannot set the fill, the fee, or the starting cash.

```json
{
  "mode": "indicator",
  "conditions": [
    {"left": "rsi", "args": [21], "op": "<", "right": {"value": 25}}
  ],
  "base_or_breakout": false,
  "above_long_averages": false
}
```

`conditions` has at least one comparison. `op` is one of `>`, `>=`, `<`, `<=`. `right` is either `{"value": number}` or `{"series": name, "args": [numbers]}`. `left` and `series` are names from the table below. `args` holds only that series' parameters, in the order listed.

A spec with no stepable number is rejected. `close > close` is rejected. A MACD comparison whose fast period is greater than or equal to its slow period is rejected. Rejection of a draft raises `Unmapped` before a ledger row is scored. Rejection of a bred child follows today's rule: that edit is not legal.

On a week where any series used by the spec is undefined, the position is out. Undefined is not an error by itself. If the series is undefined for every week, the simulation raises, and the ledger row is an error, as a simulation failure is today.

## Series

`close` takes no arguments. `price` in a phrase is the same series. A period is an integer from 2 through 260 unless a row below says otherwise.

| Phrase token | Series | Arguments | Value on week t |
| --- | --- | --- | --- |
| `close`, `price` | `close` | none | weekly close |
| `sma_N` | `sma` | period | arithmetic mean of the last N closes, including week t |
| `ema_N` | `ema` | period | exponential mean below |
| `rsi_N` | `rsi` | period | Wilder RSI below. A compared number is from 0 through 100 |
| `macd_F_S` | `macd` | fast, slow | EMA(fast) minus EMA(slow). Fast is shorter than slow |
| `macd_signal_F_S_K` | `macd_signal` | fast, slow, signal | EMA of the MACD line. Signal period is from 2 through 260. Fast is shorter than slow |
| `macd_hist_F_S_K` | `macd_hist` | fast, slow, signal | MACD line minus its signal line. Same limits as the signal |
| `bb_upper_N_K` | `bb_upper` | period, width | middle plus width times the population standard deviation |
| `bb_mid_N_K` | `bb_mid` | period, width | the SMA. Width is stored and must be from 0.5 through 4 |
| `bb_lower_N_K` | `bb_lower` | period, width | middle minus width times the population standard deviation |
| `atr_N` | `atr` | period | Wilder average true range below |
| `stoch_N` | `stoch` | period | stochastic percent K below. A compared number is from 0 through 100 |
| `stoch_d_N_D` | `stoch_d` | K period, D period | SMA of percent K over D weeks, including week t. Both periods are from 2 through 260. A compared number is from 0 through 100 |
| `adx_N` | `adx` | period | Wilder ADX below. A compared number is from 0 through 100 |
| `donchian_high_N` | `donchian_high` | period | highest weekly high of the previous N weeks, excluding week t |
| `donchian_low_N` | `donchian_low` | period | lowest weekly low of the previous N weeks, excluding week t |
| `prior_high_N` | `prior_close_high` | period | highest weekly close of the previous N weeks, excluding week t. This is the existing prior-high value |
| `roc_N` | `roc` | period | `(close_t / close_{t-N} - 1) * 100` |
| `obv` | `obv` | none | on-balance volume below |
| `obv_sma_N` | `obv_sma` | period | SMA of the OBV series |
| `rel_volume_N` | `rel_volume` | period | this week's volume divided by the SMA of volume over N weeks, including week t. A compared number is greater than 0 |

Population standard deviation divides by N, not by N minus 1.

EMA uses `k = 2 / (period + 1)`. The first value is the SMA of the first `period` closes. Each later value is `close * k + previous * (1 - k)`.

RSI uses Wilder smoothing on close-to-close changes. The first average gain and average loss are the simple means of the first `period` changes. Each later average is `(previous * (period - 1) + current) / period`. When the average loss is 0 and the average gain is positive, RSI is 100. When both averages are 0, RSI is 50. Otherwise RSI is `100 - 100 / (1 + average gain / average loss)`.

MACD's signal EMA starts once the MACD line has `signal` values. Its first signal value is the SMA of those values, then the same EMA step.

ATR uses true range `max(high - low, abs(high - previous close), abs(low - previous close))`. The first true range exists on the second week. The first ATR is the simple mean of the first `period` true ranges. Each later ATR uses the same Wilder step as RSI.

Stochastic percent K is `100 * (close - lowest low) / (highest high - lowest low)` over the last `period` weeks, including week t. When the high equals the low, percent K is undefined. Percent D is the SMA of percent K.

ADX uses Wilder's construction. Up-move is this high minus the previous high. Down-move is the previous low minus this low. Plus DM is the up-move when it is positive and strictly larger than the down-move, else 0. Minus DM is the down-move when it is positive and strictly larger than the up-move, else 0. True range is the ATR true range. The first smoothed plus DM, minus DM, and true range are the sums of the first `period` values. Each later smoothed value is `previous - previous / period + current`. Plus DI is `100 * smoothed plus DM / smoothed true range`. Minus DI is the same with minus DM. DX is `100 * abs(plus DI - minus DI) / (plus DI + minus DI)`. The first ADX is the simple mean of the first `period` DX values. Each later ADX uses the Wilder step. A week with a zero denominator is undefined.

OBV on the first week equals that week's volume. On each later week, add the volume when the close rose, subtract it when the close fell, and leave OBV unchanged when the close was equal.

A blank volume makes `obv`, `obv_sma`, and `rel_volume` undefined. A zero volume average makes `rel_volume` undefined.

## Phrases

Each new phrase is one comparison: a token from the table, one operator, and a token or a number. The operator has one space on each side. Tokens and the original phrases are lowercase. `sma_7 > sma_20` is a new phrase. It does not need to be one of the original pairs. An integer and an integer-valued decimal are the same number: a width of `2` and a width of `2.0` both mean 2. A compared number whose series does not list a range may be any finite number. A non-finite number does not parse.

These original phrases still parse, and they still mean the original spec when the whole draft is a valid original spec:

- `base_or_breakout`
- `above_long_averages`
- `weekly_close > sma_N` and `weekly_close < sma_N`
- `down_week` followed by one of `0.05`, `0.08`, `0.10`, `0.12`
- `sma_F > sma_S` for an original pair
- `close >= prior_high_N` for an original N

When the draft is not a valid original spec, those same phrases become indicator comparisons, except `down_week`, `base_or_breakout`, and `above_long_averages`:

- `weekly_close > sma_N` becomes `close > sma` with period N
- `weekly_close < sma_N` becomes `close < sma` with period N
- `sma_F > sma_S` becomes `sma > sma`
- `close >= prior_high_N` becomes `close >= prior_close_high`

`close > sma_50 > sma_200` has two operators, so the draft is not tested. Two phrases, `close > sma_50` and `sma_50 > sma_200`, are tested. Every parsed comparison, wherever it was found in `conditions`, `entry`, `exit`, or `trend_filter`, must be true on the same week. An exit phrase in an indicator draft is not a separate sell trigger.

Numbers outside a range fail the draft. `rsi_1 < 25`, `rsi_14 < 120`, a Bollinger width of 0.4 or 4.5, and `rel_volume_20 >= 0` are not tested. `rsi_21 < 25` is tested. A 7-week average is tested.

## Scoring a volume idea

A spec needs volume when any series is `obv`, `obv_sma`, or `rel_volume`.

A spec that does not need volume is scored as today: Coinbase, 100 remix paths, and 100 synthetic paths. It enters the pool only when the Coinbase edge is positive, both path-family means are at least half of that edge, and the row is not fragile.

A spec that needs volume is scored on Coinbase and on the synthetic paths. Remix files have no volume, so they are not run. `remix_mean_edge` is null. `stress_pass` is true when the Coinbase edge is positive and the synthetic mean is at least half of that edge. A non-positive Coinbase edge still skips every path family, stores null means, and fails the stress check. The other pool rules are unchanged. If the Coinbase weeks do not have volume, the simulation raises and the row is an error.

## Breeding an indicator parent

For a parent whose mode is `indicator`, each legal edit changes exactly one number by one step. Every other field stays the same.

- A period, an RSI level, a stochastic level, an ADX level, or any other compared number steps by 1
- A Bollinger width steps by 0.5. A width of 2.2 becomes 1.7 or 2.7
- A relative-volume multiple steps by 0.1. A multiple of 1.55 becomes 1.45 or 1.65

A step that would leave the range, make a relative-volume multiple 0 or negative, or make a MACD fast period greater than or equal to its slow period is not a legal edit. At a period of 2 the only step is to 3. At 260 the only step is to 259.

`rsi_21 < 25` can become `rsi_20 < 25`, `rsi_22 < 25`, `rsi_21 < 24`, or `rsi_21 < 26`. An indicator spec whose only average period is 7 can become 6 or 8. That is different from a `threshold` parent whose 8-week field still moves to 6 or 10 along the original ladder.

The edit is chosen with the same seeded generator as today. The same seed and cycle produce the same child from the same parent.

## Tests

Tests live under `tests/search/` and `tests/strategies/`. They use small fixtures. They do not generate 200 paths.

- Copying the locked 8-week rule still uses today's legal edits. The 8-week field moves to 6 or 10, not to 7. A search run does not modify `price_forecast/strategies/crashgate_v1.py`
- A draft that uses only the original locked phrases still becomes the locked spec
- `funding` still adds one side-pile line and produces no score
- A 7-week average draft becomes an indicator spec and can be simulated
- `rsi_21 < 25` becomes an indicator spec and can be simulated
- `rsi_1 < 25`, `rsi_14 < 120`, `close > sma_50 > sma_200`, and a down-week phrase mixed with RSI produce no score
- Once `rsi_21 < 25` is the parent, one edit changes only one number, to period 20 or 22 or to level 24 or 26
- Once a 7-week indicator average is the parent, one edit moves that period to 6 or 8
- A volume spec leaves `remix_mean_edge` null and can still pass on the synthetic mean. A price spec still requires both means
- Hand-computed series, from closes `10, 11, 12, 11, 13`:
  - SMA(3) on the last close is 12
  - EMA(3) on the last close is 12. The multiplier is 0.5, the seed at the third close is 11, and the fourth close stays 11
  - RSI(2) on the last close is `100 - 100 / 6`
  - ROC(2) on the last close is `(13 / 12 - 1) * 100`
- On those same closes, MACD(2, 3) on the last close is `7/18`. The signal period is 2. The signal on the last close is `10/27`. The histogram is `1/54`
- On the last two of those closes, with width 2, the middle is 12, the upper band is 14, and the lower band is 10
- Hand-computed OHLC, four weeks `(high, low, close, volume)` = `(10, 8, 9, 100)`, `(12, 9, 11, 50)`, `(11, 7, 8, 80)`, `(13, 10, 12, 40)`:
  - The second week's true range is 3 and the third week's true range is 4. ATR(2) on the third week is 3.5
  - Donchian high of 2 on the third week is 12
  - OBV on the first three weeks is `100, 150, 70`
  - Relative volume over 2 weeks on the third week is `80 / 65`
  - Stochastic percent K over 2 weeks is 75 on the second week and 20 on the third week. Percent D over 2 is 47.5 on the third week
  - ADX(2) on the fourth week is 25. Plus DI and minus DI are equal on the third week, so that week's DX is 0. The fourth week's DX is 50

## Files

- `price_forecast/strategies/indicators.py` holds the weekly bars and the series functions
- `price_forecast/search/spec.py` accepts `mode: indicator` and checks ranges
- `price_forecast/search/translate.py` parses the phrases
- `price_forecast/search/mutate.py` steps one number for an indicator parent and leaves the original three modes alone
- `price_forecast/search/runner.py` evaluates the comparisons on the same fill clock
- `price_forecast/search/score.py` and `price_forecast/search/__main__.py` skip remix for a spec that needs volume
- Tests cover the cases in the section above
