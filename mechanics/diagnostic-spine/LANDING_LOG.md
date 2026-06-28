# Landing Log

- Initial skeleton: package created to route doctor and validation work.
- Extracted `doctor validate` file/latest/systemd/bridge probe collection into
  `abyss_machine.doctor_adapters`; CLI still binds live probes and writes
  latest/history.
- Extracted doctor report writes, machine-report compact artifact reads, and
  machine-report latest/history/markdown writes into `doctor_adapters`; CLI
  still collects live inputs and owns repair orchestration.
