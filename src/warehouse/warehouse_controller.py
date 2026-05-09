import fact_driver_race
import fact_constructor_race

import pre_race_driver_features
import pre_race_constructor_features

import current_race_driver_features
import current_race_constructor_features


def build_warehouse(year, race_num):

    #fact_driver_race
    fact_driver_race.build_fact_driver_race()
    fact_driver_race.validate_fact_driver_race()


    #fact_constructor_race
    fact_constructor_race.build_fact_constructor_race()
    fact_constructor_race.validate_fact_constructor_race()


    #pre_race_driver_features
    pre_race_driver_features.build_pre_race_driver_features()
    pre_race_driver_features.validate_pre_race_driver_features()


    #pre_race_constructor_features
    pre_race_constructor_features.build_pre_race_constructor_features()
    pre_race_constructor_features.validate_pre_race_constructor_features()


    #current_week_driver_features
    current_race_driver_features.build_current_race_driver_features(year=year, race_num=race_num)
    current_race_driver_features.validate_current_race_driver_features(year=year, race_num=race_num)


    #current_week_constructor_features
    current_race_constructor_features.build_current_race_constructor_features(year=year, race_num=race_num)
    current_race_constructor_features.validate_current_race_constructor_features(year=year, race_num=race_num)




if __name__ == "__main__":
    build_warehouse(2026, 7)