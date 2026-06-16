from .models import Category
from django.db.models import Prefetch

def categories(request):
    active_children = Category.objects.filter(is_active=True)

    top_level = Category.objects.filter(
        parent=None,
        is_active=True
    ).prefetch_related(
        Prefetch('children', queryset=active_children)
    )

    return {'categories': top_level}