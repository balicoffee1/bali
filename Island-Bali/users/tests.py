from django.test import TestCase
from django.urls import reverse
from fcm_django.models import FCMDevice
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import CustomUser


class FCMTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            login="+79991112233",
            first_name="Test",
            last_name="Barista",
            role="employee",
            is_staff=True,
        )
        self.register_url = reverse("users:fcm-register")
        self.unregister_url = reverse("users:fcm-unregister")

    def _auth(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_register_fcm_token_authenticated(self):
        self._auth()
        token = "test_fcm_token_12345"
        response = self.client.post(
            self.register_url,
            {"registration_id": token, "type_device": "android"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok"})

        device = FCMDevice.objects.get(registration_id=token)
        self.assertEqual(device.user, self.user)
        self.assertTrue(device.active)
        self.assertEqual(device.type, "android")

    def test_register_fcm_token_requires_auth(self):
        response = self.client.post(
            self.register_url,
            {"registration_id": "token_unauth"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_fcm_token_requires_registration_id(self):
        self._auth()
        response = self.client.post(
            self.register_url,
            {"type_device": "android"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unregister_fcm_token_deletes_device_and_clears_user_field(self):
        token = "test_token_to_unregister"
        FCMDevice.objects.create(
            registration_id=token,
            user=self.user,
            active=True,
            type="ios",
        )
        self.user.fcm_token = token
        self.user.save(update_fields=["fcm_token"])

        # Unregister works even without Authorization header (e.g. after logout)
        response = self.client.post(
            self.unregister_url,
            {"registration_id": token},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok"})

        self.assertFalse(FCMDevice.objects.filter(registration_id=token).exists())
        self.user.refresh_from_db()
        self.assertIsNone(self.user.fcm_token)

    def test_unregister_fcm_token_idempotent(self):
        response = self.client.post(
            self.unregister_url,
            {"registration_id": "non_existent_token"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok"})

    def test_unregister_fcm_token_requires_registration_id(self):
        response = self.client.post(
            self.unregister_url,
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
