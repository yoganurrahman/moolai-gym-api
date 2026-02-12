"""
Reports Router - Revenue, Members, Attendance
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.db import get_db_connection
from app.middleware import verify_bearer_token, check_permission, get_branch_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["CMS - Reports"])


# ============== Endpoints ==============

@router.get("/dashboard")
def get_dashboard(
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Get dashboard summary"""
    check_permission(auth, "report.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        today = date.today()
        # Use provided date range or default to first day of month
        if date_from and date_to:
            revenue_start = datetime.strptime(date_from, "%Y-%m-%d").date()
            revenue_end = datetime.strptime(date_to, "%Y-%m-%d").date()
        else:
            revenue_start = today.replace(day=1)
            revenue_end = today

        # Members stats
        member_branch_filter = "AND t.branch_id = %s" if branch_id else ""
        member_params = [today, branch_id] if branch_id else [today]
        cursor.execute(
            f"""
            SELECT
                COUNT(CASE WHEN mm.status = 'active' THEN 1 END) as active_members,
                COUNT(CASE WHEN mm.status = 'expired' THEN 1 END) as expired_members,
                COUNT(CASE WHEN mm.status = 'frozen' THEN 1 END) as frozen_members,
                COUNT(CASE WHEN DATE(mm.created_at) = %s THEN 1 END) as new_today
            FROM member_memberships mm
            LEFT JOIN transactions t ON mm.transaction_id = t.id
            WHERE 1=1 {member_branch_filter}
            """,
            member_params,
        )
        member_stats = cursor.fetchone()

        # Revenue stats
        branch_filter = "AND branch_id = %s" if branch_id else ""
        revenue_params = [revenue_start, revenue_end]
        if branch_id:
            revenue_params.append(branch_id)
        cursor.execute(
            f"""
            SELECT
                COALESCE(SUM(grand_total), 0) as total_revenue,
                COUNT(*) as total_transactions,
                COALESCE(AVG(grand_total), 0) as avg_transaction
            FROM transactions
            WHERE payment_status = 'paid' AND DATE(created_at) BETWEEN %s AND %s
            {branch_filter}
            """,
            revenue_params,
        )
        revenue_stats = cursor.fetchone()
        revenue_stats["total_revenue"] = float(revenue_stats["total_revenue"])
        revenue_stats["avg_transaction"] = float(revenue_stats["avg_transaction"])

        # Check-ins (date range for total, today for currently_in)
        checkin_branch_filter = "AND branch_id = %s" if branch_id else ""
        checkin_params = [revenue_start, revenue_end]
        if branch_id:
            checkin_params.append(branch_id)
        cursor.execute(
            f"""
            SELECT
                COUNT(*) as total_checkins,
                COUNT(DISTINCT user_id) as unique_members
            FROM member_checkins
            WHERE DATE(checkin_time) BETWEEN %s AND %s
            {checkin_branch_filter}
            """,
            checkin_params,
        )
        checkin_stats = cursor.fetchone()

        # Currently in gym (always today)
        currently_in_params = [today]
        if branch_id:
            currently_in_params.append(branch_id)
        cursor.execute(
            f"""
            SELECT COUNT(*) as currently_in
            FROM member_checkins
            WHERE DATE(checkin_time) = %s AND checkout_time IS NULL
            {checkin_branch_filter}
            """,
            currently_in_params,
        )
        currently_in = cursor.fetchone()
        checkin_stats["currently_in"] = currently_in["currently_in"]

        # Upcoming expirations (next 30 days)
        expiring_branch_filter = "AND t.branch_id = %s" if branch_id else ""
        expiring_params = [today, today + timedelta(days=30)]
        if branch_id:
            expiring_params.append(branch_id)
        cursor.execute(
            f"""
            SELECT COUNT(*) as expiring_soon
            FROM member_memberships mm
            LEFT JOIN transactions t ON mm.transaction_id = t.id
            WHERE mm.status = 'active' AND mm.end_date BETWEEN %s AND %s
            {expiring_branch_filter}
            """,
            expiring_params,
        )
        expiring = cursor.fetchone()

        # Class bookings today
        if branch_id:
            cursor.execute(
                """
                SELECT COUNT(*) as total_bookings
                FROM class_bookings cb
                JOIN class_schedules cs ON cb.schedule_id = cs.id
                WHERE cb.class_date = %s AND cb.status IN ('booked', 'attended')
                AND cs.branch_id = %s
                """,
                (today, branch_id),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) as total_bookings
                FROM class_bookings
                WHERE class_date = %s AND status IN ('booked', 'attended')
                """,
                (today,),
            )
        class_stats = cursor.fetchone()

        # PT sessions today
        pt_branch_filter = "AND branch_id = %s" if branch_id else ""
        pt_params = [today, branch_id] if branch_id else [today]
        cursor.execute(
            f"""
            SELECT COUNT(*) as total_pt
            FROM pt_bookings
            WHERE booking_date = %s AND status IN ('booked', 'attended')
            {pt_branch_filter}
            """,
            pt_params,
        )
        pt_stats = cursor.fetchone()

        return {
            "success": True,
            "data": {
                "members": member_stats,
                "revenue": revenue_stats,
                "checkins": checkin_stats,
                "expiring_soon": expiring["expiring_soon"],
                "classes_today": class_stats["total_bookings"],
                "pt_today": pt_stats["total_pt"],
            },
        }

    except Exception as e:
        logger.error(f"Error getting dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_DASHBOARD_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/revenue")
def get_revenue_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    group_by: str = Query("day", pattern=r"^(day|week|month)$"),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get revenue report"""
    check_permission(auth, "report.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Group by format
        if group_by == "day":
            date_format = "%Y-%m-%d"
            group_sql = "DATE(t.created_at)"
        elif group_by == "week":
            date_format = "%Y-%W"
            group_sql = "YEARWEEK(t.created_at)"
        else:  # month
            date_format = "%Y-%m"
            group_sql = "DATE_FORMAT(t.created_at, '%%Y-%%m')"

        # Branch filter
        branch_filter = "AND t.branch_id = %s" if branch_id else ""
        base_params = [date_from, date_to, branch_id] if branch_id else [date_from, date_to]

        # Revenue by period
        if branch_id:
            cursor.execute(
                f"""
                SELECT
                    {group_sql} as period,
                    COUNT(*) as transaction_count,
                    SUM(t.grand_total) as revenue,
                    SUM(t.tax_amount) as tax_collected,
                    SUM(t.discount_amount) as discount_given
                FROM transactions t
                WHERE t.payment_status = 'paid'
                AND DATE(t.created_at) BETWEEN %s AND %s
                {branch_filter}
                GROUP BY {group_sql}
                ORDER BY period ASC
                """,
                base_params,
            )
        else:
            # Superadmin: show per-branch breakdown
            cursor.execute(
                f"""
                SELECT
                    {group_sql} as period,
                    b.name as branch_name,
                    COUNT(*) as transaction_count,
                    SUM(t.grand_total) as revenue,
                    SUM(t.tax_amount) as tax_collected,
                    SUM(t.discount_amount) as discount_given
                FROM transactions t
                LEFT JOIN branches b ON t.branch_id = b.id
                WHERE t.payment_status = 'paid'
                AND DATE(t.created_at) BETWEEN %s AND %s
                GROUP BY {group_sql}, t.branch_id
                ORDER BY period ASC, branch_name ASC
                """,
                base_params,
            )
        revenue_by_period = cursor.fetchall()

        for r in revenue_by_period:
            r["revenue"] = float(r["revenue"]) if r.get("revenue") else 0
            r["tax_collected"] = float(r["tax_collected"]) if r.get("tax_collected") else 0
            r["discount_given"] = float(r["discount_given"]) if r.get("discount_given") else 0

        # Revenue by item type
        cursor.execute(
            f"""
            SELECT
                ti.item_type,
                COUNT(*) as item_count,
                SUM(ti.subtotal) as revenue
            FROM transaction_items ti
            JOIN transactions t ON ti.transaction_id = t.id
            WHERE t.payment_status = 'paid'
            AND DATE(t.created_at) BETWEEN %s AND %s
            {branch_filter}
            GROUP BY ti.item_type
            ORDER BY revenue DESC
            """,
            base_params,
        )
        revenue_by_type = cursor.fetchall()

        for r in revenue_by_type:
            r["revenue"] = float(r["revenue"]) if r.get("revenue") else 0

        # Payment method breakdown
        cursor.execute(
            f"""
            SELECT
                t.payment_method,
                COUNT(*) as transaction_count,
                SUM(t.grand_total) as revenue
            FROM transactions t
            WHERE t.payment_status = 'paid'
            AND DATE(t.created_at) BETWEEN %s AND %s
            {branch_filter}
            GROUP BY t.payment_method
            ORDER BY revenue DESC
            """,
            base_params,
        )
        by_payment_method = cursor.fetchall()

        for r in by_payment_method:
            r["revenue"] = float(r["revenue"]) if r.get("revenue") else 0

        # Summary
        cursor.execute(
            f"""
            SELECT
                COUNT(*) as total_transactions,
                COALESCE(SUM(t.grand_total), 0) as total_revenue,
                COALESCE(SUM(t.tax_amount), 0) as total_tax,
                COALESCE(SUM(t.discount_amount), 0) as total_discount,
                COALESCE(AVG(t.grand_total), 0) as avg_transaction
            FROM transactions t
            WHERE t.payment_status = 'paid'
            AND DATE(t.created_at) BETWEEN %s AND %s
            {branch_filter}
            """,
            base_params,
        )
        summary = cursor.fetchone()
        for key in ["total_revenue", "total_tax", "total_discount", "avg_transaction"]:
            summary[key] = float(summary[key])

        # Per-branch revenue breakdown for superadmin (no branch_id filter)
        by_branch = None
        if not branch_id:
            cursor.execute(
                """
                SELECT
                    b.id as branch_id,
                    b.name as branch_name,
                    COUNT(*) as transaction_count,
                    COALESCE(SUM(t.grand_total), 0) as revenue
                FROM transactions t
                LEFT JOIN branches b ON t.branch_id = b.id
                WHERE t.payment_status = 'paid'
                AND DATE(t.created_at) BETWEEN %s AND %s
                GROUP BY t.branch_id
                ORDER BY revenue DESC
                """,
                base_params,
            )
            by_branch = cursor.fetchall()
            for r in by_branch:
                r["revenue"] = float(r["revenue"]) if r.get("revenue") else 0

        result_data = {
            "summary": summary,
            "by_period": revenue_by_period,
            "by_type": revenue_by_type,
            "by_payment_method": by_payment_method,
        }
        if by_branch is not None:
            result_data["by_branch"] = by_branch

        return {
            "success": True,
            "data": result_data,
        }

    except Exception as e:
        logger.error(f"Error getting revenue report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_REVENUE_REPORT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/members")
def get_members_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get members report"""
    check_permission(auth, "report.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Branch filtering via transaction_id -> transactions.branch_id
        branch_join = "LEFT JOIN transactions t ON mm.transaction_id = t.id" if branch_id else ""
        branch_filter = "AND t.branch_id = %s" if branch_id else ""

        # New members by day
        new_members_params = [date_from, date_to, branch_id] if branch_id else [date_from, date_to]
        cursor.execute(
            f"""
            SELECT
                DATE(mm.created_at) as date,
                COUNT(*) as new_members
            FROM member_memberships mm
            {branch_join}
            WHERE DATE(mm.created_at) BETWEEN %s AND %s
            {branch_filter}
            GROUP BY DATE(mm.created_at)
            ORDER BY date ASC
            """,
            new_members_params,
        )
        new_members = cursor.fetchall()

        # Members by package
        by_package_params = [branch_id] if branch_id else []
        cursor.execute(
            f"""
            SELECT
                mp.name as package_name,
                COUNT(*) as member_count
            FROM member_memberships mm
            JOIN membership_packages mp ON mm.package_id = mp.id
            {branch_join}
            WHERE mm.status = 'active'
            {branch_filter}
            GROUP BY mp.id
            ORDER BY member_count DESC
            """,
            by_package_params,
        )
        by_package = cursor.fetchall()

        # Member retention (renewed vs churned)
        retention_params = [date_from, date_to, branch_id] if branch_id else [date_from, date_to]
        cursor.execute(
            f"""
            SELECT
                COUNT(CASE WHEN mm.status = 'active' THEN 1 END) as active,
                COUNT(CASE WHEN mm.status = 'expired' THEN 1 END) as expired,
                COUNT(CASE WHEN mm.status = 'cancelled' THEN 1 END) as cancelled,
                COUNT(CASE WHEN mm.status = 'frozen' THEN 1 END) as frozen
            FROM member_memberships mm
            {branch_join}
            WHERE DATE(mm.created_at) BETWEEN %s AND %s
            {branch_filter}
            """,
            retention_params,
        )
        retention = cursor.fetchone()

        # Expiring members
        expiring_params = [date.today(), date.today() + timedelta(days=30)]
        if branch_id:
            expiring_params.append(branch_id)
        cursor.execute(
            f"""
            SELECT
                mm.id, mm.membership_code, mm.end_date,
                u.name, u.email, u.phone,
                mp.name as package_name
            FROM member_memberships mm
            JOIN users u ON mm.user_id = u.id
            JOIN membership_packages mp ON mm.package_id = mp.id
            {branch_join}
            WHERE mm.status = 'active' AND mm.end_date BETWEEN %s AND %s
            {branch_filter}
            ORDER BY mm.end_date ASC
            LIMIT 50
            """,
            expiring_params,
        )
        expiring = cursor.fetchall()

        return {
            "success": True,
            "data": {
                "new_members": new_members,
                "by_package": by_package,
                "retention": retention,
                "expiring_soon": expiring,
            },
        }

    except Exception as e:
        logger.error(f"Error getting members report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_MEMBERS_REPORT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()


@router.get("/attendance")
def get_attendance_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    auth: dict = Depends(verify_bearer_token),
    branch_id: Optional[int] = Depends(get_branch_id),
):
    """Get attendance report"""
    check_permission(auth, "report.view")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Branch filter for member_checkins
        checkin_branch_filter = "AND mc.branch_id = %s" if branch_id else ""
        checkin_params = [date_from, date_to, branch_id] if branch_id else [date_from, date_to]

        # Check-ins by day
        cursor.execute(
            f"""
            SELECT
                DATE(mc.checkin_time) as date,
                COUNT(*) as total_checkins,
                COUNT(DISTINCT mc.user_id) as unique_members,
                AVG(TIMESTAMPDIFF(MINUTE, mc.checkin_time, COALESCE(mc.checkout_time, mc.checkin_time))) as avg_duration_minutes
            FROM member_checkins mc
            WHERE DATE(mc.checkin_time) BETWEEN %s AND %s
            {checkin_branch_filter}
            GROUP BY DATE(mc.checkin_time)
            ORDER BY date ASC
            """,
            checkin_params,
        )
        checkins_by_day = cursor.fetchall()

        for c in checkins_by_day:
            c["avg_duration_minutes"] = float(c["avg_duration_minutes"]) if c.get("avg_duration_minutes") else 0

        # Check-ins by hour
        cursor.execute(
            f"""
            SELECT
                HOUR(mc.checkin_time) as hour,
                COUNT(*) as checkin_count
            FROM member_checkins mc
            WHERE DATE(mc.checkin_time) BETWEEN %s AND %s
            {checkin_branch_filter}
            GROUP BY HOUR(mc.checkin_time)
            ORDER BY hour ASC
            """,
            checkin_params,
        )
        checkins_by_hour = cursor.fetchall()

        # Check-ins by day of week
        cursor.execute(
            f"""
            SELECT
                DAYOFWEEK(mc.checkin_time) as day_of_week,
                COUNT(*) as checkin_count
            FROM member_checkins mc
            WHERE DATE(mc.checkin_time) BETWEEN %s AND %s
            {checkin_branch_filter}
            GROUP BY DAYOFWEEK(mc.checkin_time)
            ORDER BY day_of_week ASC
            """,
            checkin_params,
        )
        checkins_by_dow = cursor.fetchall()

        # Class attendance
        class_branch_filter = "AND cs.branch_id = %s" if branch_id else ""
        class_params = [date_from, date_to, branch_id] if branch_id else [date_from, date_to]
        cursor.execute(
            f"""
            SELECT
                ct.name as class_name,
                COUNT(cb.id) as total_bookings,
                COUNT(CASE WHEN cb.status = 'attended' THEN 1 END) as attended,
                COUNT(CASE WHEN cb.status = 'no_show' THEN 1 END) as no_show,
                COUNT(CASE WHEN cb.status = 'cancelled' THEN 1 END) as cancelled
            FROM class_bookings cb
            JOIN class_schedules cs ON cb.schedule_id = cs.id
            JOIN class_types ct ON cs.class_type_id = ct.id
            WHERE cb.class_date BETWEEN %s AND %s
            {class_branch_filter}
            GROUP BY ct.id
            ORDER BY total_bookings DESC
            """,
            class_params,
        )
        class_attendance = cursor.fetchall()

        # Top visitors
        cursor.execute(
            f"""
            SELECT
                u.id, u.name, u.email,
                COUNT(mc.id) as visit_count,
                AVG(TIMESTAMPDIFF(MINUTE, mc.checkin_time, COALESCE(mc.checkout_time, mc.checkin_time))) as avg_duration
            FROM member_checkins mc
            JOIN users u ON mc.user_id = u.id
            WHERE DATE(mc.checkin_time) BETWEEN %s AND %s
            {checkin_branch_filter}
            GROUP BY u.id
            ORDER BY visit_count DESC
            LIMIT 20
            """,
            checkin_params,
        )
        top_visitors = cursor.fetchall()

        for v in top_visitors:
            v["avg_duration"] = float(v["avg_duration"]) if v.get("avg_duration") else 0

        # Summary
        cursor.execute(
            f"""
            SELECT
                COUNT(*) as total_checkins,
                COUNT(DISTINCT mc.user_id) as unique_members,
                AVG(TIMESTAMPDIFF(MINUTE, mc.checkin_time, COALESCE(mc.checkout_time, mc.checkin_time))) as avg_duration
            FROM member_checkins mc
            WHERE DATE(mc.checkin_time) BETWEEN %s AND %s
            {checkin_branch_filter}
            """,
            checkin_params,
        )
        summary = cursor.fetchone()
        summary["avg_duration"] = float(summary["avg_duration"]) if summary.get("avg_duration") else 0

        return {
            "success": True,
            "data": {
                "summary": summary,
                "by_day": checkins_by_day,
                "by_hour": checkins_by_hour,
                "by_day_of_week": checkins_by_dow,
                "class_attendance": class_attendance,
                "top_visitors": top_visitors,
            },
        }

    except Exception as e:
        logger.error(f"Error getting attendance report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GET_ATTENDANCE_REPORT_FAILED", "message": str(e)},
        )
    finally:
        cursor.close()
        conn.close()
