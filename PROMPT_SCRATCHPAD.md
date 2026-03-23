We'd like to create a plan for a new separate module under src.
This will provide a set of utility scripts to scan through a set of securities. (we'll start with just AAPL/MSFT/AMZN/TSLA/GOOG to start but this should be easily configurable in a separate securities list config file). 

We're going to download the data from Y-Finance.
Some of the functionality will include the following:
* calculate aggregates, such as advances and declines breadth/depth, that kind of thing. 
* calculate and surface securities that have triggered an indicator. For example, we can start with a simple ROC zero crossover, but we expect to eventually build this out to include a wide variety of indicators - each indicator should hav its own python file.

Please create a detailed plan for this module and put it in a new document in the PLANS folder.


-------

We're going to build out the indicator suite in src/backend/app/security_scan - currently we just have roc I think? Let's add a new indicator that
works as follows: 1) first calculate multiple ROCs (different lookbacks) 2) For each ROC calculated, determine if it increased/flat/decreased vs a set
of lookbacks, giving each the appropriate +1/0/-1 score 3) The indicator is the aggregated score 4) We also calculate two moving averages on the
indicator, one short, one longer
The scan will be the indicator crossing above/below both MAs (also ofc already above 1 and then cross above other - and vice-versa for down - is ok)
Create a plan to implement this in the PLANS folder

-------

We'd like the ability to "sanity check" the indicators by looking at a dual pane plot of the price and the indicator, for any of the indicators we've calculated. Create a python script that does this. The script should be runnable as a jupyter notebook with cell boundaries delimited by `# %%`. Create a plan to implement this in the PLANS folder.


.venv/bin/python -m app.security_scan.cli \
  --start-date 2025-10-01 \
  --end-date 2025-12-31

uv run python -m app.security_scan.cli --backfill-aggregates

--------

We'd like to update the html output from src/backend/app/security_scan as follows:
* Make the tables more visually appealing by adding alternating row colors, and thicker borders.
* Move all the run metadata to the bottom of the report
* Move all the plots to the top of the report
* Remove the following sections from the report:
  - Indicator Overview
  - Top Tickers
  - Signal Density
  - Per-Ticker Summary
* For the Summary (Breadth) section:
  - Add comparisan columns for t-1, t-2, and an average of the last 10 days
  - Remove the Summary (Advance/Decline Lookbacks) section

Please go ahead and implement this.

-------

For the html report (and markdown report) from src/backend/app/security_scan, we'd like to add the following indicator scans (if we don't have them already):
for qrs_consist_excess:
* ma1 crosses above or below 0
* main indicator crosses above 0 after having been <= 0 for >= 3 days (or vice versa)

In the html report from src/backend/app/security_scan, in the Summary (Breadth) table, the t-1, t-2 and 10d avg columns are not poplulating. Please fix this.
Also remove all the "Signal Density" sections and the "Top Tickers by Signal Count" sections from the report

For the html report (and markdown report) from src/backend/app/security_scan, we'd like to do the following:
* For all indicator rollups:
  - Remove latest day highlights table since the information is already in the recent window table
  - Remove per-criteria grouping
  - Remove direction streaks
* Remove indicator signals appendix entirely
* Improve html table formatting to add zebra striping (both row and column in a way that is easy to read and where the two don't interfere with each other) and make it look more professional. The tables are currently difficult to read.
* Also use a nicer font with easier to read text.

For the html report (and markdown report) from src/backend/app/security_scan, we want to add a new dual-criteria scan to the scan report as follows:
1. SCL_v4_x5 indicator (with lag settings 2, 3, 4, 5, 11 and cd_offset1 2, cd_offset2 3, ma_period1 5, ma_period2 11) has MA2 > it's previous bar's N-day high (or MA2 < it's previous bar's N-day low) - N default can be 12
AND
2. qrs_consist_excess indicator has MA1 > it's previous bar's N-day high (or MA1 < it's previous bar's N-day low) - N default here can be 5


- `--intraday`: Enable intraday nowcast mode (disabled by default).
- `--intraday-interval`: Override intraday interval (`1m`, `5m`, `15m`, `60m`).
- `--intraday-min-bars`: Minimum intraday bars required to build the synthetic bar.

uv run python -m app.security_scan.cli --backfill-aggregates --intraday --intraday-interval 5m --intraday-min-bars 3

In the security scan html report, for the NASDAQ aggregate chart plots, we want to add them to the existing chart groups so that we don't need to duplicate the one-day and three-day percentage changes. 

In the security scan html report, For the breadth tables, we want the rows to be grouped by metric rather than by universe, so that it's easy to compare the same metric across universes.