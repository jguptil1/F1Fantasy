import race_meetings
import race_sessions
import drivers
import constructor
import fantasy_tables
import placements
import elo_ingestion


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
        race_meetings.meetings_pipeline(update=False)
    elif plan.get("meetings") == "update":
        race_meetings.meetings_pipeline(update=True)

    #sessions
    if plan.get("sessions") == "build":
        race_sessions.sessions_pipeline(update=False)
    elif plan.get("sessions") == "update":
        race_sessions.sessions_pipeline(update=True)

    #drivers
    if plan.get("drivers") == "build":
        drivers.drivers_pipeline(update=False)
    elif plan.get("drivers") == "update":
        drivers.drivers_pipeline(update=True)

    #constructors
    if plan.get("constructors") == "build":
        constructor.constructors_pipeline(update=False)
    elif plan.get("constructors") == "update":
        constructor.constructors_pipeline(update=True)

    #Fantasy tables (driver/constructor points/prices)
    if plan.get("fantasy_tables") == "build":
        fantasy_tables.fantasy_tables_pipeline() #default to always build as row count is low enough
    elif plan.get("fantasy_tables") == "update":
        fantasy_tables.fantasy_tables_pipeline()

    #placement tables
    if plan.get("placements") == "build":
        placements.driver_placements_pipeline(update=False)
    elif plan.get("placements") == "update":
        placements.driver_placements_pipeline(update=True, year = 2026)


    #elo table
    if plan.get("elo") == "build":
        elo_ingestion.elo_pipeline(update=False)
    elif plan.get("elo") == "update":
        elo_ingestion.elo_pipeline(update=True)




def main():

    plan = {
        #"meetings": "update" #this update includes updating the dim_race table
        #"sessions":"update",
        #"drivers": "build",
        #"fantasy_tables": "build", #default build
        #"constructors": "update",
        #"placements": "build",
        "elo": "build" #doesnt matter, will always build
        
    }

    run_pipeline(plan)



if __name__ == "__main__":
    main()

