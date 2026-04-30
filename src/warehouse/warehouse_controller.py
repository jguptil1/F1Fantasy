import fact_driver_race
import fact_constructor_race


def build_warehouse():

    #fact_driver_race
    fact_driver_race.build_fact_driver_race()
    fact_driver_race.validate_fact_driver_race()
    #fact_driver_race.read_fact_driver_race()

    #fact_driver_race
    fact_constructor_race.build_fact_constructor_race()
    fact_constructor_race.validate_fact_constructor_race()
    #fact_constructor_race.read_fact_constructor_race()








if __name__ == "__main__":
    build_warehouse()