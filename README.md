# dh-rto-example

An experiment to determine how a realistic real time optimization (RTO) algorithm would perform when
making hourly energy generation dispatch decisions for a district heating system with a gas boiler,
heat pump, and thermal storage tank.

The district heating system sizing is based on the oemof.solph example used in the following course:

- Modelica-based simulation of building and district energy systems course, Aalborg University Copenhagen Campus, 26–28 August 2026.

Course page: https://phd.moodle.aau.dk/blocks/vitrina/detail.php?id=2974

## Scenarios

Two scenarios are simulated and compared:

- **Perfect foresight** -- a single optimization is performed once over the entire simulated period,
  with full knowledge of the actual heat demand, gas price, and electricity price at all times. This
  wouldn't be achievable in a real operation because the future is uncertain. However, this approach
  was used to determine the sizing of the energy system components (gas-fired boiler, heat pump and
  thermal storage tank).
- **RTO with a moving (rolling) horizon** -- a realistic hourly dispatch strategy that re-solves the
  optimization every hour using accurate forecast data for a 24 hour lookahead, followed by a simple
  repeating daily profile for the remainder of the 48-hour prediction horizon, then implements only the
  decision for the current hour before repeating the optimization in the next hourly time step. This
  mimics how an actual RTO system might operate, with imperfect knowledge of future demand and prices.

The input data is hourly heating demand, electricity price, and gas price over a period of time that
includes an unexpected three-day cold snap when the demand for heating is unusually high.

Comparing the two shows the effect of assuming perfect foresight during the system design: perfect 
foresight allows it to make the capacity of the gas boiler and heat pump smaller than the maximum
possible demand by utilizing the storage tank whenever there is a future requirement for more heat.

## Installation

This repo uses a conda environment (`environment.yaml`) to install Python plus the CBC solver, and `pyproject.toml` to declare the Python package dependencies.

1. Create the environment:
   ```
   conda env create -f environment.yaml -n dh-rto
   ```

2. Activate it:
   ```
   conda activate dh-rto
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
