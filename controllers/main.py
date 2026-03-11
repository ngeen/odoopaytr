# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import hashlib
import hmac
import pprint

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

from odoo.addons.payment.logging import get_payment_logger

from .. import const


_logger = get_payment_logger(__name__, sensitive_keys=const.SENSITIVE_LOG_KEYS)


class PaytrController(http.Controller):
    _return_url = const.PAYMENT_RETURN_ROUTE
    _webhook_url = const.WEBHOOK_ROUTE

    @http.route(
        _return_url,
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
        save_session=False,
    )
    def paytr_return_from_checkout(self, **data):
        """Handle customer redirection from PAYTR.

        This route is intentionally UX-only and does not mutate transaction state. The authoritative
        payment status is processed only through the webhook.
        """
        _logger.info(
            "Handling redirection from PAYTR with data:\n%s",
            pprint.pformat({
                'merchant_oid': data.get('merchant_oid'),
                'tx_ref': data.get('tx_ref'),
                'result': data.get('result'),
            }),
        )
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False)
    def paytr_webhook(self, **data):
        """Process PAYTR notification callback and acknowledge it with plain `OK`."""
        _logger.info(
            "Notification received from PAYTR with reference=%s status=%s",
            data.get('merchant_oid'),
            data.get('status'),
        )
        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('paytr', data)
        if not tx_sudo:
            # Return OK to stop retries when the transaction is unknown in Odoo.
            return request.make_response('OK', headers=[('Content-Type', 'text/plain')])

        try:
            self._verify_signature(data, tx_sudo)
        except Forbidden:
            return request.make_response(
                'PAYTR notification failed: bad hash',
                headers=[('Content-Type', 'text/plain')],
                status=400,
            )

        # Idempotency guard for duplicated callbacks.
        if tx_sudo.state in ('done', 'error', 'cancel'):
            _logger.info(
                "Ignoring duplicate PAYTR notification for transaction %s in state %s.",
                tx_sudo.reference,
                tx_sudo.state,
            )
            return request.make_response('OK', headers=[('Content-Type', 'text/plain')])

        tx_sudo._process('paytr', data)
        return request.make_response('OK', headers=[('Content-Type', 'text/plain')])

    def _verify_signature(self, payment_data, tx_sudo):
        """Verify callback signature against PAYTR's expected HMAC-SHA256 payload."""
        received_hash = payment_data.get('hash')
        if not received_hash:
            _logger.warning("Received PAYTR callback without hash.")
            raise Forbidden()

        expected_hash = self._compute_signature(
            payment_data=payment_data,
            merchant_key=tx_sudo.provider_id.paytr_merchant_key,
            merchant_salt=tx_sudo.provider_id.paytr_merchant_salt,
        )
        if not hmac.compare_digest(received_hash, expected_hash):
            _logger.warning("Received PAYTR callback with invalid hash.")
            raise Forbidden()

    @staticmethod
    def _compute_signature(payment_data, merchant_key, merchant_salt):
        signing_string = ''.join([
            payment_data.get('merchant_oid', ''),
            merchant_salt or '',
            payment_data.get('status', ''),
            payment_data.get('total_amount', ''),
        ])
        digest = hmac.new(
            (merchant_key or '').encode('utf-8'),
            signing_string.encode('utf-8'),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode('utf-8')
