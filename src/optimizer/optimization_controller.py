import pandas as pd

import pre_race_weekend_optimizer
import optimization_tables


def main():
    
    #running the optimization engine on pre_race_weekend features
    #FIXME: should this have the capability to running different parameter settings? 
    drivers_selected_df, constructors_selected_df, summary_dict = pre_race_weekend_optimizer.pre_race_weekend_optimizer_controller()


    #saving optimization results
    optimization_tables.optimizer_tables_controller(drivers_selected_df, constructors_selected_df, summary_dict, fantasy_team_name="Guppies", is_production_run=False)
    
    




if __name__ == "__main__":
    main()
