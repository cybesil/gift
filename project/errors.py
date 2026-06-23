from django.shortcuts import render

# Handles 404 Not Found
def error_404_view(request, exception=None):
    return render(request, "Error/fallback.html", status=404)

# Handles 500 Internal Server Error
def error_500_view(request):
    return render(request, "Error/fallback.html", status=500)

# Handles 403 Forbidden
def error_403_view(request, exception=None):
    return render(request, "Error/fallback.html", status=403)

# Handles 400 Bad Request
def error_400_view(request, exception=None):
    return render(request, "Error/fallback.html", status=400)
