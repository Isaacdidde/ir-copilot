# Playbook: PowerShell Investigation

**Applies to:** Suspicious or encoded PowerShell execution (MITRE T1059.001)

## Trigger Conditions
- Sigma alert: "Suspicious PowerShell Encoded Command"
- EDR alert on powershell.exe with unusual parent process
- SIEM correlation of Event ID 4104 with suspicious script block content

## Investigation Steps

1. **Isolate the affected endpoint** from the network while preserving power state,
   to allow volatile evidence collection without further attacker action.
2. **Preserve volatile evidence**: capture a memory image and list of running processes
   before any remediation action.
3. **Collect Windows Event ID 4688** (process creation) to identify the full command
   line used to launch PowerShell.
4. **Review Sysmon Event ID 1** (process creation) for parent-child process relationships
   and the originating process (e.g., winword.exe, outlook.exe spawning powershell.exe
   is highly suspicious).
5. **Review PowerShell Operational Logs** (Event ID 4104, Script Block Logging) to
   recover the decoded script content if an encoded command was used.
6. **Identify the parent process** to determine the initial access vector (e.g., phishing
   attachment, malicious macro, exploited service).
7. **Check outbound network connections** made by the PowerShell process or its children
   for command-and-control (C2) beaconing or data exfiltration.
8. **Verify persistence mechanisms**: check scheduled tasks, registry Run keys, WMI
   subscriptions, and services created around the same timeframe.
9. **Escalate immediately if credential theft is observed** (e.g., LSASS access,
   Mimikatz-style behavior) — this requires coordinated containment and credential
   rotation.

## Containment Guidance
- Block identified C2 domains/IPs at the perimeter firewall and proxy.
- Disable compromised user accounts pending investigation.
- Consider network segmentation isolation for the affected subnet if lateral movement
  is suspected.

## Escalation Criteria
Escalate to the Incident Commander if any of the following are observed:
- Evidence of credential dumping (LSASS access)
- Lateral movement to additional hosts
- Data staging or exfiltration indicators
- Ransomware precursor activity (shadow copy deletion, mass file access)
