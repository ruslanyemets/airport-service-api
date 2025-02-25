from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from airport.models import Country, Airport, Route
from airport.serializers import RouteListSerializer, RouteDetailSerializer

ROUTE_URL = reverse("airport:route-list")


def create_airport(name, closest_big_city, country_name):
    country, _ = Country.objects.get_or_create(name=country_name)
    return Airport.objects.create(
        name=name,
        closest_big_city=closest_big_city,
        country=country
    )


def sample_route(**params):
    airport_1 = Airport.objects.create(
        name="Heathrow",
        closest_big_city="London",
        country=Country.objects.get_or_create(name="UK")[0],
    )
    airport_2 = Airport.objects.create(
        name="Frankfurt",
        closest_big_city="Frankfurt",
        country=Country.objects.get_or_create(name="Germany")[0],
    )
    defaults = {"distance": 700, "source": airport_1, "destination": airport_2}
    defaults.update(params)

    return Route.objects.create(**defaults)


def detail_url(route_id):
    return reverse("airport:route-detail", args=[route_id])


class UnauthenticatedRouteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(ROUTE_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedRouteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "test@test.com",
            "test_password_12345",
        )
        self.client.force_authenticate(self.user)
        self.new_source = create_airport(
            "LAX",
            "Los Angeles",
            "USA"
        )
        self.new_destination = create_airport(
            "JFK International",
            "New York",
            "USA"
        )

    def test_list_routes(self):
        sample_route()
        sample_route()

        res = self.client.get(ROUTE_URL)

        routes = Route.objects.all().order_by("id")
        serializer = RouteListSerializer(routes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_filter_routes_by_source_city(self):
        route_1 = sample_route()
        route_2 = sample_route(
            source=self.new_source,
            destination=self.new_destination
        )

        res = self.client.get(ROUTE_URL, {"source_city": "Los Angeles"})

        serializer_1 = RouteListSerializer(route_1)
        serializer_2 = RouteListSerializer(route_2)

        self.assertNotIn(serializer_1.data, res.data)
        self.assertIn(serializer_2.data, res.data)

    def test_filter_routes_by_destination_city(self):
        route_1 = sample_route()
        route_2 = sample_route(
            source=self.new_source,
            destination=self.new_destination
        )

        res = self.client.get(ROUTE_URL, {"destination_city": "New York"})

        serializer_1 = RouteListSerializer(route_1)
        serializer_2 = RouteListSerializer(route_2)

        self.assertNotIn(serializer_1.data, res.data)
        self.assertIn(serializer_2.data, res.data)

    def test_filter_routes_by_airport(self):
        route_1 = sample_route()
        route_2 = sample_route(
            source=self.new_source,
            destination=self.new_destination
        )

        res = self.client.get(ROUTE_URL, {"airport": "LAX"})

        serializer_1 = RouteListSerializer(route_1)
        serializer_2 = RouteListSerializer(route_2)

        self.assertNotIn(serializer_1.data, res.data)
        self.assertIn(serializer_2.data, res.data)

    def test_retrieve_route_detail(self):
        route = sample_route()
        url = detail_url(route.id)
        res = self.client.get(url)

        serializer = RouteDetailSerializer(route)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_route_forbidden(self):
        payload = {
            "distance": 2500,
            "source": self.new_source,
            "destination": self.new_destination
        }
        res = self.client.post(ROUTE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminRouteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "admin@example.com", "test_password_12345", is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.new_source = create_airport(
            "LAX",
            "Los Angeles",
            "USA"
        )
        self.new_destination = create_airport(
            "JFK International",
            "New York",
            "USA"
        )

    def test_create_route(self):
        payload = {
            "distance": 2600,
            "source": self.new_source.id,
            "destination": self.new_destination.id,
        }
        res = self.client.post(ROUTE_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        route = Route.objects.get(id=res.data["id"])
        self.assertEqual(payload["distance"], route.distance)
        self.assertEqual(payload["source"], route.source.id)
        self.assertEqual(payload["destination"], route.destination.id)

    def test_put_route_not_allowed(self):
        payload = {
            "distance": 2400,
            "source": self.new_source,
            "destination": self.new_destination
        }

        route = sample_route()
        url = detail_url(route.id)

        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_route_not_allowed(self):
        route = sample_route()
        url = detail_url(route.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
