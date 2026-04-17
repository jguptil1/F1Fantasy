import race_meetings
import race_sessions
import drivers


#1. update or build race meetings table 

#2. update or build race sessions table 

#3. update or build drivers table


def api_tables_build():
    #race_meetings.meetings_pipeline(update=False)
    #race_sessions.sessions_pipeline(update=False)
    drivers.drivers_pipeline(update=False)



def api_tables_update():
    race_meetings.meetings_pipeline(update=True)
    race_sessions.sessions_pipeline(update=True)
    drivers.drivers_pipeline(update=True)



def run_api_pipeline(plan: dict):
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






def main():

    plan = {
       #"meetings": "update",
       # "sessions":"update",
        "drivers": "build"
    }

    run_api_pipeline(plan)



if __name__ == "__main__":
    main()

