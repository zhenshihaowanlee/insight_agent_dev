# SwiftDC: Tail-Aware RDMA Congestion Control for Datacenter Fabrics

SIGCOMM 2026 paper draft.

This paper studies datacenter networking for large AI cluster networking deployments where RDMA over RoCE traffic competes with storage and RPC flows. The design combines congestion control, ECN feedback, and queue-aware scheduling to reduce p99 latency while preserving throughput.

The evaluation uses a prototype testbed, packet traces, and controlled experiments on a leaf-spine datacenter fabric. It compares against a baseline DCQCN deployment, includes ablation experiments, and reports p95 and p99 latency under incast and long-tail flow-size distributions.

Implementation constraints include SmartNIC offload limits, ASIC queue memory, PFC behavior, power, telemetry visibility, and rollout operations. The paper discusses reliability tradeoffs, failure handling, and network measurement requirements.
