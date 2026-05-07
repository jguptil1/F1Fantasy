import race_meetings
import race_sessions
import drivers
import constructor
import fantasy_tables
import placements
import elo_ingestion


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




def main():

    start_time = time.time()
    start_readable = datetime.now()

    print(f"Buid started at: {start_readable}")

    plan = {
        #"meetings": "build", #this update includes updating the dim_race table #FIXME: update does not work
        #"sessions":"build",
        #"drivers": "update",
        #"fantasy_tables": "update", #default build
        "constructors": "update",
        "placements": "update",
        "elo": "update" #doesnt matter, will always build
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

