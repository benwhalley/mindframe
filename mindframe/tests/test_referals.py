import json
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from mindframe.models import (
    Conversation,
    CustomUser,
    Intervention,
    Note,
    Referal,
    ReferalToken,
)


class ReferalTests(TestCase):
    def setUp(self):
        # Create test users
        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="testpass123",
            role="admin",
        )
        self.client_user = CustomUser.objects.create_user(
            username="testclient",
            password="testpass123",
            role="client",
        )

        # Create test intervention
        self.intervention = Intervention.objects.create(
            title="Test Intervention",
            slug="test-intervention",
        )

        # Create valid referal token
        self.referal_token = ReferalToken.objects.create(
            token="test-token-123",
            label="Test Token",
        )
        self.referal_token.permitted_interventions.add(self.intervention)

        # Create invalid referal token (expired)
        self.expired_token = ReferalToken.objects.create(
            token="expired-token-123",
            label="Expired Token",
            start=timezone.now() - timedelta(days=2),
            end=timezone.now() - timedelta(days=1),
        )

        # Create client for making requests
        self.client = Client()

    def test_create_referal_with_valid_token(self):
        """Test creating a referal with valid token and data"""
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_referal"),
            {
                # plan_token ?? TODO
                "plan_token_token": self.referal_token.id,
                "intervention": self.intervention.id,
                "username": "testclient",
                "data": json.dumps(
                    {"nickname": "Test", "interests": "testing", "current_emotion": "excited"}
                ),
                "redirect": "web",
                "create_if_doesnt_exist": True,
            },
        )

        self.assertEqual(response.status_code, 302)  # Should redirect
        self.assertTrue(Referal.objects.exists())
        self.assertTrue(Conversation.objects.exists())
        self.assertTrue(Note.objects.exists())

        referal = Referal.objects.first()
        self.assertEqual(referal.source, self.referal_token)
        self.assertEqual(referal.conversation.intervention, self.intervention)

    def test_create_referal_unauthorized(self):
        """Test that non-authenticated users cannot create referals"""
        response = self.client.post(
            reverse("create_referal"),
            {
                "referal_token": self.referal_token.id,
                "intervention": self.intervention.id,
                "username": "testclient",
                "data": json.dumps({"test": "data"}),
                "redirect": "web",
                "create_if_doesnt_exist": True,
            },
        )

        self.assertEqual(response.status_code, 302)  # Should redirect to login
        self.assertFalse(Referal.objects.exists())

    def test_create_referal_invalid_token(self):
        """Test creating referal with invalid token"""
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_referal"),
            {
                "referal_token": 999999,
                "intervention": self.intervention.id,
                "username": "testclient",
                "data": json.dumps({"test": "data"}),
                "redirect": "web",
                "create_if_doesnt_exist": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Referal.objects.exists())

    def test_create_referal_expired_token(self):
        """Test creating referal with expired token"""
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_referal"),
            {
                "referal_token": self.expired_token.id,
                "intervention": self.intervention.id,
                "username": "testclient",
                "data": json.dumps({"test": "data"}),
                "redirect": "web",
                "create_if_doesnt_exist": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Referal.objects.exists())

    def test_create_referal_invalid_intervention(self):
        """Test creating referal with invalid intervention"""
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_referal"),
            {
                "referal_token": self.referal_token.id,
                "intervention": 999999,
                "username": "testclient",
                "data": json.dumps({"test": "data"}),
                "redirect": "web",
                "create_if_doesnt_exist": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Referal.objects.exists())

    def test_create_referal_telegram_redirect(self):
        """Test creating referal with telegram redirect"""
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_referal"),
            {
                "referal_token": self.referal_token.id,
                "intervention": self.intervention.id,
                "username": "testclient",
                "data": json.dumps({"test": "data"}),
                "redirect": "telegram",
                "create_if_doesnt_exist": True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Referal.objects.exists())
        self.assertTrue("t.me" in response.url)  # Should redirect to telegram

    def test_create_referal_json_response(self):
        """Test creating referal with json response"""
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("create_referal"),
            {
                "referal_token": self.referal_token.id,
                "intervention": self.intervention.id,
                "username": "testclient",
                "data": json.dumps({"test": "data"}),
                "redirect": "json",
                "create_if_doesnt_exist": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(data)
        self.assertTrue("referal" in data)
        self.assertTrue("conversation_id" in data)
        self.assertTrue("url" in data)
        self.assertTrue("telegram_link" in data)
