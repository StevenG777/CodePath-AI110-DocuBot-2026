# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> DocuBot answers developer questions about a project using only that project's
> documentation (`docs/*.md`). It supports three modes so we can compare how
> grounding affects answer quality: naive generation, retrieval only, and RAG.
> The goal is a trustworthy assistant that says "I do not know" rather than guessing.

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> A natural-language query; the Markdown/text files in `docs/`; and environment
> variables (`GEMINI_API_KEY` to enable LLM modes).

**What outputs does DocuBot produce?**

> Depending on mode: a raw model answer (naive), formatted retrieved snippets with
> filenames (retrieval only), or a grounded answer that cites the files it used
> and refuses when evidence is missing (RAG).

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

> **Index:** `build_index` builds a simple inverted index — a dict mapping each
> lowercase whitespace token to the filenames it appears in.
>
> **Chunking:** instead of scoring whole files, `chunk_document` splits each doc
> into paragraphs (blocks separated by blank lines), so retrieval returns focused
> sections rather than entire files.
>
> **Scoring:** `score_document` lowercases the query and counts how many distinct
> query words appear as substrings of the chunk. Higher count = more relevant.
>
> **Top snippets:** `retrieve` scores every chunk, drops any scoring below
> `min_score=1` (the guardrail), sorts descending, and returns the top `top_k` (3).

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> Simplicity over precision. Substring word-counting is trivial and fast but has
> real weaknesses: (1) **no synonyms** — "generated" does not match "created";
> (2) **substring bleed** — "user" matches "users"/"user_id", and "connect"
> matches "connection"; (3) **boilerplate bias** — long intro paragraphs that
> repeat generic words ("this document explains…") often outscore the short,
> specific paragraph that actually answers the question. Ties break by document
> order, not relevance. I accepted these to keep the code pure-Python and readable.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode:
- Retrieval only mode:
- RAG mode:

> - **Naive LLM mode:** calls Gemini with only the question. Notably, our
>   `naive_answer_over_full_docs` *ignores* the docs entirely and sends a generic
>   prompt — so answers come from the model's general training, not this project.
> - **Retrieval only mode:** no LLM at all. Returns the raw top snippets.
> - **RAG mode:** retrieves snippets, then passes only those snippets to Gemini
>   with strict grounding rules.

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> The RAG prompt (`answer_from_snippets`) tells the model to: answer using **only**
> the provided snippets; **not** invent functions, endpoints, or config values;
> reply exactly "I do not know based on the docs I have." when the snippets are
> insufficient; and briefly cite which files it relied on. There is also a
> pre-LLM guardrail: if retrieval returns no snippets, we refuse without ever
> calling the model.

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

Model used for LLM modes: `gemini-2.5-flash` (the starter's `gemma-3-27b-it` is
no longer served by the API and returned 404; updated in `llm_client.py`).

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Harmful-ish: fluent generic answer, not tied to this repo | Helpful but noisy: returns AUTH.md chunks, but not the one naming `auth_utils.py` | **Refused** ("I do not know") | Answer IS in the docs (`generate_access_token` in `auth_utils.py`) but "generated"≠"created" so the right paragraph never got retrieved → RAG correctly refused given bad snippets. Retrieval limitation, not LLM. |
| How do I connect to the database? | Confident generic DB advice | Harmful: returns three generic "This document explains…" intros, not the connection section | **Refused** | Boilerplate intros outscored the real `DATABASE_URL` / Connection Configuration paragraph. |
| Which endpoint lists all users? | Plausible but invented routes | Helpful: surfaces API_REFERENCE.md chunks incl. `GET /api/users` | Grounded answer citing API_REFERENCE.md (verified before quota limit) | Retrieval landed on the right file here. |
| How does a client refresh an access token? | **Confident but wrong-for-this-repo**: gives an OAuth2 "Authorization Server + refresh token" lecture | Helpful: returns API_REFERENCE.md `/api/refresh` + AUTH.md workflow | Would cite `POST /api/refresh` from the snippets | Clearest naive-vs-grounded gap: docs describe a simple token exchange, naive invents OAuth2. |
| What environment variables are required for authentication? | Generic | Accurate but raw (SETUP.md/AUTH.md paragraphs, user must read) | **Best**: "`AUTH_SECRET_KEY` is required. (Source: SETUP.md, AUTH.md)" | RAG clear + cited; mild incompleteness (omitted optional `TOKEN_LIFETIME_SECONDS`). |

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
- When is retrieval only clearly better?  
- When is RAG clearly better than both?

> **Naive impressive-but-untrustworthy:** "How does a client refresh a token?" —
> naive produces a polished, authoritative OAuth2 explanation (Authorization
> Server, dedicated refresh tokens). None of that is in our docs; the real app
> just exchanges a valid token at `POST /api/refresh`. It *sounds* expert but
> describes a different system.
>
> **Retrieval only clearly better:** when you need to *verify the source*. It never
> fabricates — it hands back exact doc text with filenames. Downside: it is hard
> to read (you get raw paragraphs, including irrelevant boilerplate, and must
> synthesize the answer yourself).
>
> **RAG clearly better than both:** "What environment variables are required for
> authentication?" — RAG gives a one-line answer *and* cites SETUP.md/AUTH.md.
> It combines retrieval's grounding with a readable synthesis, and refuses when
> snippets are weak instead of bluffing like naive mode.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

> **Failure case 1 (false refusal — RAG still fails):** "Where is the auth token
> generated?" The answer exists verbatim in AUTH.md (`generate_access_token` in
> `auth_utils.py`), but because the query says "generated" and the doc says
> "created," lexical scoring never ranked that paragraph into the top-3. RAG then
> refused. *What should happen:* retrieval should surface the paragraph naming
> `auth_utils.py`; semantic/synonym-aware retrieval would fix this.
>
> **Failure case 2 (boilerplate crowd-out):** "How do I connect to the database?"
> Retrieval returned three generic "This document explains…" intro paragraphs
> instead of DATABASE.md's Connection Configuration section, so RAG refused even
> though `DATABASE_URL` is documented. *What should happen:* down-weight
> boilerplate/intro text so specific paragraphs win.

**When should DocuBot say “I do not know based on the docs I have”?**  
Give at least two specific situations.

> 1. When retrieval finds no chunk containing any query term (e.g. "Is there any
>    mention of payment processing?" — genuinely absent → correct refusal).
> 2. When the retrieved snippets are present but do not actually contain the
>    specific fact asked for. Refusing here is safer than letting the LLM
>    extrapolate beyond the evidence.

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

> - **Score threshold** (`min_score=1` in `retrieve`): chunks with no query-word
>   overlap are discarded, so zero-evidence results become an empty list.
> - **Empty-result refusal:** both answering modes return the "I do not know"
>   message when retrieval is empty — and RAG never calls the LLM in that case.
> - **Strict prompt rules:** only-use-snippets, no invented values, exact refusal
>   string, and file citations.
> - **Snippet cap** (`top_k=3`): bounds context size and cost.

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. **Lexical-only matching:** no understanding of synonyms or meaning, so
   "generated" vs "created" misses (Failure case 1).
2. **Boilerplate bias / weak tie-breaking:** long generic paragraphs outrank
   short specific ones, and ties break by file order (Failure case 2).
3. **Substring matching is loose:** "user" matches "users"/"user_id" and can
   inflate scores on incidental words rather than the meaningful term.
4. **No punctuation handling:** "token." and "token" are different index tokens.
5. **External dependency / quotas:** LLM modes depend on the Gemini API; we hit
   free-tier rate limits (5 req/min) and transient 503s during testing.

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. **Semantic retrieval** (embeddings) to fix synonym/vocabulary mismatches.
2. **Better scoring:** normalize by chunk length and/or down-weight common words
   (TF-IDF-style) so boilerplate intros stop winning.
3. **Tokenize with punctuation stripping** and count term frequency, not just
   presence, for finer-grained ranking.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

> _Your answer here._

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- _Guideline 1_
- _Guideline 2_
- _Guideline 3 (optional)_

---
