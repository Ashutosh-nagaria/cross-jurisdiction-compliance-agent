"""
Ground Truth: the deterministic rule lookup (Chapter 9).

Best Effort and Chain of Custody both let an AI model generate the actual answer text.
Ground Truth does not. Every fact this system can state is hardcoded below
in LOOKUP_TABLE, copied directly from the 25 statute files in
corpus/statutes/, not generated or paraphrased by any model. The only
job an AI model does here is figure out which jurisdiction and theme a
question is asking about, so the right table row can be looked up. The
model never gets to invent, phrase, or embellish the actual legal fact.

This makes Ground Truth the most trustworthy of the three systems for a
narrow set of questions (exact numbers, exact citations), and the
least flexible: it cannot draft documents, compare jurisdictions in
prose, or handle anything outside its five jurisdictions and five
themes. It is meant to be compared against Best Effort and Chain of Custody in Chapter
10, not to replace them.
"""

import os
from typing import List

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL = "claude-sonnet-5"

VALID_JURISDICTIONS = [
    "eu-gdpr",
    "india-dpdp",
    "california",
    "brazil-lgpd",
    "singapore-pdpa",
]
VALID_THEMES = [
    "breach-notification",
    "lawful-basis-consent",
    "dsr-response-deadline",
    "dpo-requirement",
    "cross-border-transfer",
]

# --- The lookup table --------------------------------------------------
#
# Every value below was copied by hand from the actual text in
# corpus/statutes/, re-read directly from those files while building
# this table (Chapter 9), not recalled from memory or generated. Where
# the statute itself does not give a fixed number, has_fixed_number is
# False and the answer says so explicitly, instead of a number being
# invented to fill the gap.

LOOKUP_TABLE = {
    "eu-gdpr": {
        "breach-notification": {
            "answer": "The controller must notify the supervisory authority without undue delay and, where feasible, not later than 72 hours after becoming aware of the breach, unless the breach is unlikely to result in a risk to individuals.",
            "citation": "GDPR Article 33(1)",
            "source_file": "corpus/statutes/eu-gdpr/breach-notification.md",
            "has_fixed_number": True,
        },
        "lawful-basis-consent": {
            "answer": "Processing is lawful only if it meets one of six grounds, including consent, contract necessity, legal obligation, vital interests, public interest, or legitimate interests. Where consent is used, it must be demonstrable, freely given, and as easy to withdraw as to give.",
            "citation": "GDPR Article 6 and Article 7",
            "source_file": "corpus/statutes/eu-gdpr/lawful-basis-consent.md",
            "has_fixed_number": False,
        },
        "dsr-response-deadline": {
            "answer": "The controller must respond to a data subject request without undue delay and within one month of receipt. This period may be extended by two further months where necessary, given the complexity and number of requests.",
            "citation": "GDPR Article 12(3)",
            "source_file": "corpus/statutes/eu-gdpr/dsr-response-deadline.md",
            "has_fixed_number": True,
        },
        "dpo-requirement": {
            "answer": "A Data Protection Officer must be designated where processing is carried out by a public authority, or where core activities require regular and systematic monitoring of data subjects on a large scale, or large scale processing of special category or criminal data.",
            "citation": "GDPR Article 37(1)",
            "source_file": "corpus/statutes/eu-gdpr/dpo-requirement.md",
            "has_fixed_number": False,
        },
        "cross-border-transfer": {
            "answer": "Transfers to a third country are only allowed if the conditions in the transfer chapter are met, generally an adequacy decision, or appropriate safeguards such as Standard Contractual Clauses or binding corporate rules.",
            "citation": "GDPR Article 44 and Article 46",
            "source_file": "corpus/statutes/eu-gdpr/cross-border-transfer.md",
            "has_fixed_number": False,
        },
    },
    "india-dpdp": {
        "breach-notification": {
            "answer": "The Act does not state a fixed number of hours or days. It requires the Data Fiduciary to give the Board and each affected Data Principal intimation of the breach in such form and manner as may be prescribed.",
            "citation": "DPDP Act Section 8(6)",
            "source_file": "corpus/statutes/india-dpdp/breach-notification.md",
            "has_fixed_number": False,
        },
        "lawful-basis-consent": {
            "answer": "Personal data may be processed only with the Data Principal's consent or for certain legitimate uses. Where consent is the basis, it must be free, specific, informed, unconditional, and unambiguous, with a clear affirmative action, and must be as easy to withdraw as to give.",
            "citation": "DPDP Act Section 4 and Section 6",
            "source_file": "corpus/statutes/india-dpdp/lawful-basis-consent.md",
            "has_fixed_number": False,
        },
        "dsr-response-deadline": {
            "answer": "The Act does not state a fixed number of days. Grievances must be responded to within such period as may be prescribed, a figure the Act leaves to future rules rather than stating itself.",
            "citation": "DPDP Act Section 13(2)",
            "source_file": "corpus/statutes/india-dpdp/dsr-response-deadline.md",
            "has_fixed_number": False,
        },
        "dpo-requirement": {
            "answer": "A Data Protection Officer is required only for a Significant Data Fiduciary, a status the government assigns by notification, not a general requirement for every Data Fiduciary. The DPO must be based in India and report to the Significant Data Fiduciary's Board or similar governing body.",
            "citation": "DPDP Act Section 10(2)(a)",
            "source_file": "corpus/statutes/india-dpdp/dpo-requirement.md",
            "has_fixed_number": False,
        },
        "cross-border-transfer": {
            "answer": "Cross-border transfer is allowed by default. The Central Government may, by notification, restrict transfer of personal data to specific countries or territories outside India.",
            "citation": "DPDP Act Section 16",
            "source_file": "corpus/statutes/india-dpdp/cross-border-transfer.md",
            "has_fixed_number": False,
        },
    },
    "california": {
        "breach-notification": {
            "answer": "Disclosure of a security breach must be made within 30 calendar days of discovery or notification of the breach, subject to a delay for legitimate law enforcement needs.",
            "citation": "California Civil Code Section 1798.82(a)(2)(A)",
            "source_file": "corpus/statutes/california/breach-notification.md",
            "has_fixed_number": True,
        },
        "lawful-basis-consent": {
            "answer": "California follows an opt-out model rather than a GDPR-style opt-in consent regime. Businesses must inform consumers at or before collection of the categories and purposes of data collected, and whether it is sold or shared.",
            "citation": "California Civil Code Section 1798.100",
            "source_file": "corpus/statutes/california/lawful-basis-consent.md",
            "has_fixed_number": False,
        },
        "dsr-response-deadline": {
            "answer": "A business must disclose, correct, or delete information within 45 days of receiving a verifiable consumer request. This period may be extended once by an additional 45 days when reasonably necessary, with notice to the consumer.",
            "citation": "California Civil Code Section 1798.130(a)(2)(A)",
            "source_file": "corpus/statutes/california/dsr-response-deadline.md",
            "has_fixed_number": True,
        },
        "dpo-requirement": {
            "answer": "There is no general Data Protection Officer mandate under the CCPA/CPRA. California law does not require businesses to appoint a DPO.",
            "citation": "No statutory basis, structural gap in California law",
            "source_file": "corpus/statutes/california/dpo-requirement.md",
            "has_fixed_number": False,
        },
        "cross-border-transfer": {
            "answer": "California has no dedicated cross-border transfer mechanism like an adequacy decision. Whether moving data across a border counts as a sale or share depends on the definitions of those terms, and internal business use transfers generally do not qualify as a sale or share.",
            "citation": "California Civil Code Section 1798.140(ad) and (ah)",
            "source_file": "corpus/statutes/california/cross-border-transfer.md",
            "has_fixed_number": False,
        },
    },
    "brazil-lgpd": {
        "breach-notification": {
            "answer": "The LGPD does not state a fixed number of hours or days. The controller must notify the supervisory authority and data subjects within a reasonable term, as defined by the supervisory authority.",
            "citation": "LGPD Article 48, Paragraph 1",
            "source_file": "corpus/statutes/brazil-lgpd/breach-notification.md",
            "has_fixed_number": False,
        },
        "lawful-basis-consent": {
            "answer": "Personal data may be processed only under ten listed legal bases, including consent. Where consent is used, it must be given in writing or by another means proving the data subject's manifestation of will, refer to defined purposes, and be revocable at any time through a free and facilitated procedure.",
            "citation": "LGPD Article 7 and Article 8",
            "source_file": "corpus/statutes/brazil-lgpd/lawful-basis-consent.md",
            "has_fixed_number": False,
        },
        "dsr-response-deadline": {
            "answer": "Confirmation of existence of or access to personal data must be provided immediately in simplified form, or within up to fifteen days as a complete statement.",
            "citation": "LGPD Article 19, item II",
            "source_file": "corpus/statutes/brazil-lgpd/dsr-response-deadline.md",
            "has_fixed_number": True,
        },
        "dpo-requirement": {
            "answer": "The controller must indicate a data protection officer, called the Encarregado, whose identity and contact details must be publicly disclosed. This is stated as a general requirement for the controller, not limited to large scale processing.",
            "citation": "LGPD Article 41",
            "source_file": "corpus/statutes/brazil-lgpd/dpo-requirement.md",
            "has_fixed_number": False,
        },
        "cross-border-transfer": {
            "answer": "International transfer is permitted only in specific listed cases, including transfer to a country with an adequate level of protection, or where the controller demonstrates guarantees such as standard contractual clauses, binding corporate rules, or specific consent from the data subject.",
            "citation": "LGPD Article 33",
            "source_file": "corpus/statutes/brazil-lgpd/cross-border-transfer.md",
            "has_fixed_number": False,
        },
    },
    "singapore-pdpa": {
        "breach-notification": {
            "answer": "Where an organisation assesses a data breach as notifiable, it must notify the Personal Data Protection Commission as soon as practicable, and in any case no later than 3 calendar days after making that assessment.",
            "citation": "PDPA Section 26D(1)",
            "source_file": "corpus/statutes/singapore-pdpa/breach-notification.md",
            "has_fixed_number": True,
        },
        "lawful-basis-consent": {
            "answer": "An organisation must not collect, use, or disclose personal data unless the individual has given or is deemed to have given consent, or the collection, use, or disclosure is otherwise authorised by law. Consent is not validly given if it is obtained through false or misleading information, or made an unreasonable condition of service.",
            "citation": "PDPA Section 13 and Section 14",
            "source_file": "corpus/statutes/singapore-pdpa/lawful-basis-consent.md",
            "has_fixed_number": False,
        },
        "dsr-response-deadline": {
            "answer": "The Act does not state a fixed number of days. An organisation must provide an individual with their personal data and related disclosure information as soon as reasonably possible after a request.",
            "citation": "PDPA Section 21(1)",
            "source_file": "corpus/statutes/singapore-pdpa/dsr-response-deadline.md",
            "has_fixed_number": False,
        },
        "dpo-requirement": {
            "answer": "An organisation must designate one or more individuals responsible for ensuring the organisation complies with the Act, and must make the business contact information of at least one of them available to the public. This applies to organisations generally, not only to a designated subset.",
            "citation": "PDPA Section 11(3)",
            "source_file": "corpus/statutes/singapore-pdpa/dpo-requirement.md",
            "has_fixed_number": False,
        },
        "cross-border-transfer": {
            "answer": "An organisation must not transfer personal data outside Singapore except in accordance with requirements prescribed under the Act, ensuring a standard of protection comparable to the protection under the Act.",
            "citation": "PDPA Section 26(1)",
            "source_file": "corpus/statutes/singapore-pdpa/cross-border-transfer.md",
            "has_fixed_number": False,
        },
    },
}


# --- The only AI step: classification, not generation -----------------
#
# Claude never gets to state a legal fact in this system. Its only job
# is to read the question and say which (jurisdiction, theme) row of
# LOOKUP_TABLE the question is asking about. The actual answer text
# always comes from the table above, never from the model's response.


class LookupTarget(BaseModel):
    jurisdiction: str = Field(description="One of: eu-gdpr, india-dpdp, california, brazil-lgpd, singapore-pdpa")
    theme: str = Field(
        description="One of: breach-notification, lawful-basis-consent, dsr-response-deadline, dpo-requirement, cross-border-transfer"
    )


class QuestionClassification(BaseModel):
    targets: List[LookupTarget] = Field(
        description=(
            "Which jurisdiction and theme pairs this question is asking "
            "about. Include one pair per jurisdiction the question "
            "touches on, using the theme that matches what is being "
            "asked. Return an empty list if the question is not about "
            "any of these jurisdictions and themes."
        )
    )


_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def classify_question(question):
    """
    Asks Claude which jurisdiction and theme row (or rows, for a
    comparison question) this question is about, using a forced tool
    call so the response is data, not prose. Keeping this prompt short
    is deliberate: a longer version with extra caveats and edge case
    instructions was found, while building Chain of Custody, to sometimes
    trigger a refusal from the model for unrelated reasons. A short,
    direct prompt has proven reliable.
    """
    prompt = (
        "Classify which jurisdiction and theme this compliance question "
        "is about.\n\n"
        "Jurisdictions: eu-gdpr, india-dpdp, california, brazil-lgpd, "
        "singapore-pdpa\n"
        "Themes: breach-notification, lawful-basis-consent, "
        "dsr-response-deadline, dpo-requirement, cross-border-transfer\n\n"
        f"Question: {question}\n\n"
        "List every jurisdiction and theme pair this question is asking "
        "about. Return an empty list if none apply."
    )
    client = _get_anthropic_client()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        tools=[
            {
                "name": "classify_question",
                "description": "Selects which jurisdiction and theme pairs a compliance question is about.",
                "input_schema": QuestionClassification.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "classify_question"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if block.type == "tool_use":
            raw_targets = block.input.get("targets", [])
            break
    else:
        raw_targets = []

    # Safety net: only keep pairs that are actually rows in the table,
    # in case the model returns a jurisdiction or theme key that does
    # not exist.
    valid_targets = []
    for target in raw_targets:
        jurisdiction = target.get("jurisdiction")
        theme = target.get("theme")
        if jurisdiction in VALID_JURISDICTIONS and theme in VALID_THEMES:
            valid_targets.append((jurisdiction, theme))
    return valid_targets


def build_answer(targets):
    """
    Turns the classified (jurisdiction, theme) pairs into the final
    answer text, purely by copying values out of LOOKUP_TABLE. No
    model call happens here, this function only formats what the table
    already says.
    """
    if not targets:
        return (
            "This question is outside the scope of the five "
            "jurisdictions (eu-gdpr, india-dpdp, california, "
            "brazil-lgpd, singapore-pdpa) and five themes "
            "(breach-notification, lawful-basis-consent, "
            "dsr-response-deadline, dpo-requirement, "
            "cross-border-transfer) covered by this lookup table."
        )

    lines = []
    for jurisdiction, theme in targets:
        entry = LOOKUP_TABLE[jurisdiction][theme]
        lines.append(
            f"- {jurisdiction} / {theme}: {entry['answer']} "
            f"({entry['citation']}, Source: {entry['source_file']})"
        )
    return "\n".join(lines)


def answer_question(question):
    """
    Runs Ground Truth end to end: classify which table rows the question is
    about, then return exactly what those rows say. retrieved_chunks is
    returned as an empty list since this system does not use vector
    search at all, it looks answers up in a fixed table instead.
    """
    targets = classify_question(question)
    answer = build_answer(targets)
    return {
        "answer": answer,
        "retrieved_chunks": [],
        "matched_targets": [{"jurisdiction": j, "theme": t} for j, t in targets],
    }
