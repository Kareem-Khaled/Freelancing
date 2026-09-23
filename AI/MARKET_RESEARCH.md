# Freelance Market Research — RAG / Document AI

**Date:** 22 September 2026
**Status: PARTIAL.** Most job boards blocked automated access. Everything below is
labelled by how it was obtained, so nothing here is mistaken for verified data.

---

## What I could NOT retrieve (and why)

| Source | Result |
| --- | --- |
| `upwork.com/freelance-jobs/rag/` | **Cloudflare challenge** — bot protection, no content returned |
| `upwork.com/hire/rag-freelancers/` | Cloudflare challenge |
| `weworkremotely.com` "RAG LLM" | "There aren't any jobs that match your search" |
| `freelancer.com/jobs/rag/` | Category page exists but returned **0 jobs** |
| `hnhiring.com/technologies/rag` | 404 — page does not exist |

Upwork and Fiverr both actively block scraping. **I cannot give you verified
Upwork job counts, bid amounts or hourly rates**, and I'm not going to invent
plausible-looking ones — you'd price against fiction.

---

## What I DID observe (directly quoted from fetched pages)

### Signal 1 — clients are burned by AI devs who can't finish

PeoplePerHour, "Experienced AI (Outbound) Telemarketer", posted 3 hours before
fetch, 5 proposals:

> "Two different developers have attempted the project but have been unable to
> achieve the level of accuracy, timing, responsiveness and natural conversation
> flow required."

> "We are specifically looking for someone with proven, relevant experience
> rather than someone learning or experimenting with AI voice technology for the
> first time."

> "Due to the number of enquiries we receive, we will not respond to
> applications that do not include relevant examples of previous work."

**Implication:** evidence beats claims. A proposal with measured numbers and a
runnable demo clears a bar that most applicants fail.

### Signal 2 — active distrust of ungrounded LLM output

PeoplePerHour, "Contract review and advice":

> "I would prefer to hear from legal professionals rather than people running
> this through chatgtp or claude please."

**Implication:** the market has learned that a confident answer is not a correct
one. This is *exactly* the anxiety citation-verified, refuse-when-unsure
retrieval is built to address. Lead with it.

### Signal 3 — PDF/OCR extraction is steady, unglamorous, paid work

Live PeoplePerHour and Freelancer listings:

| Job | Budget (as displayed) |
| --- | --- |
| "Convert PDF Paragraphs to Text" — mixed text + scanned pages, OCR needed | $205 avg bid |
| "Accurate PDF-to-Word Conversion" — preserve layout, tables, images | $371 avg bid |
| "Placer AI Data Extraction" — 112 locations into structured Excel | $112 avg bid |

Note the first one explicitly says *"Some pages let you highlight the words,
while other pages are only images of the text, so a mix of simple copy-and-paste
and OCR will be necessary."* — that is precisely what `doc-intelligence` parsing
handles (detect by content, OCR fallback, confidence gate).

### Signal 4 — salaried AI roles pay well (context for your rate floor)

RemoteOK listings with disclosed salary:

- Sticker Mule — "AI agent engineer", Europe — **$150k–$250k**
- Salesforge — "Senior Backend Engineer, Build AI Agents"
- Benzinga — "AI Engineer, Data APIs"

**Caveat:** RemoteOK's `/remote-rag-jobs` tag page is poorly filtered — it
returned payroll assistants and cider technicians alongside AI roles. Treat the
salary figures as directional only.

---

## Honest read of the demand picture

What I can support from the above:

1. **Generic "RAG" as a search term is not where the jobs are indexed.**
   Freelancer's RAG category had literally zero posts. Clients don't write "I
   need RAG" — they write *"chatbot for our PDFs"*, *"AI that answers from our
   manuals"*, *"extract data from invoices"*. **Write your profile in their
   words, not ours.**

2. **Trust and verifiability are the live objection**, per Signal 2. Not speed,
   not model choice.

3. **Delivery risk is the other live objection**, per Signal 1.

What I *cannot* support and you should verify yourself: job volume, typical
budgets for RAG builds specifically, competition levels, or which platform
converts better.

---

## How to get the real numbers (15 minutes, manual)

Automated access is blocked, but your logged-in browser is not:

1. Upwork → search **"RAG"**, **"chatbot our documents"**, **"AI document
   extraction"**, **"knowledge base AI"**
2. Filter: *Posted last 7 days*, *$1k+ fixed* or *$30+/hr*
3. Record for 20 listings: budget, proposals so far, client spend, exact wording
4. Sort your Fiverr search by *Best Selling* to see what packaging actually sells

Paste 5–10 of those listings back to me and I'll tailor the proposal template in
`FREELANCE_PORTFOLIO.md` to the precise language those clients use.
