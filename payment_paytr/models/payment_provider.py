# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.urls import urljoin as url_join

from odoo.addons.payment_paytr import const


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('paytr', "PAYTR")], ondelete={'paytr': 'set default'}
    )
    paytr_merchant_id = fields.Char(
        string="PAYTR Merchant ID", required_if_provider='paytr', copy=False
    )
    paytr_merchant_key = fields.Char(
        string="PAYTR Merchant Key",
        required_if_provider='paytr',
        copy=False,
        groups='base.group_system',
    )
    paytr_merchant_salt = fields.Char(
        string="PAYTR Merchant Salt",
        required_if_provider='paytr',
        copy=False,
        groups='base.group_system',
    )
    paytr_test_mode = fields.Boolean(
        string="PAYTR Test Mode",
        compute='_compute_paytr_test_mode',
        inverse='_inverse_paytr_test_mode',
    )

    @api.depends('state', 'code')
    def _compute_paytr_test_mode(self):
        for provider in self:
            provider.paytr_test_mode = provider.code == 'paytr' and provider.state == 'test'

    def _inverse_paytr_test_mode(self):
        for provider in self.filtered(lambda p: p.code == 'paytr'):
            provider.state = 'test' if provider.paytr_test_mode else 'enabled'

    def _compute_feature_support_fields(self):
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'paytr').update({
            'support_express_checkout': False,
            'support_manual_capture': None,
            'support_refund': 'none',
            'support_tokenization': False,
        })

    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'paytr':
            supported_currencies = supported_currencies.filtered(
                lambda currency: currency.name == const.SUPPORTED_CURRENCY_CODE
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        self.ensure_one()
        if self.code != 'paytr':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    @api.constrains('state', 'code', 'paytr_merchant_id', 'paytr_merchant_key', 'paytr_merchant_salt')
    def _check_paytr_credentials_when_active(self):
        for provider in self.filtered(
            lambda p: p.code == 'paytr' and p.state in ('enabled', 'test')
        ):
            if not (provider.paytr_merchant_id and provider.paytr_merchant_key and provider.paytr_merchant_salt):
                raise ValidationError(_("PAYTR credentials are required in Enabled/Test mode."))

    def _build_request_url(self, endpoint, **kwargs):
        if self.code != 'paytr':
            return super()._build_request_url(endpoint, **kwargs)
        return url_join(const.PAYTR_API_BASE_URL, endpoint)

    def _parse_response_content(self, response, **kwargs):
        if self.code != 'paytr':
            return super()._parse_response_content(response, **kwargs)

        response_content = response.json()
        if response_content.get('status') != 'success':
            reason = response_content.get('reason') or _("Unknown PAYTR error.")
            raise ValidationError(_("The payment provider rejected the request.\n%s", reason))
        return response_content
