"""
Object registry. Adding an object (customers, bank accounts, assets, POs ...)
means writing one module like suppliers.py (RULES, load_inputs, run, funnel)
and registering it here with its parameters from config.py.
"""
from migration_scope import config
from migration_scope.objects import suppliers

OBJECTS = {
    'suppliers': {'module': suppliers, 'label': 'Suppliers', 'params': config.SUPPLIER_PARAMS, 'available': True,
                  'icon': 'lucide:truck'},
    'customers': {'module': None, 'label': 'Customers', 'params': {}, 'available': False,
                  'icon': 'lucide:users', 'note': 'Planned: needs individual / organisation rules (Appendix H)'},
}
