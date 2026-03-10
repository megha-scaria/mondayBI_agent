"""
BI Agent — Conversational interface. Data is fetched dynamically from Monday.com (no local paths).
"""
import streamlit as st
from monday_client import fetch_work_orders, fetch_deals
from data_processor import build_data_context, normalize_work_orders, normalize_deals
from llm_client import chat_with_context
from config import DATA_CACHE_TTL_SECONDS

st.set_page_config(page_title="BI Agent", layout="centered")

if "messages" not in st.session_state:
    st.session_state.messages = []


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS)
def get_monday_data():
    """Fetch and preprocess data from Monday.com only. No local paths."""
    try:
        work_orders = fetch_work_orders()
        deals = fetch_deals()
        return {
            "work_orders": work_orders,
            "deals": deals,
            "error": None,
        }
    except Exception as e:
        return {"work_orders": [], "deals": [], "error": str(e)}


def main():
    st.title("Business Intelligence Agent")
    st.caption("Ask about pipeline, work orders, revenue, and sectors. Data is fetched from Monday.com.")

    data = get_monday_data()
    if data["error"]:
        st.error("Could not load data from Monday.com: " + data["error"])
        st.info("Set MONDAY_API_TOKEN, MONDAY_WORK_ORDERS_BOARD_ID, and MONDAY_DEALS_BOARD_ID. See README.")
        return

    work_orders = data["work_orders"]
    deals = data["deals"]
    if not work_orders and not deals:
        st.warning("No data returned from Monday.com. Check board IDs and permissions.")
        return

    data_context = build_data_context(work_orders, deals)
    wo_norm = normalize_work_orders(work_orders)
    dl_norm = normalize_deals(deals)
    st.sidebar.metric("Work orders", len(wo_norm))
    st.sidebar.metric("Deals", len(dl_norm))
    st.sidebar.caption(f"Data cached for {DATA_CACHE_TTL_SECONDS}s. Refresh to refetch.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a business question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]]
                reply = chat_with_context(prompt, data_context, history)
            st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

    if st.sidebar.button("Clear chat"):
        st.session_state.messages = []
        get_monday_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
