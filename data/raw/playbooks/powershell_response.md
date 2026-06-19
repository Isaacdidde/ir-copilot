# Suspicious PowerShell Execution Response

## Detection criteria
Encoded or obfuscated PowerShell commands.
Event ID 4104 present.
Unexpected parent process.

## Immediate actions
1. Isolate affected host.
2. Review PowerShell logs.
3. Decode encoded commands.
4. Check outbound connections.

## Escalation criteria
Escalate if persistence, lateral movement, or C2 activity is identified.

## Related ATT&CK techniques
T1059.001
T1027
T1071.001