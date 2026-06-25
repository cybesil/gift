from django.contrib import admin
from .models import *

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductSizeInline(admin.TabularInline):
    model = ProductSize
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline, ProductSizeInline]

admin.site.register(Product, ProductAdmin)
admin.site.register(UserProfile)
admin.site.register(Category)
admin.site.register(ProductImage)
admin.site.register(Size)
admin.site.register(ProductSize)
admin.site.register(ShippingAddress)
admin.site.register(User)
admin.site.register(ExchangeRate)
admin.site.register(OrderItem)
@admin.register(BannerAd)
class BannerAdAdmin(admin.ModelAdmin):
    list_display = ['name', 'header', 'cta_text', 'is_active', 'created_at']
    list_editable = ['is_active']   # toggle live/off directly from the list view
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Identity', {'fields': ('name',)}),
        ('Visuals', {'fields': ('image',)}),
        ('Copy', {'fields': ('header', 'subheading', 'teaser', 'cta_text', 'price_tag')}),
        ('Action', {'fields': ('redirect_url', 'is_active')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(BannerAd2)
class BannerAd2Admin(admin.ModelAdmin):
    list_display = ['name', 'header', 'cta_text', 'is_active', 'created_at']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Identity', {'fields': ('name',)}),
        ('Visuals', {'fields': ('image',)}),
        ('Copy', {'fields': ('header', 'subheading', 'teaser', 'cta_text', 'price_tag')}),
        ('Action', {'fields': ('redirect_url', 'is_active')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )