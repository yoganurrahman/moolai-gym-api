"""
Email Utility for Moolai Gym
Handles sending various email notifications
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
)

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send email using SMTP server (supports TLS and SSL)

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (HTML supported)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        message["To"] = to_email

        # Add HTML body
        html_part = MIMEText(body, "html")
        message.attach(html_part)

        # Connect to SMTP server
        # Support both TLS (port 587) and SSL (port 465)
        if SMTP_PORT == 465:
            # Use SSL for port 465
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(message)
        else:
            # Use TLS for port 587 or other ports
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(message)

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {str(e)}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {type(e).__name__}: {str(e)}")
        return False


def send_otp_email(to_email: str, otp_code: str, username: str) -> bool:
    """
    Send OTP email for password reset

    Args:
        to_email: Recipient email address
        otp_code: OTP code to send
        username: Username of the user

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Reset Password - Kode OTP Anda | Moolai Gym"

    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background-color: white; padding: 30px; border-radius: 0 0 10px 10px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #667eea; text-align: center; letter-spacing: 5px; padding: 20px; background-color: #f0f0f0; border-radius: 5px; margin: 20px 0; }}
            .warning {{ color: #ff0000; font-size: 14px; margin-top: 20px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Reset Password</h1>
            </div>
            <div class="content">
                <p>Halo <strong>{username}</strong>,</p>
                <p>Anda telah meminta untuk mereset password akun Moolai Gym Anda. Gunakan kode OTP berikut:</p>
                <div class="otp-code">{otp_code}</div>
                <p><strong>Kode OTP ini berlaku selama 10 menit.</strong></p>
                <p>Jika Anda tidak meminta reset password, abaikan email ini.</p>
                <p class="warning"><strong>Perhatian:</strong> Jangan berikan kode OTP ini kepada siapapun.</p>
                <div class="footer">
                    <p>&copy; 2024 Moolai Gym. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(to_email, subject, body)


def send_registration_otp_email(to_email: str, otp_code: str) -> bool:
    """
    Send OTP email for registration verification

    Args:
        to_email: Recipient email address
        otp_code: OTP code to send

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Verifikasi Email - Kode OTP Pendaftaran | Moolai Gym"

    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background-color: white; padding: 30px; border-radius: 0 0 10px 10px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #667eea; text-align: center; letter-spacing: 5px; padding: 20px; background-color: #f0f0f0; border-radius: 5px; margin: 20px 0; }}
            .warning {{ color: #ff0000; font-size: 14px; margin-top: 20px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Verifikasi Email</h1>
            </div>
            <div class="content">
                <p>Halo,</p>
                <p>Terima kasih telah mendaftar di Moolai Gym. Gunakan kode OTP berikut untuk memverifikasi email Anda:</p>
                <div class="otp-code">{otp_code}</div>
                <p><strong>Kode OTP ini berlaku selama 10 menit.</strong></p>
                <p>Jika Anda tidak melakukan pendaftaran, abaikan email ini.</p>
                <p class="warning"><strong>Perhatian:</strong> Jangan berikan kode OTP ini kepada siapapun.</p>
                <div class="footer">
                    <p>&copy; 2024 Moolai Gym. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(to_email, subject, body)


def send_welcome_email(to_email: str, username: str) -> bool:
    """
    Send welcome email after successful registration

    Args:
        to_email: Recipient email address
        username: Name of the new member

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = "Selamat Datang di Moolai Gym!"

    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background-color: white; padding: 30px; border-radius: 0 0 10px 10px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Selamat Datang!</h1>
            </div>
            <div class="content">
                <p>Halo <strong>{username}</strong>,</p>
                <p>Selamat bergabung di Moolai Gym! Akun Anda telah berhasil dibuat.</p>
                <p>Dengan menjadi member Moolai Gym, Anda dapat:</p>
                <ul>
                    <li>Mengakses fasilitas gym kami</li>
                    <li>Mendaftar kelas-kelas fitness</li>
                    <li>Berkonsultasi dengan personal trainer</li>
                    <li>Melacak progress latihan Anda</li>
                </ul>
                <p>Jika ada pertanyaan, jangan ragu untuk menghubungi kami.</p>
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


def send_membership_expiry_reminder(to_email: str, username: str, expiry_date: str, days_remaining: int) -> bool:
    """
    Send membership expiry reminder email

    Args:
        to_email: Recipient email address
        username: Name of the member
        expiry_date: Membership expiry date
        days_remaining: Days until expiry

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    subject = f"Membership Anda Akan Berakhir dalam {days_remaining} Hari | Moolai Gym"

    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; }}
            .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background-color: white; padding: 30px; border-radius: 0 0 10px 10px; }}
            .expiry-box {{ background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Reminder Membership</h1>
            </div>
            <div class="content">
                <p>Halo <strong>{username}</strong>,</p>
                <p>Kami ingin mengingatkan bahwa membership Moolai Gym Anda akan segera berakhir.</p>
                <div class="expiry-box">
                    <p><strong>Tanggal Berakhir:</strong> {expiry_date}</p>
                    <p><strong>Sisa Waktu:</strong> {days_remaining} hari</p>
                </div>
                <p>Perpanjang membership Anda sekarang untuk terus menikmati fasilitas gym kami!</p>
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
