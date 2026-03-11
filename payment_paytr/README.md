# payment_paytr (Odoo 19 Community)

PAYTR Direct API payment provider for Odoo 19 Community (`payment` + `website_sale`).

## Features

- Provider code: `paytr`
- Redirect checkout to `https://www.paytr.com/odeme`
- 3D-only flow (`non_3d=0`)
- TRY-only support (`TL` on PAYTR side)
- Installment disabled (`installment_count=0`)
- Callback signature validation (`merchant_oid + merchant_salt + status + total_amount`)
- Idempotent webhook handling for duplicate callbacks

## Installed Files

- `models/payment_provider.py`: provider fields and capability setup
- `models/payment_transaction.py`: checkout payload, token generation, status updates
- `controllers/main.py`: return and webhook routes
- `views/payment_paytr_templates.xml`: redirect form template
- `views/payment_provider_views.xml`: provider settings form
- `data/payment_provider_data.xml`: bootstrap provider record

## Configuration

1. Install module `payment_paytr`.
2. Open **Accounting -> Configuration -> Payment Providers -> PAYTR**.
3. Fill:
   - `PAYTR Merchant ID`
   - `PAYTR Merchant Key`
   - `PAYTR Merchant Salt`
4. Keep state on **Test Mode** during staging.
5. Move state to **Enabled** for live traffic.

`paytr_test_mode` is synchronized with provider state:
- `state=test` => `paytr_test_mode=True`
- `state=enabled` => `paytr_test_mode=False`

## Routes

- Return URL (UX only): `/payment/paytr/return`
- Webhook URL (authoritative): `/payment/paytr/webhook`

Set webhook URL in PAYTR merchant panel and ensure the endpoint is public over HTTPS.

## Security Notes

- Webhook rejects invalid signature with HTTP 400.
- Secrets are stored in provider credentials and never logged in clear text.
- Duplicate callbacks for terminal transactions (`done`, `error`, `cancel`) are acknowledged with `OK` and ignored.
- Amount and currency are validated through Odoo transaction processing.

## Operational Runbook

1. If PAYTR panel shows payment but Odoo is still pending:
   - Verify webhook URL is reachable from internet.
   - Check reverse proxy/body forwarding for POST parameters.
   - Confirm callback returns plain `OK`.
2. If callbacks fail with hash errors:
   - Re-check `merchant_key` and `merchant_salt`.
   - Confirm payload is not rewritten by middleware.
3. Daily reconciliation:
   - Compare PAYTR successful transactions against Odoo `payment.transaction` records in `done`.

## Go-live Checklist

- HTTPS enabled and valid certificate
- PAYTR live credentials configured
- Provider state set to `enabled`
- Webhook URL configured in PAYTR panel
- End-to-end payment test executed in production-like environment
