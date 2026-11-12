"""Hybrid classical-quantum autoencoder (Section 9.4, unsupervised framing).

Pipeline: StandardScaler -> PCA (classical dimensionality reduction to QUANTUM_MAX_QUBITS)
-> quantum PQC (angle encoding + RealAmplitudes) whose per-qubit Z-expectation values are
trained to reproduce the PCA-reduced input on *normal* synthetic data only -> reconstruction
error (MSE between PCA-reduced input and quantum output) is the anomaly score.

Training happens offline (see training.py) and produces artifacts loaded at inference time —
never trained synchronously inside a request (Section 10).
"""

from dataclasses import dataclass

import numpy as np
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import EstimatorV2
from qiskit_machine_learning.neural_networks import EstimatorQNN

from app.ai.quantum.circuit import build_autoencoder_circuit, circuit_hash


@dataclass
class QuantumJobCost:
    qubit_count: int
    shot_count: int
    circuit_depth: int
    circuit_hash: str
    wall_clock_seconds: float


class QuantumAutoencoder:
    def __init__(self, num_qubits: int, reps: int = 2, shots: int = 1024):
        self.num_qubits = num_qubits
        self.shots = shots
        self.circuit, self.feature_params, self.weight_params, self.observables = (
            build_autoencoder_circuit(num_qubits, reps)
        )
        self._circuit_hash = circuit_hash(self.circuit)
        self._circuit_depth = self.circuit.depth()

        estimator = EstimatorV2(options={"run_options": {"shots": shots}})
        # RealAmplitudes composes as an opaque instruction block; Aer's assembler can't
        # execute it directly, so it must be transpiled (decomposed into basis gates)
        # before running. A preset pass manager targeting AerSimulator does this.
        pass_manager = generate_preset_pass_manager(optimization_level=1, backend=AerSimulator())
        self.qnn = EstimatorQNN(
            circuit=self.circuit,
            observables=self.observables,
            input_params=list(self.feature_params),
            weight_params=self.weight_params,
            estimator=estimator,
            pass_manager=pass_manager,
        )
        self.trained_weights: np.ndarray | None = None

    @property
    def num_parameters(self) -> int:
        return len(self.weight_params)

    def forward(self, X: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        """X: (n_samples, num_qubits) PCA-reduced, angle-scaled input.
        Returns reconstruction of shape (n_samples, num_qubits)."""
        w = weights if weights is not None else self.trained_weights
        if w is None:
            raise ValueError("Model has no trained weights loaded")
        return np.asarray(self.qnn.forward(X, w))

    def reconstruction_error(self, X: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        recon = self.forward(X, weights)
        return np.mean((recon - X) ** 2, axis=1)

    def cost_metadata(self, wall_clock_seconds: float) -> QuantumJobCost:
        return QuantumJobCost(
            qubit_count=self.num_qubits,
            shot_count=self.shots,
            circuit_depth=self._circuit_depth,
            circuit_hash=self._circuit_hash,
            wall_clock_seconds=wall_clock_seconds,
        )

    def load_weights(self, weights: np.ndarray) -> None:
        if weights.shape[0] != self.num_parameters:
            raise ValueError(
                f"Weight vector length {weights.shape[0]} does not match circuit's "
                f"{self.num_parameters} trainable parameters"
            )
        self.trained_weights = weights
