# DPUQueue: SmartNIC Offload for Tail Latency Control

OSDI-style systems paper draft.

This source studies SmartNIC and DPU offload for datacenter RDMA queue management. The mechanism offloads telemetry collection, ECN marking support, and queue-aware scheduling to the NIC.

Experiments use a physical testbed and compare against a host-based baseline. The report includes ablation, p99 latency, failure handling, rollback operations, compatibility issues, power limits, PCIe DMA overhead, and security isolation constraints.
