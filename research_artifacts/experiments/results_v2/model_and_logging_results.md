# Model and logging results

Data source: SOURCE_TO_FILL.

## Original training-script inventory

| Original model | Original training script |
| --- | --- |
| rf_full | No original training script found |
| rf_reduced | backend/scripts/train_risk_tier_reduced_model.py |
| gb_full | No original training script found |
| gb_reduced | No original training script found |
| mlp_full | No original training script found |
| mlp_reduced | No original training script found |

## Test-split model metrics

Each confusion matrix uses tier labels in ascending order as rows (actual) and columns (predicted).

| Model | Old accuracy | New accuracy | Accuracy change | Old macro-F1 | New macro-F1 | Macro-F1 change | Prediction agreement | Old confusion matrix | New confusion matrix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rf_full | 0.793103 | 0.793103 | 0.000000 | 0.837143 | 0.837143 | 0.000000 | 1.000000 | labels=[1, 2, 3, 4, 5]; matrix=[[8,2,0,0,0],[0,23,3,0,0],[0,4,19,4,0],[0,0,5,14,0],[0,0,0,0,5]] | labels=[1, 2, 3, 4, 5]; matrix=[[8,2,0,0,0],[0,23,3,0,0],[0,4,19,4,0],[0,0,5,14,0],[0,0,0,0,5]] |
| rf_reduced | 0.781609 | 0.781609 | 0.000000 | 0.781423 | 0.781423 | 0.000000 | 1.000000 | labels=[1, 2, 3, 4, 5]; matrix=[[9,1,0,0,0],[2,21,3,0,0],[0,1,22,4,0],[0,0,6,13,0],[0,0,0,2,3]] | labels=[1, 2, 3, 4, 5]; matrix=[[9,1,0,0,0],[2,21,3,0,0],[0,1,22,4,0],[0,0,6,13,0],[0,0,0,2,3]] |
| gb_full | 0.850575 | 0.850575 | 0.000000 | 0.832831 | 0.832831 | 0.000000 | 1.000000 | labels=[1, 2, 3, 4, 5]; matrix=[[9,1,0,0,0],[1,23,2,0,0],[0,1,24,2,0],[0,0,3,14,2],[0,0,0,1,4]] | labels=[1, 2, 3, 4, 5]; matrix=[[9,1,0,0,0],[1,23,2,0,0],[0,1,24,2,0],[0,0,3,14,2],[0,0,0,1,4]] |
| gb_reduced | 0.747126 | 0.747126 | 0.000000 | 0.778558 | 0.778558 | 0.000000 | 1.000000 | labels=[1, 2, 3, 4, 5]; matrix=[[9,1,0,0,0],[2,19,5,0,0],[0,1,22,4,0],[0,0,8,11,0],[0,0,0,1,4]] | labels=[1, 2, 3, 4, 5]; matrix=[[9,1,0,0,0],[2,19,5,0,0],[0,1,22,4,0],[0,0,8,11,0],[0,0,0,1,4]] |
| mlp_full | 0.942529 | 0.942529 | 0.000000 | 0.935999 | 0.935999 | 0.000000 | 1.000000 | labels=[1, 2, 3, 4, 5]; matrix=[[10,0,0,0,0],[1,25,0,0,0],[0,0,25,2,0],[0,0,1,17,1],[0,0,0,0,5]] | labels=[1, 2, 3, 4, 5]; matrix=[[10,0,0,0,0],[1,25,0,0,0],[0,0,25,2,0],[0,0,1,17,1],[0,0,0,0,5]] |
| mlp_reduced | 0.758621 | 0.758621 | 0.000000 | 0.748095 | 0.748095 | 0.000000 | 1.000000 | labels=[1, 2, 3, 4, 5]; matrix=[[7,3,0,0,0],[1,22,3,0,0],[0,1,23,3,0],[0,0,7,9,3],[0,0,0,0,5]] | labels=[1, 2, 3, 4, 5]; matrix=[[7,3,0,0,0],[1,22,3,0,0],[0,1,23,3,0],[0,0,7,9,3],[0,0,0,0,5]] |

## SHAP faithfulness: old vs v2

| Model | SHAP metric | Old value | V2 value | Old tolerance/95% interval | V2 tolerance/95% interval |
| --- | --- | --- | --- | --- | --- |
| full_7items | additivity_mean_absolute_error | 7.158507739325764e-09 | 7.158507739325764e-09 | 6.294381340425313e-09 to 8.089906658076597e-09 | 6.294381340425313e-09 to 8.089906658076597e-09 |
| full_7items | additivity_within_tolerance_share | 1.0 | 1.0 | 1.0 to 1.0 | 1.0 to 1.0 |
| full_7items | rank_spearman_mean | 0.950714285714286 | 0.950714285714286 | 0.8205357142857151 to 1.0 | 0.8205357142857151 to 1.0 |
| full_7items | deletion_top_2_shap | 0.13122463105546345 | 0.13122463105546345 | 0.09964153976584317 to 0.16320421914648303 | 0.09964153976584317 to 0.16320421914648303 |
| full_7items | deletion_random_k | 0.043600763168358016 | 0.043600763168358016 | 0.0252904918733938 to 0.06256175895233049 | 0.0252904918733938 to 0.06256175895233049 |
| full_7items | deletion_lowest_2_shap | -0.018627665608501154 | -0.018627665608501154 | -0.032343796896162694 to -0.005534646403682247 | -0.032343796896162694 to -0.005534646403682247 |
| reduced_4items | additivity_mean_absolute_error | 1.3184827286155346e-08 | 1.3184827286155346e-08 | 1.2053390176507699e-08 to 1.4251868670939385e-08 | 1.2053390176507699e-08 to 1.4251868670939385e-08 |
| reduced_4items | additivity_within_tolerance_share | 1.0 | 1.0 | 1.0 to 1.0 | 1.0 to 1.0 |
| reduced_4items | rank_spearman_mean | 0.9514000000000001 | 0.9514000000000001 | 0.7999999999999999 to 1.0 | 0.7999999999999999 to 1.0 |
| reduced_4items | deletion_top_2_shap | 0.2720189951155254 | 0.2720189951155254 | 0.21746021016172049 to 0.3315580782367799 | 0.21746021016172049 to 0.3315580782367799 |
| reduced_4items | deletion_random_k | 0.1473714667457599 | 0.1473714667457599 | 0.1100584327790869 to 0.18415658743878133 | 0.1100584327790869 to 0.18415658743878133 |
| reduced_4items | deletion_lowest_2_shap | 0.02392723442152357 | 0.02392723442152357 | -0.0028614503196555913 to 0.05159585129958691 | -0.0028614503196555913 to 0.05159585129958691 |

## Trace completeness: before vs after

| Dataset | Before traces | Before gaps | After traces | After gaps | After complete |
| --- | --- | --- | --- | --- | --- |
| synthetic_cohort | 5000 | 0 | 5000 | 0 | 5000 |
| logged_database | 21 | 0 | 21 | 6 | 15 |

## Replay totals

| Dataset | Old replay mismatches | V2 replay mismatches |
| --- | --- | --- |
| synthetic_cohort | 0 | 0 |
| logged_database | 6 | 6 |

## Split and runtime

| Item | Value |
| --- | --- |
| Seed | 42 |
| Training rows | 347 |
| Test rows | 87 |
| Training-data SHA256 | 165bc88de8191ccad7c57ad226c2640b34f99866278cc091ffe602575046e022 |
| Python | 3.13.2 |
| NumPy | 2.2.5 |
| SciPy | 1.15.3 |
| scikit-learn | 1.7.0 |
| joblib | 1.5.1 |
| SHAP | 0.53.0 |
| Matplotlib | 3.10.1 |

## Source and execution

Original models without a training script are retrained by `backend/scripts/retrain_risk_models.py`.

Commands:

```powershell
python backend\scripts\retrain_risk_models.py
python research_artifacts\experiments\faithfulness.py --model-version old
python research_artifacts\experiments\faithfulness.py --model-version v2
python research_artifacts\experiments\model_logging_analysis.py
```
