We'd like to create a plan for a new separate module under src.
This will provide a set of utility scripts to scan through a set of securities. (we'll start with just AAPL/MSFT/AMZN/TSLA/GOOG to start but this should be easily configurable in a separate securities list config file). 

We're going to download the data from Y-Finance.
Some of the functionality will include the following:
* calculate aggregates, such as advances and declines breadth/depth, that kind of thing. 
* calculate and surface securities that have triggered an indicator. For example, we can start with a simple ROC zero crossover, but we expect to eventually build this out to include a wide variety of indicators - each indicator should hav its own python file.

Please create a detailed plan for this module and put it in a new document in the PLANS folder.


.venv/bin/python -m app.security_scan.cli \
  --start-date 2025-10-01 \
  --end-date 2025-12-31