import pytest
from datetime import datetime, timedelta
from src.models import CouponType, CouponStatus
from src.coupon_manager import CouponManager


@pytest.fixture
def manager():
    return CouponManager()

@pytest.fixture
def now():
    return datetime(2023, 10, 1, 12, 0, 0)

@pytest.fixture
def valid_coupon_id():
    return "COUPON_001"

@pytest.fixture
def create_valid_coupon(manager, now, valid_coupon_id):
    manager.set_current_time(now)
    manager.create_coupon(
        coupon_id=valid_coupon_id,
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=20.0,
        min_consumption=100.0,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=1),
        total_stock=10
    )

def test_create_coupon_success(manager, now):
    manager.set_current_time(now)
    coupon = manager.create_coupon(
        coupon_id="C1",
        coupon_type=CouponType.DISCOUNT,
        face_value=0.8,
        min_consumption=50.0,
        start_time=now,
        end_time=now + timedelta(days=7),
        total_stock=100
    )
    assert coupon.id == "C1"
    assert coupon.type == CouponType.DISCOUNT
    assert coupon.status == CouponStatus.VALID

def test_create_duplicate_coupon_raises_error(manager, now, create_valid_coupon):
    with pytest.raises(ValueError, match="already exists"):
        manager.create_coupon(
            coupon_id="COUPON_001",
            coupon_type=CouponType.FULL_REDUCTION,
            face_value=10.0,
            min_consumption=50.0,
            start_time=now,
            end_time=now + timedelta(days=1),
            total_stock=5
        )

def test_query_coupons_by_type(manager, now):
    manager.set_current_time(now)
    manager.create_coupon("C1", CouponType.FULL_REDUCTION, 10, 0, now, now+timedelta(days=1), 10)
    manager.create_coupon("C2", CouponType.DISCOUNT, 0.9, 0, now, now+timedelta(days=1), 10)
    
    fr_coupons = manager.query_coupons(coupon_type=CouponType.FULL_REDUCTION)
    assert len(fr_coupons) == 1
    assert fr_coupons[0].id == "C1"

def test_query_coupons_by_status(manager, now):
    manager.set_current_time(now)
    manager.create_coupon("C1", CouponType.FULL_REDUCTION, 10, 0, now, now+timedelta(days=1), 10)
    manager.invalidate_coupon("C1")
    
    invalid_coupons = manager.query_coupons(status=CouponStatus.INVALID)
    assert len(invalid_coupons) == 1
    assert invalid_coupons[0].id == "C1"

def test_invalidate_coupon(manager, now, create_valid_coupon):
    manager.invalidate_coupon("COUPON_001")
    coupon = manager.coupons["COUPON_001"]
    assert coupon.status == CouponStatus.INVALID

def test_invalidate_nonexistent_coupon_raises_error(manager):
    with pytest.raises(ValueError, match="does not exist"):
        manager.invalidate_coupon("NON_EXISTENT")

def test_claim_coupon_success(manager, now, create_valid_coupon):
    uc = manager.claim_coupon("user_1", "COUPON_001")
    assert uc.user_id == "user_1"
    assert uc.coupon_id == "COUPON_001"
    assert uc.is_used is False

def test_claim_expired_coupon_raises_error(manager, now):
    manager.set_current_time(now)
    manager.create_coupon(
        coupon_id="EXP_C",
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=10,
        min_consumption=0,
        start_time=now - timedelta(days=2),
        end_time=now - timedelta(days=1), # Expired
        total_stock=10
    )
    with pytest.raises(ValueError, match="validity period"):
        manager.claim_coupon("user_1", "EXP_C")

def test_claim_exhausted_coupon_raises_error(manager, now):
    manager.set_current_time(now)
    manager.create_coupon(
        coupon_id="STOCK_C",
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=10,
        min_consumption=0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=1
    )
    manager.claim_coupon("user_1", "STOCK_C")
    with pytest.raises(ValueError, match="stock is exhausted"):
        manager.claim_coupon("user_2", "STOCK_C")

def test_claim_duplicate_coupon_by_same_user_raises_error(manager, now, create_valid_coupon):
    manager.claim_coupon("user_1", "COUPON_001")
    with pytest.raises(ValueError, match="already claimed"):
        manager.claim_coupon("user_1", "COUPON_001")

def test_calculate_best_discount_no_coupons(manager, now):
    manager.set_current_time(now)
    result = manager.calculate_best_discount("user_empty", 100.0)
    assert result["discount_amount"] == 0.0
    assert result["paid_amount"] == 100.0

def test_calculate_best_discount_full_reduction(manager, now):
    manager.set_current_time(now)
    manager.create_coupon(
        coupon_id="FR1",
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=20.0,
        min_consumption=100.0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    manager.claim_coupon("user_1", "FR1")
    
    # Order amount 150, meets min_consumption 100
    result = manager.calculate_best_discount("user_1", 150.0)
    assert result["discount_amount"] == 20.0
    assert result["paid_amount"] == 130.0
    assert len(result["used_coupon_records"]) == 1

def test_calculate_best_discount_not_meet_min_consumption(manager, now):
    manager.set_current_time(now)
    manager.create_coupon(
        coupon_id="FR1",
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=20.0,
        min_consumption=100.0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    manager.claim_coupon("user_1", "FR1")
    
    # Order amount 50, does not meet min_consumption 100
    result = manager.calculate_best_discount("user_1", 50.0)
    assert result["discount_amount"] == 0.0

def test_calculate_best_discount_discount_coupon(manager, now):
    manager.set_current_time(now)
    manager.create_coupon(
        coupon_id="DISC1",
        coupon_type=CouponType.DISCOUNT,
        face_value=0.8, # 20% off
        min_consumption=50.0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    manager.claim_coupon("user_1", "DISC1")
    
    result = manager.calculate_best_discount("user_1", 100.0)
    assert result["discount_amount"] == 20.0 # 100 * 0.2
    assert result["paid_amount"] == 80.0

def test_calculate_best_discount_choose_max_saving(manager, now):
    manager.set_current_time(now)
    # FR: save 20
    manager.create_coupon(
        coupon_id="FR1",
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=20.0,
        min_consumption=0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    # DISC: 10% off. If order=100, save 10. FR is better.
    manager.create_coupon(
        coupon_id="DISC1",
        coupon_type=CouponType.DISCOUNT,
        face_value=0.9,
        min_consumption=0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    
    manager.claim_coupon("user_1", "FR1")
    manager.claim_coupon("user_1", "DISC1")
    
    result = manager.calculate_best_discount("user_1", 100.0)
    assert result["discount_amount"] == 20.0
    assert result["used_coupon_records"][0].coupon_id == "FR1"

def test_calculate_best_discount_choose_discount_when_better(manager, now):
    manager.set_current_time(now)
    # FR: save 20
    manager.create_coupon(
        coupon_id="FR1",
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=20.0,
        min_consumption=0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    # DISC: 50% off. If order=100, save 50. DISC is better.
    manager.create_coupon(
        coupon_id="DISC1",
        coupon_type=CouponType.DISCOUNT,
        face_value=0.5,
        min_consumption=0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    
    manager.claim_coupon("user_1", "FR1")
    manager.claim_coupon("user_1", "DISC1")
    
    result = manager.calculate_best_discount("user_1", 100.0)
    assert result["discount_amount"] == 50.0
    assert result["used_coupon_records"][0].coupon_id == "DISC1"

def test_submit_order_success(manager, now, create_valid_coupon):
    manager.claim_coupon("user_1", "COUPON_001")
    scheme = manager.calculate_best_discount("user_1", 150.0)
    
    order = manager.submit_order(
        order_id="ORD_1",
        user_id="user_1",
        order_amount=150.0,
        used_coupon_records=scheme["used_coupon_records"]
    )
    
    assert order.order_id == "ORD_1"
    assert order.discount_amount == 20.0
    assert order.paid_amount == 130.0
    assert order.is_refunded is False
    
    # Check coupon status updated
    uc = manager.user_coupons[scheme["used_coupon_records"][0].record_id]
    assert uc.is_used is True

def test_submit_order_with_used_coupon_raises_error(manager, now, create_valid_coupon):
    uc = manager.claim_coupon("user_1", "COUPON_001")
    uc.is_used = True # Manually mark as used to simulate
    
    with pytest.raises(ValueError, match="already been used"):
        manager.submit_order(
            order_id="ORD_1",
            user_id="user_1",
            order_amount=150.0,
            used_coupon_records=[uc]
        )

def test_refund_order_success(manager, now, create_valid_coupon):
    manager.claim_coupon("user_1", "COUPON_001")
    scheme = manager.calculate_best_discount("user_1", 150.0)
    order = manager.submit_order(
        order_id="ORD_1",
        user_id="user_1",
        order_amount=150.0,
        used_coupon_records=scheme["used_coupon_records"]
    )
    
    manager.refund_order("ORD_1")
    
    assert order.is_refunded is True
    uc = manager.user_coupons[scheme["used_coupon_records"][0].record_id]
    assert uc.is_used is False

def test_refund_nonexistent_order_raises_error(manager):
    with pytest.raises(ValueError, match="Order does not exist"):
        manager.refund_order("NON_EXISTENT")

def test_refund_already_refunded_order_raises_error(manager, now, create_valid_coupon):
    manager.claim_coupon("user_1", "COUPON_001")
    scheme = manager.calculate_best_discount("user_1", 150.0)
    manager.submit_order(
        order_id="ORD_1",
        user_id="user_1",
        order_amount=150.0,
        used_coupon_records=scheme["used_coupon_records"]
    )
    manager.refund_order("ORD_1")
    
    with pytest.raises(ValueError, match="already been refunded"):
        manager.refund_order("ORD_1")

def test_get_statistics(manager, now):
    manager.set_current_time(now)
    
    # Create FR Coupon
    manager.create_coupon(
        coupon_id="FR1",
        coupon_type=CouponType.FULL_REDUCTION,
        face_value=20.0,
        min_consumption=0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    
    # Create DISC Coupon
    manager.create_coupon(
        coupon_id="DISC1",
        coupon_type=CouponType.DISCOUNT,
        face_value=0.9,
        min_consumption=0,
        start_time=now,
        end_time=now + timedelta(days=1),
        total_stock=10
    )
    
    # User 1 claims and uses FR1
    manager.claim_coupon("u1", "FR1")
    scheme1 = manager.calculate_best_discount("u1", 100.0)
    manager.submit_order("O1", "u1", 100.0, scheme1["used_coupon_records"])
    
    # User 2 claims DISC1 but does not use
    manager.claim_coupon("u2", "DISC1")
    
    stats = manager.get_statistics()
    
    # FR Stats: 1 total, 1 used. Saved 20.
    assert stats["full_reduction"]["usage_rate"] == 100.0
    assert stats["full_reduction"]["total_saved"] == 20.0
    
    # DISC Stats: 1 total, 0 used. Saved 0.
    assert stats["discount"]["usage_rate"] == 0.0
    assert stats["discount"]["total_saved"] == 0.0