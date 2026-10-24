from django.conf import settings


def theme(request):
    return {"theme": settings.THEME_CONFIG["theme"]}
