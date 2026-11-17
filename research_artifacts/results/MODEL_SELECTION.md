# Why the Random Forest is the production model

All numbers are measured on the same held-out test set: 87 of 434 respondents, a stratified 80/20 split with seed 42. All six models were trained on the same 347 rows.

## Results

| Model | 7-item accuracy | 4-item accuracy | Exact per-prediction SHAP |
|---|---|---|---|
| **Random Forest ★ (production)** | 79.3% | **78.2% (best)** | **Yes (TreeSHAP)** |
| Gradient Boosting | 85.1% | 74.7% | No: TreeSHAP rejects multiclass GB |
| MLP Neural Net | **94.3% (best)** | 75.9% | No: approximate KernelSHAP only |

## Why we chose it

1. **Quick mode (4 questions): the Random Forest is the most accurate model.**
   In this mode the model's prediction *is* the user's risk tier. The Random Forest scores 78.2%, against 75.9% for the MLP and 74.7% for Gradient Boosting. It also has the best weighted F1 (0.783) and quadratic-weighted κ (0.903).

2. **Every prediction must be explained exactly, and only tree ensembles allow that here.**
   The app shows each user *why* they got their tier, using per-question SHAP contributions (see `13_shap_example_production.png`).
   - SHAP's TreeExplainer computes exact values for a Random Forest in milliseconds and needs no reference data.
   - For multiclass Gradient Boosting, TreeExplainer raises *"only supported for binary classification"*. We have 5 tiers.
   - An MLP can only use KernelSHAP. That method samples feature combinations against a chosen background dataset, so the explanation is an estimate and depends on which sample was picked.

3. **Full mode (7 questions): accuracy matters less, because the model doesn't set the tier.**
   With all 7 answers, the tier comes from the deterministic weighted-sum formula, which is correct by definition. The Random Forest's job here is only to give a second opinion with an exact SHAP explanation. The MLP's higher 7-item accuracy (94.3%) therefore wouldn't change any user's tier, and it would cost us exact explanations.

4. **One algorithm and one explainer for both modes.**
   Quick and full mode share the same prediction and explanation code (`predict_with_explanation`), with only the model file swapped. That keeps explanations consistent across modes.

5. **Errors are never far off.**
   Every production prediction on the test set lands within ±1 tier of the true tier (100%). The Random Forest never mistakes a conservative investor for an aggressive one.

## Trade-offs to state openly

- On the 7-item set the Random Forest is the least accurate of the three (79.3% against 94.3% for the MLP). This is acceptable only because full mode uses the deterministic formula for the actual tier.
- In quick mode the Random Forest is not best on every metric. The MLP has higher balanced accuracy (77.4% against 76.1%), and Gradient Boosting has a higher macro ROC-AUC (0.949 against 0.938).
- The test set is small (87 people, with only 5 in tier 5), so differences of a few points are within noise.
- Future work: if an exact explainer for neural networks becomes acceptable (for example DeepSHAP on a framework model), the MLP is the strongest full-mode candidate.

## Suggested slide order

1. `01_class_distribution.png`: the data
2. `02_accuracy_comparison.png`: headline comparison
3. `00_summary_table.png`: all metrics
4. `04_confusion_matrix_grid.png`: where each model makes mistakes
5. `05_roc_comparison.png`: ranking quality
6. `14_model_selection_table.png`: **why the Random Forest**
7. `13_shap_example_production.png`: what the user actually sees
8. Backup: learning curves (`11`), feature importance (`09`, `10`), training curves (`07`, `08`, `08b`)
