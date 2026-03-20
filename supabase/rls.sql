-- ============================================
-- EVERBLOOM ROW LEVEL SECURITY POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- ============================================
-- HELPER FUNCTION: Check if user is admin
-- ============================================
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM profiles
    WHERE id = auth.uid() AND role = 'admin'
  );
$$ LANGUAGE sql SECURITY DEFINER;

-- ============================================
-- PROFILES POLICIES
-- ============================================
CREATE POLICY "Users can view own profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Admins can view all profiles" ON profiles
  FOR SELECT USING (is_admin());

CREATE POLICY "Admins can update all profiles" ON profiles
  FOR UPDATE USING (is_admin());

-- ============================================
-- CATEGORIES POLICIES (public read)
-- ============================================
CREATE POLICY "Anyone can read categories" ON categories
  FOR SELECT USING (TRUE);

CREATE POLICY "Admins can manage categories" ON categories
  FOR ALL USING (is_admin());

-- ============================================
-- PRODUCTS POLICIES
-- ============================================
CREATE POLICY "Anyone can read active products" ON products
  FOR SELECT USING (is_active = TRUE);

CREATE POLICY "Admins can read all products" ON products
  FOR SELECT USING (is_admin());

CREATE POLICY "Admins can manage products" ON products
  FOR ALL USING (is_admin());

-- ============================================
-- ORDERS POLICIES
-- ============================================
CREATE POLICY "Customers can view own orders" ON orders
  FOR SELECT USING (auth.uid() = customer_id);

CREATE POLICY "Customers can create orders" ON orders
  FOR INSERT WITH CHECK (auth.uid() = customer_id);

CREATE POLICY "Customers can update own orders (payment proof)" ON orders
  FOR UPDATE USING (auth.uid() = customer_id);

CREATE POLICY "Admins can view all orders" ON orders
  FOR SELECT USING (is_admin());

CREATE POLICY "Admins can update all orders" ON orders
  FOR UPDATE USING (is_admin());

-- ============================================
-- ORDER ITEMS POLICIES
-- ============================================
CREATE POLICY "Customers can view own order items" ON order_items
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM orders WHERE orders.id = order_items.order_id AND orders.customer_id = auth.uid())
  );

CREATE POLICY "Customers can insert order items" ON order_items
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM orders WHERE orders.id = order_items.order_id AND orders.customer_id = auth.uid())
  );

CREATE POLICY "Admins can view all order items" ON order_items
  FOR SELECT USING (is_admin());

-- ============================================
-- ORDER TRACKING POLICIES
-- ============================================
CREATE POLICY "Customers can view own tracking" ON order_tracking
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM orders WHERE orders.id = order_tracking.order_id AND orders.customer_id = auth.uid())
  );

CREATE POLICY "Admins can manage tracking" ON order_tracking
  FOR ALL USING (is_admin());

-- ============================================
-- NOTIFICATIONS POLICIES
-- ============================================
CREATE POLICY "Users can view own notifications" ON notifications
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own notifications (mark read)" ON notifications
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Admins can manage all notifications" ON notifications
  FOR ALL USING (is_admin());

-- Service role can insert notifications (for edge functions)
CREATE POLICY "Service role can insert notifications" ON notifications
  FOR INSERT WITH CHECK (TRUE);
