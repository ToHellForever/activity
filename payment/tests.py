from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, override_settings

from payment.robokassa import build_payment_url, verify_result_signature
import hashlib


@override_settings(
    ROBOKASSA_MERCHANT_LOGIN="test-shop",
    ROBOKASSA_PASSWORD1="password-one",
    ROBOKASSA_PASSWORD2="password-two",
    ROBOKASSA_HASH_ALGORITHM="MD5",
    ROBOKASSA_TEST_MODE=True,
)
class RobokassaIntegrationTests(SimpleTestCase):
    def test_payment_url_contains_amount_invoice_and_valid_signature(self):
        url = build_payment_url(42, "125.5", "Event ticket", "buyer@example.com")
        params = parse_qs(urlparse(url).query)

        self.assertEqual(params["MerchantLogin"], ["test-shop"])
        self.assertEqual(params["OutSum"], ["125.50"])
        self.assertEqual(params["InvId"], ["42"])
        self.assertEqual(params["IsTest"], ["1"])
        expected = hashlib.md5(
            b"test-shop:125.50:42:password-one"
        ).hexdigest().upper()
        self.assertEqual(params["SignatureValue"], [expected])

    def test_result_signature_sorts_custom_parameters(self):
        params = {
            "OutSum": "125.50",
            "InvId": "42",
            "Shp_z": "last",
            "Shp_a": "first",
        }
        signature_base = (
            "125.50:42:password-two:Shp_a=first:Shp_z=last"
        )
        params["SignatureValue"] = hashlib.md5(
            signature_base.encode("utf-8")
        ).hexdigest()

        self.assertTrue(verify_result_signature(params))
        params["OutSum"] = "125.51"
        self.assertFalse(verify_result_signature(params))
