# Landing Log

- Initial skeleton: package created to route doctor and validation work.
- Extracted `doctor validate` file/latest/systemd/bridge probe collection into
  `abyss_machine.doctor_adapters`; CLI still binds live probes and writes
  latest/history.
- Extracted doctor report writes, machine-report compact artifact reads, and
  machine-report latest/history/markdown writes into `doctor_adapters`; CLI
  still collects live inputs and owns repair orchestration.
- Extracted doctor machine-report input collection into `doctor_adapters` through
  fakeable doctor, memory, nervous, AI policy, and artifact-read ports; CLI still
  binds concrete live functions and owns repair orchestration.
- Extracted doctor safe repair orchestration into `doctor_adapters` through
  fakeable semantic-maintenance and docs-mesh runners; CLI still computes live
  safe-action need and binds concrete refresh functions.
- Extracted doctor core status probe collection into `doctor_adapters` through
  fakeable platform, filesystem, topology validate, and stack-bridge validate
  ports; CLI still binds concrete live functions and owns deeper status probes.
- Extracted doctor power/cooling status probe collection into `doctor_adapters`
  through fakeable status-readmodel and systemd-unit ports; CLI still binds the
  concrete host status document and owns broader live status probes.
- Extracted doctor storage/process status probe collection into
  `doctor_adapters` through fakeable filesystem-facts, storage-policy,
  storage-hooks, and process-latest ports; CLI still binds concrete readers and
  owns broader live status probes.
- Extracted doctor snapshot/observability status probe collection into
  `doctor_adapters` through fakeable status-readmodel ports; CLI still binds the
  concrete host status document and owns broader live status probes.
- Extracted doctor dictation status probe collection into `doctor_adapters`
  through fakeable status-readmodel, service-state, and path-exists ports; CLI
  still binds concrete host status/service readers and owns broader live status
  probes.
- Extracted doctor AI/runtime status probe collection into `doctor_adapters`
  through fakeable AI facts, status, capability, TTS profile, policy, storage,
  runtime snapshot, report-latest, workload, and systemd-unit ports. CLI still
  binds concrete host functions and owns command rendering; local-AI modules
  remain the owner of runtime behavior.
