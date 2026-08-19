"""
Chapter 11: a small Streamlit web app for the compliance agent.

Streamlit turns a plain Python script into a web page with buttons,
text boxes, and tables, without writing any HTML, CSS, or JavaScript.
This one file is the whole app: pick a system, ask a question, see the
answer and its citations, and for System B specifically, review and
actually approve or reject the answer before it counts as final.

Nothing in this file calls an AI model, a database, or the internet
just by starting the app or opening the page. A call only happens once
someone actually submits a question, which is the point where using
this app starts to cost a small amount of real API money.

Run this with: streamlit run app.py
"""

import streamlit as st

from src import system_a, system_c
from src.rate_limit import DAILY_LIMIT, get_remaining_today, try_use_budget
from src.system_b import resume_with_decision, start_question

st.set_page_config(page_title="Cross Jurisdiction Compliance Agent", layout="wide")

st.title("Cross Jurisdiction Compliance Agent")

with st.expander("About this project", expanded=True):
    st.markdown(
        """
This project answers data privacy compliance questions across five
jurisdictions (the European Union, India, California, Brazil, and
Singapore), and cites the exact statute section behind every answer.

Three different approaches are built side by side here, so they can be
compared honestly instead of assuming one of them is simply the best.

**System A** retrieves the most relevant statute text for a question
and lets an AI model write the answer in its own words, citing where
each fact came from.

**System B** is a slower, more careful multi step agent. It figures
out which country a question is about, searches each relevant
country's text separately, pulls out individual factual claims,
checks every claim word for word against the real statute text, and
pauses for a human to approve the answer before it is treated as
final.

**System C** does not generate any legal fact at all. It uses an AI
model only to work out which country and topic a question is about,
then looks up the answer in a fixed table built directly from the
real statute text. It cannot phrase an answer creatively, but it also
cannot invent a wrong number.

No single approach wins at everything. Asking a question below calls
a real AI model, and for Systems A and B, a real vector search
database too, so each question asked here has a small real cost.
Nothing is called just by loading this page.

This is a public demo, so it shares one small daily budget across
every visitor combined, not a separate allowance for each person.
Once that budget runs out, the app stops answering new questions
until it resets the next day.
"""
    )

SYSTEM_NAMES = ["System A", "System B", "System C"]

remaining_today = get_remaining_today()
st.info(
    f"Shared daily budget: {remaining_today} of {DAILY_LIMIT} question(s) "
    "left today, across all visitors. Comparing all three systems at once "
    "uses three of these in a single click."
)


def render_citations(system_name, result):
    """Shows where an answer's facts came from, in whatever form that system tracks it."""
    if system_name == "System A":
        chunks = result.get("retrieved_chunks", [])
        if chunks:
            st.caption("Sources consulted:")
            for chunk in chunks:
                st.caption(f"- {chunk['relative_path']}")
    elif system_name == "System B":
        verified = result.get("verified_claims", [])
        rejected = result.get("rejected_claims", [])
        if verified:
            st.caption(f"Verified claims used in this answer ({len(verified)}):")
            for claim in verified:
                st.caption(f"- {claim['claim']} (Source: {claim['source_file']})")
        if rejected:
            st.caption(
                f"{len(rejected)} additional claim(s) were extracted but rejected "
                "because their quoted text did not match the source file word for "
                "word, so they were left out."
            )
    elif system_name == "System C":
        targets = result.get("matched_targets", [])
        if targets:
            st.caption("Looked up from the fixed table:")
            for target in targets:
                st.caption(f"- {target['jurisdiction']} / {target['theme']}")


tab_single, tab_compare = st.tabs(["Ask one system", "Compare all three"])

# --- Ask one system ------------------------------------------------------

with tab_single:
    st.write(
        "Pick a system, type a question, and submit it. System B will "
        "pause partway through and ask you to approve or reject its "
        "answer before it is finalized, the same way a real deployment "
        "would wait for a compliance reviewer."
    )

    system_choice = st.selectbox("Which system do you want to ask?", SYSTEM_NAMES)
    question = st.text_input("Your question", key="single_question")
    ask_clicked = st.button("Ask", key="ask_single")

    if ask_clicked and question:
        if not try_use_budget(1):
            st.error(
                "Today's shared question budget has been used up by visitors "
                "to this demo. Please come back after it resets, at midnight "
                "UTC."
            )
        elif system_choice == "System A":
            with st.spinner("Asking System A..."):
                result = system_a.answer_question(question)
            st.session_state["single_result"] = {
                "system": "System A",
                "result": result,
                "awaiting_approval": False,
            }
        elif system_choice == "System C":
            with st.spinner("Asking System C..."):
                result = system_c.answer_question(question)
            st.session_state["single_result"] = {
                "system": "System C",
                "result": result,
                "awaiting_approval": False,
            }
        else:
            with st.spinner("Asking System B, this takes longer than the other two..."):
                pending = start_question(question)
            st.session_state["single_result"] = {
                "system": "System B",
                "pending": pending,
                "awaiting_approval": True,
            }

    if "single_result" in st.session_state:
        data = st.session_state["single_result"]
        st.divider()

        if data["awaiting_approval"]:
            pending = data["pending"]

            with st.container(border=True):
                st.subheader(":material/pending_actions: Human approval required")
                st.write(
                    "System B has verified its claims against the real statute "
                    "text, but nothing is final yet. Review what it found below, "
                    "then approve or reject it."
                )

                verified = pending["verified_claims"]
                rejected = pending["rejected_claims"]

                if verified:
                    st.write(f"Verified claims ({len(verified)}), ready to release if approved:")
                    for claim in verified:
                        st.write(f"- {claim['claim']} (Source: {claim['source_file']})")
                else:
                    st.write("No claims survived verification for this question.")

                if rejected:
                    st.write(
                        f"Rejected claims ({len(rejected)}), left out because their "
                        "quoted text did not match the source file word for word:"
                    )
                    for claim in rejected:
                        st.write(f"- {claim['claim']}")

                st.divider()

                col_approve, col_reject = st.columns(2)
                with col_approve:
                    if st.button(
                        "Approve",
                        key="approve_single",
                        type="primary",
                        icon=":material/check_circle:",
                        use_container_width=True,
                        help="Release this answer as final, using only the verified claims above",
                    ):
                        with st.spinner("Finalizing..."):
                            final = resume_with_decision(pending["thread_id"], True)
                        st.session_state["single_result"] = {
                            "system": "System B",
                            "result": final,
                            "awaiting_approval": False,
                        }
                        st.rerun()
                with col_reject:
                    if st.button(
                        "Reject",
                        key="reject_single",
                        icon=":material/cancel:",
                        use_container_width=True,
                        help="Discard this answer entirely, nothing is released",
                    ):
                        with st.spinner("Recording rejection..."):
                            final = resume_with_decision(pending["thread_id"], False)
                        st.session_state["single_result"] = {
                            "system": "System B",
                            "result": final,
                            "awaiting_approval": False,
                        }
                        st.rerun()
        else:
            st.subheader(f"{data['system']} answer")
            st.write(data["result"]["answer"])
            render_citations(data["system"], data["result"])

# --- Compare all three ----------------------------------------------------

with tab_compare:
    st.write(
        "Ask the same question to all three systems at once. System B may "
        "be noticeably slower and cost more per question than the other "
        "two, since it makes multiple separate model calls (one to route "
        "the question to the right country, another to extract claims) "
        "instead of one, plus its own retrieval and verification steps."
    )
    st.caption(
        "For this side by side view only, System B's approval step is "
        "auto-approved so all three answers appear together. Use "
        "\"Ask one system\" above to try the real approve or reject step "
        "yourself."
    )

    compare_question = st.text_input("Your question", key="compare_question")
    compare_clicked = st.button("Compare all three", key="compare_button")

    if compare_clicked and compare_question and not try_use_budget(3):
        st.error(
            "Comparing all three systems needs 3 units of today's shared "
            "question budget, and not enough remain. Try \"Ask one system\" "
            "above instead, or come back after the budget resets at "
            "midnight UTC."
        )
    elif compare_clicked and compare_question:
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("System A")
            with st.spinner("Asking System A..."):
                result_a = system_a.answer_question(compare_question)
            st.write(result_a["answer"])
            render_citations("System A", result_a)

        with col_b:
            st.subheader("System B")
            with st.spinner("Asking System B, this takes longer..."):
                pending_b = start_question(compare_question)
                final_b = resume_with_decision(pending_b["thread_id"], True)
            st.write(final_b["answer"])
            render_citations("System B", final_b)

        with col_c:
            st.subheader("System C")
            with st.spinner("Asking System C..."):
                result_c = system_c.answer_question(compare_question)
            st.write(result_c["answer"])
            render_citations("System C", result_c)
