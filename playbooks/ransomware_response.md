# Playbook: Ransomware Response

**Applies to:** Suspected or confirmed ransomware activity (MITRE T1486, T1490)

## Trigger Conditions
- Sigma alert: "Volume Shadow Copy Deletion via vssadmin or wmic"
- Mass file rename/encryption events detected by EDR or file integrity monitoring
- Ransom note discovered on one or more endpoints or file shares

## Immediate Actions (First 15 Minutes)

1. **Isolate affected endpoints from the network immediately** (disable network
   interface or switch port) to halt further encryption and lateral spread.
2. **Do not power off affected machines** unless instructed by forensics — memory may
   contain the encryption key or process artifacts.
3. **Identify patient zero** and the initial access vector using EDR process trees and
   email/web gateway logs.
4. **Check backup integrity** — confirm offline/immutable backups have not been
   tampered with or deleted.
5. **Notify the Incident Commander and activate the crisis communication plan.**

## Investigation Steps

6. Review process creation logs for vssadmin.exe / wmic.exe shadow copy deletion
   commands and the account/process that issued them.
7. Identify the ransomware family via file extension patterns, ransom note content,
   and any available hash/IOC matching.
8. Determine scope: enumerate all hosts and shares showing encryption activity.
9. Review authentication logs for compromised accounts used to move laterally
   (RDP, SMB, PsExec, WMI).
10. Preserve a sample of encrypted files and the ransom note for law enforcement /
    incident response vendor analysis.

## Eradication and Recovery
- Remove attacker persistence mechanisms across all affected hosts before restoring
  from backup.
- Rotate credentials for all accounts active in the environment during the incident
  window.
- Restore from the most recent known-clean backup after full eradication is confirmed.
- Monitor restored systems closely for re-infection indicators.

## Escalation Criteria
- Encryption observed on more than one host → activate full incident response team
- Domain controller or backup infrastructure affected → executive/legal notification
- Evidence of data exfiltration prior to encryption (double extortion) → legal and
  regulatory breach-notification review
