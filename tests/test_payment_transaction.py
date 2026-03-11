# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import hashlib
import hmac

from unittest.mock import patch

from odoo.tests import tagged

from .. import const
from ..models.payment_transaction import PaymentTransaction
from .common import PaytrCommon


@tagged('post_install', '-at_install')
class TestPaytrPaymentTransaction(PaytrCommon):

    def test_rendering_values_contains_required_fields(self):
        tx = self._create_transaction('redirect', currency_id=self.currency_try.id)
        with patch.object(
            PaymentTransaction, '_paytr_get_customer_ip', return_value='127.0.0.1'
        ):
            rendering_values = tx._get_specific_rendering_values({})

        self.assertEqual(rendering_values['api_url'], const.PAYTR_CHECKOUT_URL)
        self.assertIn('merchant_id', rendering_values['paytr_values'])
        self.assertIn('merchant_oid', rendering_values['paytr_values'])
        self.assertIn('paytr_token', rendering_values['paytr_values'])
        self.assertEqual(rendering_values['paytr_values']['merchant_oid'], tx.reference)

    def test_token_generation_is_deterministic(self):
        tx = self._create_transaction('redirect', currency_id=self.currency_try.id)
        with patch.object(
            PaymentTransaction, '_paytr_get_customer_ip', return_value='127.0.0.1'
        ):
            payload = tx._paytr_prepare_checkout_payload()

        hash_str = ''.join([
            payload['merchant_id'],
            payload['user_ip'],
            payload['merchant_oid'],
            payload['email'],
            payload['payment_amount'],
            payload['payment_type'],
            payload['installment_count'],
            payload['currency'],
            payload['test_mode'],
            payload['non_3d'],
        ])
        expected_token = base64.b64encode(
            hmac.new(
                tx.provider_id.paytr_merchant_key.encode('utf-8'),
                f"{hash_str}{tx.provider_id.paytr_merchant_salt}".encode('utf-8'),
                hashlib.sha256,
            ).digest()
        ).decode('utf-8')
        self.assertEqual(tx._paytr_compute_token(payload), expected_token)

    def test_process_success_confirms_transaction(self):
        tx = self._create_transaction(
            'redirect',
            currency_id=self.currency_try.id,
            reference=f'{self.reference}-success',
        )
        tx._set_pending()

        tx._process('paytr', {
            'merchant_oid': tx.reference,
            'status': 'success',
            'total_amount': '100.99',
        })
        self.assertEqual(tx.state, 'done')

    def test_process_failed_sets_transaction_error(self):
        tx = self._create_transaction(
            'redirect',
            currency_id=self.currency_try.id,
            reference=f'{self.reference}-failed',
        )
        tx._set_pending()

        tx._process('paytr', {
            'merchant_oid': tx.reference,
            'status': 'failed',
            'total_amount': '100.99',
            'failed_reason_msg': 'Insufficient funds',
        })
        self.assertEqual(tx.state, 'error')

    def test_amount_mismatch_sets_transaction_error(self):
        tx = self._create_transaction(
            'redirect',
            currency_id=self.currency_try.id,
            reference=f'{self.reference}-mismatch',
        )
        tx._set_pending()

        tx._process('paytr', {
            'merchant_oid': tx.reference,
            'status': 'success',
            'total_amount': '1.00',
        })
        self.assertEqual(tx.state, 'error')

    def test_extract_amount_data_accepts_minor_and_major_units(self):
        tx = self._create_transaction('redirect', currency_id=self.currency_try.id)
        amount_data_minor = tx._extract_amount_data({'total_amount': '10099'})
        amount_data_major = tx._extract_amount_data({'total_amount': '100.99'})

        self.assertEqual(amount_data_minor['currency_code'], 'TRY')
        self.assertEqual(amount_data_major['currency_code'], 'TRY')
        self.assertAlmostEqual(amount_data_minor['amount'], 100.99, places=2)
        self.assertAlmostEqual(amount_data_major['amount'], 100.99, places=2)
