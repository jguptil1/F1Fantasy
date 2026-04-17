import fastf1

fastf1.Cache.enable_cache("data/cache/fastf1")

session = fastf1.get_session(2023, 1, "R")
session.load()

print(session.results.columns)
print(session.results[["FullName", "Abbreviation", "TeamName", "TeamId"]])