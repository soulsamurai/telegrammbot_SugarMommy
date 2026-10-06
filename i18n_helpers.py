"""Вспомогательные функции для JSON i18n полей услуг."""

from db.models.service import Service


def service_name(service: Service, locale: str) -> str:
    return (
        service.name_i18n.get(locale)
        or service.name_i18n.get("ru")
        or next(iter(service.name_i18n.values()), str(service.id))
    )


def service_description(service: Service, locale: str) -> str:
    return (
        service.description_i18n.get(locale)
        or service.description_i18n.get("ru")
        or ""
    )
