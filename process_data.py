import logging
import pandas as pd
import numpy as np

def process_csv(csv_path, machines, report_date):
    """Procesa el CSV en la fecha indicada y devuelve un DataFrame que contiene los eventos de movimiento/detención
    detectados, hora de inicio, hora de fin, producto en proceso y máquina en cuestión."""
    try:
        logging.info("Procesando CSV para la fecha: %s", report_date.strftime('%d-%m-%Y'))
        df = pd.read_csv(csv_path, parse_dates=['DATE_TIME'])

        # Filtrar registros por fecha
        df = df[df["DATE_TIME"].dt.date == report_date]

        dfs_machines = []

        if df.empty:
            logging.info(f"No se registraron movimientos.")
            return dfs_machines

        else:
            for machine in machines['machine_name']:
                # Filtrar por máquina
                df_machine = df[df["MACHINE"] == machine]

                if df_machine.empty:
                    logging.info(f"No se registraron movimientos en {machine}.")
                    dfs_machines.append([machine, df_machine, df_machine])
                    continue
            
                # Ordenar por tiempo
                df_machine = df_machine.sort_values('DATE_TIME')

                # Filtrar registros con USER = "ADMIN" o "Pc-Corte-1"
                df_machine = df_machine[~df_machine['USER'].isin(['ADMIN', 'Pc-Corte-1'])]

                # Definir intervalos
                df_machine['INTERVAL_START'] = df_machine['DATE_TIME']
                df_machine['INTERVAL_END'] = df_machine['DATE_TIME'].shift(-1)
                df_machine['DELTA_T'] = (df_machine['INTERVAL_END'] - df_machine['INTERVAL_START']).dt.total_seconds()

                df_machine['X_POS_START'] = df_machine['X_POS']
                df_machine['Y_POS_START'] = df_machine['Y_POS']
                df_machine['X_POS_END'] = df_machine['X_POS'].shift(-1)
                df_machine['Y_POS_END'] = df_machine['Y_POS'].shift(-1)

                df_machine['DELTA_X'] = (df_machine['X_POS_END'] - df_machine['X_POS_START']).round(3)
                df_machine['DELTA_Y'] = (df_machine['Y_POS_END'] - df_machine['Y_POS_START']).round(3)

                df_machine['X_VEL'] = (df_machine['DELTA_X'] / df_machine['DELTA_T']).round(3)
                df_machine['Y_VEL'] = (df_machine['DELTA_Y'] / df_machine['DELTA_T']).round(3)

                # Asignar estado según la duración del intervalo y la velocidad
                # Intervalos mayores a 3 segundos se consideran "DETENIDO"
                # Si la velocidad es mayor a 50 mm/seg se consideran "DETENIDO", ya que corresponde a un seteo manual de coordenadas
                df_machine['STATUS'] = np.where(df_machine['DELTA_T'] > 3, 'DETENIDO', 'MOVIMIENTO')
                df_machine['STATUS'] = np.where((df_machine['X_VEL'] > 50) | (df_machine['X_VEL'] < -50) | (df_machine['Y_VEL'] > 50) | (df_machine['Y_VEL'] < -50), 'DETENIDO', df_machine['STATUS'])

                # Reasignar coordenadas a 0 si el estado es "DETENIDO"
                df_machine['X_POS_START'] = np.where(df_machine['STATUS'] == 'DETENIDO', 0, df_machine['X_POS_START'])
                df_machine['Y_POS_START'] = np.where(df_machine['STATUS'] == 'DETENIDO', 0, df_machine['Y_POS_START'])
                df_machine['X_POS_END'] = np.where(df_machine['STATUS'] == 'DETENIDO', 0, df_machine['X_POS_END'])
                df_machine['Y_POS_END'] = np.where(df_machine['STATUS'] == 'DETENIDO', 0, df_machine['Y_POS_END'])

                # Crear grupos de intervalos cada vez que el estado cambia
                df_machine['INTERVAL_GROUP'] = (df_machine['STATUS'] != df_machine['STATUS'].shift()).cumsum()

                # Agrupar intervalos consecutivos con el mismo estado
                df_intervals = df_machine.groupby('INTERVAL_GROUP').agg({
                    'INTERVAL_START': 'first',
                    'INTERVAL_END': 'last',
                    'STATUS': 'first',
                    'X_POS_START': 'first',
                    'Y_POS_START': 'first',
                    'X_POS_END': 'last',
                    'Y_POS_END': 'last',
                    'G-CODE': lambda x: x.mode()[0] if x.iloc[0] == "No File Loaded." else x.iloc[0],
                    'USER': 'first'
                }).reset_index(drop=True)

                # Calcular duraciones y velocidades de intervalos agrupados
                df_intervals['DELTA_T'] = (df_intervals['INTERVAL_END'] - df_intervals['INTERVAL_START']).dt.total_seconds()

                # Reasignar coordenadas a 0 si el intervalo es menor a 10 segundos
                df_intervals['X_POS_START'] = np.where(df_intervals['DELTA_T'] < 10, 0, df_intervals['X_POS_START'])
                df_intervals['Y_POS_START'] = np.where(df_intervals['DELTA_T'] < 10, 0, df_intervals['Y_POS_START'])
                df_intervals['X_POS_END'] = np.where(df_intervals['DELTA_T'] < 10, 0, df_intervals['X_POS_END'])
                df_intervals['Y_POS_END'] = np.where(df_intervals['DELTA_T'] < 10, 0, df_intervals['Y_POS_END'])

                df_intervals['DELTA_X'] = (df_intervals['X_POS_END'] - df_intervals['X_POS_START']).round(3)
                df_intervals['DELTA_Y'] = (df_intervals['Y_POS_END'] - df_intervals['Y_POS_START']).round(3)

                df_intervals['X_VEL'] = (df_intervals['DELTA_X'] / df_intervals['DELTA_T']).round(3)
                df_intervals['Y_VEL'] = (df_intervals['DELTA_Y'] / df_intervals['DELTA_T']).round(3)


                # Reasignar velocidades a 0 si son mayores a 50 mm/seg
                df_intervals['X_VEL'] = np.where(df_intervals['X_VEL'] > 50, 0, df_intervals['X_VEL'])
                df_intervals['Y_VEL'] = np.where(df_intervals['Y_VEL'] > 50, 0, df_intervals['Y_VEL'])
                df_intervals['X_VEL'] = np.where(df_intervals['X_VEL'] < -50, 0, df_intervals['X_VEL'])
                df_intervals['Y_VEL'] = np.where(df_intervals['Y_VEL'] < -50, 0, df_intervals['Y_VEL'])

                # Determinar dirección de velocidades
                df_intervals['X_DIR'] = np.sign(df_intervals['X_VEL'])
                df_intervals['Y_DIR'] = np.sign(df_intervals['Y_VEL'])

                # Calcular velocidad compuesta
                df_intervals['VEL'] = np.sqrt(df_intervals['X_VEL']**2 + df_intervals['Y_VEL']**2).round(3)

                # Asignar dirección a velocidad compuesta
                df_intervals['VEL'] = np.where(
                    df_intervals['X_DIR'] != 0,
                    np.sign(df_intervals['X_DIR']) * abs(df_intervals['VEL']),
                    np.sign(df_intervals['Y_DIR']) * abs(df_intervals['VEL'])
                )

                # Reasignar estado a "DETENIDO" si ambas velocidades son 0
                df_intervals['STATUS'] = np.where(df_intervals['VEL'] == 0, 'DETENIDO', df_intervals['STATUS'])

                # Reasignar coordenadas a 0 si el estado es "DETENIDO"
                df_intervals['X_POS_START'] = np.where(df_intervals['STATUS'] == 'DETENIDO', 0, df_intervals['X_POS_START'])
                df_intervals['Y_POS_START'] = np.where(df_intervals['STATUS'] == 'DETENIDO', 0, df_intervals['Y_POS_START'])
                df_intervals['X_POS_END'] = np.where(df_intervals['STATUS'] == 'DETENIDO', 0, df_intervals['X_POS_END'])
                df_intervals['Y_POS_END'] = np.where(df_intervals['STATUS'] == 'DETENIDO', 0, df_intervals['Y_POS_END'])                

                # Crear grupos cada vez que el estado cambia
                df_intervals['INTERVAL_GROUP'] = (df_intervals['STATUS'] != df_intervals['STATUS'].shift()).cumsum()

                # Agrupar intervalos consecutivos con el mismo estado
                df_intervals = df_intervals.groupby('INTERVAL_GROUP').agg({
                    'INTERVAL_START': 'first',
                    'INTERVAL_END': 'last',
                    'X_POS_START': 'first',
                    'Y_POS_START': 'first',
                    'X_POS_END': 'last',
                    'Y_POS_END': 'last',
                    'VEL': 'mean',
                    'G-CODE': lambda x: x.mode()[0] if x.iloc[0] == "No File Loaded." else x.iloc[0],
                    'USER': 'first'
                }).reset_index(drop=True)

                # Renombrar la columna G-CODE para evitar conflictos al procesar CSV
                df_machine = df_machine.rename(columns={"G-CODE": "G_CODE"})
                df_intervals = df_intervals.rename(columns={"G-CODE": "G_CODE"})

                dfs_machines.append([machine, df_machine, df_intervals])
                logging.info(f"Movimientos de {machine} procesados correctamente.")

            return dfs_machines

    except Exception as e:
        logging.error(f"Error al procesar CSV: {e}")
        raise
