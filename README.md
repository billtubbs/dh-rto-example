# dh-rto-example

An experiment to determine how a realistic real time optimization (RTO) algorithm would perform when
making hourly energy generation dispatch decisions for a district heating system with a gas boiler,
heat pump, and thermal storage tank.

The district heating system sizing is based on the oemof.solph example used in the following course:

- Modelica-based simulation of building and district energy systems course, Aalborg University Copenhagen Campus, 26–28 August 2026.

Course page: https://phd.moodle.aau.dk/blocks/vitrina/detail.php?id=2974

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
