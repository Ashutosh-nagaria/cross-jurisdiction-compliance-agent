# Fictional company document, generated for this project

**Data Subject Request (DSR) Handling Procedure**

**1. Purpose**
This internal standard operating procedure details how KlioHR Systems receives, verifies, processes, and fulfills Data Subject Requests (DSRs). This process ensures compliance with global privacy regulations, including GDPR, LGPD, CCPA, and others, while maintaining an internal Service Level Agreement (SLA) of 14 calendar days.

**2. Request Intake**
Individuals can submit a DSR through two primary channels:

* A dedicated web form available in the footer of the KlioHR corporate website.
* An email sent directly to privacy@kliohr.com.

When a request is received, it is automatically routed to our internal PrivacyOps ticketing system. A ticket is generated, and the 14 day internal SLA timer begins.

**3. Triage and Controller vs. Processor Check**
The Privacy Operations team first determines our legal role regarding the requested data.

* **If KlioHR is the Data Controller:** (e.g., the requester is a current corporate employee, a direct job applicant to KlioHR, or a marketing contact). We will process the request directly following the steps below.
* **If KlioHR is the Data Processor:** (e.g., the requester is an employee of a KlioHR enterprise customer). We cannot unilaterally alter or provide this data. The PrivacyOps team will notify the requester within 72 hours, redirecting them to their employer's HR department, and we will simultaneously alert the designated customer administrator of the inquiry.

**4. Identity Verification**
Before disclosing or deleting personal data, we must verify the requester's identity.

* For active platform users, verification is handled via a secure login prompt.
* For inactive users or external contacts, we send a verification email with a unique secure link. We may also request confirmation of recent interactions with KlioHR. Government ID is only requested as a last resort in high risk scenarios.

**5. Execution of Rights**
Once verified, the PrivacyOps team coordinates with relevant departments to execute the specific request:

* **Right to Access:** We run automated scripts against our primary databases to compile a structured, machine readable JSON file containing the user's data.
* **Right to Deletion:** We trigger a soft delete protocol. User identifiers are scrubbed from active production databases and third party marketing tools. Data remains in encrypted backups for 30 days before aging out completely.
* **Right to Correction:** We route the request to the relevant department head to update inaccurate records within the operational systems.

**6. Final Delivery and Closure**
The PrivacyOps agent reviews the compiled data or deletion confirmation log. A formal response is drafted using approved legal templates and sent to the requester via a secure, encrypted messaging portal. The ticket is then marked as closed, and a compliance log is generated for annual auditing purposes.
