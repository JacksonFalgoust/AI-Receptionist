# Payment link — deferred options

The `sendPaymentLink` reservation tool (`app/payments.py`,
`app/postmark_client.py`, `app/twilio_client.py`, dispatched from
`app/guide_client.py`) sends a **placeholder link**
(`PAYMENT_LINK_BASE_URL` + the order id — no real checkout page, no charge)
by email (Postmark) or SMS (Twilio), depending on `channel` /
`PAYMENT_LINK_DEFAULT_CHANNEL`. SMS is currently unusable pending
carrier/government verification, which is why email defaults on. One thing
was deliberately left out of that first pass and is documented here so the
path to a real version isn't lost.

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
`app/payments.py`'s `send_payment_link` need to change — the
channel-sending and Booqable-lookup plumbing around it stays the same.

## 2. Email delivery — implemented via Postmark

Twilio's Programmable Messaging API only sends SMS/MMS, not email, and SMS
itself is currently unusable pending carrier/government verification, so
**Postmark** was added as the email channel (chosen over SendGrid/SMTP/Gmail
API, all considered here previously — Postmark was preferred for its simple
single-email HTTP endpoint and clear per-message error codes).

`app/postmark_client.py` mirrors `app/twilio_client.py`'s shape: a small
wrapper POSTing to `https://api.postmarkapp.com/email` with
`X-Postmark-Server-Token` auth, raising `PostmarkError` the same way
`TwilioSmsError`/`BooqableError` do — on an HTTP error status, and also on a
non-zero Postmark `ErrorCode` in an otherwise-200 response (e.g. `406`
inactive recipient, `401` unconfirmed sender signature — `POSTMARK_FROM_EMAIL`
must be a confirmed Sender Signature in the Postmark account).

It plugs into `app/payments.send_payment_link` alongside `TwilioSmsClient` —
the contact lookup (`get_order_contact`) already returns `email` alongside
`phone`; `send_payment_link` picks whichever channel is requested (or
falls back to `config.PAYMENT_LINK_DEFAULT_CHANNEL`, `"email"` today) and
sends through the matching client. The link itself is still the placeholder
from §1 above — implementing email didn't touch that.
