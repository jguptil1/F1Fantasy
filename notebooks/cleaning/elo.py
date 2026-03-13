import pandas as pd


#need to read in the dataframe and should be agnostic as to type, which one is the important question


def add_elo_rating(
   df: pd.DataFrame,
   asset_type: str,
   baseline_year: int = 2023, 
   baseline_elo_rating: int = 1500
):
    """
    This is a repeatable function that will add a elo rating column to a dataframe with custom settings

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe that will manipulated
    asset_type : str
        weather the dataframe is focused on drivers or constructors
    baseline_year : int
        this defaults to 2023 but it is the first year in the dataset. Race 1 of this year will automatically be set to baseline_elo_rating
    baseline_elo_rating : int
        The baseline elo value 
    

    Returns
    -------
    df
    """

    ######### assuring correct types and format #######

    needed_driver_cols = {"year", "race", "driver", "placement"}
    needed_cons_cols = {"year", "race", "constructor"}

    if (asset_type.str.lower() != "driver") | (asset_type.str.lower() != "constructor"):
        raiseValueError(
            f"asset_type is declared neither 'driver' nor 'constructor'"
        )
    


    


    return False