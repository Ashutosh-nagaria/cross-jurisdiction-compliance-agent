# Fictional company document, generated for this project

**KlioHR Systems Cross Border Data Transfer Mapping**

**1. Introduction**
Because KlioHR Systems operates a centralized SaaS architecture alongside distributed global support teams, personal data regularly crosses international borders. This document maps the primary data flows and identifies the specific legal mechanisms we rely upon to ensure these transfers comply with regional data protection laws.

**2. Primary Data Hosting Locations**
We utilize Amazon Web Services (AWS) to host our application environments. To minimize unnecessary data movement, customer tenants are provisioned in the region closest to their operational headquarters:

* **EU Customer Data:** Hosted in AWS Frankfurt, Germany.
* **US and LATAM Customer Data:** Hosted in AWS US-East (Northern Virginia).
* **APAC Customer Data:** Hosted in AWS Singapore.

**3. International Data Flows and Legal Mechanisms**

**Flow A: EU to India (Development and Support)**

* **Description:** Our tier 3 engineering support team is located in Bangalore, India. When an EU customer encounters a critical software bug, the India team may require temporary read access to logs hosted in the Frankfurt data center.
* **Legal Mechanism:** Because India is not currently subject to an adequacy decision by the European Commission, KlioHR relies on the latest Standard Contractual Clauses (SCCs). We have executed internal data transfer agreements between KlioHR Ireland and KlioHR India incorporating these clauses, supplemented by strict technical access controls and data masking.

**Flow B: Brazil to USA (Platform Processing)**

* **Description:** Brazilian customer accounts are hosted in the US-East data center. All user interactions from Brazil are routed to servers located in the United States.
* **Legal Mechanism:** Under the Brazilian LGPD, international transfers are permitted when utilizing standard contractual clauses approved by the national authority. KlioHR incorporates these LGPD specific clauses into all customer Data Processing Agreements for Latin American clients.

**Flow C: Singapore to USA (Corporate Aggregation)**

* **Description:** High level usage telemetry and aggregated financial reporting from the Singapore APAC headquarters are transferred daily to the Boston global headquarters for business intelligence analysis.
* **Legal Mechanism:** Transfers from Singapore to the United States are governed by an Intra Group Data Transfer Agreement. This agreement legally binds the US headquarters to protect the transferred data at a standard comparable to the protection mandated by the Singapore Personal Data Protection Act.

**Flow D: California to Global Offices (Remote Work)**

* **Description:** Data regarding KlioHR employees working in California may be accessed by human resources staff located in the London or Singapore offices for payroll and performance management.
* **Legal Mechanism:** No specific cross border transfer mechanisms are currently mandated by the CCPA for internal corporate HR data moving across state or national lines, provided the data is strictly used for internal business operations and appropriate security safeguards are maintained.
