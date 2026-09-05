"""Outer-loop capacity search: Bayesian optimization (Gaussian process,
scikit-optimize's gp_minimize) over gas boiler / heat pump / storage
capacity, evaluating each candidate against the REALISTIC RTO dispatch
policy from rto_coldsnap.py -- not the perfect-foresight benchmark.

Objective: daily-averaged cost -- annualized capex (same epc() formula and
investment costs as the original opt_step1.py sizing script) divided by
365 for a daily share, plus the window's own actual operating cost
(including a heavy penalty for any unmet demand) divided by the number of
days in the window. NOT a full annual LCOH: the 552-hour window is a
deliberately atypical cold-snap stress period, and scaling it up to
represent a full year would be misleading. CO2 emissions (tCO2/day,
same window-average convention) are tracked as a second output from the
same evaluations, for a separate GP surrogate -- not folded into the cost
objective, since capacity mix alone (at a single fixed dispatch CO2
price) already trades cost off against emissions.

Every evaluated (capacities -> outcomes) point is appended to
results/capacity_search_cache.csv as it's computed, and reloaded on
startup -- repeated runs of this script pick up where they left off
rather than re-running expensive simulations. The RTO simulation is
deterministic, so gp_minimize is run with noise fixed near zero rather
than its default noise estimation.
"""

from pathlib import Path

import pandas as pd
from skopt import gp_minimize
from skopt.space import Real

import rto_coldsnap as rto

RESULTS_DIR = rto.RESULTS_DIR
CACHE_PATH = RESULTS_DIR / "capacity_search_cache.csv"

CO2_PRICE = (
    20  # fixed dispatch price -- matches opt_step1.py's lambda=20 anchor
)

# Target TOTAL number of purely-random points across all invocations of
# this script (not per-run). n_initial_points is computed each run as
# max(N_INITIAL - <points already cached>, 0), so once the cache holds
# N_INITIAL points, every subsequent point -- in this run or a later one
# -- is genuinely GP-guided rather than more random sampling.
N_INITIAL = 10

# Investment costs and annualization, from the original opt_step1.py sizing script.
SPEC_INV_GAS_BOILER = 60_000  # EUR/MW
SPEC_INV_HEAT_PUMP = 500_000  # EUR/MW
SPEC_INV_STORAGE = 1060  # EUR/MWh
DISCOUNT_RATE = 0.05
LIFETIME_YEARS = 20

CACHE_COLUMNS = [
    "cap_gas_boiler",
    "cap_heat_pump",
    "cap_storage",
    "daily_cost",
    "daily_co2",
    "unserved_heat_mwh",
    "daily_capex",
    "daily_opex",
]


def epc(invest_cost, i=DISCOUNT_RATE, n=LIFETIME_YEARS):
    """Annualize a lump investment cost (identical formula to opt_step1.py)."""
    af = (i * (1 + i) ** n) / ((1 + i) ** n - 1)
    return invest_cost * af


def evaluate_candidate(
    cap_gas_boiler, cap_heat_pump, cap_storage, data_full, data_window
):
    """Run the RTO simulation for one candidate capacity set and compute
    daily-averaged cost and CO2 metrics. Returns a flat dict matching
    CACHE_COLUMNS.
    """
    initial_level, final_level = rto.discover_boundary_levels(
        data_full,
        cap_gas_boiler,
        cap_heat_pump,
        cap_storage,
        CO2_PRICE,
        rto.WINDOW_START,
        rto.WINDOW_END,
    )
    dispatch, _storage = rto.run_rto(
        data_window,
        cap_gas_boiler,
        cap_heat_pump,
        cap_storage,
        CO2_PRICE,
        initial_storage_level=initial_level,
        horizon=rto.HORIZON,
        control_step=rto.CONTROL_STEP,
        n_known=rto.N_KNOWN,
    )

    window_days = len(dispatch) / 24

    # Fuel/electricity consumption from the known, fixed conversion
    # factors -- avoids needing to extract the gas/electricity bus flows
    # separately, since efficiency and COP are constants, not decisions.
    gas_consumed = dispatch["gas_boiler"] / rto.GAS_BOILER_EFFICIENCY
    elec_consumed = dispatch["heat_pump"] / rto.COP

    fuel_cost = (
        data_window["gas price"].iloc[: len(dispatch)] * gas_consumed
    ).sum() + rto.VAR_COST_GAS_BOILER * dispatch["gas_boiler"].sum()
    elec_cost = (
        data_window["el_spot_price"].iloc[: len(dispatch)] * elec_consumed
    ).sum() + rto.VAR_COST_HEAT_PUMP * dispatch["heat_pump"].sum()
    storage_cost = rto.VAR_COST_STORAGE * (
        dispatch["storage_charge"].sum() + dispatch["storage_discharge"].sum()
    )
    unserved_mwh = dispatch["unserved_heat"].sum()
    unserved_cost = rto.VOLL_COST_EUR_PER_MWH * unserved_mwh

    operation_cost_window = (
        fuel_cost + elec_cost + storage_cost + unserved_cost
    )
    co2_window = (
        rto.CO2_GAS * gas_consumed.sum() + rto.CO2_EL * elec_consumed.sum()
    )

    invest_cost = (
        SPEC_INV_GAS_BOILER * cap_gas_boiler
        + SPEC_INV_HEAT_PUMP * cap_heat_pump
        + SPEC_INV_STORAGE * cap_storage
    )
    daily_capex = epc(invest_cost) / 365
    daily_opex = operation_cost_window / window_days

    return {
        "cap_gas_boiler": cap_gas_boiler,
        "cap_heat_pump": cap_heat_pump,
        "cap_storage": cap_storage,
        "daily_cost": daily_capex + daily_opex,
        "daily_co2": co2_window / window_days,
        "unserved_heat_mwh": unserved_mwh,
        "daily_capex": daily_capex,
        "daily_opex": daily_opex,
    }


def load_cache():
    if CACHE_PATH.exists():
        return pd.read_csv(CACHE_PATH)
    return pd.DataFrame(columns=CACHE_COLUMNS)


def append_cache(row):
    write_header = not CACHE_PATH.exists()
    pd.DataFrame([row]).to_csv(
        CACHE_PATH, mode="a", header=write_header, index=False
    )


def find_cached(
    cache_df, cap_gas_boiler, cap_heat_pump, cap_storage, tol=1e-9
):
    if len(cache_df) == 0:
        return None
    match = (
        ((cache_df["cap_gas_boiler"] - cap_gas_boiler).abs() < tol)
        & ((cache_df["cap_heat_pump"] - cap_heat_pump).abs() < tol)
        & ((cache_df["cap_storage"] - cap_storage).abs() < tol)
    )
    rows = cache_df[match]
    return rows.iloc[0] if len(rows) else None


def make_objective(data_full, data_window, cache_df, metric="daily_cost"):
    """Wraps evaluate_candidate with on-disk caching, keyed on the exact
    capacity triple. cache_df is mutated in place as new points arrive so
    later calls in the same run see earlier ones too.
    """

    def objective(x):
        cap_gas_boiler, cap_heat_pump, cap_storage = x
        cached = find_cached(
            cache_df, cap_gas_boiler, cap_heat_pump, cap_storage
        )
        if cached is not None:
            return float(cached[metric])
        result = evaluate_candidate(
            cap_gas_boiler, cap_heat_pump, cap_storage, data_full, data_window
        )
        append_cache(result)
        cache_df.loc[len(cache_df)] = result
        return result[metric]

    return objective


if __name__ == "__main__":
    data_full = pd.read_csv(
        rto.DATA_DIR / "input_data.csv", sep=";", index_col=0, parse_dates=True
    )
    data_window = data_full.loc[rto.WINDOW_START : rto.WINDOW_END]

    # Boiler/heat pump: 75% of the original perfect-foresight capacity up
    # to the window's max hourly demand (beyond which more of either
    # alone can never help -- it could already cover the worst hour by
    # itself). Storage: 75%-200% of the original, no analogous natural cap.
    max_demand = data_window["heat demand"].max()
    space = [
        Real(0.75 * rto.CAP_GAS_BOILER_MW, max_demand, name="cap_gas_boiler"),
        Real(0.75 * rto.CAP_HEAT_PUMP_MW, max_demand, name="cap_heat_pump"),
        Real(
            0.75 * rto.CAP_STORAGE_MWH,
            2.0 * rto.CAP_STORAGE_MWH,
            name="cap_storage",
        ),
    ]

    cache_df = load_cache()
    print(f"Loaded {len(cache_df)} cached evaluation(s) from {CACHE_PATH}")
    x0 = (
        cache_df[
            ["cap_gas_boiler", "cap_heat_pump", "cap_storage"]
        ].values.tolist()
        or None
    )
    y0 = cache_df["daily_cost"].tolist() or None

    objective = make_objective(
        data_full, data_window, cache_df, metric="daily_cost"
    )

    N_CALLS = (
        50  # new evaluations to run THIS invocation, on top of any cached ones
    )
    n_initial_points = max(N_INITIAL - len(cache_df), 0)
    # gp_minimize requires n_calls >= n_initial_points; if the cache
    # already covers the full random-point budget and then some, this
    # run is 100% GP-guided (n_initial_points=0), which is valid.
    if n_initial_points > N_CALLS:
        n_initial_points = N_CALLS
    print(
        f"n_initial_points this run: {n_initial_points} "
        f"({len(cache_df)} of {N_INITIAL} target random points already cached)"
    )
    result = gp_minimize(
        objective,
        space,
        x0=x0,
        y0=y0,
        n_calls=N_CALLS,
        n_initial_points=n_initial_points,
        noise=1e-10,
        # No fixed random_state: with one, repeated invocations of this
        # script would deterministically regenerate the same "random"
        # initial points every time (confirmed directly) -- harmless
        # given the cache catches the duplicates, but it wastes part of
        # each run's n_calls budget on points already known rather than
        # genuinely new ones.
    )

    print(f"\nBest daily cost found: {result.fun:.2f} EUR/day")
    print(
        f"At capacities: gas_boiler={result.x[0]:.3f} MW, heat_pump={result.x[1]:.3f} MW, storage={result.x[2]:.3f} MWh"
    )
    best_cached = find_cached(cache_df, *result.x)
    if best_cached is not None:
        print(
            f"Daily CO2: {best_cached['daily_co2']:.3f} tCO2/day, unserved heat: {best_cached['unserved_heat_mwh']:.4f} MWh"
        )
    print(
        f"\nFull evaluation history (including cached points) in {CACHE_PATH}"
    )
