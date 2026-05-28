import race_meetings
import race_sessions
import drivers
import constructor
import fantasy_tables
import placements
import elo_ingestion
import budget
import team_config
import qualifying


#processing speed
import time
from datetime import datetime


#1. update or build race meetings table 

#2. update or build race sessions table 

#3. update or build drivers table

# build fantasy tables (driver/constructor points and prices)


def api_tables_build():
    #race_meetings.meetings_pipeline(update=False)
    #race_sessions.sessions_pipeline(update=False)
    drivers.drivers_pipeline(update=False)
    

def api_tables_update():
    race_meetings.meetings_pipeline(update=True)
    race_sessions.sessions_pipeline(update=True)
    drivers.drivers_pipeline(update=True)
    

def run_pipeline(plan: dict):
    #meetings
    if plan.get("meetings") == "build":
        print("BUILDING MEETINGS")
        race_meetings.meetings_pipeline(update=False)
    elif plan.get("meetings") == "update":
        print("UPDATING MEETINGS")
        race_meetings.meetings_pipeline(update=True)

    #sessions
    if plan.get("sessions") == "build":
        print("BUILDING SESSIONS")
        race_sessions.sessions_pipeline(update=False)
    elif plan.get("sessions") == "update":
        print("UPDATING sessions")
        race_sessions.sessions_pipeline(update=True)

    #drivers
    if plan.get("drivers") == "build":
        print("BUILDING DRIVERS")
        drivers.drivers_pipeline(update=False)
    elif plan.get("drivers") == "update":
        print("UPDATING DRIVERS")
        drivers.drivers_pipeline(update=True)

    #constructors
    if plan.get("constructors") == "build":
        print("BUIDLING CONSTRUCTORS")
        constructor.constructors_pipeline(update=False)
    elif plan.get("constructors") == "update":
        print("UPDATING CONSTRUCTORS")
        constructor.constructors_pipeline(update=True)

    #Fantasy tables (driver/constructor points/prices)
    if plan.get("fantasy_tables") == "build":
        print("BUILDING FANTASY")
        fantasy_tables.fantasy_tables_pipeline() #default to always build as row count is low enough
    elif plan.get("fantasy_tables") == "update":
        print("UPDATING FANTASY")
        fantasy_tables.fantasy_tables_pipeline()

    #placement tables
    if plan.get("placements") == "build":
        print("BUILDING PLACEMENT")
        placements.driver_placements_pipeline(update=False)
    elif plan.get("placements") == "update":
        print("UPDATING PLACEMENT")
        placements.driver_placements_pipeline(update=True, year = 2026)

    #elo table
    if plan.get("elo") == "build":
        print("BUILDING ELO")
        elo_ingestion.elo_pipeline(update=False)
    elif plan.get("elo") == "update":
        print("UPDATING ELO")
        elo_ingestion.elo_pipeline(update=True)

    #budget table
    if plan.get("budget") == "build":
        print("BUILDING BUDGET")
        budget.budget_controller()
    elif plan.get("budget") == "update":
        print("UPDATING BUDGET")
        budget.budget_controller()

    #team conffiguration table
    if plan.get("teamConfiguration") == "build":
        print("BUILDING TEAM CONFIG")
        team_config.team_config_controller()
    elif plan.get("teamConfiguration") == "update":
        print("UPDATING TEAM CONFIG")
        team_config.team_config_controller()

    #qualifying
    if plan.get("qualifying") == "build":
        print("BUILDING QUALIFYING")
        qualifying.quali_results_pipeline(update=False)
    elif plan.get("qualifying") == "update":
        print("BUILDING QUALIFYING")
        qualifying.quali_results_pipeline(update=False)





def main():

    start_time = time.time()
    start_readable = datetime.now()

    print(f"Buid started at: {start_readable}")

    plan = {
        # "meetings": "build", #this update includes updating the dim_race table #FIXME: update does not work
        # "sessions":"update",
        # "drivers": "update",
        # "fantasy_tables": "build", #default build
        # "constructors": "build",
        # "placements": "update",
        #"elo": "build", #doesnt matter, will always build
         "budget": "build", #doesnt matter
        "teamConfiguration": "build", #doesnt matter
        # "qualifying": "build" #doesnt matter

    }

    run_pipeline(plan)

    end_time = time.time()
    end_readable = datetime.now()

    print(f"Process ended at: {end_readable}")

    runtime = end_time - start_time

    minutes = int(runtime // 60)
    seconds = int(runtime % 60)

    print(f"Runtime: {minutes}m {seconds}s")




if __name__ == "__main__":
    main()

