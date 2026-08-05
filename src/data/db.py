"""MySQL connection helper. Credentials come from .env, never hardcoded."""

import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    kwargs = dict(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        database=os.environ["MYSQL_DATABASE"],
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
    )

    # Cloud MySQL providers (e.g. Aiven) require SSL via a CA cert; local
    # dev has no cert and no SSL requirement, so this stays unset there.
    ssl_ca = os.environ.get("MYSQL_SSL_CA")
    if ssl_ca:
        kwargs["ssl_ca"] = ssl_ca
        kwargs["ssl_verify_cert"] = True

    return mysql.connector.connect(**kwargs)
