# Post-Mortem Note: The 12-Day Validation Gap (July 18, 2026)

**A note from the Steward:** Between July 7 and July 18, the project experienced a seeming halt in LLM validation tasks (Session 4b). Initial reviews incorrectly diagnosed this as "resume-driven development" or strategic avoidance. 

The reality was a severe hardware-level crash: dynamic prompt caching (`--cache-ram`) in `llama.cpp` was causing high-bandwidth PCIe bursts that physically dropped GPU1 from the bus, corrupting orchestrator sessions and causing kernel-level hangs. 

While the hardware fault was being diagnosed and mitigated (via dynamic tensor splitting and `--cache-ram 0`), the team wisely pivoted to building the `skills/` knowledge base architecture—a task that required structural engineering rather than heavy LLM execution. 

With the Qwythos orchestrator stabilized, the repository documentation has been fully synchronized, and we are clear to resume the pipeline blockers. For full details on the hardware crash, see [`../calibration_forge/verification/pcie_instability_postmortem.md`](../calibration_forge/verification/pcie_instability_postmortem.md).
