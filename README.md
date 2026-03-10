# Monday.com Business Intelligence Agent

Conversational AI agent that answers founder-level business questions using **data fetched dynamically from Monday.com** (no local file paths). Supports open-source/free LLMs and includes preprocessing to minimize hallucination.

## Architecture

- **Monday.com**: All data is fetched via Monday.com API (read-only). No CSV or local paths in the agent.
- **Data layer**: `monday_client.py` fetches Work Orders and Deals boards; `data_processor.py` normalizes dates, nulls, and builds a grounded context for the LLM.
- **LLM**: `llm_client.py` supports **Groq** (free tier) or **Ollama** (local open source). System prompt instructs the model to answer only from provided data.
- **UI**: Streamlit chat interface; data is cached for a short TTL to limit API calls.

## Step-by-step setup

### 1. Create a Monday.com account and boards

1. Sign up at [monday.com](https://monday.com) if you don’t have an account.
2. Create **two boards**:
   - **Work Orders** (for project execution data)
   - **Deals** (for sales pipeline data)
3. Import the provided CSVs:
   - In each board, use **Add more** → **Import** → **CSV** and upload:
     - `Work_Order_Tracker_Data.csv` → Work Orders board
     - `Deal_funnel_Data.csv` → Deals board
4. When importing, keep column names as suggested (or note any renames). The agent expects column titles similar to the CSV headers for best results.
5. Get your **Board IDs**:
   - Open each board; the URL is like `https://yourworkspace.monday.com/boards/1234567890`.
   - The number at the end is the board ID. Save both IDs.

### 2. Get your Monday.com API token

1. In Monday.com: click your **profile picture** (top right) → **Developers** (or **Admin** → **API**).
2. Under **Personal API token**, copy your **V2** token.  
   (If you don’t see it: **Profile** → **Developers** → create/copy token.)

### 3. Set up Python and dependencies

```bash
cd "c:\Christ University\6th Sem\Assessment C\bi-agent"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure environment (no hardcoded paths)

Create a `.env` file in the `bi-agent` folder (or set environment variables):

```env
MONDAY_API_TOKEN=your_monday_v2_token_here
MONDAY_WORK_ORDERS_BOARD_ID=1234567890
MONDAY_DEALS_BOARD_ID=1234567891

# LLM: use Groq (free) or Ollama (local)
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
```

- **Groq (free tier):** Get an API key at [console.groq.com](https://console.groq.com). Set `GROQ_API_KEY` and `LLM_PROVIDER=groq`.
- **Ollama (open source):** Install [Ollama](https://ollama.com), run `ollama pull llama3.2`, then set `LLM_PROVIDER=ollama`. Leave `GROQ_API_KEY` empty.

To load `.env` automatically, install dependencies with `pip install -r requirements.txt` (includes `python-dotenv`). Then create a `.env` file and run the app.

### 5. Run the agent locally

```bash
streamlit run app.py
```

Open the URL shown (e.g. `http://localhost:8501`). Ask questions in natural language (e.g. “How’s our pipeline for the energy sector?”, “Total work orders by sector?”). Data is fetched from Monday.com and cached for 5 minutes by default.

### 6. Deploy a hosted prototype (required for submission)

The assignment asks for a **working agent accessible via link** without local setup.

**Option A – Streamlit Community Cloud (recommended)**

1. Push the project to a **public** GitHub repo (omit `.env`; do not commit API keys).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and deploy the repo.
3. In the app’s **Settings** → **Secrets**, add:
   - `MONDAY_API_TOKEN`
   - `MONDAY_WORK_ORDERS_BOARD_ID`
   - `MONDAY_DEALS_BOARD_ID`
   - `GROQ_API_KEY` (if using Groq)
4. Redeploy. Share the app link (e.g. `https://your-app.streamlit.app`).

**Option B – Other hosts**

You can run the same app on any host that supports Python (e.g. Railway, Render, a VPS). Set the same environment variables there and run:

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

## Design choices (for Decision Log)

- **Dynamic fetch only:** No local paths; all data comes from Monday.com API so the agent always uses current board data.
- **Preprocessing:** Dates normalized to YYYY-MM-DD, nulls to “N/A”, duplicate header rows filtered, numeric parsing with safe defaults to avoid bogus numbers and reduce hallucination.
- **Grounded context:** The LLM receives a summary (counts, totals, by sector/stage) plus sample rows. The system prompt tells it to answer only from this context and to mention data quality when relevant.
- **Not query-based:** The agent is conversational; it interprets natural-language questions and uses the same pre-fetched context to answer (no fixed query templates).
- **Open-source LLM:** Groq (free) or Ollama; you can switch via `LLM_PROVIDER` and the corresponding API key or local setup.

## File overview

| File | Purpose |
|------|--------|
| `app.py` | Streamlit UI; loads data from Monday, builds context, runs chat. |
| `monday_client.py` | Monday.com GraphQL client; fetches boards and items (no local paths). |
| `data_processor.py` | Normalization and context building to minimize hallucination. |
| `llm_client.py` | Groq / Ollama chat with system prompt and context. |
| `config.py` | Reads env vars (API keys, board IDs, LLM provider). |

## Troubleshooting

- **“Could not load data from Monday.com”**  
  Check `MONDAY_API_TOKEN` and both board IDs. Ensure the token has read access to those boards.

- **“No data returned”**  
  Confirm the boards have items and that column names match what the processor expects (see CSV headers). If you renamed columns in Monday, you may need to align names in `data_processor.py` or keep CSV-like names on import.

- **Groq error**  
  Ensure `GROQ_API_KEY` is set and `LLM_PROVIDER=groq`. If you prefer Ollama, set `LLM_PROVIDER=ollama` and run Ollama locally with a supported model.

- **Ollama error**  
  Start Ollama, run `ollama pull llama3.2` (or the model set in `OLLAMA_MODEL`), and ensure `OLLAMA_BASE_URL` is correct (default `http://localhost:11434`).

## Submission

- **Hosted prototype:** Use the Streamlit (or other) public URL.
- **Decision Log:** Document assumptions, trade-offs, “what you’d do differently,” and how you interpreted “leadership updates” (e.g. summaries and metrics suitable for exec review).
- **Source code:** ZIP the `bi-agent` folder (without `.env` or secrets) and include this README.
