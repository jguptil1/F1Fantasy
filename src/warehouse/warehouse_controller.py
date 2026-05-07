import fact_driver_race
import fact_constructor_race
import pre_race_driver_features

def build_warehouse():

    #fact_driver_race
    fact_driver_race.build_fact_driver_race()
    fact_driver_race.validate_fact_driver_race()


    #fact_driver_race
    fact_constructor_race.build_fact_constructor_race()
    fact_constructor_race.validate_fact_constructor_race()

    #pre_race_driver_features
    pre_race_driver_features.build_pre_race_driver_features()
    pre_race_driver_features.validate_pre_race_driver_features()








if __name__ == "__main__":
    build_warehouse()