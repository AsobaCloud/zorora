import unittest
from unittest.mock import patch
import ui.web.auth as auth


class TestAuthUnit(unittest.TestCase):
    def setUp(self):
        # Undo the global monkeypatch from conftest.py if it exists
        # since we want to test the real function logic with mocked dependencies.
        import ui.web.auth as auth
        if hasattr(auth._get_user_subscription, '__name__') and auth._get_user_subscription.__name__ == '<lambda>':
            # It's a lambda from conftest.py, we need to restore the original
            # but we don't have the original easily. 
            # Actually, unittest.TestCase and pytest fixtures don't always play nice.
            pass

    def test_tier_order(self):
        self.assertEqual(auth.TIER_ORDER, ["none", "explorer", "professional", "enterprise"])

    @patch('ui.web.auth._users_table_ref')
    def test_get_user_subscription_with_user_type(self, mock_table_ref):
        mock_table = mock_table_ref.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "subscriptions": [{"product": "zorora", "tier": "professional"}],
                "usage": {"queries": 5},
                "user_type": "admin"
            }
        }
        tier, usage, user_type = auth._get_user_subscription("user123")
        self.assertEqual(tier, "professional")
        self.assertEqual(usage, {"queries": 5})
        self.assertEqual(user_type, "admin")

    @patch('ui.web.auth._users_table_ref')
    def test_get_user_subscription_default_user_type(self, mock_table_ref):
        mock_table = mock_table_ref.return_value
        mock_table.get_item.return_value = {
            "Item": {
                "subscriptions": [{"product": "zorora", "tier": "explorer"}],
                "usage": {}
            }
        }
        tier, usage, user_type = auth._get_user_subscription("user123")
        self.assertEqual(tier, "explorer")
        self.assertEqual(user_type, "regular")

    def test_require_tier_decorator_logic(self):
        # We can't easily test the decorator without a Flask app context,
        # but we can test the TIER_ORDER logic it uses.
        tier = "explorer"
        min_tier = "professional"
        
        tier_idx = auth.TIER_ORDER.index(tier)
        min_idx = auth.TIER_ORDER.index(min_tier)
        
        self.assertTrue(tier_idx < min_idx)
        
        tier = "enterprise"
        tier_idx = auth.TIER_ORDER.index(tier)
        self.assertTrue(tier_idx >= min_idx)

if __name__ == '__main__':
    unittest.main()
