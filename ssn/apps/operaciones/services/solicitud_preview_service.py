import re
from io import BytesIO
from urllib.parse import quote

import numpy as np
import pandas as pd
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from ..helpers.text_utils import pretty_json
from ..serializers import serialize_operations


class SolicitudPreviewService:
    def __init__(self, base_request, operations):
        self.base_request = base_request
        self.operations = operations  # Lista de instancias de modelo
        self.payload = None
        self.formatted_json = ""
        self.mailto_link = ""
        self.excel_link = ""
        self.is_monthly = base_request.tipo_entrega == "Mensual"

    def generar_preview(self):
        if not self.operations:
            return False  # Nada que mostrar

        # Serializa la solicitud y sus operaciones/stocks (de modelos reales)
        self.payload = serialize_operations(self.base_request, self.operations)

        # Transformaciones para operaciones semanales
        if not self.is_monthly:
            for operacion in self.payload.get("operaciones", []):
                if "cantEspecies" in operacion and operacion["cantEspecies"] is not None:
                    if operacion.get("tipoEspecie") != "FC":
                        operacion["cantEspecies"] = int(float(operacion["cantEspecies"]))

        # Formateo JSON y mailto link
        self.formatted_json = pretty_json(self.payload)
        tipo_entrega = self.payload.get("tipoEntrega", "Desconocido")
        mail_subject = f"modelo de operacion - {tipo_entrega}"
        mail_body = f"ID: {self.base_request.uuid}\nSolicitud:\n{self.formatted_json}"
        self.mailto_link = (
            f"mailto:?subject={quote(mail_subject)}&body={quote(mail_body)}"
        )
        return True

    def generar_excel(self):
        if not self.payload:
            return None

        from ..helpers import camel_to_title

        base_json = self.payload.copy()

        # Extraer datos según el tipo de entrega
        if self.is_monthly:
            stocks_json = base_json.pop("stocks", [])
            stock_inversion = [s for s in stocks_json if s.get("tipo") == "I"]
            stock_plazo_fijo = [s for s in stocks_json if s.get("tipo") == "P"]
            stock_cheque_pd = [s for s in stocks_json if s.get("tipo") == "C"]
        else:
            operaciones_json = base_json.pop("operaciones", None)

        # Info general
        base_df = pd.DataFrame(list(base_json.items()), columns=["Campo", "Valor"])
        base_df["Campo"] = base_df["Campo"].apply(camel_to_title)
        base_df = base_df.replace([np.nan, np.inf, -np.inf], "")

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            workbook = writer.book
            formats = self._build_formats(workbook)

            if self.is_monthly:
                self._write_base_sheet(writer, base_df, "Solicitud", formats)

                if stock_inversion:
                    self._write_stock_sheet(
                        writer, stock_inversion, "Stock Inversión", camel_to_title, formats
                    )
                if stock_plazo_fijo:
                    self._write_stock_sheet(
                        writer, stock_plazo_fijo, "Stock Plazo Fijo", camel_to_title, formats
                    )
                if stock_cheque_pd:
                    self._write_stock_sheet(
                        writer, stock_cheque_pd, "Stock Cheque PD", camel_to_title, formats
                    )
            else:
                self._write_semanal_sheet(
                    writer, base_df, operaciones_json or [], camel_to_title, formats
                )

        output.seek(0)
        filename = f"previews/solicitud_{self.base_request.uuid}.xlsx"
        if default_storage.exists(filename):
            default_storage.delete(filename)
        default_storage.save(filename, ContentFile(output.read()))
        from django.urls import reverse
        return reverse("operaciones:download_excel", kwargs={"uuid": str(self.base_request.uuid)})

    # ──────────────────────────────────────────────────────────────────────────
    # Formatos xlsxwriter
    # ──────────────────────────────────────────────────────────────────────────

    def _build_formats(self, workbook):
        """Crea y devuelve todos los formatos xlsxwriter reutilizables."""
        # Formato numérico: miles con separador, hasta 8 decimales sin ceros trailing.
        # xlsxwriter usa códigos Excel estándar (coma=miles, punto=decimal);
        # Excel renderiza con el locale del usuario → en Argentina: "1.234.567,8901".
        NUM_FMT = "#,##0.########"

        return {
            "border": workbook.add_format({"border": 1}),
            "bold_border": workbook.add_format({"bold": True, "border": 1}),
            "header": workbook.add_format({"bold": True, "border": 1, "bg_color": "#D9E1F2"}),
            "num": workbook.add_format({"border": 1, "num_format": NUM_FMT}),
            "total_label": workbook.add_format({
                "bold": True, "border": 1, "bg_color": "#BDD7EE",
            }),
            "total_num": workbook.add_format({
                "bold": True, "border": 1, "bg_color": "#BDD7EE", "num_format": NUM_FMT,
            }),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Conversión numérica
    # ──────────────────────────────────────────────────────────────────────────

    # Detecta strings que son puramente numéricos (entero o decimal, con signo opcional).
    # Excluye códigos alfanuméricos como "FC", "ARS", "XX123".
    _NUMERIC_STR = re.compile(r"^-?\d+(\.\d+)?$")

    def _convert_to_numeric(self, df):
        """Convierte strings numéricos del serializador SSN a tipos Python nativos.

        El serializador devuelve Decimal convertidos a str ("7654321.1234", "123456789").
        Para que Excel los reconozca como números (y permita SUM/avg), los convertimos
        de vuelta a int o float antes de escribir la celda.
        """
        def _to_num(v):
            if isinstance(v, bool) or v is None or v == "":
                return v
            if isinstance(v, (int, float)):
                return v if v == v else ""  # NaN → ""
            if isinstance(v, str) and self._NUMERIC_STR.match(v.strip()):
                try:
                    f = float(v)
                    # Preservar entero para que Excel no muestre ".0"
                    return int(f) if f == int(f) else f
                except (ValueError, OverflowError):
                    return v
            return v

        return df.apply(lambda col: col.map(_to_num))

    def _numeric_columns(self, df):
        """Devuelve el conjunto de nombres de columnas que contienen al menos un número."""
        return {
            col for col in df.columns
            if df[col].apply(
                lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
            ).any()
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Escritura de hojas
    # ──────────────────────────────────────────────────────────────────────────

    def _write_base_sheet(self, writer, base_df, sheet_name, formats):
        """Hoja de información general de la solicitud (pares Campo / Valor)."""
        base_df.to_excel(
            writer, index=False, header=False,
            startrow=0, startcol=0, sheet_name=sheet_name,
        )
        worksheet = writer.sheets[sheet_name]

        for row in range(len(base_df)):
            worksheet.write(row, 0, base_df.iloc[row, 0], formats["bold_border"])
            worksheet.write(row, 1, base_df.iloc[row, 1], formats["border"])

        for i, col in enumerate(base_df.columns):
            max_len = max(base_df[col].astype(str).map(len).max(), len(col))
            worksheet.set_column(i, i, max_len + 2)

    def _write_stock_sheet(self, writer, stock_data, sheet_name, camel_to_title, formats):
        """Hoja de stock (inversión / plazo fijo / cheque PD).

        Mejoras respecto a la versión anterior:
        - Valores numéricos escritos como números reales → Excel puede hacer SUM.
        - Formato de celda num_format para visualización con separadores.
        - Fila de totales al final de columnas numéricas.
        - Freeze del encabezado para facilitar el scroll.
        """
        stock_df = pd.json_normalize(stock_data)
        stock_df.columns = [camel_to_title(col) for col in stock_df.columns]
        stock_df = stock_df.replace([np.nan, np.inf, -np.inf], "")
        stock_df = self._convert_to_numeric(stock_df)

        num_cols = self._numeric_columns(stock_df)
        n_rows, n_cols = len(stock_df), len(stock_df.columns)

        workbook = writer.book
        # Necesitamos una hoja nueva; to_excel la crea automáticamente
        stock_df.to_excel(writer, index=False, startrow=0, startcol=0, sheet_name=sheet_name)
        worksheet = writer.sheets[sheet_name]

        # Freeze de la fila de encabezado
        worksheet.freeze_panes(1, 0)

        # Encabezado
        for col_idx, col_name in enumerate(stock_df.columns):
            worksheet.write(0, col_idx, col_name, formats["header"])

        # Filas de datos
        for row_idx, (_, row) in enumerate(stock_df.iterrows()):
            excel_row = row_idx + 1  # row 0 = header
            for col_idx, col_name in enumerate(stock_df.columns):
                value = row[col_name]
                is_num = isinstance(value, (int, float)) and not isinstance(value, bool)
                fmt = formats["num"] if (col_name in num_cols and is_num) else formats["border"]
                worksheet.write(excel_row, col_idx, value, fmt)

        # Fila de totales
        if n_rows > 0:
            total_row = n_rows + 1  # justo después de la última fila de datos
            for col_idx, col_name in enumerate(stock_df.columns):
                if col_name in num_cols:
                    col_total = stock_df[col_name].apply(
                        lambda v: v if (isinstance(v, (int, float)) and not isinstance(v, bool)) else 0
                    ).sum()
                    worksheet.write(total_row, col_idx, col_total, formats["total_num"])
                elif col_idx == 0:
                    worksheet.write(total_row, col_idx, "Total", formats["total_label"])
                else:
                    worksheet.write(total_row, col_idx, "", formats["total_label"])

        # Ancho de columnas (considera también la fila de totales)
        for i, col in enumerate(stock_df.columns):
            max_data_len = stock_df[col].astype(str).map(len).max() if n_rows > 0 else 0
            col_width = max(max_data_len, len(col), 8)
            worksheet.set_column(i, i, col_width + 2)

    def _write_semanal_sheet(self, writer, base_df, operaciones_json, camel_to_title, formats):
        """Hoja única para entrega semanal: info general + tabla de operaciones + totales."""
        sheet_name = "Solicitud"

        # Sección info general
        base_df.to_excel(
            writer, index=False, header=False,
            startrow=0, startcol=0, sheet_name=sheet_name,
        )

        operaciones_df = pd.json_normalize(operaciones_json)
        operaciones_df.columns = [camel_to_title(col) for col in operaciones_df.columns]
        operaciones_df = operaciones_df.replace([np.nan, np.inf, -np.inf], "")
        operaciones_df = self._convert_to_numeric(operaciones_df)

        startrow = len(base_df) + 2
        operaciones_df.to_excel(
            writer, index=False, startrow=startrow, startcol=0, sheet_name=sheet_name,
        )

        worksheet = writer.sheets[sheet_name]
        worksheet.freeze_panes(startrow + 1, 0)

        num_cols = self._numeric_columns(operaciones_df)
        n_rows = len(operaciones_df)

        # Estilo info general
        for row in range(len(base_df)):
            worksheet.write(row, 0, base_df.iloc[row, 0], formats["bold_border"])
            worksheet.write(row, 1, base_df.iloc[row, 1], formats["border"])

        # Encabezado operaciones
        for col_idx, col_name in enumerate(operaciones_df.columns):
            worksheet.write(startrow, col_idx, col_name, formats["header"])

        # Filas de datos operaciones
        for row_idx, (_, row) in enumerate(operaciones_df.iterrows()):
            excel_row = startrow + 1 + row_idx
            for col_idx, col_name in enumerate(operaciones_df.columns):
                value = row[col_name]
                is_num = isinstance(value, (int, float)) and not isinstance(value, bool)
                fmt = formats["num"] if (col_name in num_cols and is_num) else formats["border"]
                worksheet.write(excel_row, col_idx, value, fmt)

        # Fila de totales
        if n_rows > 0:
            total_row = startrow + 1 + n_rows
            for col_idx, col_name in enumerate(operaciones_df.columns):
                if col_name in num_cols:
                    col_total = operaciones_df[col_name].apply(
                        lambda v: v if (isinstance(v, (int, float)) and not isinstance(v, bool)) else 0
                    ).sum()
                    worksheet.write(total_row, col_idx, col_total, formats["total_num"])
                elif col_idx == 0:
                    worksheet.write(total_row, col_idx, "Total", formats["total_label"])
                else:
                    worksheet.write(total_row, col_idx, "", formats["total_label"])

        # Anchos de columna
        for i, col in enumerate(base_df.columns):
            max_len = max(base_df[col].astype(str).map(len).max(), len(col))
            worksheet.set_column(i, i, max_len + 2)
        for i, col in enumerate(operaciones_df.columns):
            max_data_len = operaciones_df[col].astype(str).map(len).max() if n_rows > 0 else 0
            col_width = max(max_data_len, len(col), 8)
            worksheet.set_column(i, i, col_width + 2)
