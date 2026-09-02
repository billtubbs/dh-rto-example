# dh-rto-example

An experiment to determine how a realistic real time optimization (RTO) algorithm would perform when
making hourly energy generation dispatch decisions for a district heating system with a gas boiler,
heat pump, and thermal storage tank.

The district heating system sizing is based on the oemof.solph example used in the following course:

- Modelica-based simulation of building and district energy systems course, Aalborg University Copenhagen Campus, 26–28 August 2026.

Course page: https://phd.moodle.aau.dk/blocks/vitrina/detail.php?id=2974

## Scenarios

This repository compares two ways of operating the same district heating system over a period that
includes an unexpected cold snap in January:

- **Perfect foresight** -- a single optimization solved once over the entire simulated period, with
  full knowledge of the actual future heat demand, gas price, and electricity price. This isn't
  achievable in real operation; it's a theoretical best-case benchmark to measure a realistic
  strategy against.
- **RTO with a moving (rolling) horizon** -- a realistic hourly dispatch strategy that re-solves the
  optimization every hour using real data for a short lookahead (24 hours) followed by a simple
  repeating forecast for the remainder of a 48-hour planning window, then implements only the
  decision for the current hour before moving on. This mimics how an automated RTO system would
  actually operate, with no knowledge of demand beyond its planning horizon.

Comparing the two shows the value of foresight: the perfect-foresight case sees the cold snap coming
days in advance and pre-charges the thermal storage accordingly, while the RTO case -- unable to see
that far ahead -- enters the cold snap with a nearly depleted reserve and fails to fully meet demand
for part of the event.

## Installation

This repo uses a conda environment (`environment.yaml`) to install Python plus the CBC solver, and `pyproject.toml` to declare the Python package dependencies.

1. Create the environment:
   ```
   conda env create -f environment.yaml
   ```

2. Activate it:
   ```
   conda activate mod-build
   ```

3. Install this repo's dependencies:
   ```
   pip install -e .
   ```

## Dependencies

- Python 3.11
- [CBC solver](https://github.com/coin-or/Cbc) (`coincbc`, via conda-forge)
- [oemof.solph](https://oemof-solph.readthedocs.io/)
- [Pyomo](https://www.pyomo.org/) (used directly for custom MILP constraints)


## To run this code the following input data file is required

[data/input_data.csv](data/input_data.csv)

## Usage

1. Run the simulations
   ```
   python rto_coldsnap.py  
   ```

   The simulation results are saved as csv files in the [results](results) directory.

2. Plot the results
   ```
   python rto_coldsnap_plot.py  
   ```

   The plot figures are saved as image files in the [plots](plots) directory.
