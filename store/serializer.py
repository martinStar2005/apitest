from django.utils.text import slugify
from django.db import transaction

from rest_framework import serializers
from decimal import Decimal

from .models import Category, Product, Comment, Cart, CartItem, Customer, Order, OrderItem


class ProductSerializer(serializers.ModelSerializer):
    price_after_tax = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'unit_price', 'category', 'price_after_tax', 'inventory']

    def get_price_after_tax(self, product):
        return round(product.unit_price * Decimal(1.15), 2)

    def create(self, validated_data):
        product = Product(**validated_data)
        product.slug = slugify(product.name)
        product.save()
        return product


class CategorySerializer(serializers.ModelSerializer):
    count_of_products_for_each_category = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['title', 'description', 'count_of_products_for_each_category']

    def get_count_of_products_for_each_category(self, category):
        return category.products.count()


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'name', 'body']

    def create(self, validated_data):
        product_id = self.context['product_pk']
        return Comment.objects.create(product_id=product_id, **validated_data)


class CartProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'unit_price']


class CartItemSerializer(serializers.ModelSerializer):
    product = CartProductSerializer()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'total_price']

    def get_total_price(self, cart_item):
        return cart_item.product.unit_price * cart_item.quantity


class CartItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['quantity']


class CartItemAddSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity']

    def create(self, validated_data):
        cart_id = self.context['cart_pk']
        product = validated_data.get('product')
        quantity = validated_data.get('quantity')

        try:
            new_item = CartItem.objects.get(cart_id=cart_id, product=product)
            new_item.quantity += quantity
            new_item.save()
        except CartItem.DoesNotExist:
            new_item = CartItem.objects.create(cart_id=cart_id, **validated_data)

        self.instance = new_item
        return new_item


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    cart_total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'cart_total_price']
        read_only_fields = ['id',]

    def get_cart_total_price(self, cart):
        return sum([item.quantity * item.product.unit_price for item in cart.items.all()])


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'user', 'birth_date']
        read_only_fields = ['user']


class OrderCustomerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')

    class Meta:
        model = Customer
        fields = ['id', 'first_name', 'last_name', 'birth_date']


class OrderItemProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'unit_price']


class OrderItemsSerializer(serializers.ModelSerializer):
    product = OrderItemProductSerializer()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity']


class OrderAdminSerializer(serializers.ModelSerializer):
    customer = OrderCustomerSerializer()
    items = OrderItemsSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'status', 'datetime_created', 'items']


class OrderUserSerializer(serializers.ModelSerializer):
    items = OrderItemsSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'status', 'datetime_created', 'items']


class OrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']

class OrderCreateSerializer(serializers.Serializer):
    cart_id = serializers.UUIDField()

    def validate_cart_id(self, cart_id):
        if not Cart.objects.filter(id=cart_id).exists():
            raise serializers.ValidationError('There is no Cart with this id')

        if CartItem.objects.filter(cart_id=cart_id).count() == 0:
            raise serializers.ValidationError('This cart is empty')

        return cart_id

    def save(self, **kwargs):
        with transaction.atomic():
            user_id = self.context['user_id']
            cart_id = self.validated_data['cart_id']
            customer = Customer.objects.get(user_id=user_id)

            order = Order()
            order.customer = customer
            order.save()

            cart_item = CartItem.objects.select_related('product').filter(cart_id=cart_id)

            order_items = [
                OrderItem(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    unit_price=item.product.unit_price
                ) for item in cart_item]

            OrderItem.objects.bulk_create(order_items)

            Cart.objects.get(id=cart_id).delete()

            return order






