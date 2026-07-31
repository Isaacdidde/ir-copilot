# Web Attack Incident Response Playbooks

---

# Playbook 1: SQL Injection (MITRE T1190)

**Applies to:** Suspected or confirmed SQL Injection against web applications.

## Trigger Conditions
- WAF/IDS alert for SQLi payloads (`UNION SELECT`, `' OR 1=1--`)
- Unexpected database errors or spikes in SQL queries
- Unauthorized database access or data exposure

## Immediate Actions (First 15 Minutes)
1. Block attacking IPs using WAF/firewall.
2. Capture HTTP requests and application logs.
3. Verify database integrity and active sessions.
4. Disable vulnerable endpoint if exploitation is active.
5. Notify Incident Commander.

## Investigation Steps
6. Review web server, WAF, and database logs.
7. Identify vulnerable parameter.
8. Determine data accessed or modified.
9. Check for privilege escalation or new DB accounts.
10. Preserve logs and malicious requests.

## Eradication and Recovery
- Patch vulnerable code using parameterized queries.
- Rotate exposed credentials.
- Validate database integrity.
- Monitor for repeat attempts.

## Escalation Criteria
- Sensitive data accessed.
- Administrative compromise.
- Multiple applications affected.

---

# Playbook 2: Cross-Site Scripting (XSS) (MITRE T1059)

**Applies to:** Stored, Reflected, or DOM-based XSS.

## Trigger Conditions
- WAF detects script injection.
- Reports of browser popups/session theft.
- Unexpected JavaScript execution.

## Immediate Actions
1. Remove malicious content.
2. Disable affected feature if necessary.
3. Invalidate user sessions.
4. Preserve application logs.
5. Notify application owner.

## Investigation Steps
6. Identify injection point.
7. Review affected accounts.
8. Check stolen session evidence.
9. Determine persistence.
10. Preserve payload samples.

## Eradication and Recovery
- Implement output encoding.
- Apply CSP.
- Validate input.
- Monitor logs.

## Escalation Criteria
- Admin sessions compromised.
- Stored XSS affecting many users.

---

# Playbook 3: Command Injection (MITRE T1059)

**Trigger Conditions**
- Unexpected shell execution.
- EDR detects cmd/bash spawned by web server.
- WAF command injection alerts.

## Immediate Actions
1. Isolate affected server.
2. Preserve memory if possible.
3. Stop malicious processes.
4. Capture logs.
5. Notify IR.

## Investigation Steps
6. Review process tree.
7. Identify vulnerable parameter.
8. Check persistence.
9. Determine attacker activity.
10. Preserve payloads.

## Eradication and Recovery
- Patch validation.
- Remove persistence.
- Rotate credentials.
- Monitor.

## Escalation Criteria
- Root/System compromise.
- Multiple hosts affected.

---

# Playbook 4: Local File Inclusion (LFI) (MITRE T1190)

## Trigger Conditions
- Requests containing `../`
- Sensitive file exposure.
- WAF traversal alerts.

## Immediate Actions
1. Block attack source.
2. Preserve logs.
3. Disable vulnerable endpoint.
4. Notify IR.
5. Review accessed files.

## Investigation Steps
6. Determine files exposed.
7. Check credential leakage.
8. Review web logs.
9. Identify exploitation chain.
10. Preserve evidence.

## Eradication and Recovery
- Canonicalize paths.
- Patch code.
- Rotate exposed secrets.

## Escalation Criteria
- Credential exposure.
- RCE achieved.

---

# Playbook 5: Remote File Inclusion (RFI)

## Trigger Conditions
- External file loading.
- Unexpected outbound HTTP requests.
- WAF RFI alerts.

## Immediate Actions
1. Block outbound connection.
2. Isolate host.
3. Capture logs.
4. Notify IR.
5. Preserve payload.

## Investigation Steps
6. Review loaded files.
7. Identify attacker infrastructure.
8. Determine persistence.
9. Check web shell installation.
10. Preserve artifacts.

## Eradication and Recovery
- Disable remote includes.
- Patch application.
- Remove web shells.

## Escalation Criteria
- Web shell found.
- Server compromise.

---

# Playbook 6: Insecure Direct Object Reference (IDOR)

## Trigger Conditions
- Access to unauthorized objects.
- Bug bounty/customer report.
- Authorization failures.

## Immediate Actions
1. Restrict endpoint.
2. Preserve logs.
3. Notify application owner.
4. Review affected users.
5. Begin impact assessment.

## Investigation Steps
6. Identify exposed records.
7. Review access logs.
8. Determine affected accounts.
9. Verify privilege abuse.
10. Preserve evidence.

## Eradication and Recovery
- Enforce authorization checks.
- Validate object ownership.
- Monitor.

## Escalation Criteria
- PII exposed.
- Regulatory impact.

---

# Playbook 7: Directory Traversal

## Trigger Conditions
- Requests with traversal sequences.
- Sensitive file downloads.
- WAF alerts.

## Immediate Actions
1. Block source.
2. Preserve logs.
3. Restrict endpoint.
4. Notify IR.
5. Review exposed files.

## Investigation Steps
6. Identify files accessed.
7. Review application behavior.
8. Check credential exposure.
9. Search persistence.
10. Preserve evidence.

## Eradication and Recovery
- Normalize paths.
- Patch validation.
- Rotate exposed credentials.

## Escalation Criteria
- System file disclosure.
- Chained compromise.

---

# Playbook 8: SSRF (MITRE T1190)

## Trigger Conditions
- Unexpected internal requests.
- Cloud metadata access.
- WAF SSRF alerts.

## Immediate Actions
1. Block outbound requests.
2. Preserve logs.
3. Disable vulnerable function.
4. Notify IR.
5. Check cloud credentials.

## Investigation Steps
6. Identify target services.
7. Review metadata access.
8. Determine credential theft.
9. Review cloud logs.
10. Preserve evidence.

## Eradication and Recovery
- Implement allowlists.
- Block metadata endpoint.
- Rotate cloud credentials.

## Escalation Criteria
- Cloud account compromise.
- Internal service access.

---

# Playbook 9: Authentication Brute Force / Credential Stuffing (MITRE T1110)

## Trigger Conditions
- Login spikes.
- Multiple failed logins.
- IAM alerts.

## Immediate Actions
1. Enable rate limiting.
2. Block malicious IPs.
3. Force MFA where possible.
4. Notify IR.
5. Preserve logs.

## Investigation Steps
6. Identify targeted accounts.
7. Review successful logins.
8. Check reused passwords.
9. Investigate lateral movement.
10. Preserve evidence.

## Eradication and Recovery
- Reset passwords.
- Enable MFA.
- Monitor authentication.

## Escalation Criteria
- Privileged accounts compromised.
- Large-scale account takeover.

---

# Playbook 10: Web Shell Deployment (MITRE T1505.003)

## Trigger Conditions
- Unexpected web scripts.
- EDR detects web server spawning shell.
- File integrity alerts.

## Immediate Actions
1. Isolate server.
2. Preserve memory and logs.
3. Block attacker IPs.
4. Notify IR.
5. Capture web shell.

## Investigation Steps
6. Identify upload vector.
7. Review process tree.
8. Search persistence.
9. Determine lateral movement.
10. Preserve artifacts.

## Eradication and Recovery
- Remove web shell.
- Patch upload vulnerability.
- Rotate credentials.
- Monitor closely.

## Escalation Criteria
- Multiple servers affected.
- Domain compromise.
- Evidence of data theft.
