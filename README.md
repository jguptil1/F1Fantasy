# Fantasy F1 Project

A data engineering, machine learning, and optimization project focused on predicting Formula 1 Fantasy points and building optimal fantasy lineups.

---

## Overview

This project ingests Formula 1 race and fantasy data, stores it in a local data warehouse, generates predictive features, trains machine learning models, and optimizes fantasy team selections under game constraints.

The project is designed as an end-to-end analytics pipeline with:

- ELT/data ingestion pipelines using API endpoints
- Centralized warehouse tables
- Feature engineering
- Predictive modeling
- Lineup optimization
- Simulation and evaluation workflows

---

## Current Features

- Automated race and fantasy data ingestion
- DuckDB-based local warehouse
- Driver and constructor prediction models
- Pre-race feature generation
- Fantasy lineup optimizer
- Historical prediction tracking
- Validation and data quality checks
- Monte Carlo lineup simulation
- Elo and momentum-based features

---

## Tech Stack

- Python
- DuckDB
- Pandas
- Scikit-learn
- LightGBM
- PuLP
- SQL

---

## Project Structure

```text
F1Fantasy/
│
├── data/ 
│   ├── database/
│   ├── clean/ (deprecated)
│   ├── myTeam/ (deprecated)
│   ├── other/ (deprecated)
│   ├── predictions/ (deprecated)
│   ├── raw/ (deprecated)
│   ├── semi-clean/ (deprecated)
│   └── staged/ (deprecated)
|
├── model_metadata/
|
├── notebooks/ (deprecated - holds MVP Work)
│
├── src/ (main folder directory used)
│   ├── admin/
│   ├── ingestion/
│   ├── models/
│   ├── optimizer/
│   ├── predictions/
│   ├── reporting/
│   ├── warehouse/
│
│
└── README.md
```

---

## Goals

- Build a production-style sports analytics pipeline
- Improve machine learning and data engineering skills
- Explore optimization and simulation techniques
- Develop risk-aware fantasy lineup construction
- Experiment with advanced racing analytics and telemetry

---

## Future Development

- Confidence interval and uncertainty modeling
- Telemetry-derived pace and degradation features
- Risk-adjusted lineup optimization
- Dashboarding and reporting
- Automated race-week pipelines

---

## Status

Active development project.

Current focus areas:
- Model enrichment
- Prediction validation
- Confidence/risk modeling

---

## Disclaimer

This project is for educational and research purposes only and is not affiliated with Formula 1 or the official F1 Fantasy platform.