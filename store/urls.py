from django.urls import path, include

from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import CategoryList, ProductList, CommentList, CartList, CartItemList, CustomerList, OrderList

app_name = 'store'

router = DefaultRouter()
router.register('category', CategoryList, basename='category')
router.register('product', ProductList, basename='product')
router.register('cart', CartList, basename="cart")
router.register('customer', CustomerList, basename='customer')
router.register('order', OrderList, basename='order')

product = routers.NestedDefaultRouter(router, 'product', lookup='product')
product.register('comment', CommentList, basename='comment')
items = routers.NestedDefaultRouter(router, 'cart', lookup='cart')
items.register('items', CartItemList, basename='items')

urlpatterns = router.urls + product.urls + items.urls
