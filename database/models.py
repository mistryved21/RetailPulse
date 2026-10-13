from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Date, DateTime, Numeric
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String)
    
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)
    sku = Column(String(100), unique=True, nullable=False)
    brand = Column(String(255))
    is_active = Column(Boolean, default=True)
    
    category = relationship("Category", back_populates="products")
    sales = relationship("Sale", back_populates="product")
    inventory = relationship("Inventory", back_populates="product")

class Customer(Base):
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20))
    city = Column(String(100))
    state = Column(String(100))
    registration_date = Column(Date)
    segment = Column(String(50))
    
    sales = relationship("Sale", back_populates="customer")

class Sale(Base):
    __tablename__ = 'sales'
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    sale_date = Column(DateTime, nullable=False)
    payment_method = Column(String(50))
    region = Column(String(100))
    
    product = relationship("Product", back_populates="sales")
    customer = relationship("Customer", back_populates="sales")

class Inventory(Base):
    __tablename__ = 'inventory'
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False, unique=True)
    current_stock = Column(Integer, nullable=False, default=0)
    reorder_level = Column(Integer, nullable=False, default=10)
    max_stock = Column(Integer, nullable=False, default=100)
    warehouse_location = Column(String(100))
    last_restocked = Column(DateTime)
    
    product = relationship("Product", back_populates="inventory")

class Supplier(Base):
    __tablename__ = 'suppliers'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255))
    phone = Column(String(20))
    city = Column(String(100))
    country = Column(String(100))
    rating = Column(Float)
