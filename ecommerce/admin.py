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
# admin.site.register(Order)
# admin.site.register(OrderItem)