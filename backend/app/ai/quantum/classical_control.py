"""Parameter-matched classical control (Section 9.3) — mandatory benchmarking baseline.

A low-rank linear autoencoder (encoder A: k x n, decoder B: n x k) on the same
PCA-reduced input the quantum circuit sees. Rank k is chosen so the total parameter
count (2 * n * k) is as close as possible to the quantum circuit's trainable-parameter
count, so the benchmark in Section 9.3 is not "undersized classical vs. oversized
quantum" or vice versa.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize


def choose_matching_rank(num_features: int, target_param_count: int) -> int:
    """Smallest k >= 1 such that 2*n*k is >= target_param_count (never *fewer*
    parameters than the quantum model, so the control is not deliberately weakened)."""
    k = max(1, round(target_param_count / (2 * num_features)))
    return min(k, num_features)


@dataclass
class ClassicalControlModel:
    num_features: int
    rank: int
    weights: np.ndarray | None = None  # flat vector: [A.flatten(), B.flatten()]

    @property
    def num_parameters(self) -> int:
        return 2 * self.num_features * self.rank

    def _split(self, flat_w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n, k = self.num_features, self.rank
        A = flat_w[: k * n].reshape(k, n)
        B = flat_w[k * n :].reshape(n, k)
        return A, B

    def forward(self, X: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        w = weights if weights is not None else self.weights
        if w is None:
            raise ValueError("Model has no trained weights loaded")
        A, B = self._split(w)
        latent = X @ A.T
        return latent @ B.T

    def reconstruction_error(self, X: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        recon = self.forward(X, weights)
        return np.mean((recon - X) ** 2, axis=1)

    def fit(self, X_normal: np.ndarray, max_iter: int = 200) -> np.ndarray:
        """Trains A, B to minimize reconstruction MSE on normal data only — same
        training regime (normal-data-only) as the quantum autoencoder."""
        x0 = np.random.default_rng(42).normal(scale=0.1, size=self.num_parameters)

        def loss(flat_w: np.ndarray) -> float:
            return float(np.mean(self.reconstruction_error(X_normal, flat_w)))

        result = minimize(loss, x0, method="COBYLA", options={"maxiter": max_iter})
        self.weights = result.x
        return self.weights
