from datetime import datetime

from django.db.models import F, Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
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
from airport.permissions import IsAdminOrIfAuthenticatedReadOnly
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
    OrderListSerializer,
    AirplaneListSerializer,
    AirplaneDetailSerializer,
    AirplaneImageSerializer
)


class AirplaneTypeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet
):
    queryset = AirplaneType.objects.all()
    serializer_class = AirplaneTypeSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class AirplaneViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Airplane.objects.select_related("airplane_type")
    serializer_class = AirplaneSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return AirplaneListSerializer

        if self.action == "retrieve":
            return AirplaneDetailSerializer

        if self.action == "upload_image":
            return AirplaneImageSerializer

        return AirplaneSerializer

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-image",
        permission_classes=[IsAdminUser],
    )
    def upload_image(self, request, pk=None):
        """Endpoint for uploading image to specific airplane"""
        airplane = self.get_object()
        serializer = self.get_serializer(airplane, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CountryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class AirportViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Airport.objects.select_related("country")
    serializer_class = AirportSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class RouteViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Route.objects.select_related("source", "destination")
    serializer_class = RouteSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_queryset(self):
        """Retrieve the routes with filters"""
        source_city = self.request.query_params.get("source_city")
        destination_city = self.request.query_params.get("destination_city")
        airport = self.request.query_params.get("airport")

        queryset = self.queryset

        if source_city:
            queryset = queryset.filter(
                source__closest_big_city__icontains=source_city
            )

        if destination_city:
            queryset = queryset.filter(
                destination__closest_big_city__icontains=destination_city
            )

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

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "source_city",
                type=OpenApiTypes.STR,
                description="Filter by source city (ex. ?source_city=London)",
            ),
            OpenApiParameter(
                "destination_city",
                type=OpenApiTypes.STR,
                description="Filter by destination city (ex. ?destination_city=Paris)",
            ),
            OpenApiParameter(
                "airport",
                type=OpenApiTypes.STR,
                description="Filter by airport name (ex. ?airport=Heathrow)",
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """Get list of routes"""
        return super().list(request, *args, **kwargs)


class CrewViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Crew.objects.all()
    serializer_class = CrewSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


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
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

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
            departure_time = datetime.strptime(
                departure_time, "%Y-%m-%d %H:%M"
            )
            queryset = queryset.filter(departure_time=departure_time)

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return FlightListSerializer

        if self.action == "retrieve":
            return FlightDetailSerializer

        return FlightSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "country",
                type=OpenApiTypes.STR,
                description="Filter by country (ex. ?country=Germany)",
            ),
            OpenApiParameter(
                "route",
                type=OpenApiTypes.INT,
                description="Filter by route id (ex. ?route=2)",
            ),
            OpenApiParameter(
                "departure_time",
                type=OpenApiTypes.DATETIME,
                description=(
                        "Filter by datetime of departure "
                        "(ex. ?departure_time=2021-08-25+15:00)"
                ),
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        """Get list of flights"""
        return super().list(request, *args, **kwargs)


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
