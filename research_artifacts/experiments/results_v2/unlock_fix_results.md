# Unlock fix results

Seed: 42
Synthetic cohort: C:\Users\woebe\Desktop\FINAL YEAR PROJECT FINAL\research_artifacts\experiments\results\cohort.csv
Logged database: C:\Users\woebe\Desktop\FINAL YEAR PROJECT FINAL\backend\dev.db

## Library versions

| Library | Version |
| --- | --- |
| Python | 3.13.2 |
| NumPy | 2.2.5 |
| SciPy | 1.15.3 |
| scikit-learn | 1.7.0 |
| SHAP | 0.53.0 |

## OLD versus NEW single-action validity

| Dataset | Logic | Check | Binding group | Goal | Conditions | Valid | Failed | Valid share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logged_database | OLD | single_action | uniquely_binding_conditions | stated_tier | 6 | 1 | 5 | 0.16666666666666666 |
| logged_database | NEW | single_action | uniquely_binding_conditions | achievable_tier | 6 | 5 | 1 | 0.8333333333333334 |
| synthetic_cohort | OLD | single_action | tied_conditions | stated_tier | 1613 | 0 | 1613 | 0.0 |
| synthetic_cohort | OLD | single_action | uniquely_binding_conditions | stated_tier | 842 | 383 | 459 | 0.45486935866983375 |
| synthetic_cohort | NEW | single_action | tied_conditions | achievable_tier | 1613 | 0 | 1613 | 0.0 |
| synthetic_cohort | NEW | single_action | uniquely_binding_conditions | achievable_tier | 842 | 790 | 52 | 0.9382422802850356 |

## OLD action bundle versus NEW joint-plan validity

| Dataset | Logic | Check | Goal | Capped profiles | Valid | Failed | Valid share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| logged_database | OLD | joint_actions | stated_tier | 6 | 1 | 5 | 0.16666666666666666 |
| logged_database | NEW | joint_plan | achievable_tier | 6 | 6 | 0 | 1.0 |
| synthetic_cohort | OLD | joint_actions | stated_tier | 1500 | 383 | 1117 | 0.25533333333333336 |
| synthetic_cohort | NEW | joint_plan | achievable_tier | 1500 | 1500 | 0 | 1.0 |

## Profiles with a lower achievable tier

| Dataset | Profiles | Capped profiles | Lower achievable tier | Share of capped profiles | Share of all profiles |
| --- | --- | --- | --- | --- | --- |
| logged_database | 21 | 6 | 0 | 0.0 | 0.0 |
| synthetic_cohort | 5000 | 1500 | 739 | 0.49266666666666664 | 0.1478 |

## Classified failures

Per-action and per-profile failure rows: 4865.
Details: [unlock_remaining_failures.csv](unlock_remaining_failures.csv)

| Dataset | Logic | Reason | Failures |
| --- | --- | --- | --- |
| logged_database | NEW | next_constraint | 1 |
| logged_database | OLD | boundary | 4 |
| logged_database | OLD | next_constraint | 6 |
| synthetic_cohort | NEW | next_constraint | 52 |
| synthetic_cohort | NEW | tie | 1613 |
| synthetic_cohort | OLD | boundary | 378 |
| synthetic_cohort | OLD | next_constraint | 378 |
| synthetic_cohort | OLD | non_actionable | 2433 |
