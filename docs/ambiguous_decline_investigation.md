# AMBIGUOUS_DECLINE F1=0.0000 Investigation

**Finding:** Structural Labeling/Threshold Artifact, Not a Bug.

## The Anomaly
During Track 1 Propensity Model training, the `AMBIGUOUS_DECLINE` slice consistently reports `F1 = 0.0000`.

## The Explanation
1. The ML model outputs continuous probabilities (`P(recoverable)`).
2. The `AMBIGUOUS_DECLINE` segment has a true empirical recovery rate of around 11% (`mean_predicted_prob: 0.1100`).
3. The binary evaluation metrics (Precision, Recall, F1) apply a hard decision threshold of `P >= 0.5` to calculate True/False Positives/Negatives.
4. Because `0.11 << 0.50`, the model correctly predicts `0` (Unrecoverable) for **every single instance** of `AMBIGUOUS_DECLINE`.
5. Since it never predicts `1` for this slice, True Positives = 0. Therefore, Precision = 0, Recall = 0, and F1 = 0.0000.

## Conclusion
This is a standard artifact of calculating binary thresholded metrics on a highly imbalanced slice where the base rate is far below the classification threshold. The continuous metric (`mean_predicted_prob`) correctly tracks the 11% rate, and the downstream optimizer (Track 3) uses this continuous probability—not the binary `0/1` threshold. The model is behaving exactly as designed.
