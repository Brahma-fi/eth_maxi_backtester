# eth_maxi_backtester

## Introduction

This repository contains python scripts that are used by [Brahma Finance](https://brahma.fi/) to simulate the performance of the ETH Maxi DegenVault. The repo is structured as follows:

[data/](https://github.com/Brahma-fi/eth_maxi_backtester/tree/main/data) folder contains the csv files related to ETHUSD price data for FTX, ETH DVOL data from Deribit and ETH 1week ATM implied volatility data.

[notebooks/](https://github.com/Brahma-fi/eth_maxi_backtester/tree/main/notebooks) folder contains the notebooks.

In terms of the python files:

1. [utils.py](https://github.com/Brahma-fi/eth_maxi_backtester/tree/main/utils.py) contains all the functions used to process the raw data.
2. [perp_utils.py](https://github.com/Brahma-fi/eth_maxi_backtester/tree/main/perp_utils.py) contains functions to backtest perpetual based strategies.
3. [option_utils.py](https://github.com/Brahma-fi/eth_maxi_backtester/tree/main/option_utlis) contains functions to backtest option and squeeth based strategies


In order to run the backtest for the strategy use the notebook:

- [eth_maxi.ipynb](https://github.com/Brahma-fi/protected_moonshot_backtester/blob/master/moonshots_simple.ipynb) runs the analysis for the backtest and strategy developed explained in the [ETH Maxi Blog Post](https://blog.brahma.fi/launching-protected-moonshot-degenvault/). 