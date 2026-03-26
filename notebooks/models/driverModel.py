import pandas as pd
import numpy as np

# Others
from pathlib import Path

# Visualization
import matplotlib.pyplot as plt
import seaborn as sns


# Model Development Core Libs
from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer

#Scaling, Onehot Encoding
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer

#Standard Linear Regressors
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.metrics import mean_absolute_error, mean_squared_error

#RF Model
from sklearn.ensemble import RandomForestRegressor

#hyperparameter tuning
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit


def get_working_directory():
    working_directory = Path.cwd().parent.parent
    return working_directory

def get_dataframes():
    working_directory = get_working_directory()

    hist_driver_points_price = working_directory / "data" / "semi-clean" / "hist_driver_points_df_v1.csv"
    curr_week_driver_points_price = working_directory / "data" / "semi-clean" / "current_week_driver_points_df_v1.csv"
    elo_table = working_directory / "data" / "semi-clean" / "elo_table.csv"
    placement_df_path = working_directory / "data" / "clean" / "placement_table.csv"
    race_session_info_path = working_directory / "data" / "clean" / "race_session_meeting_info.csv"

    hist = pd.read_csv(hist_driver_points_price).drop(columns=["Unnamed: 0"])
    hist = hist[~hist["constructor"].isna()]
    hist = hist.dropna()
    curr = pd.read_csv(curr_week_driver_points_price).drop(columns=["Unnamed: 0"])
    elo = pd.read_csv(elo_table).drop(columns=["Unnamed: 0"])
    elo = elo[["race_num", "year", "driver", "elo_before", "elo_after"]]

    hist = hist.drop(columns =["start_date"])
    curr = curr.drop(columns =["start_date"])

    return hist, curr, elo




#FIXME: might need a more dynamic way to make this list rather than hardcoding
numeric_types = ['year', 'race_num', 'price', 'points', "month", 'start_epoch', 
                 'price_change_prev_race', 'price_rank', 'points_last_three_avg', 'points_last_five_avg', 
                 'ppm_last_3', 'ppm_last_5']


#helper function to replace the hard coded variable above FIXME: this will return a df not a list
def get_numeric_types(df):

    numeric_df = df.select_dtypes(include=["number"])
    return False


### Naive Baseline  #FIXME: Test to verify
def naive_baseline(hist_df): 
    hist_df['points'].skew()

    mean_points = np.mean(hist_df["points"])
    mean_points


    target = "points"

    X = hist_df.drop(columns=[target])
    y = hist_df[target]


    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    baseline_pred = y_train.mean()


    y_pred = np.repeat(baseline_pred, len(y_test))
    

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    #print("Baseline MAE:", mae)
    #print("Baseline RMSE:", rmse)

    return mae, rmse

#### Correlation Matrix #FIXME: Test to verify

def create_correlation_matrix(hist_df): 

    numeric_df = hist_df.select_dtypes(include=["number"])
    corr_matrix = numeric_df.corr(method='pearson')

    return corr_matrix


#### Correlation Matrix Graph #FIXME: Make this into a function of some sort
def create_correlation_matrix_graph(corr_matrix):

    # Set up the Matplotlib figure
    plt.figure(figsize=(8, 6))

    # Create the Seaborn heatmap
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap='coolwarm', square=True)

    # Add a title
    plt.title('Correlation Matrix Heatmap')

    # Display the plot
    plt.show()

### Marry the dataframes #FIXME: test this

def create_married_dataframe(hist, curr, elo):

    current_week_race_num, current_year = get_current_week_race_num()


    married = pd.concat([hist, curr], ignore_index=True)


    #FEATURE ENGINEERING
    married["momentum"] = (
        married["points_last_three_avg"] - married["points_last_five_avg"]
    ).fillna(0)  #null values (first row, will be filled with zero)

    married = married.drop(columns=["month", "price_rank", "points_last_three_avg", "ppm_last_3"])

    #merging elo to the married set
    married = married.merge(elo, how="left", on=["year", "race_num", "driver"])
    married = married.rename(
        columns={"elo_before": "driver_elo"}
    )


    latest_elo = (
        elo.sort_values(["driver", "year", "race_num"])
        .groupby("driver", as_index=False)
        .tail(1)[["driver", "elo_after"]]
        .rename(columns={"elo_after": "latest_elo_after"})
    )

    married = married.merge(
        latest_elo,
        on="driver",
        how="left"
    )

    mask_current = (
        (married["year"] == current_year) &
        (married["race_num"] == current_week_race_num) &
        (married["driver_elo"].isna())
    )

    married.loc[mask_current, "driver_elo"] = married.loc[
        mask_current, "latest_elo_after"
    ]

    # fill DNS / historical gaps
    married["driver_elo"] = married["driver_elo"].fillna(
        married["latest_elo_after"]
    )

    # remove helper column
    married = married.drop(columns=["latest_elo_after", "elo_after", "meeting_key_x", "meeting_key_y"])

    #MORE FEATURE ENGINEERING
    married['price_increase'] = (married['price_change_prev_race'] > 0).astype(int)
    married['price_decrease'] = (married['price_change_prev_race'] < 0).astype(int)


    # proxy for constructor performance (car performance)
    married["teammate_points_last5"] = (
        married.groupby(["constructor", "race_num"])["points_last_five_avg"]
        .transform(lambda x: x.sum() - x)
    )

    #driver strength independent of car strength (driver performance)
    #positive means that the driver is outperforming teammate
    #drivers outperforming their teammate tend to score more points

    married["teammate_delta_last5"] = (
        married["points_last_five_avg"] - married["teammate_points_last5"]
    )

    return married


### Divorce the two dataframes #FIXME: test this

def divorce_dfs(married_df):

    current_week_race_num, current_year = get_current_week_race_num()

    curr = married_df[(married_df["race_num"] == current_week_race_num) & (married_df["year"] == current_year)] #requires use of the get_current_week_race_num

    key_cols = ["year", "race_num", "driver"]

    hist = married_df.merge(
        curr[key_cols].drop_duplicates(),
        on=key_cols,
        how="left",
        indicator=True
    )
    hist = hist[hist["_merge"] == "left_only"].drop(columns="_merge")

    hist = hist.sort_values(["start_epoch", "race_num"])
    hist = hist.drop(columns=["start_epoch"])

    return curr, hist



### Helper function #FIXME: look through this code and make sure it covers all bases. Look into april and summer break options

def get_current_week_race_num():

    today_dt = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    
    
    #calendar load
    working_directory = get_working_directory()
    file_path = working_directory / "data" / "clean" / "race_session_meeting_info.csv"
    calendar = pd.read_csv(file_path).drop(columns=["Unnamed: 0"])

    #getting the current race number
    calendar["start_date"] = pd.to_datetime(calendar["start_date"], utc=True)
    #next_race_int = calendar.loc[calendar["start_date"] >= today_dt, "race"].iloc[0].astype(int)
    next_race_int = int(calendar.loc[calendar["start_date"] >= today_dt, "race"].iloc[0])
    #getting current year

    today_dt = pd.to_datetime(today_dt)
    year = today_dt.year


    return next_race_int, year



### Pre-processing the data #FIXME: make into a function

from sklearn.model_selection import train_test_split #for splitting our data into train/test
from sklearn.compose import ColumnTransformer #allows for different preprocessing for different column groups
from sklearn.pipeline import Pipeline #chains steps in order (preprocess, model), prevents leakage
from sklearn.impute import SimpleImputer #fills in missing values in a consistent manner, we should have none
from sklearn.preprocessing import OneHotEncoder, StandardScaler #categories are (1/0) columns, standardizes numeric features
from sklearn.metrics import mean_absolute_error, mean_squared_error #metrics for our error

#Standard Linear Regressors
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.metrics import mean_absolute_error, mean_squared_error
from lightgbm import LGBMRegressor
#RF Model
from sklearn.ensemble import RandomForestRegressor

def preprocess(hist_df):

    target = "points"
    X = hist_df.drop(columns=[target])
    y = hist_df[target]

    num_cols = X.select_dtypes(include="number").columns.tolist()
    cat_cols = X.select_dtypes(exclude="number").columns.tolist()

    numeric_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")), #takes the median value and imputes as necesarry
        ("scaler", StandardScaler())  # keep for linear models; remove for tree models
    ])

    categorical_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore"))
    ])

    preprocess = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, num_cols),
            ("cat", categorical_pipe, cat_cols),
        ],
        remainder="drop"
    )


    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=True, random_state=201
    )


    models = {
        "Linear": LinearRegression(),
        "Ridge": Ridge(alpha=1.0, random_state=201),
        "Lasso": Lasso(alpha=.01, max_iter=20000, random_state=201),
        "ElasticNet": ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=20000, random_state=201),
        "RandomForest": RandomForestRegressor(n_estimators=500, random_state=201, min_samples_leaf=5),
        "LightGBM": LGBMRegressor(n_estimators = 200, learning_rate=0.03, num_leaves=7, random_state=201, verbosity=-1)
    }

    return preprocess, models, X, y, X_train, X_test, y_train, y_test

### Model Pipeline #FIXME: turn into a function

from sklearn.model_selection import TimeSeriesSplit
from sklearn.model_selection import cross_val_score

def model_pipeline(preprocess, models, X, y, X_train, X_test, y_train, y_test):

    tscv = TimeSeriesSplit(n_splits=5)

    results = []
    coef_tables = {}

    for name, model in models.items():
        # Preprocessing for each model family
        pipe = Pipeline([
            ("preprocess", preprocess),
            ("model", model)
        ])

        cv_scores = cross_val_score(
            pipe,
            X,
            y,
            cv=tscv,
            scoring="neg_mean_absolute_error"
        )

        cv_mae = -cv_scores.mean()
        cv_mae_std = cv_scores.std()
        
        
        pipe.fit(X_train, y_train)
        

        train_pred = pipe.predict(X_train)
        test_pred = pipe.predict(X_test)


        train_mae = mean_absolute_error(y_train, train_pred)
        train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))

        test_mae = mean_absolute_error(y_test, test_pred)
        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))

        results.append((name, cv_mae, cv_mae_std, train_mae, train_rmse, test_mae, test_rmse))

        # 3) Coefs for linear models only
        mdl = pipe.named_steps["model"]
        if hasattr(mdl, "coef_"):
            feature_names = pipe.named_steps["preprocess"].get_feature_names_out()
            coefs = np.ravel(mdl.coef_)

            coef_tables[name] = (
                pd.DataFrame({"feature": feature_names, "coef": coefs})
                .assign(abs_coef=lambda d: d["coef"].abs())
                .sort_values("abs_coef", ascending=False)
            )

    results_df = pd.DataFrame(
        results,
        columns=["model", "CV_MAE", "CV_MAE_STD", "Train_MAE", "Train_RMSE", "Test_MAE", "Test_RMSE"]
    ).sort_values("CV_MAE")

    return results_df, mdl



### Coefficient Analysis #FIXME: turn into a function 

def coef_analysis(models, X_train, y_train, mdl):

    coef_tables = {}

    for name, model in models.items():
        pipe = Pipeline([("preprocess", preprocess), ("model", model)])
        pipe.fit(X_train, y_train)

        mdl = pipe.named_steps["model"]

        if hasattr(mdl, "coef_"):
            coefs = mdl.coef_.ravel()
            feature_names = pipe.named_steps["preprocess"].get_feature_names_out()

            coef_tables[name] = (
                pd.DataFrame({"feature": feature_names, "coef": coefs})
                .assign(abs_coef=lambda d: d["coef"].abs())
                .sort_values("abs_coef", ascending=False)
            )
        else:
            print(f"{name}: no coef_ (use feature_importances_ or permutation importance)")


    

    #coef_tables["ElasticNet"][coef_tables["ElasticNet"]["feature"].str.contains("elo", case=False)]
    return coef_tables

#### Hyper parameterization #FIXME: turn into a function

from sklearn.pipeline import Pipeline


def hyperparameterization(preprocess, model, X_train, X_test, y_train, y_test):

    tscv = TimeSeriesSplit(n_splits=5)

    search_spaces = {
        "Ridge": (
            Ridge(random_state=201),
            {"model__alpha": [0.01, 0.1, 1, 10, 100]}
        ),
        "Lasso": (
            Lasso(max_iter=20000, random_state=201),
            {"model__alpha": [0.0005, 0.001, 0.01, 0.1, 1]}
        ),
        "ElasticNet": (
            ElasticNet(max_iter=20000, random_state=201),
            {
                "model__alpha": [0.001, 0.01, 0.1, 1],
                "model__l1_ratio": [0.1, 0.5, 0.9]
            }
        ),
        "RandomForest": (
            RandomForestRegressor(random_state=201, n_jobs=-1),
            {
                "model__n_estimators": [300, 500],
                "model__max_depth": [None, 10, 20],
                "model__min_samples_leaf": [1, 3, 5]
            }
        )
    }

    tuning_results = []
    best_pipes = {}

    for name, (model, grid_params) in search_spaces.items():
        pipe = Pipeline([("preprocess", preprocess), ("model", model)])

        grid = GridSearchCV(
            pipe,
            param_grid=grid_params,
            cv=tscv,
            scoring="neg_mean_absolute_error",
            n_jobs=-1
        )

        grid.fit(X_train, y_train)

        best_pipes[name] = grid.best_estimator_
        cv_mae = -grid.best_score_

        test_pred = best_pipes[name].predict(X_test)
        test_mae = mean_absolute_error(y_test, test_pred)

        tuning_results.append([name, cv_mae, test_mae, grid.best_params_])

    pd.DataFrame(tuning_results, columns=["model", "best_cv_mae", "test_mae", "best_params"]).sort_values("best_cv_mae")


####saving the best pipe #FIXME: not quite sure what this is, how it is helpful or if it should be embedded in this function
import joblib
from pathlib import Path

out_dir = Path("models")
out_dir.mkdir(exist_ok=True)


best_pipe = grid.best_estimator_   # already fitted

joblib.dump(best_pipe, out_dir / "elasticnet_best_pipe.joblib")

out_dir = Path("models")
out_dir.mkdir(exist_ok=True)

# if you used GridSearchCV:
best_pipe = grid.best_estimator_   # already fitted

joblib.dump(best_pipe, out_dir / "elasticnet_best_pipe.joblib")
import json

meta = {
    "model_name": "ElasticNet",
    "best_params": grid.best_params_,
    "cv_mae": float(-grid.best_score_),
    "features": list(X.columns),
}
with open("models/elasticnet_best_pipe_meta.json", "w") as f:
    json.dump(meta, f, indent=2)


# 1) load fitted pipeline
best_pipe = joblib.load("models/elasticnet_best_pipe.joblib")

# (optional) load metadata so you know exactly what columns it expects
with open("models/elasticnet_best_pipe_meta.json", "r") as f:
    meta = json.load(f)

feature_cols = meta["features"]  # these are the raw columns from X.columns when you trained




###getting current week predictions #FIXME: turn this into a function

current_week_df = curr.drop(columns=["points"])
current_week_df.columns


X_curr = current_week_df.reindex(columns=feature_cols)

pred_points = best_pipe.predict(X_curr)

# attach predictions
current_week_preds = current_week_df.copy()
current_week_preds["predicted_points"] = pred_points

output_predictons = current_week_preds[["year", "race_num", "driver", "price", "constructor", "predicted_points"]]
output_predictons = output_predictons.reset_index(drop=True)


#export the predictions
in_file_path = working_directory / "data" / "predictions" / "drivers" / f"driver_predictions_2026.csv"
in_file = pd.read_csv(in_file_path)
in_file.columns

combined = pd.concat([in_file, output_predictons], ignore_index=True)
combined.to_csv(in_file_path, index=False)