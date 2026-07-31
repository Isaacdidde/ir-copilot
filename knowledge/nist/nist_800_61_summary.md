# NIST SP 800-61 — Computer Security Incident Handling Guide (Summary)

> Note: This is an original summary of the publicly available NIST incident handling
> guidance, written for internal knowledge-base use. It is not a verbatim reproduction.

## Phase 1: Preparation

Organizations should establish an incident response capability before incidents occur.
Key preparation activities include:

- Building and equipping an incident response team with defined roles and escalation paths
- Deploying detection and monitoring tooling (EDR, SIEM, network sensors)
- Maintaining an up-to-date asset inventory and network diagram
- Establishing communication plans, including out-of-band channels
- Preparing forensic toolkits and jump bags for on-site response
- Running tabletop exercises to validate the plan

## Phase 2: Detection and Analysis

This phase focuses on identifying that an incident has occurred and understanding its scope.

- Correlate alerts from multiple sources (EDR, firewall, DNS, proxy, SIEM) to confirm true positives
- Document initial indicators of compromise (IOCs): hashes, IPs, domains, file paths
- Determine the attack vector and estimate scope (single host vs. widespread)
- Assign a severity/priority level based on functional impact, information impact, and recoverability
- Maintain a detailed incident timeline and chain of custody for evidence

## Phase 3: Containment, Eradication, and Recovery

### Containment
- Short-term containment: isolate affected systems from the network to stop the bleeding
  (e.g., network isolation, disabling switch ports, blocking IOCs at the firewall)
- Evidence preservation: capture volatile data (memory, running processes, network
  connections) before powering down or reimaging a system
- Long-term containment: apply temporary fixes to allow systems to remain in production
  safely while a permanent remediation is prepared

### Eradication
- Remove malware, disable breached accounts, close exploited vulnerabilities
- Patch systems and rotate compromised credentials
- Identify and remove persistence mechanisms (scheduled tasks, run keys, services,
  startup folder entries, rogue accounts)

### Recovery
- Restore systems from known-good backups or clean rebuilds
- Validate system integrity before returning to production
- Increase monitoring on recovered systems for a defined observation period
- Confirm normal business operations have resumed

## Phase 4: Post-Incident Activity

- Conduct a lessons-learned meeting shortly after resolution
- Document what happened, what worked, and what did not
- Update playbooks, detection rules, and the incident response plan based on findings
- Track remediation action items to closure
- Retain evidence per legal/regulatory retention requirements

## Incident Prioritization Factors

1. **Functional impact** — effect on business operations (none, low, medium, high)
2. **Information impact** — sensitivity/type of data affected (none, privacy breach,
   proprietary breach, integrity loss)
3. **Recoverability** — effort and resources required to recover (regular, supplemented,
   extended, not recoverable)

## Containment Strategy Considerations

When selecting a containment strategy, responders should weigh:
- Potential damage to and theft of resources
- Need for evidence preservation
- Service availability requirements (e.g., production e-commerce systems)
- Time and resources needed to implement the strategy
- Effectiveness of the strategy (partial vs. full containment)
- Duration of the solution (emergency workaround vs. permanent fix)
