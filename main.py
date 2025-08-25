import os
import logging
import yaml
from datetime import datetime, date, timedelta

from download_data import download_csv_from_gdrive
from process_data import process_csv
from generate_report import generate_pdf_report
from send_email import send_email_report

# =========================
# 1. Cargar configuración
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Rutas
DATA_DIR = os.path.join(BASE_DIR, config["paths"]["data_dir"])
REPORTS_DIR = os.path.join(BASE_DIR, config["paths"]["reports_dir"])
LOGS_DIR = os.path.join(BASE_DIR, config["paths"]["logs_dir"])
CREDENTIALS_FILE = os.path.join(BASE_DIR, config["google_drive"]["credentials_file"])

try:
    with open(os.path.join(BASE_DIR, config["paths"]["last_sync_file_path"]), "r") as file:
        LAST_SYNC_DATE = datetime.strptime(file.read().strip(), "%Y-%m-%d").date()
except (FileNotFoundError, ValueError) as e:
    LAST_SYNC_DATE = f"Error al leer la fecha de última sincronización: {e}"

for folder in [DATA_DIR, REPORTS_DIR, LOGS_DIR, os.path.dirname(CREDENTIALS_FILE)]:
    os.makedirs(folder, exist_ok=True)

# Archivos
INPUT_CSV_FILE = os.path.join(DATA_DIR, config["paths"]["input_csv_file"])
REPORT_FILE_BASE_NAME = config["paths"]["report_file_base_name"]

# Máquinas
MACHINES = config["machines"]

# Última fecha de reporte
LAST_REPORT_DATE = datetime.strptime(config['last_report_date'], '%Y-%m-%d').date()

# Días en que se envían reportes
REPORT_DAYS = config["report_days"]

# Logging
LOG_FILE = os.path.join(LOGS_DIR, "daily_report.log")
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
    handlers=[file_handler]
)

# =========================
# 2. Main
# =========================
def main():
    if not isinstance(LAST_SYNC_DATE, date):
        logging.error(LAST_SYNC_DATE)

    elif LAST_REPORT_DATE < LAST_SYNC_DATE - timedelta(days=1): 
        logging.info("== INICIO DEL SCRIPT ==")
        
        # Generar lista de fechas de reportes pendientes
        pending_reports = [
            LAST_REPORT_DATE + timedelta(days=i+1)
            for i in range((LAST_SYNC_DATE - timedelta(days=1) - LAST_REPORT_DATE).days)
            if (LAST_REPORT_DATE + timedelta(days=i+1)).weekday() in REPORT_DAYS
            ]
        
        logging.info(f"Fechas de reportes pendientes: {[d.strftime('%Y-%m-%d') for d in pending_reports]}")

        try:
            download_csv_from_gdrive(
                config["google_drive"]["file_id"],
                INPUT_CSV_FILE,
                CREDENTIALS_FILE
            )
            
            temp_files = []

            for report_date in pending_reports:
                machines_dataframes = process_csv(INPUT_CSV_FILE, MACHINES, report_date)
                report_file_name = f"{REPORT_FILE_BASE_NAME.replace("date", report_date.strftime('%d-%m-%Y'))}"
                report_file = os.path.join(REPORTS_DIR, report_file_name)

                
                if machines_dataframes != []:
                    generate_pdf_report(machines_dataframes, report_file, report_date)
                    send_email_report(
                        subject=f"Reporte Pantógrafos ({report_date.strftime('%d-%m-%Y')})",
                        body="--- Email generado de forma automática ---",
                        attachment_path=report_file,
                        smtp_config=config["smtp"]
                    )
                    temp_files.append(report_file)
                
                else:
                    send_email_report(
                        subject=f"Reporte Pantógrafos ({report_date.strftime('%d-%m-%Y')})",
                        body="No se registraron movimientos en la fecha.\n" \
                        "--- Email generado de forma automática ---",
                        attachment_path=None,
                        smtp_config=config["smtp"]
                    )

                # Modificar fecha de último reporte enviado
                config['last_report_date'] = report_date.strftime('%Y-%m-%d')

                # Guardar cambios en archivo de configuración
                with open("config.yaml", "w", encoding="utf-8") as f:
                    yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
                

            # --- Eliminar informe generados de la carpeta local ---
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)

            if os.path.exists(INPUT_CSV_FILE):
                os.remove(INPUT_CSV_FILE)

        except Exception as e:
            logging.critical(f"Ejecución interrumpida: {e}")
        finally:
            logging.info("== FIN DEL SCRIPT ==")

if __name__ == "__main__":
    main()
