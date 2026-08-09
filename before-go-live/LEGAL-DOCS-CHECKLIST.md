# Legal Pages & Policies Checklist
Status: STRUCTURAL CHECKLIST — not legal advice, not drafted legal text.
This is a "bring this list to a lawyer" document, not a "copy-paste this
into production" document. Every bracketed clause below is a placeholder
for what a real lawyer needs to draft for your actual jurisdiction(s),
entity structure, and hosting setup. Do not launch to paying non-friend
customers on self-written versions of these.

Two jurisdictions matter most given this repo's existing context: wherever
you incorporate/operate from, and Germany/EU (since German tax-jurisdiction
handling already exists in `J2-tax-aware-selling.md` and the target market
includes EU users). Get counsel who can speak to both, or one in each.

---

## 1. Terms of Service / Terms of Use

The contract between you and every user. Sections a lawyer will typically
want to cover:

- **Description of the service** — analytics/decision-support software,
  explicitly framed as a tool, not a person or firm giving advice.
- **"Not investment advice" clause** — the service does not constitute
  investment, legal, or tax advice; you are not a registered investment
  adviser or broker-dealer (state this plainly, not just implied).
- **No guarantee of results** — past performance, backtests, and model
  outputs are not indicative of future results.
- **User responsibility** — the user, not the service, makes all final
  trading decisions; trades are manually executed by the user, the service
  never executes trades automatically (keep this true operationally too —
  see the architecture doc's note on not touching live execution without
  separate legal review).
- **Eligibility** — minimum age, jurisdictions where the service is/isn't
  offered, sanctions/export-control screening if relevant.
- **Subscription & billing terms** — $9.99/mo pricing, free trial terms,
  referral program terms, auto-renewal, cancellation, refund policy (can
  live here or in a standalone Billing Terms page — see §4).
- **Acceptable use** — no reverse-engineering the models, no scraping, no
  reselling signals, no abusing the referral program, one account per
  person.
- **Intellectual property** — you own the software/models; user owns their
  own data (positions, trade history).
- **Data & third-party accuracy disclaimer** — market data comes from
  third-party providers and may be delayed, incomplete, or wrong; the
  service is not liable for data provider errors.
- **Limitation of liability** — cap on damages, exclusion of consequential
  damages, "as is" warranty disclaimer.
- **Indemnification** — user indemnifies you for their own misuse.
- **Termination** — your right to suspend/terminate accounts (e.g. for
  referral fraud, abuse), user's right to cancel anytime.
- **Dispute resolution** — governing law, arbitration clause (if desired),
  venue.
- **Changes to terms** — how you'll notify users of updates.
- **Force majeure, severability, entire agreement** — standard boilerplate
  a lawyer will add.

---

## 2. Privacy Policy

Required by law (GDPR if any EU users, CCPA if California users, and most
jurisdictions have some equivalent) — not optional at commercial scale.

- **What data is collected** — account info (email, payment via Stripe),
  financial data the user inputs (holdings, trade ledger, tax settings),
  usage/analytics data, cookies.
- **How data is used** — to run the service, compute suggestions, process
  payments, send transactional emails.
- **Third-party sharing** — name the actual vendors: payment processor
  (Stripe), hosting provider, market data provider, any analytics tool
  (e.g. PostHog, Plausible). Users should be able to see this list.
- **Data retention & deletion** — how long data is kept, how a user
  requests deletion, what happens to data on account cancellation.
- **GDPR rights section (if any EU users)** — right to access, rectify,
  erase, port, object, and restrict processing; right to lodge a complaint
  with a supervisory authority; legal basis for processing (consent /
  contract / legitimate interest).
- **CCPA rights section (if any California users)** — right to know, right
  to delete, right to opt out of sale (you're likely not "selling" data in
  the CCPA sense, but state it explicitly).
- **International data transfers** — if the servers are in one region and
  users in another (e.g. hosted in the US/EU, users elsewhere), this needs
  an explicit mechanism (SCCs for EU transfers, etc.) — a lawyer's call.
- **Cookies** — what's used and why (see §6, may be a standalone page).
- **Children's privacy** — service not directed at or intended for minors.
- **Security measures** — a general, honest statement of what you actually
  do (encryption in transit, access controls) — don't overstate this.
- **Contact info** — a real email or address for privacy inquiries; a
  named Data Protection Officer isn't required at small scale but a
  contact point is.

---

## 3. Financial / Investment Disclaimer

Often its own standalone page (linked prominently, plus a click-through
modal on first login before any trade suggestion is shown), separate from
the general ToS disclaimer clause, because financial regulators generally
expect this to be conspicuous, not buried in paragraph 14 of a ToS.

- Plain-language "this is not investment advice" statement, in the user's
  own words, not just legal boilerplate.
- "We are not a registered investment adviser / broker-dealer" statement.
- Risk-of-loss disclosure — investing involves risk of loss, including
  total loss of principal.
- Model/algorithm accuracy disclaimer — ML and quantitative outputs are
  estimates, not guarantees, and can be wrong.
- Data disclaimer — same third-party data caveat as the ToS, restated here
  since this is the page users will actually read.
- Encourage consulting a licensed, independent financial/tax advisor before
  acting on anything the tool suggests.
- Require an affirmative click-through acknowledgment before a first-time
  user can see any BUY/SELL/target-weight output — log the acknowledgment
  (timestamp + version of the disclaimer they agreed to) so you have a
  record.

---

## 4. Billing / Subscription Terms

Can be a section of the ToS or a standalone page — standalone is easier to
update independently (e.g. if pricing or the referral program changes)
without re-running a full ToS re-acceptance flow.

- Price ($9.99/mo), billing cadence, currency.
- Free trial terms — duration, card-required-upfront, what happens at
  trial end (auto-converts to paid, cancel anytime before then).
- Referral program terms — reward mechanics, the 12-free-months/year cap,
  what counts as a "successful" referral, and an explicit right to revoke
  credits obtained through abuse/fraud (needed so you can actually act on
  the fraud-prevention notes in the monetization doc).
- Refund policy — state it clearly either way (no refunds / pro-rated /
  case-by-case) rather than leaving it undefined.
- Cancellation — how, and what happens to data/access after cancellation.
- Price change policy — how much notice you'll give before a price
  increase, and whether it applies to existing subscribers immediately or
  only to new sign-ups.

---

## 5. Acceptable Use Policy

Sometimes folded into the ToS (§1), sometimes standalone if it needs to be
updated more often than the core contract terms:

- No scraping, no automated access outside the intended UI/API.
- No reverse-engineering or attempting to extract the underlying models.
- No redistributing or reselling signal output.
- No abusing the referral program (fake accounts, self-referral, etc.).
- One personal account per person; no account sharing at commercial scale.

---

## 6. Cookie Policy / Cookie Consent

Legally required for EU visitors under the ePrivacy Directive (separate
from, but related to, GDPR). If you use any analytics or non-essential
cookies:

- A cookie banner that lets EU visitors actually opt in/out (not just a
  "by using this site you accept cookies" notice — that doesn't satisfy
  current EU guidance).
- A cookie policy page listing what cookies are set, by whom, and why —
  essential (session/auth) vs. non-essential (analytics) should be
  distinguished.

---

## 7. Risk Disclosure Statement

Distinct from the general financial disclaimer (§3) in that it goes into
more specific detail — some jurisdictions/regulators expect this level of
specificity for anything touching securities, even in an advisory-adjacent
"analytics tool" framing:

- Market risk / volatility risk generally.
- Concentration risk (relevant given the correlation-cluster and
  sector-cap work already in this repo — you can honestly say the tool
  tries to manage this, but the disclaimer still needs to state the risk
  exists).
- Tax implications disclaimer — tax-aware selling (J2) estimates a tax
  drag, it does not constitute tax advice; users should confirm with their
  own tax advisor/accountant, especially outside the flat-rate
  jurisdictions where J2 already flags its own approximation.
- No suitability review — the tool does not assess whether any particular
  strategy is suitable for a particular user's full financial situation
  the way a licensed advisor performing a suitability review would.

---

## 8. Impressum (Germany-specific — likely required)

If the service is offered to or operated from Germany, German law (§5
TMG / now largely folded into the Digital Services Act framework)
generally requires a legal notice page ("Impressum") on any commercial
website, distinct from a Privacy Policy:

- Company name and legal form.
- Registered address.
- Contact details (email, sometimes phone).
- Commercial register number, if incorporated.
- VAT ID, if applicable.
- Name of a responsible person for content (Verantwortlicher).

This is a real, specific, commonly-enforced requirement — don't skip it if
Germany is a target market, which the existing tax-jurisdiction work
suggests it is.

---

## 9. Data Processing Agreement (DPA) / Sub-processor list

More relevant if you ever sell B2B (per `how-to-make-money.md` Path 2), but
worth having a sub-processor list (Stripe, hosting provider, data provider,
analytics tool) ready even for B2C — it's good practice and something a
privacy-conscious user or a future B2B customer may ask for directly.

---

## 10. Where these show up in the product, not just as static pages

- **Signup flow:** ToS + Privacy Policy checkbox (unchecked by default,
  required to proceed) before payment is collected.
- **First login, before any signal is shown:** the Financial Disclaimer
  (§3) as a click-through modal, logged with a timestamp and disclaimer
  version.
- **Every rebalance/signal page:** a persistent, small "not investment
  advice" footer or badge — the disclaimer.md doesn't do its job if it's
  only ever shown once and then forgotten.
- **Footer of every page:** links to ToS, Privacy Policy, Impressum (if
  applicable), and the financial disclaimer.
- **Cancellation flow:** link to the refund/cancellation policy at the
  point of cancellation, not just buried in the ToS.

---

## Next step

Take this list, plus `SAAS-MONETIZATION-AND-SCALE-ARCHITECTURE.md` and the
"does removing BUY/SELL labels help?" answer below, to an actual lawyer
before onboarding the first non-friend paying customer. This document is a
map of what to ask for, not a substitute for asking.
