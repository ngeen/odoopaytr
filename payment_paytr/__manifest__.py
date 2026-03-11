{
    'name': 'PAYTR Payment Provider',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'PAYTR redirect checkout integration for Odoo 19 Community',
    'depends': ['payment', 'website_sale'],
    'data': [
        'views/payment_paytr_templates.xml',
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
