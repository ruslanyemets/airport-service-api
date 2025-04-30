from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework import status

from airport.models import Crew, Flight
from airport.serializers import FlightListSerializer, FlightDetailSerializer
from tests.test_airplane_api import sample_airplane
from tests.test_route_api import sample_route, create_airport

FLIGHT_URL = reverse("airport:flight-list")


def sample_flight(**params):
    airplane = sample_airplane()
    route = sample_route()
    dt_1 = datetime.strptime("2025-04-05 12:00:00", "%Y-%m-%d %H:%M:%S")
    dt_2 = datetime.strptime("2025-04-05 14:00:00", "%Y-%m-%d %H:%M:%S")
    defaults = {
        "departure_time": timezone.make_aware(dt_1),
        "arrival_time": timezone.make_aware(dt_2),
        "airplane": airplane,
        "route": route,
    }
    defaults.update(params)

    return Flight.objects.create(**defaults)


def detail_url(flight_id):
    return reverse("airport:flight-detail", args=[flight_id])


class UnauthenticatedFlightApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(FLIGHT_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedFlightApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "test@test.com",
            "test_password_12345",
        )
        self.client.force_authenticate(self.user)
        self.flight = sample_flight()
        self.serializer = self.remove_ticket_field(
            FlightListSerializer(self.flight).data.copy()
        )
        self.new_route = sample_route(
            source=create_airport("LAX", "Los Angeles", "USA"),
            destination=create_airport("JFK International", "New York", "USA"),
        )
        self.new_departure_time = timezone.make_aware(
            datetime.strptime("2025-04-05 10:00:00", "%Y-%m-%d %H:%M:%S")
        )
        self.new_flight = sample_flight(
            route=self.new_route, departure_time=self.new_departure_time
        )

    @staticmethod
    def remove_ticket_field(data):
        data.pop("tickets_available", None)
        return data

    def test_list_flights(self):
        sample_flight()
        sample_flight()

        res = self.client.get(FLIGHT_URL)

        flights = Flight.objects.all().order_by("id")
        serializer = FlightListSerializer(flights, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        resp_ids = {item["id"] for item in res.data}
        expected_ids = {item["id"] for item in serializer.data}

        self.assertEqual(resp_ids, expected_ids)
        self.assertEqual(len(res.data), len(serializer.data))

        for resp_item, ser_item in zip(res.data, serializer.data):
            self.assertEqual(
                resp_item["departure_time"], ser_item["departure_time"]
            )
            self.assertEqual(
                resp_item["arrival_time"], ser_item["arrival_time"]
            )
            self.assertEqual(
                resp_item["flight_duration"], ser_item["flight_duration"]
            )

    def test_filter_flights_by_country(self):
        flight_2 = self.new_flight

        res = self.client.get(FLIGHT_URL, {"country": "USA"})

        serializer_1 = self.serializer
        serializer_2 = self.remove_ticket_field(
            FlightListSerializer(flight_2).data.copy()
        )

        res_data = [self.remove_ticket_field(item.copy()) for item in res.data]

        self.assertNotIn(serializer_1, res_data)
        self.assertIn(serializer_2, res_data)

    def test_filter_flights_by_route(self):
        flight_2 = self.new_flight

        res = self.client.get(FLIGHT_URL, {"route": self.new_route.id})

        serializer_1 = self.serializer
        serializer_2 = self.remove_ticket_field(
            FlightListSerializer(flight_2).data.copy()
        )

        res_data = [self.remove_ticket_field(item.copy()) for item in res.data]

        self.assertNotIn(serializer_1, res_data)
        self.assertIn(serializer_2, res_data)

    def test_filter_flights_by_departure_time(self):
        flight_2 = self.new_flight

        departure_time_str = (
            self.new_flight.departure_time.strftime("%Y-%m-%d %H:%M")
        )

        res = self.client.get(
            FLIGHT_URL, {"departure_time": departure_time_str}
        )

        serializer_1 = self.serializer
        serializer_2 = self.remove_ticket_field(
            FlightListSerializer(flight_2).data.copy()
        )

        res_data = [self.remove_ticket_field(item.copy()) for item in res.data]

        self.assertNotIn(serializer_1, res_data)
        self.assertIn(serializer_2, res_data)

    def test_retrieve_flight_detail(self):
        flight = sample_flight()
        url = detail_url(flight.id)
        res = self.client.get(url)

        serializer = FlightDetailSerializer(flight)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_flight_forbidden(self):
        airplane = sample_airplane()
        route = sample_route()
        dt_1 = datetime.strptime("2025-04-05 12:00:00", "%Y-%m-%d %H:%M:%S")
        dt_2 = datetime.strptime("2025-04-05 14:00:00", "%Y-%m-%d %H:%M:%S")
        payload = {
            "departure_time": timezone.make_aware(dt_1),
            "arrival_time": timezone.make_aware(dt_2),
            "airplane": airplane,
            "route": route,
        }
        res = self.client.post(FLIGHT_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminFlightApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "admin@example.com", "test_password_12345", is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.new_route = sample_route(
            source=create_airport("LAX", "Los Angeles", "USA"),
            destination=create_airport("JFK International", "New York", "USA"),
        )
        self.new_flight = sample_flight(route=self.new_route)

    def test_create_flight(self):
        airplane = sample_airplane()
        route = sample_route()
        dt_1 = datetime.strptime("2025-04-05 12:00:00", "%Y-%m-%d %H:%M:%S")
        dt_2 = datetime.strptime("2025-04-05 14:00:00", "%Y-%m-%d %H:%M:%S")
        payload = {
            "departure_time": timezone.make_aware(dt_1),
            "arrival_time": timezone.make_aware(dt_2),
            "airplane": airplane.id,
            "route": route.id,
        }
        res = self.client.post(FLIGHT_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        flight = Flight.objects.get(id=res.data["id"])
        self.assertEqual(payload["departure_time"], flight.departure_time)
        self.assertEqual(payload["route"], flight.route.id)
        self.assertEqual(payload["airplane"], flight.airplane.id)

    def test_create_flight_with_crew(self):
        airplane = sample_airplane()
        route = sample_route()
        crew_1 = Crew.objects.create(first_name="John", last_name="Doe")
        crew_2 = Crew.objects.create(first_name="Alice", last_name="Smith")
        dt_1 = datetime.strptime("2025-04-05 12:00:00", "%Y-%m-%d %H:%M:%S")
        dt_2 = datetime.strptime("2025-04-05 14:00:00", "%Y-%m-%d %H:%M:%S")
        payload = {
            "departure_time": timezone.make_aware(dt_1),
            "arrival_time": timezone.make_aware(dt_2),
            "crew": [crew_1.id, crew_2.id],
            "airplane": airplane.id,
            "route": route.id,
        }
        res = self.client.post(FLIGHT_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        flight = Flight.objects.get(id=res.data["id"])
        crew = flight.crew.all()
        self.assertEqual(crew.count(), 2)
        self.assertIn(crew_1, crew)
        self.assertIn(crew_2, crew)

    def test_put_flight(self):
        airplane = sample_airplane()
        dt_1 = datetime.strptime("2025-05-05 10:00:00", "%Y-%m-%d %H:%M:%S")
        dt_2 = datetime.strptime("2025-05-05 18:00:00", "%Y-%m-%d %H:%M:%S")
        payload = {
            "departure_time": timezone.make_aware(dt_1),
            "arrival_time": timezone.make_aware(dt_2),
            "airplane": airplane.id,
            "route": self.new_route.id,
        }

        flight = sample_flight()
        url = detail_url(flight.id)

        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_delete_flight_not_allowed(self):
        flight = sample_flight()
        url = detail_url(flight.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
