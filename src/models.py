from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


class CouponType(Enum):
    FULL_REDUCTION = "full_reduction"  # 满减
    DISCOUNT = "discount"              # 折扣


class CouponStatus(Enum):
    VALID = "valid"           # 有效
    EXHAUSTED = "exhausted"   # 已用完
    EXPIRED = "expired"       # 已过期
    INVALID = "invalid"       # 手动失效


@dataclass
class Coupon:
    id: str
    type: CouponType
    face_value: float  # 面值：满减为金额，折扣为比例(如0.8)
    min_consumption: float  # 最低消费金额
    start_time: datetime
    end_time: datetime
    total_stock: int
    status: CouponStatus = CouponStatus.VALID
    
    def is_available(self, current_time: Optional[datetime] = None) -> bool:
        """检查优惠券是否可用（状态有效、未过期、有库存）"""
        if self.status != CouponStatus.VALID:
            return False
        
        now = current_time or datetime.now()
        if now < self.start_time or now > self.end_time:
            return False
            
        return True

@dataclass
class UserCoupon:
    record_id: str
    user_id: str
    coupon_id: str
    claim_time: datetime
    is_used: bool = False
    use_time: Optional[datetime] = None

@dataclass
class Order:
    order_id: str
    user_id: str
    original_amount: float
    discount_amount: float
    paid_amount: float
    used_coupon_ids: List[str] = field(default_factory=list)
    is_refunded: bool = False