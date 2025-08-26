import os
import logging
import numpy as np

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def generate_pdf_report(dfs_machines, report_file, report_date):
    """"""
    try:
        # ======================
        # 1. CONFIGURACIÓN PDF
        # ======================
        doc = SimpleDocTemplate(report_file, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)

        # ======================
        # 2. ESTILOS PERSONALIZADOS
        # ======================
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name="TituloPrincipal",
            fontSize=20,
            leading=24,
            alignment=1,  # centrado
            textColor=colors.HexColor("#003366"),
            spaceAfter=20
        ))

        styles.add(ParagraphStyle(
            name="Subtitulo1",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#006699"),
            spaceAfter=12
        ))

        styles.add(ParagraphStyle(
            name="Subtitulo2",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#006699"),
            spaceAfter=12
        ))

        styles.add(ParagraphStyle(
            name="TextoNormal",
            fontSize=11,
            leading=14
        ))

        # ======================
        # 3. LISTA DE ELEMENTOS
        # ======================
        elements = []
        temp_files = []

        # Portada
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        elements.append(Paragraph("Reporte Diario de Pantógrafos", styles["TituloPrincipal"]))
        elements.append(Paragraph(f"Fecha de generación: {fecha_actual}", styles['TextoNormal']))
        elements.append(Paragraph(f"Fecha de Informe: {report_date.strftime('%d/%m/%Y')}", styles['TextoNormal']))
        elements.append(Spacer(1, 30))

        # ==================
        # 4. TABLA RESUMEN
        # ==================
        
        for machine, df_events, df_intervals in dfs_machines:
            elements.append(Paragraph(F"{machine}", styles['Subtitulo1']))
            
            if not df_intervals.empty:
                df_intervals = df_intervals[['INTERVAL_START', 'INTERVAL_END', 'VEL', 'G_CODE', 'USER']].copy()
                df_intervals['DURATION'] = (df_intervals['INTERVAL_END'] - df_intervals['INTERVAL_START']).dt.total_seconds() / 60
                df_intervals["DURATION"] = df_intervals["DURATION"].round(3)
                
                # Detectar puntos donde cambia la dirección
                df_intervals['DIRECTION'] = np.sign(df_intervals['VEL'])
                df_intervals['DIR_CHANGE'] = df_intervals['DIRECTION'].diff(2).abs() == 2

                df_intervals["CYCLE_ID"] = df_intervals["DIR_CHANGE"].cumsum()

                operation_time = df_intervals['DURATION'].sum().round(2)
                operation_time_hr = round((operation_time / 60), 2)
                motion_time = df_intervals[df_intervals['VEL'] != 0]['DURATION'].sum().round(2)
                motion_time_hr = round((motion_time / 60), 2)
                detention_time = df_intervals[df_intervals['VEL'] == 0]['DURATION'].sum().round(2)
                detention_time_hr = round((detention_time / 60), 2)
                ciclos = df_intervals['CYCLE_ID'].nunique()

                elements.append(Paragraph(
                    f"Tiempo de operación: {operation_time} min. ({operation_time_hr} hs.)", styles['TextoNormal']
                    ))
                elements.append(Paragraph(
                    f"Tiempo en movimiento: {motion_time} min. ({motion_time_hr} hs.)", styles['TextoNormal']
                    ))
                elements.append(Paragraph(
                    f"Tiempo en detención: {detention_time} min. ({detention_time_hr} hs.)", styles['TextoNormal']
                    ))
                elements.append(Paragraph(f"N° de ciclos: {ciclos}", styles['TextoNormal']))
                elements.append(Spacer(1, 30))

                elements.append(Paragraph(F"Resumen por Código G", styles['Subtitulo2']))

                df_cycles = (
                    df_intervals.groupby("CYCLE_ID")
                    .agg(
                        duration=('DURATION', 'sum'),
                        motion_time=('DURATION', lambda x: x[df_intervals["VEL"] != 0].sum()),
                        detention_time=('DURATION', lambda x: x[df_intervals["VEL"] == 0].sum()),
                        gcode=('G_CODE', 'first')
                    )
                    .reset_index()
                )

                df_gcodes = (
                    df_cycles.groupby('gcode')
                    .agg(
                        ncycles=('CYCLE_ID', 'count'),
                        average_duration=('duration', 'mean'),
                        average_motion=('motion_time', 'mean'),
                        average_detention=('detention_time', 'mean'),
                    )
                    .reset_index()
                )

                gcode_summary = [
                    ['Código G', "Ciclos", "Duración\nPromedio\n(min)", "Tiempo prom.\nen Movimiento\n(min)", 'Tiempo prom.\nDetención\n(min)']
                    ]
                
                for gcode_row in df_gcodes.itertuples(index=False):
                    gcode = gcode_row.gcode
                    gcode = gcode.replace(" (ala 2.5)", "").replace(".tap", "").replace("No File Loaded.", "Sin definir")
                    ncycles = gcode_row.ncycles
                    average_duration = round(gcode_row.average_duration, 2)
                    average_motion = round(gcode_row.average_motion, 2)
                    average_detention = round(gcode_row.average_detention, 2)

                    gcode_summary.append([gcode, ncycles, average_duration, average_motion, average_detention])


                gcodes_table = Table(gcode_summary, colWidths=[150, 80, 100, 100, 100])
                gcodes_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke)
                ]))

                elements.append(gcodes_table)
                elements.append(Spacer(1, 30))

                # ===================================
                # 5. DESGLOSE DE CICLOS POR MÁQUINA
                # ===================================        
                elements.append(Paragraph(F"Desglose de Ciclos", styles['Subtitulo2']))
                
                cycles_table = [['Ciclo N°', 'Inicio', 'Fin', 'Duración\n(min)', 'Estado', 'Usuario', 'Código G']]

                for interval in df_intervals.itertuples(index=False):
                    cycle_id = interval.CYCLE_ID + 1
                    start_time = interval.INTERVAL_START.strftime('%H:%M')
                    end_time = interval.INTERVAL_END.strftime('%H:%M')
                    duration = round(interval.DURATION, 2)
                    state = 'MOVIMIENTO' if interval.VEL != 0 else 'DETENIDO'
                    user = interval.USER
                    gcode = interval.G_CODE
                    gcode = gcode.replace(" (ala 2.5)", "").replace(".tap", "").replace("No File Loaded.", "-")

                    cycles_table.append([cycle_id, start_time, end_time, duration, state, user, gcode])

                table2 = Table(cycles_table, colWidths=[50, 40, 40, 60, 80, 100, 150])
                table2.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke)
                ]))
                elements.append(table2)
                elements.append(Spacer(1, 30))


                fig, ax1 = plt.subplots(figsize=(8.0, 4.5))

                # Primer eje vertical: Coordenadas X e Y
                ax1.scatter(df_events['DATE_TIME'], df_events['X_POS'], label='X_POS', s=0.5)
                ax1.scatter(df_events['DATE_TIME'], df_events['Y_POS'], label='Y_POS', s=0.5)
                ax1.set_ylabel("Posición (mm)")
                ax1.set_xlabel("Hora")
                ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
                plt.xticks(rotation=45)

                # Marcar puntos de cambio de dirección
                turning_points = df_intervals[df_intervals['DIR_CHANGE']].copy()
                turning_points = turning_points.reset_index()
                ax1.vlines(turning_points['INTERVAL_START'], ymin=-5000, ymax=5000, linestyle='--', color='green')

                # Segundo eje vertical: Velocidad compuesta
                ax2 = ax1.twinx()
                ax2.step(df_intervals['INTERVAL_START'], df_intervals['VEL'], where='post', label='VEL', alpha=0.6, color='red')
                ax2.set_ylabel("Velocidad (mm/s)")

                # Título y leyendas)
                ax1.legend(loc='upper left')
                ax2.legend(loc='upper right')
                ax1.set_ylim(-4500, 4500)
                ax2.set_ylim(-30, 30)
                fig.tight_layout()
                ax1.grid(True)

                grafico_path = f"grafico_{machine.replace(' ', '_')}_{report_date.strftime('%d-%m-%Y')}.png"
                plt.savefig(grafico_path, dpi=600, bbox_inches='tight')
                temp_files.append(grafico_path)
                plt.close()

                elements.append(Paragraph(f"Operaciones de máquina", styles['Subtitulo2']))
                elements.append(Image(grafico_path, width=18*cm, height=10.125*cm))
                elements.append(PageBreak())

            else:
                elements.append(Paragraph(
                    "No se registraron movimientos en la fecha de reporte.",
                    styles['TextoNormal']
                ))
                elements.append(Spacer(1, 40))

        # ================
        # 6. GENERAR PDF
        # ================
        doc.build(elements)
        
        # --- Eliminar el gráfico temporal ---
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)

        logging.info(f"Reporte generado correctamente.")

    except Exception as e:
        logging.error(f"Error al generar reporte: {e}")
        raise
