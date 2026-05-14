from datetime import datetime
from typing import List, Dict, Optional
from .models import Coupon, CouponType, CouponStatus, UserCoupon


class CouponManager:
    def __init__(self):
        # 存储所有优惠券定义
        self.coupons: Dict[str, Coupon] = {}
        # 存储用户领取的优惠券记录: record_id -> UserCoupon
        self.user_coupons: Dict[str, UserCoupon] = {}
        # 索引：user_id -> list of record_ids
        self.user_coupon_index: Dict[str, List[str]] = {}
        # 当前时间模拟（用于测试）
        self.current_time: Optional[datetime] = None

    def set_current_time(self, dt: datetime):
        self.current_time = dt

    def get_current_time(self) -> datetime:
        return self.current_time or datetime.now()

    def create_coupon(
        self,
        coupon_id: str,
        coupon_type: CouponType,
        face_value: float,
        min_consumption: float,
        start_time: datetime,
        end_time: datetime,
        total_stock: int
    ) -> Coupon:
        if coupon_id in self.coupons:
            raise ValueError(f"Coupon ID {coupon_id} already exists")
        
        coupon = Coupon(
            id=coupon_id,
            type=coupon_type,
            face_value=face_value,
            min_consumption=min_consumption,
            start_time=start_time,
            end_time=end_time,
            total_stock=total_stock,
            status=CouponStatus.VALID
        )
        self.coupons[coupon_id] = coupon
        return coupon

    def query_coupons(
        self,
        coupon_type: Optional[CouponType] = None,
        status: Optional[CouponStatus] = None
    ) -> List[Coupon]:
        result = list(self.coupons.values())
        
        if coupon_type:
            result = [c for c in result if c.type == coupon_type]
        
        if status:
            result = [c for c in result if c.status == status]
            
        return result

    def invalidate_coupon(self, coupon_id: str):
        if coupon_id not in self.coupons:
            raise ValueError(f"Coupon ID {coupon_id} does not exist")
        
        self.coupons[coupon_id].status = CouponStatus.INVALID

    def claim_coupon(self, user_id: str, coupon_id: str) -> UserCoupon:
        if coupon_id not in self.coupons:
            raise ValueError("Coupon does not exist")
        
        coupon = self.coupons[coupon_id]
        now = self.get_current_time()
        
        # 校验有效性
        if not coupon.is_available(now):
            if coupon.status != CouponStatus.VALID:
                raise ValueError("Coupon is invalid or expired")
            else:
                raise ValueError("Coupon is out of validity period")
        
        # 校验库存 (注意：这里简化处理，实际并发场景需要锁)
        # 库存检查基于剩余未领取数量？ 
        # 题目要求：库存数量。通常指总发行量。
        # 我们需要计算已领取数量。
        claimed_count = sum(
            1 for uc in self.user_coupons.values() 
            if uc.coupon_id == coupon_id
        )
        
        if claimed_count >= coupon.total_stock:
            raise ValueError("Coupon stock is exhausted")
        
        # 校验用户是否已领取
        user_records = self.user_coupon_index.get(user_id, [])
        for record_id in user_records:
            uc = self.user_coupons[record_id]
            if uc.coupon_id == coupon_id:
                raise ValueError("User has already claimed this coupon")
        
        # 创建领取记录
        import uuid
        record_id = str(uuid.uuid4())
        user_coupon = UserCoupon(
            record_id=record_id,
            user_id=user_id,
            coupon_id=coupon_id,
            claim_time=now
        )
        
        self.user_coupons[record_id] = user_coupon
        if user_id not in self.user_coupon_index:
            self.user_coupon_index[user_id] = []
        self.user_coupon_index[user_id].append(record_id)
        
        return user_coupon

    def get_user_available_coupons(self, user_id: str, order_amount: float) -> List[UserCoupon]:
        """获取用户可用于当前订单金额的优惠券"""
        user_record_ids = self.user_coupon_index.get(user_id, [])
        available = []
        now = self.get_current_time()
        
        for record_id in user_record_ids:
            uc = self.user_coupons[record_id]
            if uc.is_used:
                continue
            
            coupon = self.coupons.get(uc.coupon_id)
            if not coupon:
                continue
                
            if not coupon.is_available(now):
                continue
                
            if order_amount < coupon.min_consumption:
                continue
                
            available.append(uc)
            
        return available

    def calculate_best_discount(
        self, 
        user_id: str, 
        order_amount: float
    ) -> Dict:
        """
        计算最优优惠方案。
        规则：
        1. 满减和折扣不能同时用。
        2. 同类型最多用1张（题目暗示：同一订单可使用多张不同类型的券...但满减券最多使用1张，折扣券最多使用1张）。
        3. 选择节省金额最高的方案。
        
        返回: {
            "original_amount": float,
            "discount_amount": float,
            "paid_amount": float,
            "used_coupon_records": List[UserCoupon]
        }
        """
        available_coupons = self.get_user_available_coupons(user_id, order_amount)
        
        best_saving = 0.0
        best_scheme: List[UserCoupon] = []
        
        # 分类
        full_reduction_coupons = [uc for uc in available_coupons if self.coupons[uc.coupon_id].type == CouponType.FULL_REDUCTION]
        discount_coupons = [uc for uc in available_coupons if self.coupons[uc.coupon_id].type == CouponType.DISCOUNT]
        
        # 方案1: 不使用任何优惠券
        # saving = 0
        
        # 方案2: 使用一张满减券 (选减免最多的)
        max_fr_saving = 0.0
        best_fr_uc = None
        for uc in full_reduction_coupons:
            coupon = self.coupons[uc.coupon_id]
            saving = coupon.face_value
            # 确保不超过订单金额（通常优惠券不会导致负数支付，但需确认逻辑，这里假设可以抵扣至0或保留最小支付额？题目未说明，通常直减）
            # 如果 face_value > order_amount, saving is order_amount? 
            # 题目说"直减面值金额"。如果面值大于订单金额，实付可能为负？通常电商逻辑是实付>=0。
            # 这里我们假设 saving = min(face_value, order_amount) 以防止负数支付，或者仅比较 face_value。
            # 为了简单且符合常规，节省金额不能超过订单金额。
            actual_saving = min(saving, order_amount)
            
            if actual_saving > max_fr_saving:
                max_fr_saving = actual_saving
                best_fr_uc = uc
        
        if max_fr_saving > best_saving:
            best_saving = max_fr_saving
            best_scheme = [best_fr_uc] if best_fr_uc else []
            
        # 方案3: 使用一张折扣券 (选折扣后价格最低的，即节省最多的)
        max_disc_saving = 0.0
        best_disc_uc = None
        for uc in discount_coupons:
            coupon = self.coupons[uc.coupon_id]
            # 折扣券面值如 0.8 表示 8折。节省比例 = 1 - 0.8 = 0.2
            discount_rate = coupon.face_value
            if discount_rate >= 1.0:
                continue # 无优惠
                
            saving = order_amount * (1 - discount_rate)
            if saving > max_disc_saving:
                max_disc_saving = saving
                best_disc_uc = uc
        
        if max_disc_saving > best_saving:
            best_saving = max_disc_saving
            best_scheme = [best_disc_uc] if best_disc_uc else []
            
        return {
            "original_amount": order_amount,
            "discount_amount": round(best_saving, 2),
            "paid_amount": round(order_amount - best_saving, 2),
            "used_coupon_records": best_scheme
        }

    def submit_order(
        self,
        order_id: str,
        user_id: str,
        order_amount: float,
        used_coupon_records: List[UserCoupon]
    ) -> 'Order':
        from .models import Order
        
        # 重新验证优惠券状态，防止并发问题或状态变更
        now = self.get_current_time()
        final_discount = 0.0
        used_ids = []
        
        for uc in used_coupon_records:
            # 检查是否已被使用
            if uc.is_used:
                raise ValueError(f"Coupon record {uc.record_id} has already been used")
            
            coupon = self.coupons.get(uc.coupon_id)
            if not coupon or not coupon.is_available(now):
                raise ValueError(f"Coupon {uc.coupon_id} is no longer valid")
                
            # 计算该券优惠
            if coupon.type == CouponType.FULL_REDUCTION:
                final_discount += coupon.face_value
            elif coupon.type == CouponType.DISCOUNT:
                final_discount += order_amount * (1 - coupon.face_value)
                
            used_ids.append(uc.coupon_id)
            
        # 限制：满减和折扣不能共存，且各最多1张。
        # 由于 calculate_best_discount 已经保证了这一点，这里主要是扣减状态。
        # 但为了健壮性，再次检查逻辑一致性
        fr_count = sum(1 for cid in used_ids if self.coupons[cid].type == CouponType.FULL_REDUCTION)
        disc_count = sum(1 for cid in used_ids if self.coupons[cid].type == CouponType.DISCOUNT)
        
        if fr_count > 1 or disc_count > 1:
            raise ValueError("Invalid coupon combination")
        if fr_count > 0 and disc_count > 0:
            raise ValueError("Full reduction and discount coupons cannot be used together")

        # 扣减上限
        if final_discount > order_amount:
            final_discount = order_amount
            
        paid_amount = order_amount - final_discount
        
        # 更新用户优惠券状态
        for uc in used_coupon_records:
            uc.is_used = True
            uc.use_time = now
            
        # 创建订单
        order = Order(
            order_id=order_id,
            user_id=user_id,
            original_amount=order_amount,
            discount_amount=round(final_discount, 2),
            paid_amount=round(paid_amount, 2),
            used_coupon_ids=used_ids
        )
        
        # 存储订单 (简单内存存储，实际应存入DB)
        if not hasattr(self, 'orders'):
            self.orders = {}
        self.orders[order_id] = order
        
        return order

    def refund_order(self, order_id: str):
        if not hasattr(self, 'orders') or order_id not in self.orders:
            raise ValueError("Order does not exist")
            
        order = self.orders[order_id]
        if order.is_refunded:
            raise ValueError("Order has already been refunded")
            
        # 恢复优惠券状态
        for record_id in self.user_coupon_index.get(order.user_id, []):
            uc = self.user_coupons[record_id]
            if uc.coupon_id in order.used_coupon_ids and uc.is_used:
                # 需要确认这个记录确实是用于这个订单的
                # 由于一个用户可能多次领取同一张券（如果允许的话，但本题逻辑是不允许重复领取同一张券ID）
                # 既然不允许重复领取同一张券ID，那么 coupon_id 和 user_id 唯一确定一个 user_coupon 记录吗？
                # 是的，claim_coupon 中检查了 user 是否已领取该 coupon_id。
                # 所以可以直接通过 coupon_id 找到对应的 user_coupon 记录并恢复。
                uc.is_used = False
                uc.use_time = None
                
        order.is_refunded = True

    def get_statistics(self) -> Dict:
        """
        按类型统计优惠券的使用率和节省金额
        """
        stats = {
            CouponType.FULL_REDUCTION: {"total": 0, "used": 0, "saved": 0.0},
            CouponType.DISCOUNT: {"total": 0, "used": 0, "saved": 0.0}
        }
        
        # 遍历所有用户优惠券记录
        for uc in self.user_coupons.values():
            coupon = self.coupons.get(uc.coupon_id)
            if not coupon:
                continue
            
            ctype = coupon.type
            if ctype not in stats:
                continue
                
            stats[ctype]["total"] += 1
            if uc.is_used:
                stats[ctype]["used"] += 1
                # 计算节省金额需要知道订单金额，但 UserCoupon 没存订单金额。
                # 这是一个数据模型设计的缺陷。
                # 为了完成功能，我们需要从 Order 中反推，或者在 UserCoupon 中保存节省金额。
                # 鉴于现有结构，我们遍历 Orders 来统计节省金额更准确。
                
        # 重新通过 Orders 统计节省金额，因为 UserCoupon 不知道具体省了多少（特别是折扣券依赖订单金额）
        saved_by_type = {
            CouponType.FULL_REDUCTION: 0.0,
            CouponType.DISCOUNT: 0.0
        }
        
        if hasattr(self, 'orders'):
            for order in self.orders.values():
                if order.is_refunded:
                    continue
                # 分配优惠金额到具体的券类型
                # 由于一个订单只有一种类型的券（互斥），我们可以直接将 discount_amount 归因于该类型
                if order.used_coupon_ids:
                    first_cid = order.used_coupon_ids[0]
                    c = self.coupons.get(first_cid)
                    if c:
                        saved_by_type[c.type] += order.discount_amount

        result = {}
        for ctype, data in stats.items():
            total = data["total"]
            used = data["used"]
            usage_rate = (used / total * 100) if total > 0 else 0.0
            result[ctype.value] = {
                "usage_rate": round(usage_rate, 2),
                "total_saved": round(saved_by_type[ctype], 2)
            }
            
        return result