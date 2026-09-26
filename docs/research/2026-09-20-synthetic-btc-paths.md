# Synthetic BTC paths for a frozen SMAGateV1 stress test

**Date:** 2026-09-20  
**Scope:** Product/research note for Prism. Not investment advice. No recommendation to buy, sell, hedge, or size a Bitcoin position.  
**Question:** How should Prism emit extra Bitcoin-like daily histories so a later run of the *already frozen* SMAGateV1 rule (SMA-8 in / SMA-16 out) can be stress-tested without retuning on one Coinbase path?  
**This note is the spec for the history factory.** It does not pick a new SMA pair. It does not score 8/16 on remixed paths.

**Code:** `python -m price_forecast.remix.remix` — `price_forecast/remix/remix.py`. Real tape: Coinbase BTC-USD daily closes via `load_daily_closes(source="coinbase")`. Weeks: existing `weekly_closes`.

---

## The answer in one paragraph

Ship a **history factory**, not a new rule. Remix the real Coinbase daily *log-return* tape with `arch.bootstrap.StationaryBootstrap` (Politis & Romano 1994), rebuild prices from the first real close, keep the **original dates**. Default mean block length is **182 bars** (~26 weeks of 7-day BTC), long enough that SMA-8/16 still sees real trends. That is a **stress layer**: many rearrangements of *this* 2018→now process. It does **not** stop backtest overfitting. Overfitting is the number of trials on one sample, not “we only have one chart.” Bailey, Borwein, López de Prado, and Zhu use **crossing moving averages** as the worked example. Do not hunt a better pair on the fake movies. Do not treat a pretty cloud of KPIs as out-of-sample proof. Combinatorial CV, deflated Sharpe, a holdout, and costs still sit above this factory.

---

## What this factory is for

SMAGateV1 is frozen: weekly BTC, buy when close is strictly above SMA-8, sell when strictly below SMA-16, same-bar Sunday fill, 0.15% per fill (`price_forecast/strategies/smagate_v1.py`). That freeze was named after looking at the Coinbase path. One movie. A rule can look good because it sat in cash during *this* 2022 hole and *this* 2025–26 grind.

The factory’s job is extra movies that still use real Bitcoin return chunks, in a new order, so a *later* job can run the **same** 8/16 state machine and look at a cloud of full-path KPIs. Calendar labels (2022, Oct 2025–Jun 2026) die when you shuffle. Later scoring is full-path only.

**Not the job:** generate training data for Chronos. Invent dumps worse than anything in the tape. Re-open `{4,6,8,10,12} × {12,16,20,26,40}`. Replace `synthetic_daily` in `price_forecast/data/series.py` (that stub is deterministic unit-test drift).

---

## How one fake history is made

1. Load real daily closes. Work in **bar index**, not calendar days (Coinbase can gap).
2. `r_t = log(P_t / P_{t-1})`.
3. Draw remixed returns with `StationaryBootstrap(182, r, seed=...)` then `bootstrap(n_paths)` ([arch low-level bootstrap interface](https://arch.readthedocs.io/en/latest/bootstrap/low-level-interface.html)). Block lengths are exponential/geometric. The series wraps (circular). Do **not** hand-roll blocks. Do **not** use `scipy.stats.bootstrap` (IID; kills SMA-scale dependence).
4. `P'_0 = P_0`, `P'_t = P'_0 * exp(cumsum(r'))`. Wrap in `PriceSeries` on the original dates.
5. Weeks, if needed, come from existing `weekly_closes`. No calendar rewrite.

**Why 182, not `optimal_block_length`:** that helper is for standard errors of statistics. The docs even suggest running it on *squared* returns. Auto-picked lengths are often much shorter than SMA-16 and would scramble the trend the rule is built to catch (Künsch 1989: `ℓ` must grow with the dependence of interest). The CLI may *print* `optimal_block_length` as a diagnostic. It is not the factory default. Too long (~years) and every path is the original movie. 26 weeks is the middle.

**Sanity (required, or the factory is theater):** compare the real series to remixed paths and to a `mean_block_bars=1` IID-style control on daily/weekly vol, excess kurtosis / a left-tail daily return, buy-and-hold max drawdown, daily ACF lag 1, weekly ACF lags 1, 4, 8. If median remixed HODL max DD is much shallower than the real tape (~−75% on the published SMA windows) or weekly ACF at lags 4–8 collapses toward the IID control, the movies are not Bitcoin-like enough to stress 8/16.

---

## What synthetic data cannot replace

Primary sources are consistent. Extra paths can reduce **one-path luck**. They cannot replace **multiple-testing control**, and they can inflate confidence if the generator is wrong or leaky.

- Overfitting is **N trials**, not chart count. After a handful of zero-skill trials the expected *best* in-sample Sharpe is already large, with zero expected out-of-sample Sharpe (Bailey, Borwein, López de Prado, Zhu, [Pseudo-Mathematics and Financial Charlatanism](https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf), *Notices of the AMS* 61(5), 2014). Crossing moving averages are the motivating strategy class in that paper and in the PBO paper.
- Holdout is not enough if you hold out often enough. Report N (or effective N). Use the **deflated Sharpe ratio** when you later score a cloud (Bailey & López de Prado, [JPM 2014](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)).
- Combinatorial symmetric/purged CV (CSCV → probability of backtest overfitting; CPCV in *Advances in Financial Machine Learning* ch. 7 and 12) is the first-class tool **on the real series**. The PBO paper lists pseudorandom scenarios as a practitioner method with an explicit caveat: the generator “may also be overfit, or may not contain all relevant statistical features” ([The Probability of Backtest Overfitting](https://davidhbailey.com/dhbpapers/backtest-prob.pdf)).
- White’s Reality Check is a data-snooping *test* on one history, not a new market ([A Reality Check for Data Snooping](https://users.ssc.wisc.edu/~behansen/718/White2000.pdf), *Econometrica* 68(5), 2000). A thin spike of remixed KPIs around the historical number means you never left the original movie.
- Fees, fill assumptions, and point-in-time data bugs survive remixing. SMAGateV1’s 0.15% same-bar fill is still an assumption on every fake path.
- Structural breaks outside 2018→now are not in the tape (PBO §5.2). Bitcoin’s own persistence changed; Bariviera et al. (2017) report Hurst falling toward 0.5 after ~2014.

A later GARCH-t simulation (`arch_model.simulate`) is a valid **negative control**, not this factory: if 8/16 still “works” on GARCH-t, it may only be harvesting drift and vol, not trend. GBM / Heston / GANs are the wrong DGP for this rule (Cont 2001 stylized facts; GAN memorization, Sun & Lyuu arXiv:2209.04895).

---

## Honest limits of *this* remix

- Rearrangements of **this** Coinbase return process. Cannot invent a dump worse than blocks already in the tape.
- Glue points can split a crash chapter. Random-length blocks were a deliberate choice over crash-atomic blocks (fewer hidden knobs).
- Selection bias from having named 8/16 on the real path **stays**. Remixing does not un-see the grid.

---

## What to do, in order

1. **This job (done when `price_forecast/remix/remix.py` lands):** emit seeded `PriceSeries` paths; print a sanity comparison vs real and vs `mean_block_bars=1`. Do not retune 8/16.
2. **Next job (not this factory):** run SMAGateV1 vs buy-and-hold on N remixed paths. Publish the KPI *cloud* (median, 10th/90th of max DD and ending wealth vs hold). Full-path only. No new lookback.
3. **Later, if that cloud is not a spike around the historical number:** optional GARCH-t negative control; then CSCV/PBO and DSR on the *real* trial matrix if anyone reopens a grid. Do not reopen a grid to make PBO look good.

**Skip for now:** CSV dumps of hundreds of paths, GANs, QuantLib GBM/Heston, inventing worse-than-history crashes, treating remixed dollars as a live allocation.

---

## Sources

- Politis, D. N., & Romano, J. P. (1994). “The Stationary Bootstrap.” *Journal of the American Statistical Association*, 89(428), 1303–1313. [DOI](https://doi.org/10.1080/01621459.1994.10476870).
- `arch.bootstrap.StationaryBootstrap` — [low-level interface](https://arch.readthedocs.io/en/latest/bootstrap/low-level-interface.html); [time-series bootstraps](https://arch.readthedocs.io/en/latest/bootstrap/timeseries-bootstraps.html) (exponential block lengths). Already a repo dependency (`arch>=7.0` in `pyproject.toml`).
- Künsch, H. R. (1989). “The Jackknife and the Bootstrap for General Stationary Observations.” *Annals of Statistics*, 17(3), 1217–1241. Block length vs dependence.
- Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). “Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance.” *Notices of the AMS*, 61(5). [PDF](https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf). Crossing MAs; MinBTL.
- Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2015/2017). “The Probability of Backtest Overfitting.” *Journal of Computational Finance*. [PDF](https://davidhbailey.com/dhbpapers/backtest-prob.pdf). CSCV/PBO; generator-overfit caveat.
- Bailey, D. H., & López de Prado, M. (2014). “The Deflated Sharpe Ratio.” *Journal of Portfolio Management*, 40(5). [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).
- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. Ch. 7 (purged/embargoed CV), ch. 12 (CPCV).
- White, H. (2000). “A Reality Check for Data Snooping.” *Econometrica*, 68(5), 1097–1126.
- Cont, R. (2001). “Empirical Properties of Asset Returns: Stylized Facts and Statistical Issues.” *Quantitative Finance*, 1, 223–236. [PDF](http://rama.cont.perso.math.cnrs.fr/pdf/empirical.pdf).
- Bariviera, A. F., Basgall, M. J., Hasperué, W., & Naiouf, M. (2017). “Some Stylized Facts of the Bitcoin Market.” *Physica A*, 484. [arXiv:1708.04532](https://arxiv.org/abs/1708.04532).
- `docs/research/2026-09-17-sma-rule-debate.md` — freeze of buy8/sell16; SMAGateV1 addendum.
- `price_forecast/strategies/smagate_v1.py` — live SMAGateV1 runner. Do not retune.
- `price_forecast/data/series.py` — `synthetic_daily` stays a unit-test stub; Coinbase is the real tape.
