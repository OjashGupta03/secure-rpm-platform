"""Quantum circuit construction for the hybrid autoencoder (Section 9.2, 9.4).

Default choice: angle encoding (simplest, good default for <=8 features per the spec)
composed with a small RealAmplitudes variational ansatz (1-2 entangling layers — kept
shallow to limit barren-plateau risk on a simulator with no real advantage to chase).
"""

import hashlib

from qiskit import QuantumCircuit
from qiskit.circuit import Parameter, ParameterVector
from qiskit.circuit.library import RealAmplitudes
from qiskit.quantum_info import SparsePauliOp


def build_autoencoder_circuit(
    num_qubits: int, reps: int = 2
) -> tuple[QuantumCircuit, ParameterVector, list, list[SparsePauliOp]]:
    """Returns (full_circuit, feature_params, weight_params, observables).

    Feature map: one RY(angle-encoded feature) rotation per qubit (angle encoding).
    Ansatz: RealAmplitudes(num_qubits, reps) — a standard shallow entangling PQC.
    Observables: single-qubit Z on each qubit, giving num_qubits real-valued outputs
    that serve as the quantum-processed "reconstruction" of the PCA-reduced input.
    """
    if not (1 <= num_qubits <= 8):
        raise ValueError("num_qubits must be between 1 and 8 (Section 9.2 qubit budget)")

    feature_params = ParameterVector("x", num_qubits)
    feature_map = QuantumCircuit(num_qubits, name="angle_encoding")
    for i in range(num_qubits):
        feature_map.ry(feature_params[i], i)

    ansatz = RealAmplitudes(num_qubits=num_qubits, reps=reps, name="ansatz")

    full_circuit = QuantumCircuit(num_qubits)
    full_circuit.compose(feature_map, inplace=True)
    full_circuit.compose(ansatz, inplace=True)

    observables = [
        SparsePauliOp.from_list([("I" * i + "Z" + "I" * (num_qubits - i - 1), 1.0)])
        for i in range(num_qubits)
    ]

    return full_circuit, feature_params, list(ansatz.parameters), observables


def circuit_hash(circuit: QuantumCircuit) -> str:
    """Stable hash of circuit structure for audit logging (Section 9A) — never the data
    run through it, just an identifier for which circuit variant executed. Built from
    static structural metadata rather than a QASM dump, since QuantumCircuit.qasm() is
    no longer available on Qiskit 1.0+."""
    structure = [
        circuit.num_qubits,
        circuit.depth(),
        tuple(instr.operation.name for instr in circuit.data),
    ]
    return hashlib.sha256(repr(structure).encode("utf-8")).hexdigest()[:16]
