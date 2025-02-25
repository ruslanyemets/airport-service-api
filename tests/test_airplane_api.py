import tempfile
import os

from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from airport.models import Airplane, AirplaneType
from airport.serializers import (
    AirplaneListSerializer,
    AirplaneDetailSerializer
)

AIRPLANE_URL = reverse("airport:airplane-list")


def create_airplane_type(name):
    return AirplaneType.objects.get_or_create(name=name)[0]


def sample_airplane(**params):
    airplane_type, _ = AirplaneType.objects.get_or_create(name="Boeing 737")
    defaults = {
        "name": "Sample airplane",
        "rows": 30,
        "seats_in_row": 6,
        "airplane_type": airplane_type,
    }
    defaults.update(params)

    return Airplane.objects.create(**defaults)


def image_upload_url(airplane_id):
    """Return URL for airplane image upload"""
    return reverse("airport:airplane-upload-image", args=[airplane_id])


def detail_url(airplane_id):
    return reverse("airport:airplane-detail", args=[airplane_id])


class UnauthenticatedAirplaneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(AIRPLANE_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedAirplaneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "test@test.com",
            "test_password_12345",
        )
        self.client.force_authenticate(self.user)
        self.new_airplane_type = create_airplane_type("Airbus A320")

    def test_list_airplanes(self):
        sample_airplane()
        sample_airplane()

        res = self.client.get(AIRPLANE_URL)

        flights = Airplane.objects.all().order_by("id")
        serializer = AirplaneListSerializer(flights, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_airplane_detail(self):
        airplane = sample_airplane()
        url = detail_url(airplane.id)
        res = self.client.get(url)

        serializer = AirplaneDetailSerializer(airplane)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_airplane_forbidden(self):
        payload = {
            "name": "Sample airplane",
            "rows": 30,
            "seats_in_row": 6,
            "airplane_type": self.new_airplane_type.id,
        }
        res = self.client.post(AIRPLANE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminAirplaneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "admin@example.com", "test_password_12345", is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.new_airplane_type = create_airplane_type("Boeing 777")

    def test_create_airplane(self):
        payload = {
            "name": "Sample airplane",
            "rows": 30,
            "seats_in_row": 6,
            "airplane_type": self.new_airplane_type.id,
        }
        res = self.client.post(AIRPLANE_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        airplane = Airplane.objects.get(id=res.data["id"])
        self.assertEqual(payload["name"], airplane.name)
        self.assertEqual(payload["rows"], airplane.rows)
        self.assertEqual(payload["seats_in_row"], airplane.seats_in_row)
        self.assertEqual(payload["airplane_type"], airplane.airplane_type.id)

    def test_put_airplane_not_allowed(self):
        payload = {
            "name": "Some airplane",
            "rows": 40,
            "seats_in_row": 8,
            "airplane_type": self.new_airplane_type.id,
        }

        airplane = sample_airplane()
        url = detail_url(airplane.id)

        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_airplane_not_allowed(self):
        airplane = sample_airplane()
        url = detail_url(airplane.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AirplaneImageUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser(
            "admin@myproject.com", "password_12345"
        )
        self.client.force_authenticate(self.user)
        self.airplane = sample_airplane()

    def tearDown(self):
        self.airplane.image.delete()

    def test_upload_image_to_airplane(self):
        """Test uploading an image to airplane"""
        url = image_upload_url(self.airplane.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(url, {"image": ntf}, format="multipart")
        self.airplane.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.airplane.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading an invalid image"""
        url = image_upload_url(self.airplane.id)
        res = self.client.post(url, {"image": "not image"}, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_image_to_airport_list_should_not_work(self):
        url = AIRPLANE_URL
        airplane_type = create_airplane_type("Airbus A320")
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(
                url,
                {
                    "name": "Some airplane",
                    "rows": 40,
                    "seats_in_row": 8,
                    "airplane_type": airplane_type.id,
                    "image": ntf,
                },
                format="multipart",
            )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        airplane = Airplane.objects.get(name="Some airplane")
        self.assertFalse(airplane.image)

    def test_image_url_is_shown_on_airplane_detail(self):
        url = image_upload_url(self.airplane.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            self.client.post(url, {"image": ntf}, format="multipart")
        res = self.client.get(detail_url(self.airplane.id))

        self.assertIn("image", res.data)

    def test_image_url_is_shown_on_airplane_list(self):
        url = image_upload_url(self.airplane.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            self.client.post(url, {"image": ntf}, format="multipart")
        res = self.client.get(AIRPLANE_URL)

        self.assertIn("image", res.data[0].keys())
