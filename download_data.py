import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

def download_csv_from_gdrive(file_id, dest_path, credentials_file):
    """Descarga un archivo CSV desde Google Drive usando una cuenta de servicio."""
    try:
        logging.info("Iniciando descarga de CSV desde Google Drive...")
        creds = service_account.Credentials.from_service_account_file(credentials_file)
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

        request = service.files().get_media(fileId=file_id)
        with open(dest_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logging.info(f"Progreso descarga: {int(status.progress() * 100)}%")
        logging.info(f"Archivo descargado correctamente.")
    except Exception as e:
        logging.error(f"Error al descargar archivo: {e}")
        raise
