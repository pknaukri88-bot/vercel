from http.server import BaseHTTPRequestHandler
import cgi
import json
from io import BytesIO
import pandas as pd


def sql_escape(value):
    if pd.isna(value):
        return "NULL"
    value = str(value).replace("'", "''")
    return f"'{value}'"


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_type = self.headers.get("Content-Type")
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                },
            )

            uploaded_file = form["file"]
            table_name = form.getvalue("table_name") or "table_name"

            file_name = uploaded_file.filename.lower()
            file_data = uploaded_file.file.read()

            if file_name.endswith(".csv"):
                df = pd.read_csv(BytesIO(file_data))
            elif file_name.endswith((".xlsx", ".xls")):
                df = pd.read_excel(BytesIO(file_data))
            else:
                raise Exception("Only CSV, XLS, and XLSX files are supported.")

            dtype_mapping = {
                "object": "VARCHAR(255)",
                "int64": "INT",
                "float64": "FLOAT",
                "datetime64[ns]": "DATETIME",
                "bool": "BOOLEAN",
            }

            columns_with_types = []
            for column, dtype in zip(df.columns, df.dtypes):
                sql_type = dtype_mapping.get(str(dtype), "VARCHAR(255)")
                columns_with_types.append(f"`{column}` {sql_type}")

            create_table = (
                f"CREATE TABLE `{table_name}` (\n"
                + ",\n".join(columns_with_types)
                + "\n);"
            )

            columns = ", ".join([f"`{col}`" for col in df.columns])
            values_list = []

            for _, row in df.iterrows():
                values = ", ".join([sql_escape(value) for value in row.values])
                values_list.append(f"({values})")

            insert_statement = (
                f"INSERT INTO `{table_name}` ({columns}) VALUES\n"
                + ",\n".join(values_list)
                + ";"
            )

            sql_script = create_table + "\n\n" + insert_statement

            response = {
                "sql": sql_script,
                "filename": f"{table_name}.sql",
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
