# Dependency Security and Execution Policies

## Local First Approach
PulseLab handles proprietary electronic designs. As such, the default execution policy for the internal AI tools is local.
- **Ollama Default:** We actively prefer `localhost:11434` endpoints over Cloud API keys.
- **Data Exfiltration Risk:** Users working on sensitive circuits must not have their proprietary Netlists uploaded to external LLM servers without explicit intent.

## Subprocess Execution Policies
The `bridge/kicad_bridge.py` relies heavily on `subprocess.run` to orchestrate `kicad-cli`.
- Never pass unsanitized user inputs to subprocess arguments.
- Paths should be fully qualified or safely escaped using `os.path` and strictly isolated within the `output/` directory of the project.
- Always implement timeouts for subprocess executions so that infinite loops in the solver or CLI do not hard-lock the backend.

## Python Environment
Dependencies in PulseLab must be pinned explicitly in `requirements.txt`.
- Do not blindly upgrade `pygame` or `numpy` without regression testing the MNA solver, as matrix mathematical instability can occur across major version updates.
- Keep `openai` SDK up to date only if it does not break backwards compatibility with `Ollama` local endpoints.
