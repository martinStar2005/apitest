from django.shortcuts import get_object_or_404

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework import status
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Prefetch

from .filters import ProductFilter
from .serializer import ProductSerializer, CategorySerializer, CommentSerializer, CartSerializer, CartItemSerializer, \
    CartItemAddSerializer, CartItemUpdateSerializer, CustomerSerializer, OrderAdminSerializer, OrderUserSerializer, \
    OrderCreateSerializer, OrderUpdateSerializer
from .models import Product, Category, Comment, Cart, CartItem, Customer, Order, OrderItem
from .paginations import DefaultPagination
from .permission import IsAdminOrReadOnly, SendEmailPermission
from .signals import order_created

class ProductList(ModelViewSet):
    serializer_class = ProductSerializer
    search_fields = ['name']
    ordering_fields = ['unit_price']
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter, ]
    filterset_class = ProductFilter
    pagination_class = DefaultPagination
    queryset = Product.objects.all()

    def destroy(self, request, pk):
        product = get_object_or_404(Product.objects.prefetch_related('category'), pk=pk)
        if product.order_items.count() > 0:
            return Response({'error': 'There are some order items for this product, you should remove them first'})
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryList(ModelViewSet):
    queryset = Category.objects.all().prefetch_related('products')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def destroy(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        if category.products.count() > 0:
            return Response({'error': 'There are some products for this category, you should remove them first'})
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentList(ModelViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self, *args, **kwargs):
        product_id = self.kwargs['product_pk']
        return Comment.objects.filter(product_id=product_id)

    def get_serializer_context(self):
        return {'product_pk': self.kwargs['product_pk']}


class CartList(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, GenericViewSet):
    serializer_class = CartSerializer
    queryset = Cart.objects.prefetch_related(
        Prefetch('items', CartItem.objects.select_related('product'))
    )


class CartItemList(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']
    lookup_value_regex = '^[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}$'

    # serializer_class = CartItemSerializer

    def get_queryset(self):
        cart_pk = self.kwargs['cart_pk']
        return CartItem.objects.select_related('product').filter(cart_id=cart_pk)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CartItemAddSerializer
        elif self.request.method == 'PATCH':
            return CartItemUpdateSerializer
        return CartItemSerializer

    def get_serializer_context(self):
        return {'cart_pk': self.kwargs['cart_pk']}


class CustomerList(ModelViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get', 'put'], permission_classes=[IsAuthenticated, ])
    def me(self, request):
        user_id = request.user.id
        user = Customer.objects.get(user_id=user_id)
        if request.method == 'GET':
            serializer = CustomerSerializer(user)
            return Response(serializer.data)

        elif request.method == 'PUT':
            serializer = CustomerSerializer(user, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

    @action(detail=True, permission_classes=[SendEmailPermission])
    def send_email(self, request, pk):
        return Response(f'You are allowed to send a email to user id={pk}')


class OrderList(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'options', 'head']

    def get_permissions(self):
        if self.request.method in ['PATCH', 'DELETE']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        elif self.request.method == 'PATCH':
            return OrderUpdateSerializer

        if self.request.user.is_staff:
            return OrderAdminSerializer
        return OrderUserSerializer

    def get_queryset(self):
        queryset = Order.objects.prefetch_related(
            Prefetch(
                'items',
                OrderItem.objects.select_related('product')
            )
        ).select_related('customer__user').all()

        user = self.request.user
        if user.is_staff:
            return queryset

        return queryset.filter(customer_id=user.id)

    def get_serializer_context(self):
        return {'user_id': self.request.user.id}

    def create(self, request, *args, **kwargs):
        created_order_serializer = OrderCreateSerializer(data=request.data, context={'user_id': self.request.user.id})
        created_order_serializer.is_valid(raise_exception=True)
        order_saved = created_order_serializer.save()

        order_created.send_robust(__class__, order=order_saved)

        order_serializer = OrderUserSerializer(order_saved)
        return Response(order_serializer.data)

