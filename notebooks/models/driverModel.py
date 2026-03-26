import pandas as pd
import numpy as np

# Others
from pathlib import Path
import joblib
import json

# Visualization
import matplotlib.pyplot as plt

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

#Light Gradient Boost Model
from lightgbm import LGBMRegressor

#Pre-processing pipeline modules
from sklearn.model_selection import train_test_split #for splitting our data into train/test
from sklearn.compose import ColumnTransformer #allows for different preprocessing for different column groups
from sklearn.pipeline import Pipeline #chains steps in order (preprocess, model), prevents leakage
from sklearn.impute import SimpleImputer #fills in missing values in a consistent manner, we should have none
from sklearn.preprocessing import OneHotEncoder, StandardScaler #categories are (1/0) columns, standardizes numeric features
from sklearn.metrics import mean_absolute_error, mean_squared_error #metrics for our error

#hyperparameter tuning
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

########################HELPER FUNCTIONS####################################

def get_working_directory():
    return Path(__file__).resolve().parents[2]


### Helper function #FIXME: look through this code and make sure it covers all bases. Look into april and summer break options

def get_current_week_race_num():

    today_dt = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    
    
    #calendar load
    working_directory = get_working_directory()
    file_path = working_directory / "data" / "clean" / "race_session_meeting_info.csv"
    calendar = pd.read_csv(file_path).drop(columns=["Unnamed: 0"])

    #getting the current race number
    today_dt = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    calendar["start_date"] = pd.to_datetime(calendar["start_date"], utc=True)
    next_race_int = calendar.loc[calendar["start_date"] >= today_dt, "race"].iloc[0]
    #getting current year

    today_dt = pd.to_datetime(today_dt)
    current_year = today_dt.year


    return next_race_int, current_year



#########################CORE FUNCTIONS###################################
 
def load_data():
    working_directory = get_working_directory()

    hist_path = working_directory / "data" / "semi-clean" / "hist_driver_points_df_v1.csv"
    curr_path = working_directory / "data" / "semi-clean" / "current_week_driver_points_df_v1.csv"
    elo_path = working_directory / "data" / "semi-clean" / "elo_table.csv"
    #placement_df_path = working_directory / "data" / "clean" / "placement_table.csv"
    #race_session_info_path = working_directory / "data" / "clean" / "race_session_meeting_info.csv"

    hist = pd.read_csv(hist_path).drop(columns=["Unnamed: 0"])
    curr = pd.read_csv(curr_path).drop(columns=["Unnamed: 0"])
    elo = pd.read_csv(elo_path).drop(columns=["Unnamed: 0"])
    
    hist = hist[~hist["constructor"].isna()].copy()
    hist = hist.dropna(subset=["points"]).copy()
    hist["time_id"] = hist["year"] * 100 + hist["race_num"]
    hist = hist.sort_values(["time_id", "driver"]).reset_index(drop=True)

    curr = curr.copy()
    elo = elo[["race_num", "year", "driver", "elo_before", "elo_after"]].copy()

    hist = hist.drop(columns=["start_date"], errors="ignore")
    curr = curr.drop(columns=["start_date"], errors="ignore")



    return hist, curr, elo

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
        married.groupby(["year", "race_num", "constructor"])["points_last_five_avg"]
        .transform(lambda x: x.sum() - x)
    )

    #driver strength independent of car strength (driver performance)
    #positive means that the driver is outperforming teammate
    #drivers outperforming their teammate tend to score more points

    married["teammate_delta_last5"] = (
        married["points_last_five_avg"] - married["teammate_points_last5"]
    )

    return married

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

    hist = hist.sort_values(["year", "race_num", "driver"]).reset_index(drop=True)
    hist = hist.drop(columns=["start_epoch"], errors="ignore")

    return curr, hist

def prepare_model_data(hist_df, n_test_races=4):
    target = "points"

    hist_df = hist_df.copy()
    hist_df = hist_df.sort_values(["time_id", "driver"]).reset_index(drop=True)

    unique_races = hist_df["time_id"].drop_duplicates().sort_values().tolist()
    test_races = unique_races[-n_test_races:]

    train_df = hist_df[~hist_df["time_id"].isin(test_races)].copy()
    test_df = hist_df[hist_df["time_id"].isin(test_races)].copy()

    X = hist_df.drop(columns=[target])
    y = hist_df[target]

    X_train = train_df.drop(columns=[target])
    y_train = train_df[target]

    X_test = test_df.drop(columns=[target])
    y_test = test_df[target]

    return X, y, X_train, X_test, y_train, y_test

def build_preprocessor(X):

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

    return preprocess

def get_models():
    models = {
        "Linear": LinearRegression(),
        "Ridge": Ridge(alpha=1.0, random_state=201),
        "Lasso": Lasso(alpha=.01, max_iter=20000, random_state=201),
        "ElasticNet": ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=20000, random_state=201),
        "RandomForest": RandomForestRegressor(n_estimators=500, random_state=201, min_samples_leaf=5),
        "LightGBM": LGBMRegressor(n_estimators = 150, learning_rate=0.03, num_leaves=5, min_child_samples=20, random_state=201, verbosity=-1)
    }
    return models   

def train_and_evaluate(preprocess, models, X, y, X_train, X_test, y_train, y_test): 

    tscv = TimeSeriesSplit(n_splits=5)

    results = []
    fitted_pipes = {}
    coef_tables = {}

    for name, model in models.items():
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
        fitted_pipes[name] = pipe

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
    ).sort_values("CV_MAE").reset_index(drop=True)

    best_name = results_df.loc[0, "model"]
    best_pipe = fitted_pipes[best_name]
    feature_cols = X.columns.tolist()

    return results_df, best_name, best_pipe, feature_cols, coef_tables

def predict_current_week(best_pipe, curr_df, feature_cols):
    current_week_df = curr_df.drop(columns=["points"])
    current_week_df.columns


    X_curr = pd.DataFrame(
        current_week_df.reindex(columns=feature_cols),
        columns=feature_cols
    )

    pred_points = best_pipe.predict(X_curr)

    # attach predictions
    current_week_preds = current_week_df.copy()
    current_week_preds["predicted_points"] = pred_points

    output_predictions = current_week_preds[
        ["year", "race_num", "driver", "price", "constructor", "predicted_points"]
    ].reset_index(drop=True)

    return output_predictions

def save_predictions(output_predictions, path):
    path = Path(path)
    #export the predictions

    if path.exists():
        in_file = pd.read_csv(path)
        combined = pd.concat([in_file, output_predictions], ignore_index=True)
    else:
        combined = output_predictions.copy()

    combined.to_csv(path, index=False)

def hyperparameterize_models(preprocess, X_train, y_train, X_test, y_test):
    tscv = TimeSeriesSplit(n_splits=5)

    search_spaces = {
        "Ridge": (
            Ridge(random_state=201),
            {"model__alpha": [0.01, 0.1, 1, 10, 100]}
        ),
        "ElasticNet": (
            ElasticNet(max_iter=20000, random_state=201),
            {
                "model__alpha": [0.001, 0.01, 0.1, 1],
                "model__l1_ratio": [0.1, 0.3, 0.5, 0.7, 0.9]
            }
        ),
        "RandomForest": (
            RandomForestRegressor(random_state=201, n_jobs=-1),
            {
                "model__n_estimators": [300, 500],
                "model__max_depth": [None, 8, 12, 20],
                "model__min_samples_leaf": [1, 3, 5]
            }
        ),
        "LightGBM": (
            LGBMRegressor(random_state=201, verbosity=-1),
            {
                "model__n_estimators": [100, 200, 400],
                "model__learning_rate": [0.02, 0.03, 0.05],
                "model__num_leaves": [7, 15, 31],
                "model__min_child_samples": [5, 10, 20]
            }
        )
    }

    tuning_results = []
    best_pipes = {}

    for name, (model, param_grid) in search_spaces.items():
        pipe = Pipeline([
            ("preprocess", preprocess),
            ("model", model)
        ])

        grid = GridSearchCV(
            estimator=pipe,
            param_grid=param_grid,
            cv=tscv,
            scoring="neg_mean_absolute_error",
            n_jobs=-1,
            refit=True
        )

        grid.fit(X_train, y_train)

        best_pipe = grid.best_estimator_
        best_pipes[name] = best_pipe

        cv_mae = -grid.best_score_
        test_pred = best_pipe.predict(X_test)
        test_mae = mean_absolute_error(y_test, test_pred)
        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))

        tuning_results.append({
            "model": name,
            "best_cv_mae": cv_mae,
            "test_mae": test_mae,
            "test_rmse": test_rmse,
            "best_params": grid.best_params_
        })

    tuning_results_df = pd.DataFrame(tuning_results).sort_values("best_cv_mae").reset_index(drop=True)

    best_name = tuning_results_df.loc[0, "model"]
    best_pipe = best_pipes[best_name]

    return tuning_results_df, best_name, best_pipe

def save_model_artifacts(best_pipe, best_name, feature_cols, cv_mae):
    out_dir = Path("models")
    out_dir.mkdir(exist_ok=True)

    model_path = out_dir / f"{best_name.lower()}_best_pipe.joblib"
    meta_path = out_dir / f"{best_name.lower()}_best_pipe_meta.json"

    joblib.dump(best_pipe, model_path)

    meta = {
        "model_name": best_name,
        "cv_mae": float(cv_mae),
        "features": feature_cols,
    }

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)


#######################Controller###################################

def run_driver_model(run_tuning=False):
    hist, curr, elo = load_data()
    married = create_married_dataframe(hist, curr, elo)
    curr_df, hist_df = divorce_dfs(married)

    X, y, X_train, X_test, y_train, y_test = prepare_model_data(hist_df)
    preprocess = build_preprocessor(X)
    models = get_models()

    results_df, best_name, best_pipe, feature_cols, coef_tables = train_and_evaluate(
        preprocess, models, X, y, X_train, X_test, y_train, y_test
    )

    final_model_name = best_name
    final_pipe = best_pipe

    tuning_results_df = None

    if run_tuning:
        tuning_results_df, tuned_best_name, tuned_best_pipe = hyperparameterize_models(
            preprocess, X_train, y_train, X_test, y_test
        )

        final_model_name = tuned_best_name
        final_pipe = tuned_best_pipe

    # refit on all historical data before predicting
    final_pipe.fit(X, y)

    output_predictions = predict_current_week(final_pipe, curr_df, feature_cols)

    current_week_race_num, current_year = get_current_week_race_num()
    working_directory = get_working_directory()




    output_path = (
        working_directory / "data" / "predictions" / "drivers" / f"driver_predictions_{current_year}.csv"
    )

    save_predictions(output_predictions, output_path)
    save_model_artifacts(
        best_pipe=final_pipe,
        best_name=best_name,
        feature_cols=feature_cols,
        cv_mae=results_df.loc[0, "CV_MAE"]
    )

    return {
        "results_df": results_df,
        "best_name": final_model_name,
        "best_pipe": final_pipe,
        "feature_cols": feature_cols,
        "coef_tables": coef_tables,
        "predictions": output_predictions,
    }



########################Supplementary Functions##################################

def naive_baseline_time_aware(hist_df, n_test_races=4):
    target = "points"

    hist_df = hist_df.copy()
    hist_df["time_id"] = hist_df["year"] * 100 + hist_df["race_num"]
    hist_df = hist_df.sort_values(["time_id", "driver"]).reset_index(drop=True)

    unique_races = hist_df["time_id"].drop_duplicates().sort_values().tolist()
    test_races = unique_races[-n_test_races:]

    train_df = hist_df[~hist_df["time_id"].isin(test_races)].copy()
    test_df = hist_df[hist_df["time_id"].isin(test_races)].copy()

    y_train = train_df[target]
    y_test = test_df[target]

    baseline_pred = y_train.mean()
    y_pred = np.repeat(baseline_pred, len(y_test))

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    return mae, rmse, baseline_pred


def get_old_baselines(race_num):
    hist, curr, elo = load_data()
    hist_week = hist[
    (hist["year"] < 2026) |
    ((hist["year"] == 2026) & (hist["race_num"] < race_num))
    ].copy()

    mae, rmse, baseline_pred = naive_baseline_time_aware(hist_week, n_test_races=4)
    
    
    return mae, rmse, baseline_pred



def create_correlation_matrix(hist_df): 

    numeric_df = hist_df.select_dtypes(include=["number"])
    corr_matrix = numeric_df.corr(method='pearson')

    return corr_matrix

def create_correlation_matrix_graph(corr_matrix):

    # Set up the Matplotlib figure
    plt.figure(figsize=(8, 6))

    # Create the Seaborn heatmap
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap='coolwarm', square=True)

    # Add a title
    plt.title('Correlation Matrix Heatmap')

    # Display the plot
    plt.show()

def coef_analysis(models, X_train, y_train):

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



if __name__ == "__main__":
    current_directory = get_working_directory()
    print(f"Current Directory: {current_directory}")
    outputs = run_driver_model()
    print(outputs["results_df"])
    print(f"Best model: {outputs['best_name']}")
    print(outputs["predictions"].head())
    
    
    #mae, rmse, baseline_pred = get_old_baselines(2)
    #print(f"Race 2 Baseline: MAE: {mae}, RMSE: {rmse}, baseline_pred: {baseline_pred}")
    #mae, rmse, baseline_pred = get_old_baselines(3)
    #print(f"Race 3 Baseline: MAE: {mae}, RMSE: {rmse}, baseline_pred: {baseline_pred}")




