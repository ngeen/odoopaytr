# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.payment.tests.http_common import PaymentHttpCommon

from .. import const
from ..controllers.main import PaytrController
from .common import PaytrCommon


@tagged('post_install', '-at_install')
class TestPaytrController(PaytrCommon, PaymentHttpCommon):

    def _build_signed_payload(self, tx, status='success', total_amount='100.99', **extra):
        payload = {
            'merchant_oid': tx.reference,
            'status': status,
            'total_amount': total_amount,
            **extra,
        }
        payload['hash'] = PaytrController._compute_signature(
            payload,
            tx.provider_id.paytr_merchant_key,
            tx.provider_id.paytr_merchant_salt,
        )
        return payload

    def test_webhook_success_confirms_transaction(self):
        tx = self._create_transaction(
            'redirect',
            currency_id=self.currency_try.id,
            reference=f'{self.reference}-webhook-success',
        )
        tx._set_pending()
        payload = self._build_signed_payload(tx, status='success', total_amount='100.99')

        response = self._make_http_post_request(self._build_url(const.WEBHOOK_ROUTE), data=payload)
        tx.invalidate_recordset()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'OK')
        self.assertEqual(tx.state, 'done')

    def test_webhook_duplicate_callback_is_idempotent(self):
        tx = self._create_transaction(
            'redirect',
            currency_id=self.currency_try.id,
            reference=f'{self.reference}-webhook-duplicate',
        )
        tx._set_pending()
        payload = self._build_signed_payload(tx, status='success', total_amount='100.99')

        first_response = self._make_http_post_request(
            self._build_url(const.WEBHOOK_ROUTE), data=payload
        )
        second_response = self._make_http_post_request(
            self._build_url(const.WEBHOOK_ROUTE), data=payload
        )
        tx.invalidate_recordset()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.text, 'OK')
        self.assertEqual(second_response.text, 'OK')
        self.assertEqual(tx.state, 'done')

    def test_webhook_invalid_signature_returns_400(self):
        tx = self._create_transaction(
            'redirect',
            currency_id=self.currency_try.id,
            reference=f'{self.reference}-webhook-invalid-signature',
        )
        tx._set_pending()
        payload = self._build_signed_payload(tx, status='success', total_amount='100.99')
        payload['hash'] = 'invalid_hash'

        response = self._make_http_post_request(self._build_url(const.WEBHOOK_ROUTE), data=payload)
        tx.invalidate_recordset()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(tx.state, 'pending')

    def test_webhook_amount_mismatch_marks_transaction_error(self):
        tx = self._create_transaction(
            'redirect',
            currency_id=self.currency_try.id,
            reference=f'{self.reference}-webhook-mismatch',
        )
        tx._set_pending()
        payload = self._build_signed_payload(tx, status='success', total_amount='1.00')

        response = self._make_http_post_request(self._build_url(const.WEBHOOK_ROUTE), data=payload)
        tx.invalidate_recordset()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'OK')
        self.assertEqual(tx.state, 'error')
