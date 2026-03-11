def post_init_hook(env):
    """Ensure a PAYTR provider exists after module installation/upgrade."""
    Provider = env['payment.provider'].sudo()

    card_method = env.ref('payment.payment_method_card', raise_if_not_found=False)
    redirect_form_view = _find_redirect_form_view(env)
    existing_provider = Provider.search([('code', '=', 'paytr')], limit=1)
    if existing_provider:
        write_vals = {}
        if redirect_form_view and not existing_provider.redirect_form_view_id:
            write_vals['redirect_form_view_id'] = redirect_form_view.id
        if card_method and card_method not in existing_provider.payment_method_ids:
            write_vals['payment_method_ids'] = [(4, card_method.id)]
        if write_vals:
            existing_provider.write(write_vals)
        return

    values = {
        'name': 'PAYTR',
        'code': 'paytr',
        'state': 'disabled',
    }
    if redirect_form_view:
        values['redirect_form_view_id'] = redirect_form_view.id
    if card_method:
        values['payment_method_ids'] = [(6, 0, [card_method.id])]

    Provider.create(values)


def _find_redirect_form_view(env):
    imd = env['ir.model.data'].sudo()
    for module_name in ('payment_paytr', 'odoo_paytr', 'odooPayTR'):
        xmlid = imd.search([
            ('module', '=', module_name),
            ('name', '=', 'redirect_form'),
            ('model', '=', 'ir.ui.view'),
        ], limit=1)
        if xmlid:
            return env['ir.ui.view'].sudo().browse(xmlid.res_id)
    return env['ir.ui.view'].sudo().search([('name', '=', 'redirect_form')], limit=1)
