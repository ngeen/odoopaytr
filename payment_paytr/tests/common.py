# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.payment.tests.common import PaymentCommon


class PaytrCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.currency_try = cls._enable_currency('TRY')
        cls.currency = cls.currency_try
        cls.amount = 100.99
        cls.reference = "PAYTR-Test-TX"

        cls.paytr = cls._prepare_provider('paytr', update_values={
            'paytr_merchant_id': 'merchant_id_test',
            'paytr_merchant_key': 'merchant_key_test',
            'paytr_merchant_salt': 'merchant_salt_test',
            'state': 'test',
        })
        cls.provider = cls.paytr
        cls.payment_method = cls.env.ref('payment.payment_method_card')
        cls.payment_method_id = cls.payment_method.id

        cls.payment_data_success = {
            'merchant_oid': cls.reference,
            'status': 'success',
            'total_amount': '100.99',
        }
