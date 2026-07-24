# Payment link — deferred options

The `sendPaymentLink` reservation tool (`app/payments.py`,
`app/twilio_client.py`, dispatched from `app/guide_client.py`) currently sends an SMS
with a **placeholder link** (`PAYMENT_LINK_BASE_URL` + the order id — no real
checkout page, no charge). Two things were deliberately left out of that first
pass and are documented here so the path to a real version isn't lost.

## 1. Real payment-link generation (currently a placeholder)

Booqable's dashboard has a manual "Request Payment" button that creates a
Stripe-backed URL a customer can open to pay, but **that action is not
exposed through Booqable's documented v4 API** — only these endpoints exist:
`payment_charges`, `payment_authorizations`, `payment_methods`,
`payment_refunds`. Those charge a card that's already on file; they don't
produce a "customer enters their card" URL. So closing this gap means picking
one of:

- **Direct Stripe Checkout Session** (recommended if you want full
  automation). Create a Stripe Checkout Session with your own Stripe
  account/API keys for the order's `grand_total_usd` (see
  `reservations.get_order_contact`), send the session's hosted URL instead of
  the placeholder in `payments.build_test_payment_link`. Tradeoff: payment
  status then lives in Stripe, not Booqable's own paid/unpaid field — you'd
  need a Stripe webhook (`checkout.session.completed`) that reconciles back
  into Booqable, e.g. by posting a note on the order/customer or (if it
  becomes available) updating a payment-status field via the API.
- **Booqable-native request link** (recommended if you want payment status to
  stay natively in sync with Booqable/Stripe). Staff manually generates the
  link from the Booqable dashboard's "Request Payment" action and this app
  just relays whatever URL is supplied. Keeps everything inside Booqable's own
  Stripe connection, but isn't automatable through the current API — would
  need a person in the loop, or Booqable support/API access to unlock a
  programmatic version if one exists beyond what's publicly documented.

Either way, only `payments.build_test_payment_link` and (for the Stripe path)
`app/payments.py`'s `send_payment_link` need to change — the Twilio-sending
and Booqable-lookup plumbing around it stays the same.

## 2. Email delivery (not implemented — SMS only for now)

Twilio's Programmable Messaging API only sends SMS/MMS, not email. Options,
in order of fit for this app:

- **SendGrid** (Twilio's own email product). Best fit if staying inside the
  Twilio ecosystem. Needs its own API key (`SENDGRID_API_KEY`) and a verified
  sender identity/domain. Would mirror `app/twilio_client.py`'s shape: a small
  `app/sendgrid_client.py` wrapping a POST to
  `https://api.sendgrid.com/v3/mail/send` (or the `sendgrid` PyPI package),
  raising a `SendGridError` the same way `TwilioSmsError`/`BooqableError` do.
- **Plain SMTP** (an existing mailbox/provider, e.g. Gmail/Office365). No new
  vendor account, but more deliverability risk (personal accounts get rate
  limited/flagged) and needs an app password or OAuth setup. Python's
  built-in `smtplib`/`email.mime` would suffice.
- **Gmail API**. Only worth it if you specifically want to send "from" a
  Gmail/Workspace account already connected elsewhere in your tooling;
  otherwise SendGrid is the more production-appropriate choice for a
  business-facing "pay now" email.

Whichever is chosen, it plugs into `app/payments.send_payment_link` the same
way `TwilioSmsClient` does today — the contact lookup (`get_order_contact`)
already returns `email` alongside `phone`, it's just unused by the payments
flow right now.
