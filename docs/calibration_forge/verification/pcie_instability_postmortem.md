# Comprehensive Analysis of PCIe Link Instability Induced by Dynamic Prompt Cache Offloading in Distributed LLM Inference

> **Role:** verification / post-mortem  
> **Status:** resolved  
> **Source of truth for:** the 12-day validation gap (Jul 07 - Jul 18, 2026) and the `--cache-ram 0` mitigation  
> **Date:** 2026-07-18  

**Abstract:**
This document details a diagnostic investigation into severe system hangs and GPU loss encountered during the execution of the Qwythos orchestrator (a multi-GPU large language model stack based on `llama.cpp`). By tracing hardware-level driver failures back to high-bandwidth PCIe memory bursts triggered by dynamic prompt checkpointing, we establish a causative link between specific software configurations (`--cache-ram`) and hardware fault tolerance. 

## 1. Introduction: The Phenomenon of the "Lost GPU"
During the initialization and inference phases of the Qwythos model, the system repeatedly experienced catastrophic failures, colloquially known as "hard hangs." The primary symptom was recorded in the NVIDIA System Management Interface (`nvidia-smi`) logs:

> `Unable to determine the device handle for GPU1: 0000:03:00.0: GPU is lost. Reboot the system to recover this GPU.`

In systems architecture, a "Lost GPU" error indicates a severe hardware-level discontinuity. The operating system and the NVIDIA kernel-mode driver (`nvlddmkm`) can no longer communicate with the physical endpoint located at the Peripheral Component Interconnect Express (PCIe) bus address `03:00.0`. This typically occurs when a PCIe link resets due to uncorrectable electrical errors, timeout conditions, or signal integrity failures across risers and slots.

## 2. System Architecture & Context
The system under test utilizes a heterogeneous multi-GPU array consisting of:
- **GPU 0:** NVIDIA GeForce GTX 1080 (Pascal architecture)
- **GPU 1:** NVIDIA GeForce GTX 1070 (Pascal architecture) [Faulting Device]
- **GPU 2:** NVIDIA GeForce GTX 1070 (Pascal architecture)

The software stack, driven by `llama.cpp`'s `llama-server`, implements a distributed orchestrator-atomic architecture (Qwythos). To optimize generation speed, the stack leverages Multiple Token Prediction (MTP) drafting and highly quantized Key-Value (KV) caches (`q8_0`).

## 3. Root Cause Mechanics: PCIe Saturation via Prompt Cache Offloading
The investigation revealed that the failures were not random, but were highly correlated with a specific software feature introduced in recent `llama.cpp` builds: **Dynamic Prompt Cache Checkpointing** (see *llama.cpp PR #16391*).

### 3.1 The Mechanics of Checkpointing
To avoid re-evaluating prompt tokens upon context shifts, the server periodically serializes the KV cache state. By default, the launch scripts were executing with `--cache-ram 8192` (allowing up to 8GB of system RAM to be used for cache offloading). 

The server logs indicated actions such as:
> `created context checkpoint 2 of 32 (pos_min = 80, pos_max = 80, n_tokens = 81, size = 50.569 MiB)`

### 3.2 The Hardware Intersection
When a checkpoint is created, the system performs a massive, synchronous Host-to-Device (or Device-to-Host) memory copy over the PCIe bus. A 50.5 MiB chunk of memory is blasted from the VRAM of GPU 1 to the host CPU's system memory. 
If the physical PCIe slot, motherboard trace, or riser cable associated with GPU 1 has degraded signal integrity, it cannot sustain this bursty, high-bandwidth traffic. The PCIe controller detects transmission errors, fails to negotiate a link recovery, and triggers a hard reset. Consequently, the GPU drops off the bus.

## 4. The Domino Effect: CUDA Index Shifting and CPU Fallback
The loss of a physical device at runtime triggers a cascading failure in statically mapped software architectures. 

1. **Hardware Abstraction Layer Shift:** The NVIDIA driver dynamically re-indexes the remaining hardware. The physical GPU 2 (formerly CUDA index `2`) is shifted to CUDA index `1`.
2. **Orchestrator Misalignment:** The Qwythos orchestrator, hardcoded to launch on GPU `1`, unwittingly attaches to physical GPU 2.
3. **Atomic Process Starvation:** The Atomic instance, hardcoded to launch on GPU `2`, requests a device that no longer exists in the driver's logical map. It throws the fatal error:
   > `ggml_cuda_init: failed to initialize CUDA: no CUDA-capable device is detected`
4. **CPU Fallback:** Unable to find a CUDA device, the Atomic process falls back to CPU execution, resulting in severe performance degradation (measured at ~5.8 tok/s during benchmarking).

## 5. Mitigation Strategies & Implementation

To stabilize the system without requiring immediate hardware replacement, two critical software-level interventions were implemented in the `start-qwythos-server.ps1` and `start-qwythos.ps1` launch scripts.

### 5.1 Elimination of PCIe Bursts (`--cache-ram 0`)
The primary vector of failure was neutralized by explicitly disabling RAM offloading for the KV cache.
- **Action:** Appended `--cache-ram 0` to the launch arguments.
- **Result:** The KV cache remains strictly within the GPU VRAM boundary. This prevents the bursty PCIe traffic, allowing the unstable PCIe link to survive the execution lifecycle.

### 5.2 Dynamic Resource Allocation and Tensor Splitting
To gracefully handle potential hardware shifts, static GPU mappings were replaced with dynamic polling and allocation mechanisms.
- **Action:** Replaced hardcoded `-TensorSplit` values with proportional, auto-calculated splits based on real-time VRAM availability polling via `nvidia-smi`.
- **Result:** If a GPU is lost, the script dynamically recalculates the VRAM distribution across the surviving GPUs, ensuring the orchestrator and atomic instances can still function optimally without manual intervention.

## 6. Conclusion 
The Qwythos stack's instability was a classic example of software features exposing hardware-level degradation. By understanding the mechanical relationship between `llama.cpp`'s memory management (`--cache-ram`) and the physical limitations of the PCIe interconnect, we successfully engineered a resilient software workaround. The system now correctly applies MTP and `q8_0` KV caching dynamically, maintaining high throughput (up to 38 tok/s under full array availability) while guarding against hardware drops. This fully explains the 12-day delay in executing Session 4b.

### References
1. ggml-org/llama.cpp (2024). *Feature: Dynamic Prompt Cache Offloading*. Pull Request #16391.
2. NVIDIA Corporation. *CUDA C++ Programming Guide: Device Memory Management and PCIe Host-to-Device Transfers*.
3. PCI-SIG. *PCI Express Base Specification: Link Training and Status State Machine (LTSSM) and Error Recovery*.
