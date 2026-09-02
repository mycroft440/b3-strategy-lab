from __future__ import annotations

import math


def exact_positive_fold_sign_pvalue(positive_folds: int, folds: int) -> float:
    """One-sided exact sign-test p-value under P(positive fold)=0.5.

    This evaluates the out-of-sample selection *procedure*. It is intentionally
    not presented as a correction for the number of in-sample candidates tested.
    """

    if folds < 0 or positive_folds < 0 or positive_folds > folds:
        raise ValueError("positive_folds must satisfy 0 <= positive_folds <= folds")
    if folds == 0:
        return 1.0
    denominator = float(2**folds)
    tail = sum(math.comb(folds, k) for k in range(positive_folds, folds + 1))
    return min(1.0, tail / denominator)


def oos_evidence_summary(
    *,
    positive_folds: int,
    folds: int,
    alpha: float = 0.05,
    minimum_folds: int = 5,
) -> dict[str, object]:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    if minimum_folds <= 0:
        raise ValueError("minimum_folds must be positive")

    pvalue = exact_positive_fold_sign_pvalue(positive_folds, folds)
    sufficient_sample = folds >= minimum_folds
    passed = sufficient_sample and pvalue <= alpha
    return {
        "oos_sign_test_p_value": pvalue,
        "oos_sign_test_alpha": alpha,
        "oos_sign_test_minimum_folds": minimum_folds,
        "oos_sign_test_sufficient_sample": sufficient_sample,
        "oos_sign_test_passed": passed,
    }
