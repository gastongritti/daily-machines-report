import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def send_email_report(subject, body, attachment_path, smtp_config):
    """Envía un email con el reporte adjunto."""
    try:
        logging.info("Enviando reporte por email...")
        msg = MIMEMultipart()
        msg["From"] = smtp_config["user"]
        msg["To"] = ", ".join(smtp_config["recipients"])
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        if attachment_path is not None:
            if os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(attachment_path)}")
                    msg.attach(part)

        with smtplib.SMTP(smtp_config["server"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["user"], smtp_config["app_password"])
            server.send_message(msg)

        logging.info("Reporte enviado con éxito.")

    except Exception as e:
        logging.error(f"Error al enviar email: {e}")
        raise
