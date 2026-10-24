from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    return render(
        request,
        "dashboard/index.html",
        {
            "camera_stream_url": settings.CAMERA_STREAM_URL,
            "control_websocket_url": settings.CONTROL_WEBSOCKET_URL,
        },
    )
