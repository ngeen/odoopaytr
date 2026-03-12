# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import hashlib
import hmac
import json

from werkzeug import urls

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.http import request as http_request
from odoo.tools import float_round
from odoo.tools.urls import urljoin as url_join

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger

from .. import const


_logger = get_payment_logger(__name__, sensitive_keys=const.SENSITIVE_LOG_KEYS)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_processing_values(self, processing_values):
        if self.provider_code != 'paytr':
            return super()._get_specific_processing_values(processing_values)

        if self.operation in ('online_token', 'offline'):
            return {}

        try:
            payload = self._paytr_prepare_iframe_payload()
            iframe_token = self._paytr_request_iframe_token(payload)
        except ValidationError as err:
            self._set_error(str(err))
            return {}

        return {
            'paytr_iframe_payload': payload,
            'paytr_iframe_token': iframe_token,
        }

    def _get_specific_rendering_values(self, processing_values):
        if self.provider_code != 'paytr':
            return super()._get_specific_rendering_values(processing_values)

        iframe_token = processing_values.get('paytr_iframe_token')
        payload = processing_values.get('paytr_iframe_payload')
        if not iframe_token:
            try:
                payload = payload or self._paytr_prepare_iframe_payload()
                iframe_token = self._paytr_request_iframe_token(payload)
            except ValidationError as err:
                self._set_error(str(err))
                return {}

        return {
            'api_url': f'{const.PAYTR_IFRAME_CHECKOUT_URL}/{iframe_token}',
        }

    def _paytr_prepare_iframe_payload(self):
        self.ensure_one()
        provider = self.provider_id

        if self.currency_id.name != const.SUPPORTED_CURRENCY_CODE:
            raise ValidationError(_("PAYTR only supports TRY transactions in this module."))
        if not self.partner_email:
            raise ValidationError(_("Customer email is required for PAYTR payments."))
        if not provider.paytr_merchant_id or not provider.paytr_merchant_key or not provider.paytr_merchant_salt:
            raise ValidationError(_("PAYTR credentials are missing."))

        merchant_ok_url, merchant_fail_url = self._paytr_get_return_urls()
        payment_amount = str(payment_utils.to_minor_currency_units(self.amount, self.currency_id))
        no_installment = '1'
        max_installment = '0'
        payload = {
            'merchant_id': provider.paytr_merchant_id,
            'user_ip': self._paytr_get_customer_ip(),
            'merchant_oid': self._paytr_get_merchant_oid(),
            'email': self.partner_email,
            'payment_amount': payment_amount,
            'currency': const.SUPPORTED_PAYTR_CURRENCY,
            'test_mode': '0' if provider.state == 'enabled' else '1',
            'no_installment': no_installment,
            'max_installment': max_installment,
            'merchant_ok_url': merchant_ok_url,
            'merchant_fail_url': merchant_fail_url,
            'user_name': self.partner_name or '',
            'user_address': self.partner_address or '',
            'user_phone': self.partner_phone or '',
            'user_basket': self._paytr_build_user_basket(),
            'debug_on': '0',
            'client_lang': 'tr' if self.env.lang and self.env.lang.startswith('tr') else 'en',
            'timeout_limit': '30',
        }
        payload['paytr_token'] = self._paytr_compute_token(payload)
        return payload

    def _paytr_request_iframe_token(self, payload):
        self.ensure_one()
        response_data = self.provider_id._send_api_request(
            'POST',
            const.PAYTR_IFRAME_TOKEN_ENDPOINT,
            data=payload,
            reference=self.reference,
        )
        iframe_token = response_data.get('token')
        if not iframe_token:
            raise ValidationError(_("PAYTR did not return an iframe token."))
        return iframe_token

    def _paytr_get_merchant_oid(self):
        self.ensure_one()
        # PAYTR expects merchant_oid to be strictly alphanumeric.
        return f'TX{self.id}'

    def _paytr_get_return_urls(self):
        self.ensure_one()
        base_url = self.provider_id.get_base_url()
        base_return_url = url_join(base_url, const.PAYMENT_RETURN_ROUTE)
        ok_query = urls.url_encode({'tx_ref': self.reference, 'result': 'success'})
        fail_query = urls.url_encode({'tx_ref': self.reference, 'result': 'failed'})
        return f'{base_return_url}?{ok_query}', f'{base_return_url}?{fail_query}'

    @api.model
    def _paytr_format_amount(self, amount):
        return f'{float_round(amount, precision_digits=2):.2f}'

    def _paytr_build_user_basket(self):
        self.ensure_one()

        basket = []
        if hasattr(self, 'sale_order_ids') and self.sale_order_ids:
            order = self.sale_order_ids[:1]
            for line in order.order_line.filtered(lambda l: not l.display_type):
                basket.append([
                    (line.product_id.display_name or line.name or self.reference)[:100],
                    self._paytr_format_amount(line.price_unit),
                    int(line.product_uom_qty or 1),
                ])

        if not basket:
            basket = [[self.reference, self._paytr_format_amount(self.amount), 1]]

        basket_json = json.dumps(basket, ensure_ascii=False)
        return base64.b64encode(basket_json.encode('utf-8')).decode('utf-8')

    def _paytr_get_customer_ip(self):
        self.ensure_one()
        if not http_request:
            return '127.0.0.1'

        forwarded_for = http_request.httprequest.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return http_request.httprequest.remote_addr or '127.0.0.1'

    def _paytr_compute_token(self, payload):
        self.ensure_one()
        provider = self.provider_id

        hash_str = ''.join([
            payload['merchant_id'],
            payload['user_ip'],
            payload['merchant_oid'],
            payload['email'],
            payload['payment_amount'],
            payload['user_basket'],
            payload['no_installment'],
            payload['max_installment'],
            payload['currency'],
            payload['test_mode'],
        ])
        token_payload = f'{hash_str}{provider.paytr_merchant_salt}'.encode('utf-8')
        digest = hmac.new(
            provider.paytr_merchant_key.encode('utf-8'),
            token_payload,
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode('utf-8')

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        if provider_code != 'paytr':
            return super()._extract_reference(provider_code, payment_data)
        merchant_oid = payment_data.get('merchant_oid') or payment_data.get('reference')
        if not merchant_oid:
            return None
        if merchant_oid.startswith('TX') and merchant_oid[2:].isdigit():
            tx = self.browse(int(merchant_oid[2:])).exists()
            return tx.reference if tx else None
        return merchant_oid

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'paytr':
            return super()._extract_amount_data(payment_data)

        if payment_data.get('status') == 'failed':
            # PAYTR returns total_amount=0 for failed payments; skip amount validation and let
            # `_apply_updates` set the transaction as error with the provider's reason.
            return None

        raw_amount = payment_data.get('total_amount') or payment_data.get('payment_amount')
        if raw_amount is None:
            return {}

        raw_amount_str = str(raw_amount).strip().replace(',', '.')
        parsed_amounts = []
        try:
            parsed_amounts.append(float(raw_amount_str))
        except ValueError:
            pass
        if raw_amount_str.isdigit():
            parsed_amounts.append(
                payment_utils.to_major_currency_units(int(raw_amount_str), self.currency_id)
            )

        if not parsed_amounts:
            return {}

        # PAYTR integrations sometimes return decimal and sometimes minor-unit values.
        # Pick the representation that matches the transaction amount when possible.
        amount = parsed_amounts[0]
        for candidate in parsed_amounts:
            if self.currency_id.compare_amounts(candidate, self.amount) == 0:
                amount = candidate
                break

        return {
            'amount': amount,
            'currency_code': const.SUPPORTED_CURRENCY_CODE,
        }

    def _apply_updates(self, payment_data):
        if self.provider_code != 'paytr':
            return super()._apply_updates(payment_data)

        self.provider_reference = payment_data.get('merchant_oid') or self.provider_reference

        status = payment_data.get('status')
        if status == 'success':
            self._set_done()
        elif status == 'failed':
            reason = payment_data.get('failed_reason_msg') or _(
                "The payment was declined by PAYTR."
            )
            _logger.info(
                "PAYTR marked transaction %s as failed. Reason code=%s, message=%s",
                self.reference,
                payment_data.get('failed_reason_code'),
                reason,
            )
            self._set_error(_("PAYTR payment failed: %s", reason))
        else:
            _logger.warning(
                "Received invalid PAYTR status '%s' for transaction %s.",
                status,
                self.reference,
            )
            self._set_error(_("PAYTR: Received data with invalid status: %s", status))
