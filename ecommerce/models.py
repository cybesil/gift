from django.db import models
from django.contrib.auth.models import AbstractUser
from django.urls import reverse
from django.db.models.signals import post_save
from django.dispatch import receiver
from cloudinary.models import CloudinaryField
from cloudinary import CloudinaryImage
from django.utils.text import slugify
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys


# ─── USERS ───────────────────────────────────────────

class User(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, blank=True)
    profile_img = CloudinaryField('image', null=True, blank=True)
    phone_num = models.CharField(max_length=20, blank=True)#call line
    phone_num2 = models.CharField(max_length=20, blank=True)#whatsapp
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active_customer = models.BooleanField(default=True)
    # for adding to cart after logging out and logging back in
    old_cart = models.CharField(max_length=1000, null=True, blank=True)

    @property
    def profile_pic(self):
        if self.profile_img:
            return CloudinaryImage(str(self.profile_img)).build_url(
                width=500, height=500, crop='fill', format='jpg'
            )
        return None

    def __str__(self):
        return f"{self.user.username}'s Profile"


# ─── CATALOG ─────────────────────────────────────────

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )
    description = models.TextField(blank=True)
    image = CloudinaryField('image', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        # Resize image before saving
        if self.image:
            self.image = self._resize_image(self.image)
        super().save(*args, **kwargs)

    def _resize_image(self, image_field, size=(800, 800), quality=85):
        """Resize and crop image to exact square dimensions."""
        img = Image.open(image_field)
        img = img.convert('RGB')

        # Crop to centered square first, then resize
        width, height = img.size
        min_dim = min(width, height)

        # Calculate crop box for center crop
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim

        img = img.crop((left, top, right, bottom))
        img = img.resize(size, Image.LANCZOS)

        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)

        # Generate clean filename
        original_name = getattr(image_field, 'name', 'image.jpg')
        base_name = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name

        return InMemoryUploadedFile(
            output,
            'ImageField',
            f"{base_name}.jpg",
            'image/jpeg',
            sys.getsizeof(output),
            None
        )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('ecommerce:products', args=[self.slug])


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='products'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.PositiveIntegerField(null=True, blank=True)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def get_absolute_url(self):
        return reverse('ecommerce:product_detail', args=[self.slug])

    @property
    def primary_image(self):
        key_img = self.images.filter(is_key=True).first()
        if key_img:
            return key_img.image_url
        first_img = self.images.first()
        return first_img.image_url if first_img else None

    @property
    def is_on_sale(self):
        return self.discount_price is not None and self.discount_price < self.price

    @property
    def display_price(self):
        return self.discount_price if self.is_on_sale else self.price

    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.slug:
            base = slugify(self.name)
            slug = base
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug

        # Auto-generate SKU (num explicitly scoped to avoid linter warnings)
        if not self.sku:
            num = 1
            last = Product.objects.order_by('-id').first()
            if last and last.sku and last.sku.startswith('PRD-'):
                try:
                    num = int(last.sku.split('-')[1]) + 1
                except (IndexError, ValueError):
                    pass
            self.sku = f"PRD-{num:03d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image')
    alt_text = models.CharField(max_length=255, blank=True, help_text="SEO / accessibility description")
    is_key = models.BooleanField(default=False, help_text="Primary display image for this product")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'created_at']

    @property
    def image_url(self):
        if self.image:
            return CloudinaryImage(str(self.image)).build_url(
                width=800, height=800, crop='fill', format='jpg', quality='auto'
            )
        return None

    @property
    def thumbnail_url(self):
        if self.image:
            return CloudinaryImage(str(self.image)).build_url(
                width=300, height=300, crop='fill', format='jpg', quality='auto'
            )
        return None

    def save(self, *args, **kwargs):
        if self.is_key:
            ProductImage.objects.filter(
                product=self.product, is_key=True
            ).exclude(pk=self.pk).update(is_key=False)
        if self.image:
            self.image = self._resize_image(self.image)
        super().save(*args, **kwargs)

    def _resize_image(self, image_field, size=(800, 800), quality=85):
        """Resize and crop image to exact square dimensions."""
        img = Image.open(image_field)
        img = img.convert('RGB')

        # Crop to centered square first, then resize
        width, height = img.size
        min_dim = min(width, height)

        # Calculate crop box for center crop
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim

        img = img.crop((left, top, right, bottom))
        img = img.resize(size, Image.LANCZOS)

        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)

        # Generate clean filename
        original_name = getattr(image_field, 'name', 'image.jpg')
        base_name = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name

        return InMemoryUploadedFile(
            output,
            'ImageField',
            f"{base_name}.jpg",
            'image/jpeg',
            sys.getsizeof(output),
            None
        )

    def __str__(self):
        return f"Image for {self.product.name} {'(Key)' if self.is_key else ''}"


# ─── SIZES (Lookup table — select from existing) ─────

class Size(models.Model):
    SIZE_TYPE_CHOICES = [
        ('numeric', 'Numeric'),
        ('alpha', 'Alpha'),
    ]

    size_type = models.CharField(max_length=10, choices=SIZE_TYPE_CHOICES)
    value = models.CharField(max_length=10)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['size_type', 'display_order', 'value']
        unique_together = ['size_type', 'value']
        verbose_name_plural = 'sizes'

    def __str__(self):
        return f"{self.value} ({self.get_size_type_display()})"


class ProductSize(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sizes')
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name='product_entries')
    stock = models.PositiveIntegerField(default=0)
    price_adjustment = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Additional cost for this size variant")
    sku = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ['product', 'size']

    def __str__(self):
        return f"{self.product.name} - {self.size.value}"

    @property
    def final_price(self):
        return self.product.display_price + self.price_adjustment


# ─── SHIPPING ───────────────────────────────────────

class ShippingAddress(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='addresses',
        null=True, blank=True
    )
    full_name = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    street_address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, default='Nigeria')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} — {self.city}, {self.state}"


# ─── ORDERS ──────────────────────────────────────────

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    shipping_address = models.ForeignKey(
        ShippingAddress, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders'
    )
    shipping_address_snapshot = models.TextField(
        blank=True, help_text="Backup text in case shipping address is deleted"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    billing_address = models.TextField(blank=True)
    tracking_number = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_size = models.ForeignKey(
        ProductSize, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='order_items'
    )
    size_display = models.CharField(
        max_length=20, blank=True,
        help_text="Snapshot of size ordered, e.g. '20\\\"' or 'XL'"
    )
    product_name = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return self.price * self.quantity




@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        ShippingAddress.objects.get_or_create(user=instance)
    else:
        if not hasattr(instance, 'profile'):
            UserProfile.objects.get_or_create(user=instance)
        if not instance.addresses.exists():
            ShippingAddress.objects.get_or_create(
                user=instance,
                defaults={'is_default': True}
            )