from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from admin_api.models import AdminActivityLog
from users.models import CustomUser


class AdminUserSerializerPrivilegeTests(TestCase):
    """
    AdminUserSerializer отдавал role, is_staff и is_superuser на запись, а
    ModelViewSet принимает их и на POST, и на PATCH. То есть любой admin мог
    создать себе суперпользователя или поднять роль обычным запросом к
    /api/admin/users/, минуя set_role, закрытый IsSuperAdmin.
    """

    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            login='+79990000001', password='pw', role='owner', first_name='Owner'
        )
        self.admin = CustomUser.objects.create_user(
            login='+79990000002', password='pw', role='admin', first_name='Admin'
        )

    def auth_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'

    def payload(self, **overrides):
        data = {
            'login': '+79995550011',
            'first_name': 'Динара',
            'last_name': 'Сафина',
            'phone_number': '+79995550011',
            'role': 'employee',
        }
        data.update(overrides)
        return data

    def create_user(self, **overrides):
        return self.client.post(
            '/api/admin/users/',
            data=self.payload(**overrides),
            content_type='application/json',
        )

    # ---------------------------------------------------------------- create

    def test_admin_cannot_create_superuser(self):
        self.auth_as(self.admin)
        response = self.create_user(is_superuser=True, is_staff=True)

        self.assertEqual(response.status_code, 201, response.data)
        created = CustomUser.objects.get(login='+79995550011')
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_staff)

    def test_admin_cannot_create_privileged_role(self):
        self.auth_as(self.admin)
        for role in ('owner', 'admin', 'moderator', 'support'):
            with self.subTest(role=role):
                response = self.create_user(role=role, login=f'+7999555{role[:4]}')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('role', response.data)

    def test_admin_can_create_employee(self):
        self.auth_as(self.admin)
        response = self.create_user()

        self.assertEqual(response.status_code, 201, response.data)
        created = CustomUser.objects.get(login='+79995550011')
        self.assertEqual(created.role, 'employee')
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)

    def test_owner_can_create_admin_and_flag_follows_role(self):
        self.auth_as(self.owner)
        response = self.create_user(role='admin')

        self.assertEqual(response.status_code, 201, response.data)
        created = CustomUser.objects.get(login='+79995550011')
        self.assertEqual(created.role, 'admin')
        # is_staff выводится из роли, а не берётся из запроса.
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)

    def test_creation_is_written_to_audit_log(self):
        self.auth_as(self.admin)
        self.create_user()

        log = AdminActivityLog.objects.filter(
            action='CREATE', entity_name='CustomUser'
        ).first()
        self.assertIsNotNone(log)
        self.assertIn('+79995550011', log.summary)

    # ---------------------------------------------------------------- update

    def test_admin_cannot_escalate_existing_user_via_patch(self):
        target = CustomUser.objects.create_user(
            login='+79995550022', password='pw', role='user', first_name='Client'
        )
        self.auth_as(self.admin)

        response = self.client.patch(
            f'/api/admin/users/{target.id}/',
            data={'role': 'admin', 'is_superuser': True},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        target.refresh_from_db()
        self.assertEqual(target.role, 'user')
        self.assertFalse(target.is_superuser)
        self.assertFalse(target.is_staff)

    def test_admin_cannot_grant_itself_superuser_via_patch(self):
        self.auth_as(self.admin)

        response = self.client.patch(
            f'/api/admin/users/{self.admin.id}/',
            data={'is_superuser': True, 'is_staff': True},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_superuser)
        # admin — привилегированная роль, поэтому is_staff остаётся True,
        # но именно потому что так говорит роль, а не запрос.
        self.assertTrue(self.admin.is_staff)

    def test_owner_can_still_change_role_via_patch(self):
        target = CustomUser.objects.create_user(
            login='+79995550033', password='pw', role='user', first_name='Client'
        )
        self.auth_as(self.owner)

        response = self.client.patch(
            f'/api/admin/users/{target.id}/',
            data={'role': 'moderator'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        target.refresh_from_db()
        self.assertEqual(target.role, 'moderator')
        self.assertFalse(target.is_staff)
