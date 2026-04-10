import race_meetings
import race_sessions
import drivers


#1. update or build race meetings table 

#2. update or build race sessions table 

#3. update or build drivers table


def api_tables_build():
    race_meetings.meetings_pipeline(update=False)
    race_sessions.sessions_pipeline(update=False)
    drivers.drivers_pipeline(update=False)



def api_tables_update():
    race_meetings.meetings_pipeline(update=True)
    race_sessions.sessions_pipeline(update=True)
    drivers.drivers_pipeline(update=True)



def main():

    user_input = str(input("Would you like to build/rebuild (b) the api tables or would you like to update (u)?: "))
    
    if (user_input.lower() == "u"):
        api_tables_update()
    elif (user_input.lower() == "b"):
        api_tables_build()
    else:
        print("Invalid input")

if __name__ == "__main__":
    main()

