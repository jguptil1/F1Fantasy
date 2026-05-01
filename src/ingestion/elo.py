import pandas as pd
from itertools import combinations


def apply_result_overrides(
    df: pd.DataFrame,
    overrides_df: pd.DataFrame | None = None,
    year_col: str = "year",
    race_col: str = "race_id",
    driver_col: str = "driver",
) -> pd.DataFrame:
    """
    Apply manual overrides for known official-result edge cases.

    Example overrides_df columns:
        year, race_num, driver,
        dns_override, dnf_override, dsq_override, nc_override, position_override

    Any override column that exists and is non-null will replace the base value.
    """
    out = df.copy()

    if overrides_df is None or overrides_df.empty:
        return out

    merge_cols = [year_col, race_col, driver_col]
    out = out.merge(overrides_df, on=merge_cols, how="left")

    override_map = {
        "dns": "dns_override",
        "dnf": "dnf_override",
        "dsq": "dsq_override",
        "nc": "nc_override",
        "position": "position_override",
    }

    for base_col, override_col in override_map.items():
        if override_col in out.columns and base_col in out.columns:
            out[base_col] = out[override_col].combine_first(out[base_col])

    drop_cols = [c for c in override_map.values() if c in out.columns]
    if drop_cols:
        out = out.drop(columns=drop_cols)

    return out


def prepare_elo_input(
    df: pd.DataFrame,
    year_col: str = "year",
    race_col: str = "race_id",
    driver_col: str = "driver",
    position_col: str = "position",
    dns_col: str = "dns",
    dnf_col: str = "dnf",
    dsq_col: str = "dsq",
    nc_col: str = "nc",
    overrides_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Prepare one-row-per-driver-per-race input for ELO.

    Rules
    -----
    - DNS: exclude from ELO
    - Classified finishers: use numeric position
    - NC with blank position: assign max_classified_position + 1
    - DNF with blank position: assign max_classified_position + 1
    - DSQ with blank position: assign max_classified_position + 2
    - Manual overrides supported for official classification corrections
    """

    out = df.copy()

    required_cols = [
        year_col, race_col, driver_col,
        position_col, dns_col, dnf_col, dsq_col, nc_col
    ]
    missing = [c for c in required_cols if c not in out.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Apply manual overrides first
    out = apply_result_overrides(
        df=out,
        overrides_df=overrides_df,
        year_col=year_col,
        race_col=race_col,
        driver_col=driver_col,
    )

    # Normalize booleans
    for col in [dns_col, dnf_col, dsq_col, nc_col]:
        out[col] = out[col].fillna(False).astype(bool)

    # Normalize position
    out[position_col] = pd.to_numeric(out[position_col], errors="coerce")

    # Exclude DNS entirely
    out = out[~out[dns_col]].copy()

    # Max classified finishing position in each race
    max_classified = out.groupby([year_col, race_col])[position_col].transform("max")

    # Build resolved position for ELO
    out["elo_position"] = out[position_col]

    # NC rows with blank position go behind classified finishers
    nc_mask = out[nc_col] & out["elo_position"].isna()
    out.loc[nc_mask, "elo_position"] = max_classified[nc_mask] + 1

    # DNF rows with blank position go behind classified finishers
    dnf_mask = out[dnf_col] & out["elo_position"].isna()
    out.loc[dnf_mask, "elo_position"] = max_classified[dnf_mask] + 1

    # DSQ rows with blank position go behind NC/DNF
    dsq_mask = out[dsq_col] & out["elo_position"].isna()
    out.loc[dsq_mask, "elo_position"] = max_classified[dsq_mask] + 2

    # If a row has position filled already, keep it
    # This is important if the source already gave an official final classified position

    unresolved = out[out["elo_position"].isna()].copy()
    if not unresolved.empty:
        print("\nWarning: unresolved rows dropped before ELO build:")
        print(
            unresolved[
                [year_col, race_col, driver_col, position_col, dns_col, dnf_col, dsq_col, nc_col]
            ].head(20)
        )
        out = out[out["elo_position"].notna()].copy()

    # Keep one row per driver per race
    out = (
        out.sort_values([year_col, race_col, driver_col, "elo_position"])
           .drop_duplicates(subset=[year_col, race_col, driver_col], keep="first")
           .reset_index(drop=True)
    )

    return out


def build_driver_elo(
    df: pd.DataFrame,
    year_col: str = "year",
    race_col: str = "race_num",
    driver_col: str = "driver",
    finish_col: str = "elo_position",
    init_elo: float = 1500.0,
    k_factor: float = 8.0,
    season_shrink: float = 0.75,
    inactivity_shrink: float = 0.75,
    return_matchups: bool = False,
):
    """
    Build driver ELO table race-by-race.

    Features
    --------
    - unseen drivers start at init_elo
    - season shrink at start of each new year
    - inactivity decay for drivers returning after missed full seasons
    - batched pairwise updates within each race
    """

    required_cols = [year_col, race_col, driver_col, finish_col]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    out = df.copy()
    out[finish_col] = pd.to_numeric(out[finish_col], errors="coerce")
    out = out.dropna(subset=[year_col, race_col, driver_col, finish_col]).copy()

    out = (
        out.sort_values([year_col, race_col, finish_col, driver_col])
           .reset_index(drop=True)
    )

    current_ratings = {}
    last_seen_year = {}
    previous_year = None

    race_outputs = []
    matchup_outputs = []

    for (year_val, race_val), race_df in out.groupby([year_col, race_col], sort=True):
        race_df = race_df.copy().reset_index(drop=True)

        dupes = race_df[driver_col].duplicated()
        if dupes.any():
            bad = race_df.loc[dupes, driver_col].tolist()
            raise ValueError(
                f"Duplicate {driver_col} rows found in race {(year_val, race_val)}: {bad}"
            )

        # season adjustment
        if previous_year is not None and year_val != previous_year:
            for drv in list(current_ratings.keys()):
                current_ratings[drv] = init_elo + season_shrink * (current_ratings[drv] - init_elo)

        # pre-race ratings with inactivity decay
        elo_before_map = {}
        for drv in race_df[driver_col]:
            if drv not in current_ratings:
                elo_before_map[drv] = init_elo
            else:
                rating = current_ratings[drv]
                last_year = last_seen_year.get(drv)
                seasons_absent = max(0, year_val - last_year - 1)

                if seasons_absent > 0:
                    rating = init_elo + (inactivity_shrink ** seasons_absent) * (rating - init_elo)

                elo_before_map[drv] = rating

        race_df["elo_before"] = race_df[driver_col].map(elo_before_map)

        delta_map = {drv: 0.0 for drv in race_df[driver_col]}

        # pairwise comparisons
        for i, j in combinations(race_df.index, 2):
            row_i = race_df.loc[i]
            row_j = race_df.loc[j]

            drv_i = row_i[driver_col]
            drv_j = row_j[driver_col]

            pos_i = row_i[finish_col]
            pos_j = row_j[finish_col]

            elo_i = row_i["elo_before"]
            elo_j = row_j["elo_before"]

            # lower position is better
            if pos_i < pos_j:
                s_i, s_j = 1.0, 0.0
            elif pos_i > pos_j:
                s_i, s_j = 0.0, 1.0
            else:
                s_i, s_j = 0.5, 0.5

            e_i = 1.0 / (1.0 + 10 ** ((elo_j - elo_i) / 400.0))
            e_j = 1.0 - e_i

            delta_i = k_factor * (s_i - e_i)
            delta_j = k_factor * (s_j - e_j)

            delta_map[drv_i] += delta_i
            delta_map[drv_j] += delta_j

            if return_matchups:
                matchup_outputs.append({
                    year_col: year_val,
                    race_col: race_val,
                    "driver_a": drv_i,
                    "driver_b": drv_j,
                    "pos_a": pos_i,
                    "pos_b": pos_j,
                    "elo_a_before": elo_i,
                    "elo_b_before": elo_j,
                    "expected_a": e_i,
                    "expected_b": e_j,
                    "actual_a": s_i,
                    "actual_b": s_j,
                    "delta_a": delta_i,
                    "delta_b": delta_j,
                })

        race_df["elo_delta"] = race_df[driver_col].map(delta_map)
        race_df["elo_after"] = race_df["elo_before"] + race_df["elo_delta"]

        # persist
        for _, row in race_df.iterrows():
            drv = row[driver_col]
            current_ratings[drv] = row["elo_after"]
            last_seen_year[drv] = year_val

        previous_year = year_val
        race_outputs.append(race_df)

    elo_df = pd.concat(race_outputs, ignore_index=True)

    if return_matchups:
        return elo_df, pd.DataFrame(matchup_outputs)

    return elo_df


def run_driver_elo_pipeline(
    placement_df: pd.DataFrame,
    overrides_df: pd.DataFrame | None = None,
    year_col: str = "year",
    race_col: str = "race_num",
    driver_col: str = "driver",
    position_col: str = "position",
    dns_col: str = "dns",
    dnf_col: str = "dnf",
    dsq_col: str = "dsq",
    nc_col: str = "nc",
    init_elo: float = 1500.0,
    k_factor: float = 8.0,
    season_shrink: float = 0.75,
    inactivity_shrink: float = 0.75,
    return_matchups: bool = False,
):
    """
    Full pipeline:
      1) apply manual result overrides
      2) resolve elo_position
      3) build ELO
    """

    elo_input = prepare_elo_input(
        df=placement_df,
        year_col=year_col,
        race_col=race_col,
        driver_col=driver_col,
        position_col=position_col,
        dns_col=dns_col,
        dnf_col=dnf_col,
        dsq_col=dsq_col,
        nc_col=nc_col,
        overrides_df=overrides_df,
    )

    return build_driver_elo(
        df=elo_input,
        year_col=year_col,
        race_col=race_col,
        driver_col=driver_col,
        finish_col="elo_position",
        init_elo=init_elo,
        k_factor=k_factor,
        season_shrink=season_shrink,
        inactivity_shrink=inactivity_shrink,
        return_matchups=return_matchups,
    )


def qa_driver_elo(
    elo_df: pd.DataFrame,
    year_col: str = "year",
    race_col: str = "race_num",
    driver_col: str = "driver",
):
    """
    Simple QA checks for final ELO table.
    """
    print("\n--- QA: max rows per driver-race ---")
    print(
        elo_df.groupby([year_col, race_col, driver_col]).size().max()
    )

    print("\n--- QA: missing elo_before ---")
    print(elo_df["elo_before"].isna().sum())

    print("\n--- QA: first race of first year ---")
    min_year = elo_df[year_col].min()
    first_race = elo_df.loc[elo_df[year_col] == min_year, race_col].min()
    print(
        elo_df.loc[
            (elo_df[year_col] == min_year) & (elo_df[race_col] == first_race),
            [year_col, race_col, driver_col, "elo_before"]
        ].sort_values(driver_col).head(30)
    )

    print("\n--- QA: race delta sums (should be near zero) ---")
    print(
        elo_df.groupby([year_col, race_col])["elo_delta"]
              .sum()
              .describe()
    )


# ------------------------------------------------------------
# EXAMPLE MANUAL OVERRIDES TABLE
# ------------------------------------------------------------

# Use this only for known official-result mismatches.
# Example shown for Austin 2023.
#
# overrides_df = pd.DataFrame({
#     "year": [2023, 2023],
#     "race_num": [19, 19],
#     "driver": ["HAM", "LEC"],
#     "dsq_override": [True, True],
#     "position_override": [None, None],
#     "dns_override": [None, None],
#     "dnf_override": [None, None],
#     "nc_override": [None, None],
# })


# ------------------------------------------------------------
# EXAMPLE USAGE
# ------------------------------------------------------------

# driver_elo = run_driver_elo_pipeline(
#     placement_df=placement_df,
#     overrides_df=overrides_df,   # or None
#     year_col="year",
#     race_col="race_num",
#     driver_col="driver",
#     position_col="position",
#     dns_col="dns",
#     dnf_col="dnf",
#     dsq_col="dsq",
#     nc_col="nc",
#     init_elo=1500,
#     k_factor=8,
#     season_shrink=0.75,
#     inactivity_shrink=0.75,
#     return_matchups=False
# )

# qa_driver_elo(driver_elo)
# driver_elo.head()