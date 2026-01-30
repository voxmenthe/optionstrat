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