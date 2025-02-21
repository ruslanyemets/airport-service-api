from datetime import datetime

from django.db.models import F, Count, Q
from rest_framework import mixins
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from airport.models import (
    AirplaneType,
    Airplane,
    Country,
    Airport,
    Route,
    Crew,
    Flight,
    Order
)
from airport.serializers import (
    AirplaneTypeSerializer,
    AirplaneSerializer,
    CountrySerializer,
    AirportSerializer,
    RouteSerializer,
    CrewSerializer,
    RouteListSerializer,
    RouteDetailSerializer,
    FlightSerializer,
    FlightListSerializer,
    FlightDetailSerializer,
    OrderSerializer,
    OrderListSerializer
)


class AirplaneTypeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet
):
    queryset = AirplaneType.objects.all()
    serializer_class = AirplaneTypeSerializer
    permission_classes = (IsAuthenticated,)


class AirplaneViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Airplane.objects.select_related("airplane_type")
    serializer_class = AirplaneSerializer
    permission_classes = (IsAuthenticated,)


class CountryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = (IsAuthenticated,)


class AirportViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Airport.objects.select_related("country")
    serializer_class = AirportSerializer
    permission_classes = (IsAuthenticated,)


class RouteViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Route.objects.select_related("source", "destination")
    serializer_class = RouteSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Retrieve the routes with filters"""
        source = self.request.query_params.get("source")
        destination = self.request.query_params.get("destination")
        airport = self.request.query_params.get("airport")

        queryset = self.queryset

        if source:
            queryset = queryset.filter(source__name__icontains=source)

        if destination:
            queryset = queryset.filter(destination__name__icontains=destination)

        if airport:
            queryset = queryset.filter(
                Q(source__name__icontains=airport)
                | Q(destination__name__icontains=airport)
            )

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return RouteListSerializer

        if self.action == "retrieve":
            return RouteDetailSerializer

        return RouteSerializer


class CrewViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Crew.objects.all()
    serializer_class = CrewSerializer
    permission_classes = (IsAuthenticated,)


class FlightViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = (
        Flight.objects.all()
        .select_related("route", "airplane")
        .prefetch_related("crew")
        .annotate(
            tickets_available=(
                F("airplane__rows") * F("airplane__seats_in_row")
                - Count("tickets")
            )
        )
    )
    serializer_class = FlightSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Retrieve the flights with filters"""
        country = self.request.query_params.get("country")
        route_id_str = self.request.query_params.get("route")
        departure_time = self.request.query_params.get("departure_time")

        queryset = self.queryset

        if country:
            queryset = queryset.filter(
                Q(route__source__country__name__icontains=country)
                | Q(route__destination__country__name__icontains=country)
            )

        if route_id_str:
            queryset = queryset.filter(route__id=int(route_id_str))

        if departure_time:
            departure_time = datetime.strptime(departure_time, "%Y-%m-%d %H:%M")
            queryset = queryset.filter(departure_time=departure_time)

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return FlightListSerializer

        if self.action == "retrieve":
            return FlightDetailSerializer

        return FlightSerializer


class OrderPagination(PageNumberPagination):
    page_size = 3
    max_page_size = 100


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = Order.objects.prefetch_related(
        "tickets__flight__route", "tickets__flight__airplane"
    )
    serializer_class = OrderSerializer
    pagination_class = OrderPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer

        return OrderSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
