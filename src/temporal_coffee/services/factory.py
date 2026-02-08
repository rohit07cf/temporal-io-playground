"""Simple factory for service singletons."""

from temporal_coffee.services.brewing import BrewService
from temporal_coffee.services.notify import NotificationService
from temporal_coffee.services.payment import PaymentService


class ServiceFactory:
    """Lazily creates and caches service instances."""

    _payment: PaymentService | None = None
    _brew: BrewService | None = None
    _notification: NotificationService | None = None

    @classmethod
    def get_payment_service(cls) -> PaymentService:
        if cls._payment is None:
            cls._payment = PaymentService()
        return cls._payment

    @classmethod
    def get_brew_service(cls) -> BrewService:
        if cls._brew is None:
            cls._brew = BrewService()
        return cls._brew

    @classmethod
    def get_notification_service(cls) -> NotificationService:
        if cls._notification is None:
            cls._notification = NotificationService()
        return cls._notification
