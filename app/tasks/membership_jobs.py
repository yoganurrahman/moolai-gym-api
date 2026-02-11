"""
Membership cron jobs:
  1. Send expiry reminder emails (H-7 dan H-3)
  2. Mark expired memberships
  3. Auto-renew memberships (auto_renew = 1)
"""
import logging
from datetime import date, timedelta

from app.db import get_db_connection
from app.utils.email import send_membership_expiry_reminder

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. KIRIM REMINDER H-7 DAN H-3
# ─────────────────────────────────────────────
def job_send_expiry_reminders():
    """
    Cari membership aktif yang end_date = hari ini + 7 atau + 3,
    lalu kirim email reminder ke member.
    """
    today = date.today()
    reminder_dates = [today + timedelta(days=7), today + timedelta(days=3)]

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        placeholders = ", ".join(["%s"] * len(reminder_dates))
        query = f"""
            SELECT mm.id, mm.end_date, mm.member_id,
                   u.name AS member_name, u.email AS member_email
            FROM member_memberships mm
            JOIN users u ON u.id = mm.member_id
            WHERE mm.status = 'active'
              AND mm.end_date IN ({placeholders})
              AND u.email IS NOT NULL
              AND u.email != ''
        """
        cursor.execute(query, reminder_dates)
        rows = cursor.fetchall()

        sent = 0
        for row in rows:
            days_remaining = (row["end_date"] - today).days
            expiry_str = row["end_date"].strftime("%d %B %Y")

            ok = send_membership_expiry_reminder(
                to_email=row["member_email"],
                username=row["member_name"],
                expiry_date=expiry_str,
                days_remaining=days_remaining,
            )
            if ok:
                sent += 1
                logger.info(
                    "Reminder sent to %s (membership #%d, %d days left)",
                    row["member_email"], row["id"], days_remaining,
                )

        logger.info("Expiry reminder job done — %d emails sent from %d eligible", sent, len(rows))

    except Exception as e:
        logger.error("Error in job_send_expiry_reminders: %s", e)
    finally:
        conn.close()


# ─────────────────────────────────────────────
# 2. TANDAI MEMBERSHIP EXPIRED
# ─────────────────────────────────────────────
def job_expire_memberships():
    """
    Membership yang end_date < hari ini dan status masih 'active'
    → ubah status menjadi 'expired'.
    """
    today = date.today()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            UPDATE member_memberships
            SET status = 'expired'
            WHERE status = 'active'
              AND end_date IS NOT NULL
              AND end_date < %s
            """,
            (today,),
        )
        affected = cursor.rowcount
        conn.commit()

        logger.info("Expire job done — %d memberships marked as expired", affected)

    except Exception as e:
        conn.rollback()
        logger.error("Error in job_expire_memberships: %s", e)
    finally:
        conn.close()


# ─────────────────────────────────────────────
# 3. AUTO-RENEW MEMBERSHIP
# ─────────────────────────────────────────────
def job_auto_renew_memberships():
    """
    Membership yang auto_renew = 1, expired hari ini (status baru di-expire),
    → buat membership baru dengan durasi/quota yang sama dari package-nya.

    Karena pembayaran masih manual, kita buat record baru dengan
    status = 'pending_payment' agar admin bisa follow-up.
    Juga kirim email notifikasi ke member.
    """
    today = date.today()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Cari membership yang baru saja expired dan punya auto_renew = 1
        # Hanya membership berbasis durasi >= 7 hari (weekly ke atas)
        # Daily pass (duration_days=1) tidak di-auto-renew
        cursor.execute(
            """
            SELECT mm.id, mm.member_id, mm.package_id, mm.branch_id,
                   mm.auto_renew,
                   mp.name AS package_name, mp.duration_days, mp.visit_quota,
                   mp.price,
                   u.name AS member_name, u.email AS member_email
            FROM member_memberships mm
            JOIN membership_packages mp ON mp.id = mm.package_id
            JOIN users u ON u.id = mm.member_id
            WHERE mm.auto_renew = 1
              AND mm.status = 'expired'
              AND mm.end_date = %s
              AND mp.duration_days IS NOT NULL
              AND mp.duration_days >= 7
            """,
            (today,),
        )
        rows = cursor.fetchall()

        renewed = 0
        for row in rows:
            # Hitung end_date baru berdasarkan duration_days
            new_start = today
            new_end = None
            if row["duration_days"]:
                new_end = new_start + timedelta(days=row["duration_days"])

            # Insert membership baru dengan status pending_payment
            cursor.execute(
                """
                INSERT INTO member_memberships
                    (member_id, package_id, branch_id, start_date, end_date,
                     visit_remaining, status, auto_renew, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending_payment', %s, NOW())
                """,
                (
                    row["member_id"],
                    row["package_id"],
                    row["branch_id"],
                    new_start,
                    new_end,
                    row["visit_quota"],
                    row["auto_renew"],
                ),
            )

            renewed += 1
            logger.info(
                "Auto-renew created for member #%d, package '%s' (pending payment)",
                row["member_id"], row["package_name"],
            )

            # Kirim email notifikasi
            if row["member_email"]:
                _send_auto_renew_notification(
                    to_email=row["member_email"],
                    username=row["member_name"],
                    package_name=row["package_name"],
                    price=row["price"],
                )

        conn.commit()
        logger.info("Auto-renew job done — %d memberships renewed (pending payment)", renewed)

    except Exception as e:
        conn.rollback()
        logger.error("Error in job_auto_renew_memberships: %s", e)
    finally:
        conn.close()


def _send_auto_renew_notification(to_email: str, username: str, package_name: str, price) -> bool:
    """Kirim email notifikasi bahwa membership di-auto-renew (menunggu pembayaran)."""
    from app.utils.email import send_email

    price_formatted = f"Rp {int(price):,}".replace(",", ".")
    subject = f"Membership Auto-Renew — Menunggu Pembayaran | Moolai Gym"

    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background-color: white; padding: 30px; border-radius: 0 0 10px 10px; }}
            .info-box {{ background-color: #e8f5e9; border: 1px solid #4caf50; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Auto-Renew Membership</h1>
            </div>
            <div class="content">
                <p>Halo <strong>{username}</strong>,</p>
                <p>Membership Anda telah di-perpanjang secara otomatis. Berikut detailnya:</p>
                <div class="info-box">
                    <p><strong>Paket:</strong> {package_name}</p>
                    <p><strong>Biaya:</strong> {price_formatted}</p>
                    <p><strong>Status:</strong> Menunggu Pembayaran</p>
                </div>
                <p>Silakan lakukan pembayaran di gym atau melalui aplikasi untuk mengaktifkan membership baru Anda.</p>
                <p>Jika Anda ingin membatalkan auto-renew, Anda bisa menonaktifkannya melalui aplikasi.</p>
                <p>Salam sehat,<br><strong>Tim Moolai Gym</strong></p>
                <div class="footer">
                    <p>&copy; 2024 Moolai Gym. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(to_email, subject, body)
