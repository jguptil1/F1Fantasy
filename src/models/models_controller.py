import pandas as pd

import driverModel
import constructorModel
import constructor_predictions


def main():

    #driverModel.run_test()
    
    driver_output = driverModel.run_driver_model(model_name="v1", model_version="1", feature_set_version="4", target_variable="fantasy_points", is_production_run=True, run_tuning = False)
    
    print("-------------")
    print("model results")
    print(driver_output["results_df"])
    print(f"Best model: {driver_output['best_name']}")
    print(driver_output["predictions"].head())


    
    
    constructor_output = constructorModel.run_constructor_model(model_name="v1_constructor", model_version="1", feature_set_version="2", target_variable="fantasy_points", is_production_run=True, run_tuning = False)
    print("-------------")
    print("model results")
    print(constructor_output["results_df"])
    print(f"Best model: {constructor_output['best_name']}")
    print(constructor_output["predictions"].head())



if __name__ == "__main__":
    
    main()
