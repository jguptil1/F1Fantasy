from src.reporting.build_rpt_driver_predictions_view import build_rpt_driver_predictions
from src.reporting.build_rpt_constructor_predictions_view import build_rpt_constructor_predictions
from src.reporting.build_rpt_driver_residuals_view import build_rpt_driver_residuals
from src.reporting.build_rpt_optimizer_runs_view import build_rpt_optimizer_runs
from src.reporting.build_rpt_model_evaluation import build_rpt_model_evaluation
from src.reporting.build_rpt_simulation_results import build_rpt_simulation_results


def main():
    build_rpt_driver_predictions()
    build_rpt_constructor_predictions()
    build_rpt_driver_residuals()
    build_rpt_optimizer_runs()
    build_rpt_model_evaluation()
    build_rpt_simulation_results()


if __name__ == "__main__":
    main()