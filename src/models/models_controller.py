import driverModel

def main():

    driver_output = driverModel.run_driver_model(model_name="v1", model_version="1", feature_set_version="1", target_variable="fantasy_points", is_production_run=False, run_tuning = False)

    print("-------------")
    print("model results")
    print(driver_output["results_df"])
    print(f"Best model: {driver_output['best_name']}")
    print(driver_output["predictions"].head())




if __name__ == "__main__":
    main()
